# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

"""Tests for the URBANoptAnalysis helper classmethods.

Covers:

* :meth:`URBANoptAnalysis.resolve_uo_project_paths` — pure path resolution,
  tested against tmpdir fakes to keep the unit tests self-contained.
* :meth:`URBANoptAnalysis.bootstrap_from_uo_results` — the post-process
  bootstrap. Every test exercises the real ``URBANoptAnalysis +
  URBANoptResults`` pipeline against the bundled ``three_building_5G``
  fixture so the assertions hit real attributes / dataframes. Only the
  narrow "what happens when process_load_results raises" cases patch a
  single method on URBANoptResults to force an exception.
"""

import shutil
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

import pytest

from urbanopt_des.urbanopt_analysis import URBANoptAnalysis
from urbanopt_des.urbanopt_results import URBANoptResults

# Suppress noisy pandas/seaborn warnings that the existing tests also silence.
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.simplefilter(action="ignore", category=FutureWarning)


# Fixture paths shared by the bootstrap_from_uo_results tests.
FIXTURE_ROOT = Path(__file__).parent / "data" / "three_building_5G"
FIXTURE_PROJECT_DIR = FIXTURE_ROOT / "three_building_test"
FIXTURE_GEOJSON = FIXTURE_PROJECT_DIR / "FLXenabler.json"
FIXTURE_SCENARIO_NAME = "baseline"


class TestResolveUOProjectPaths(unittest.TestCase):
    """Verify ``resolve_uo_project_paths`` handles every supported input shape."""

    def setUp(self):
        # ``.resolve()`` here matches what the production code does to its
        # inputs, so macOS ``/var → /private/var`` symlinks don't cause
        # spurious equality failures.
        self.temp_path = Path(tempfile.mkdtemp()).resolve()

    def tearDown(self):
        if self.temp_path.exists():
            shutil.rmtree(self.temp_path)

    def _make_project(
        self,
        name: str = "coincident",
        scenarios: tuple = ("baseline_scenario",),
        geojson_name: str = "class_project_coincident.json",
    ) -> Path:
        """Build a fake URBANopt project layout and return its root path."""
        project_dir = self.temp_path / name
        run_dir = project_dir / "run"
        run_dir.mkdir(parents=True)
        for scenario in scenarios:
            (run_dir / scenario).mkdir()
        (project_dir / geojson_name).write_text("{}", encoding="utf-8")
        return project_dir

    def test_project_dir_with_baseline_scenario(self):
        """Passing the project root picks up baseline_scenario when present."""
        project_dir = self._make_project()

        result = URBANoptAnalysis.resolve_uo_project_paths(project_dir)

        assert result["uo_project_dir"] == project_dir
        assert result["run_dir"] == project_dir / "run"
        assert result["scenario_name"] == "baseline_scenario"
        assert result["scenario_results_dir"] == project_dir / "run" / "baseline_scenario"
        assert result["geojson_path"] == project_dir / "class_project_coincident.json"
        # Auto-created summary dir
        assert result["results_summary_dir"].exists()
        assert result["results_summary_dir"].name == "_results_summary"

    def test_project_dir_falls_back_to_first_scenario(self):
        """When baseline_scenario doesn't exist, pick the first alphabetic dir."""
        project_dir = self._make_project(
            scenarios=("zeta_scenario", "alpha_scenario", "mu_scenario")
        )

        result = URBANoptAnalysis.resolve_uo_project_paths(project_dir)

        assert result["scenario_name"] == "alpha_scenario"

    def test_scenario_dir_input(self):
        """A scenario directory under run/ is recognized and unwrapped."""
        project_dir = self._make_project(scenarios=("custom_scenario",))
        scenario_dir = project_dir / "run" / "custom_scenario"

        result = URBANoptAnalysis.resolve_uo_project_paths(scenario_dir)

        assert result["uo_project_dir"] == project_dir
        assert result["scenario_name"] == "custom_scenario"
        assert result["scenario_results_dir"] == scenario_dir

    def test_explicit_scenario_name_override(self):
        """An explicit scenario_name takes precedence over auto-discovery."""
        project_dir = self._make_project(scenarios=("baseline_scenario", "custom_scenario"))

        result = URBANoptAnalysis.resolve_uo_project_paths(
            project_dir, scenario_name="custom_scenario"
        )

        assert result["scenario_name"] == "custom_scenario"

    def test_geojson_glob_fallback_to_star_json(self):
        """If the default glob misses, fall back to any *.json in the project."""
        project_dir = self._make_project(geojson_name="custom_feature.json")

        result = URBANoptAnalysis.resolve_uo_project_paths(project_dir)

        assert result["geojson_path"] == project_dir / "custom_feature.json"

    def test_geojson_glob_custom(self):
        """Caller can override the geojson glob entirely."""
        project_dir = self._make_project(geojson_name="weird_name.geojson")
        # Default glob looks for `class_project*.json`; ours is .geojson.
        result = URBANoptAnalysis.resolve_uo_project_paths(
            project_dir, geojson_glob="*.geojson"
        )

        assert result["geojson_path"] == project_dir / "weird_name.geojson"

    def test_missing_input_path_raises(self):
        with pytest.raises(FileNotFoundError, match="Input path does not exist"):
            URBANoptAnalysis.resolve_uo_project_paths(
                self.temp_path / "definitely_not_there"
            )

    def test_path_neither_project_nor_scenario_raises(self):
        """A plain directory without run/ and not under run/ is rejected."""
        random_dir = self.temp_path / "stray"
        random_dir.mkdir()

        with pytest.raises(ValueError, match="contains run/"):
            URBANoptAnalysis.resolve_uo_project_paths(random_dir)

    def test_run_directory_missing_under_project_dir_raises(self):
        """A project directory whose run/ is missing surfaces a clear error."""
        project_dir = self.temp_path / "broken_project"
        project_dir.mkdir()
        # No run/ subdirectory.
        with pytest.raises(ValueError, match="contains run/"):
            URBANoptAnalysis.resolve_uo_project_paths(project_dir)

    def test_no_scenario_dirs_raises(self):
        """Project dir with empty run/ should surface a FileNotFoundError."""
        project_dir = self.temp_path / "empty_run"
        (project_dir / "run").mkdir(parents=True)
        (project_dir / "feature.json").write_text("{}", encoding="utf-8")

        with pytest.raises(FileNotFoundError, match="No scenario directories"):
            URBANoptAnalysis.resolve_uo_project_paths(project_dir)

    def test_missing_geojson_raises(self):
        """A project dir without any *.json file should fail noisily."""
        project_dir = self.temp_path / "no_geojson"
        (project_dir / "run" / "baseline_scenario").mkdir(parents=True)

        with pytest.raises(FileNotFoundError, match="No project GeoJSON"):
            URBANoptAnalysis.resolve_uo_project_paths(project_dir)

    def test_results_summary_dir_is_created(self):
        """resolve_uo_project_paths should mkdir the summary dir (idempotent)."""
        project_dir = self._make_project()
        summary = project_dir / "run" / "baseline_scenario" / "_results_summary"
        assert not summary.exists()

        URBANoptAnalysis.resolve_uo_project_paths(project_dir)
        assert summary.exists()

        # Second call is a no-op (mkdir exist_ok=True).
        URBANoptAnalysis.resolve_uo_project_paths(project_dir)
        assert summary.exists()


class TestBootstrapFromUoResults(unittest.TestCase):
    """End-to-end tests for ``bootstrap_from_uo_results``.

    Uses the real :class:`URBANoptAnalysis` + :class:`URBANoptResults` pipeline
    against the bundled ``three_building_5G`` fixture. Each assertion is on a
    real attribute / dataframe.

    The fixture exposes a custom scenario name (``baseline``, not
    ``baseline_scenario``) which lets us also verify the explicit override path.
    """

    @classmethod
    def setUpClass(cls):
        if not (FIXTURE_PROJECT_DIR / "run" / FIXTURE_SCENARIO_NAME).exists():
            raise unittest.SkipTest(
                "three_building_5G fixture is not present; skipping tests."
            )

    def setUp(self):
        # Surgical cleanup: only remove the URBANopt-generated CSVs that
        # save_dataframes will rewrite. Anything else under output/ (e.g.
        # ``building_metrics_annual.csv`` written by post-process notebooks)
        # is preserved.
        scenario_output = (
            FIXTURE_PROJECT_DIR / "run" / FIXTURE_SCENARIO_NAME / "output"
        )
        if scenario_output.is_dir():
            for pattern in ("loads_*.csv", "power_*.csv"):
                for path in scenario_output.glob(pattern):
                    if path.is_file():
                        path.unlink()

    def _bootstrap(self, **overrides):
        """Run ``bootstrap_from_uo_results`` against the fixture project."""
        kwargs = dict(
            input_path=FIXTURE_PROJECT_DIR,
            scenario_name=FIXTURE_SCENARIO_NAME,
            year_of_data=2017,
        )
        kwargs.update(overrides)
        return URBANoptAnalysis.bootstrap_from_uo_results(**kwargs)

    def test_returns_real_analysis_and_results(self):
        """Smoke test: real URBANoptAnalysis with a real URBANoptResults attached."""
        uo_analysis, paths = self._bootstrap()

        assert isinstance(uo_analysis, URBANoptAnalysis)
        assert isinstance(uo_analysis.urbanopt, URBANoptResults)
        assert uo_analysis.year_of_data == 2017
        # The fixture's three buildings should be reachable through geojson
        assert uo_analysis.geojson.get_building_ids() == ["11", "14", "26"]

    def test_default_display_name_is_non_connected(self):
        uo_analysis, _ = self._bootstrap()
        assert uo_analysis.urbanopt.display_name == "Non-Connected"

    def test_custom_display_name_is_honored(self):
        uo_analysis, _ = self._bootstrap(display_name="REopt Optimized")
        assert uo_analysis.urbanopt.display_name == "REopt Optimized"

    def test_returns_resolved_paths(self):
        """The paths dict should be the same as resolve_uo_project_paths returns."""
        _, paths = self._bootstrap()

        expected_keys = {
            "uo_project_dir",
            "run_dir",
            "scenario_name",
            "scenario_results_dir",
            "geojson_path",
            "results_summary_dir",
        }
        assert set(paths.keys()) == expected_keys
        # ``.resolve()`` matches the production code's normalization step.
        assert paths["uo_project_dir"] == FIXTURE_PROJECT_DIR.resolve()
        assert paths["scenario_name"] == FIXTURE_SCENARIO_NAME
        assert paths["geojson_path"] == FIXTURE_GEOJSON.resolve()
        assert paths["results_summary_dir"].exists()

    def test_save_dataframes_regenerates_load_csvs(self):
        """``bootstrap_from_uo_results`` calls ``save_dataframes`` — verify the
        expected URBANopt CSVs land in the scenario output directory."""
        # setUp guarantees these files are absent before bootstrap runs.
        scenario_output = (
            FIXTURE_PROJECT_DIR / "run" / FIXTURE_SCENARIO_NAME / "output"
        )

        self._bootstrap()

        for name in ("loads_15min.csv", "loads_60min.csv", "power_15min.csv", "power_60min.csv"):
            assert (scenario_output / name).exists(), f"{name} was not regenerated"

    def test_process_load_results_was_invoked(self):
        """The real URBANoptResults should have data_loads populated after bootstrap."""
        uo_analysis, _ = self._bootstrap()
        # The fixture has real building load exports, so data_loads should be a DataFrame.
        assert uo_analysis.urbanopt.data_loads is not None

    def test_skip_missing_load_exports_emits_warning(self):
        """Patch only ``URBANoptResults.process_load_results`` so it raises;
        the rest of the pipeline still uses the real instance."""
        with mock.patch.object(
            URBANoptResults,
            "process_load_results",
            side_effect=RuntimeError("load file missing"),
        ):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                uo_analysis, _ = self._bootstrap(skip_missing_load_exports=True)

        msgs = [str(w.message) for w in caught]
        assert any("Skipping missing building load exports" in m for m in msgs)

        # The instance is still a real URBANoptResults — only the one method
        # was patched, the rest of the pipeline ran normally.
        assert isinstance(uo_analysis.urbanopt, URBANoptResults)
        assert uo_analysis.urbanopt.display_name == "Non-Connected"

    def test_skip_missing_load_exports_false_propagates(self):
        """With ``skip_missing_load_exports=False`` the exception bubbles up."""
        with mock.patch.object(
            URBANoptResults,
            "process_load_results",
            side_effect=RuntimeError("load file missing"),
        ):
            with pytest.raises(RuntimeError, match="load file missing"):
                self._bootstrap(skip_missing_load_exports=False)

    def test_explicit_analysis_dir_override(self):
        """``analysis_dir`` argument should be honored instead of the default."""
        custom_dir = Path(tempfile.mkdtemp()).resolve()
        try:
            uo_analysis, _ = self._bootstrap(analysis_dir=custom_dir)
            assert uo_analysis.analysis_dir == custom_dir
            # The analysis_output_dir lives under analysis_dir.
            assert uo_analysis.analysis_output_dir == custom_dir / "_results_summary"
        finally:
            shutil.rmtree(custom_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
