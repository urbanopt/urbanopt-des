# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

from urbanopt_des.uo_cli_wrapper import UOCliWrapper


class TestUOCliWrapper(unittest.TestCase):
    """Test UOCliWrapper functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = Path(__file__).parent / "data"
        self.base_workflow_path = self.test_data_dir / "base_workflow.osw"
        self.base_feature_file_path = self.test_data_dir / "base_feature_file.json"

        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary files."""
        if self.temp_path.exists():
            shutil.rmtree(self.temp_path)

    def test_replace_weather_file_in_feature_and_mapper_file_success(self):
        """Test successful weather file replacement in mapper files and feature file."""
        # Create a test project structure
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()
        (project_path / "mappers").mkdir()
        (project_path / "weather").mkdir()

        # Create test mapper files with ChangeBuildingLocation step
        mapper_names = ["test_mapper1.osw", "test_mapper2.osw"]
        for mapper_name in mapper_names:
            mapper_data = {
                "steps": [
                    {
                        "measure_dir_name": "ChangeBuildingLocation",
                        "arguments": {"weather_file_name": "old_weather.epw", "climate_zone": "Old Zone"},
                    }
                ]
            }
            mapper_path = project_path / "mappers" / mapper_name
            with open(mapper_path, "w") as f:
                json.dump(mapper_data, f)

        # Create feature file in project root
        feature_file_path = project_path / "base_feature_file.json"
        shutil.copy(self.base_feature_file_path, feature_file_path)

        # Create weather files
        new_weather_name = "new_weather"
        for ext in ["epw", "ddy", "stat"]:
            weather_file = project_path / "weather" / f"{new_weather_name}.{ext}"
            weather_file.touch()

        # Create wrapper and replace weather
        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)
        wrapper.replace_weather_file_in_feature_and_mapper_file(new_weather_name, "6A")

        # Verify all mappers were updated
        for mapper_name in mapper_names:
            mapper_path = project_path / "mappers" / mapper_name
            with open(mapper_path) as f:
                mapper_data_after = json.load(f)

            assert mapper_data_after["steps"][0]["arguments"]["weather_file_name"] == f"{new_weather_name}.epw"
            assert mapper_data_after["steps"][0]["arguments"]["climate_zone"] == "ASHRAE 169-2013-6A"

        # Verify feature file was updated
        with open(feature_file_path) as f:
            feature_data_after = json.load(f)

        assert feature_data_after["project"]["weather_filename"] == f"{new_weather_name}.epw"
        assert feature_data_after["project"]["climate_zone"] == "6A"
        assert feature_data_after["features"][0]["properties"]["weather_filename"] == f"{new_weather_name}.epw"
        assert feature_data_after["features"][0]["properties"]["climate_zone"] == "6A"

    def test_replace_weather_file_in_feature_and_mapper_file_missing_mappers_dir(self):
        """Test that replacement method raises exception for missing mappers directory."""
        # Create a test project structure without mappers directory
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()
        (project_path / "weather").mkdir()

        # Create weather files but no mappers directory
        new_weather_name = "new_weather"
        for ext in ["epw", "ddy", "stat"]:
            weather_file = project_path / "weather" / f"{new_weather_name}.{ext}"
            weather_file.touch()

        # Create wrapper
        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)

        # Verify exception is raised
        with pytest.raises(Exception, match="does not exist"):
            wrapper.replace_weather_file_in_feature_and_mapper_file(new_weather_name, "ASHRAE 169-2013-6A")

    def test_replace_weather_file_in_feature_and_mapper_file_missing_weather_files(self):
        """Test that replacement method raises exception for missing weather files."""
        # Create a test project structure
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()
        (project_path / "mappers").mkdir()
        (project_path / "weather").mkdir()

        # Create a test mapper file
        mapper_data = {
            "steps": [
                {
                    "measure_dir_name": "ChangeBuildingLocation",
                    "arguments": {"weather_file_name": "old_weather.epw", "climate_zone": "Old Zone"},
                }
            ]
        }
        mapper_path = project_path / "mappers" / "test_mapper.json"
        with open(mapper_path, "w") as f:
            json.dump(mapper_data, f)

        # Create wrapper (weather files don't exist)
        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)

        # Verify exception is raised
        with pytest.raises(Exception, match="does not exist"):
            wrapper.replace_weather_file_in_feature_and_mapper_file("missing_weather", "6A")

    def test_set_number_parallel(self):
        """Test setting number of parallel processes in runner.conf."""
        # Create a test project structure
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()

        # Create a runner.conf file
        runner_conf_data = {"num_parallel": 4, "other_setting": "value"}
        runner_conf_path = project_path / "runner.conf"
        with open(runner_conf_path, "w") as f:
            json.dump(runner_conf_data, f)

        # Create wrapper and set number of parallel processes
        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)
        wrapper.set_number_parallel(8)

        # Verify the runner.conf was updated
        with open(runner_conf_path) as f:
            runner_conf_data_after = json.load(f)

        assert runner_conf_data_after["num_parallel"] == 8
        assert runner_conf_data_after["other_setting"] == "value"

    def test_set_number_parallel_creates_new_setting(self):
        """Test that set_number_parallel updates existing setting correctly."""
        # Create a test project structure
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()

        # Create a runner.conf file with default num_parallel
        runner_conf_data = {"num_parallel": 1, "max_iterations": 10}
        runner_conf_path = project_path / "runner.conf"
        with open(runner_conf_path, "w") as f:
            json.dump(runner_conf_data, f)

        # Create wrapper and set number of parallel processes to different value
        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)
        wrapper.set_number_parallel(16)

        # Verify the runner.conf was updated correctly
        with open(runner_conf_path) as f:
            runner_conf_data_after = json.load(f)

        assert runner_conf_data_after["num_parallel"] == 16
        assert runner_conf_data_after["max_iterations"] == 10

    def test_create_project_at_path_sets_runnerconf_to_n_minus_2(self):
        """Test create_project_at_path updates runner.conf to CPU count minus two."""
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()

        runner_conf_path = project_path / "runner.conf"
        with open(runner_conf_path, "w") as f:
            json.dump({"num_parallel": 1, "other_setting": "value"}, f)

        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)

        with mock.patch("urbanopt_des.uo_cli_wrapper.os.cpu_count", return_value=10):
            with mock.patch.object(wrapper, "_run_command") as run_cmd:
                wrapper.create_project_at_path(project_path=project_path)

        run_cmd.assert_called_once_with(f"uo create -p {project_path}")

        with open(runner_conf_path) as f:
            runner_conf_data_after = json.load(f)

        assert runner_conf_data_after["num_parallel"] == 8
        assert runner_conf_data_after["other_setting"] == "value"

    def test_create_project_at_path_runnerconf_minimum_one(self):
        """Test create_project_at_path never sets num_parallel below one."""
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()

        runner_conf_path = project_path / "runner.conf"
        with open(runner_conf_path, "w") as f:
            json.dump({"num_parallel": 4}, f)

        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)

        with mock.patch("urbanopt_des.uo_cli_wrapper.os.cpu_count", return_value=2):
            with mock.patch.object(wrapper, "_run_command") as run_cmd:
                wrapper.create_project_at_path(project_path=project_path)

        run_cmd.assert_called_once_with(f"uo create -p {project_path}")

        with open(runner_conf_path) as f:
            runner_conf_data_after = json.load(f)

        assert runner_conf_data_after["num_parallel"] == 1

    def test_des_params_command(self):
        """Test des_params executes uo des_params command."""
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()

        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)
        wrapper.des_params(
            "ten1/baseline_scenario.csv",
            "ten1/class_project_ten_coincident.json",
            "ten1/sys_param.json",
        )

        with open(wrapper.log_file) as f:
            log_contents = f.read()

        assert (
            "Running command: uo des_params --scenario ten1/baseline_scenario.csv "
            "--feature ten1/class_project_ten_coincident.json --sys-param ten1/sys_param.json"
        ) in log_contents

    def test_des_create_command(self):
        """Test des_create executes uo des_create command."""
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()

        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)
        wrapper.des_create(
            "ten1/sys_param.json",
            "ten1/class_project_ten_coincident.json",
            des_name="ten1/modelica_project",
        )

        with open(wrapper.log_file) as f:
            log_contents = f.read()

        assert (
            "Running command: uo des_create --sys-param ten1/sys_param.json "
            "--feature ten1/class_project_ten_coincident.json --des-name ten1/modelica_project"
        ) in log_contents

    def test_des_run_command(self):
        """Test des_run executes uo des_run command."""
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()

        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)
        wrapper.des_run("ten1/modelica_project")

        with open(wrapper.log_file) as f:
            log_contents = f.read()

        assert "Running command: uo des_run --model ten1/modelica_project" in log_contents

    def test_update_project_files(self):
        """Test update_project_files executes uo update and returns a new UOCliWrapper."""
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()

        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)
        new_project_name = "diverse"
        new_wrapper = wrapper.update_project_files(new_project_name)

        # Check the log for the correct command
        with open(wrapper.log_file) as f:
            log_contents = f.read()

        assert (
            f"Running command: uo update --existing-project-folder {project_name} --new-project-directory {new_project_name}"
        ) in log_contents

        # Check that the returned object is a UOCliWrapper for the new project
        assert isinstance(new_wrapper, UOCliWrapper)
        assert new_wrapper.uo_project == new_project_name
        assert new_wrapper.working_dir == self.temp_path
        assert new_wrapper.template_dir == Path(__file__).parent

    def test_wrapper_initialization(self):
        """Test UOCliWrapper initialization."""
        # Create a test project structure
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()

        template_dir = Path(__file__).parent

        # Create wrapper
        wrapper = UOCliWrapper(self.temp_path, project_name, template_dir)

        # Verify wrapper properties
        assert wrapper.working_dir == self.temp_path
        assert wrapper.uo_project == project_name
        assert wrapper.template_dir == template_dir
        assert wrapper.project_path == project_path
        assert wrapper.log_file == self.temp_path / f"{project_name}.log"


class TestEnableMeasuresInMapper(unittest.TestCase):
    """Cover the empty-stub-now-implemented enable_measures_in_mapper method."""

    # Canonical line emitted by the URBANopt CLI mapper templates.
    SKIP_TRUE = "OpenStudio::Extension.set_measure_argument(osw, '{measure}', '__SKIP__', true)"
    SKIP_FALSE = "OpenStudio::Extension.set_measure_argument(osw, '{measure}', '__SKIP__', false)"

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.project_name = "test_project"
        self.project_path = self.temp_path / self.project_name
        (self.project_path / "mappers").mkdir(parents=True)
        self.template_dir = Path(__file__).parent
        self.wrapper = UOCliWrapper(self.temp_path, self.project_name, self.template_dir)

    def tearDown(self):
        if self.temp_path.exists():
            shutil.rmtree(self.temp_path)

    def _write_mapper(self, name: str, measures_skipped: list) -> Path:
        """Drop a Ruby-ish mapper file at project_path/mappers/<name>."""
        lines = ["# Test mapper file"]
        for measure in measures_skipped:
            lines.append(self.SKIP_TRUE.format(measure=measure))
        path = self.project_path / "mappers" / name
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def test_flips_skip_true_to_false(self):
        """When a measure's __SKIP__ is true, it should be flipped to false."""
        measures = ["MeasureA", "MeasureB"]
        mapper_path = self._write_mapper("ClassProject.rb", measures)

        changed = self.wrapper.enable_measures_in_mapper("ClassProject.rb", measures)

        text = mapper_path.read_text(encoding="utf-8")
        assert sorted(changed) == sorted(measures)
        for measure in measures:
            assert self.SKIP_FALSE.format(measure=measure) in text
            assert self.SKIP_TRUE.format(measure=measure) not in text

    def test_skips_measures_not_present(self):
        """Measures that aren't in the file should be silently skipped."""
        self._write_mapper("ClassProject.rb", ["MeasureA"])

        changed = self.wrapper.enable_measures_in_mapper("ClassProject.rb", ["MeasureA", "MeasureMissing"])

        assert changed == ["MeasureA"]

    def test_accepts_absolute_path(self):
        """An absolute path argument should be used as-is, not joined to project_path."""
        # Put the mapper somewhere outside the project_path/mappers tree.
        alt_dir = self.temp_path / "alt_mappers"
        alt_dir.mkdir()
        mapper_path = alt_dir / "Other.rb"
        mapper_path.write_text(self.SKIP_TRUE.format(measure="MeasureA"), encoding="utf-8")

        changed = self.wrapper.enable_measures_in_mapper(mapper_path, ["MeasureA"])

        assert changed == ["MeasureA"]
        assert self.SKIP_FALSE.format(measure="MeasureA") in mapper_path.read_text()

    def test_raises_when_mapper_missing(self):
        """A clear FileNotFoundError beats a cryptic IOError."""
        with pytest.raises(FileNotFoundError):
            self.wrapper.enable_measures_in_mapper("DoesNotExist.rb", ["MeasureA"])

    def test_empty_measure_list_no_changes(self):
        """No measures means no work and no error."""
        mapper_path = self._write_mapper("ClassProject.rb", ["MeasureA"])
        before = mapper_path.read_text(encoding="utf-8")

        changed = self.wrapper.enable_measures_in_mapper("ClassProject.rb", [])

        assert changed == []
        assert mapper_path.read_text(encoding="utf-8") == before


class TestCopyTemplateMappers(unittest.TestCase):
    """Exercise copy_template_mappers for both single-string and list inputs."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.template_dir = self.temp_path / "template"
        (self.template_dir / "mappers").mkdir(parents=True)
        self.project_name = "test_project"
        (self.temp_path / self.project_name).mkdir()
        self.wrapper = UOCliWrapper(self.temp_path, self.project_name, self.template_dir)

    def tearDown(self):
        if self.temp_path.exists():
            shutil.rmtree(self.temp_path)

    def _seed_template_mapper(self, name: str, contents: str) -> Path:
        path = self.template_dir / "mappers" / name
        path.write_text(contents, encoding="utf-8")
        return path

    def test_copies_single_string_name(self):
        """A bare string is accepted just like a one-element list."""
        self._seed_template_mapper("Baseline.rb", "# baseline contents")

        copied = self.wrapper.copy_template_mappers("Baseline.rb")

        assert len(copied) == 1
        dest = self.wrapper.project_path / "mappers" / "Baseline.rb"
        assert copied[0] == dest
        assert dest.read_text(encoding="utf-8") == "# baseline contents"

    def test_copies_list_of_names(self):
        """Multiple files in one call land in the project's mappers directory."""
        self._seed_template_mapper("Baseline.rb", "# baseline")
        self._seed_template_mapper("base_workflow.osw", '{"steps": []}')

        copied = self.wrapper.copy_template_mappers(["Baseline.rb", "base_workflow.osw"])

        dest_dir = self.wrapper.project_path / "mappers"
        assert {p.name for p in copied} == {"Baseline.rb", "base_workflow.osw"}
        assert (dest_dir / "Baseline.rb").exists()
        assert (dest_dir / "base_workflow.osw").exists()

    def test_overwrites_existing_destination(self):
        """If a file already exists in mappers/, it should be replaced."""
        self._seed_template_mapper("Baseline.rb", "# NEW contents")
        dest_dir = self.wrapper.project_path / "mappers"
        dest_dir.mkdir()
        existing = dest_dir / "Baseline.rb"
        existing.write_text("# OLD contents", encoding="utf-8")

        self.wrapper.copy_template_mappers("Baseline.rb")

        assert existing.read_text(encoding="utf-8") == "# NEW contents"

    def test_creates_mappers_dir_if_missing(self):
        """``project_path / "mappers"`` should be created on demand."""
        self._seed_template_mapper("Baseline.rb", "# baseline")
        # No mappers/ directory under the project.
        assert not (self.wrapper.project_path / "mappers").exists()

        self.wrapper.copy_template_mappers("Baseline.rb")

        assert (self.wrapper.project_path / "mappers" / "Baseline.rb").exists()

    def test_raises_when_template_missing(self):
        """A clear FileNotFoundError when a source file isn't in the template dir."""
        with pytest.raises(FileNotFoundError):
            self.wrapper.copy_template_mappers("does_not_exist.rb")


class TestBootstrapProject(unittest.TestCase):
    """Verify bootstrap_project orchestrates the right sequence of calls.

    The underlying ``uo`` commands shell out, so we patch the methods that
    invoke them and assert on the call sequence + arguments. This keeps the
    test self-contained — no URBANopt CLI required.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.template_dir = Path(__file__).parent
        self.wrapper = UOCliWrapper(self.temp_path, "pre_project", self.template_dir)

    def tearDown(self):
        if self.temp_path.exists():
            shutil.rmtree(self.temp_path)

    def _patched_wrapper(self):
        """Build a child wrapper whose post-update methods are all mocked."""
        new_wrapper = UOCliWrapper(self.temp_path, "coincident", self.template_dir)
        new_wrapper.set_number_parallel = mock.MagicMock()
        new_wrapper.copy_over_weather = mock.MagicMock()
        new_wrapper.replace_weather_file_in_feature_and_mapper_file = mock.MagicMock()
        new_wrapper.copy_template_mappers = mock.MagicMock()
        return new_wrapper

    def test_coincident_full_flow_invokes_each_step(self):
        new_wrapper = self._patched_wrapper()

        with (
            mock.patch.object(self.wrapper, "create_example_coincident_project") as create_ex,
            mock.patch.object(self.wrapper, "create_example_diverse_project") as create_div,
            mock.patch.object(self.wrapper, "create_scenarios") as create_scen,
            mock.patch.object(self.wrapper, "update_project_files", return_value=new_wrapper) as update,
        ):
            result = self.wrapper.bootstrap_project(
                feature_file="class_project_coincident.json",
                new_project_name="coincident",
                project_type="coincident",
                num_parallel=4,
                weather=("USA_FL_MacDill.AFB.747880_TMY3", "1A"),
                mappers_to_copy=["Baseline.rb", "base_workflow.osw"],
            )

        # Coincident path uses the coincident example creator only.
        create_ex.assert_called_once_with()
        create_div.assert_not_called()
        create_scen.assert_called_once_with("class_project_coincident.json")
        update.assert_called_once_with("coincident")

        # Steps below should run on the *new* wrapper returned by update.
        new_wrapper.set_number_parallel.assert_called_once_with(4)
        new_wrapper.copy_over_weather.assert_called_once_with()
        new_wrapper.replace_weather_file_in_feature_and_mapper_file.assert_called_once_with("USA_FL_MacDill.AFB.747880_TMY3", "1A")
        new_wrapper.copy_template_mappers.assert_called_once_with(["Baseline.rb", "base_workflow.osw"])

        assert result is new_wrapper

    def test_diverse_project_type(self):
        new_wrapper = self._patched_wrapper()

        with (
            mock.patch.object(self.wrapper, "create_example_coincident_project") as create_ex,
            mock.patch.object(self.wrapper, "create_example_diverse_project") as create_div,
            mock.patch.object(self.wrapper, "create_scenarios"),
            mock.patch.object(self.wrapper, "update_project_files", return_value=new_wrapper),
        ):
            self.wrapper.bootstrap_project(
                feature_file="class_project_diverse.json",
                new_project_name="diverse",
                project_type="diverse",
            )

        create_ex.assert_not_called()
        create_div.assert_called_once_with()

    def test_skips_optional_steps_when_omitted(self):
        """num_parallel=None, weather=None, mappers_to_copy=None each skip their step."""
        new_wrapper = self._patched_wrapper()

        with (
            mock.patch.object(self.wrapper, "create_example_coincident_project"),
            mock.patch.object(self.wrapper, "create_scenarios"),
            mock.patch.object(self.wrapper, "update_project_files", return_value=new_wrapper),
        ):
            self.wrapper.bootstrap_project(
                feature_file="feature.json",
                new_project_name="coincident",
            )

        # copy_over_weather is unconditional; the other three are conditional.
        new_wrapper.copy_over_weather.assert_called_once_with()
        new_wrapper.set_number_parallel.assert_not_called()
        new_wrapper.replace_weather_file_in_feature_and_mapper_file.assert_not_called()
        new_wrapper.copy_template_mappers.assert_not_called()

    def test_invalid_project_type_raises(self):
        with pytest.raises(ValueError, match="project_type must be"):
            self.wrapper.bootstrap_project(
                feature_file="feature.json",
                new_project_name="coincident",
                project_type="some_other_thing",
            )


if __name__ == "__main__":
    unittest.main()
