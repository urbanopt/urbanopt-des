# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

import json
import os
import shutil
import unittest
from pathlib import Path

import pytest
from geojson_modelica_translator.modelica.modelica_runner import ModelicaRunner

from urbanopt_des.uo_cli_wrapper import UOCliWrapper


class TestUOCliFromScratchWorkflow(unittest.TestCase):
    """Tests for the from-scratch URBANopt command chain."""

    # List of IDs to remove -- they can be a bit slow, saves 10-20 minutes of runtime.
    pruned_feature_ids = {"10", "12"}
    expected_simulated_feature_ids = {str(i) for i in range(1, 14)} - pruned_feature_ids
    des_building_limit = 3

    output_root = Path(__file__).parent / "output" / "from_scratch_workflow"
    shared_workspace = output_root / "shared_workspace"
    run_phase_artifact = output_root / "run_phase_artifact.json"

    def setUp(self):
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.temp_path = self.shared_workspace
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.template_dir = Path(__file__).parent
        self._prune_feature_ids_from_project(self.temp_path, self.pruned_feature_ids)
        print(f"Test artifacts directory: {self.temp_path}")

    def tearDown(self):
        # Keep artifacts for post-run inspection under tests/output.
        pass

    def _project_paths(self, workspace: Path, project_name: str = "scratch_project"):
        project_path = workspace / project_name
        geojson_path = project_path / "example_project.json"
        feature_path = project_path / "example_project.json"
        scenario_path = project_path / "baseline_scenario.csv"
        sys_param_path = project_path / "sysparams.json"
        des_name = project_path / "des_model"
        return project_path, geojson_path, feature_path, scenario_path, sys_param_path, des_name

    def _run_scenario_dir(self, project_path: Path) -> Path:
        return project_path / "run" / "baseline_scenario"

    def _run_phase_complete(self, project_path: Path) -> bool:
        run_scenario_dir = self._run_scenario_dir(project_path)
        return run_scenario_dir.exists()

    def _run_status_feature_ids(self, project_path: Path) -> set[str]:
        run_status_path = self._run_scenario_dir(project_path) / "run_status.json"
        if not run_status_path.exists():
            return set()

        with open(run_status_path) as f:
            run_status = json.load(f)

        return {str(result.get("id")) for result in run_status.get("results", []) if result.get("id") is not None}

    def _prune_feature_ids_from_project(self, workspace: Path, feature_ids: set[str]) -> None:
        project_path = workspace / "scratch_project"
        if not project_path.exists():
            return

        example_project_path = project_path / "example_project.json"
        if example_project_path.exists():
            with open(example_project_path) as f:
                example_project = json.load(f)

            example_project["features"] = [
                feature for feature in example_project.get("features", []) if feature.get("properties", {}).get("id") not in feature_ids
            ]
            for scenario in example_project.get("scenarios", []):
                scenario["feature_mappings"] = [
                    mapping for mapping in scenario.get("feature_mappings", []) if mapping.get("feature_id") not in feature_ids
                ]

            with open(example_project_path, "w") as f:
                json.dump(example_project, f, indent=2)

        for scenario_csv in project_path.glob("*_scenario.csv"):
            csv_lines = scenario_csv.read_text().splitlines()
            if not csv_lines:
                continue

            header = csv_lines[:1]
            filtered_rows = [line for line in csv_lines[1:] if line.split(",", 1)[0].strip() not in feature_ids]
            scenario_csv.write_text("\n".join(header + filtered_rows) + "\n")

    def _write_run_phase_artifact(
        self,
        temp_path: Path,
        project_path: Path,
        geojson_path: Path,
        feature_path: Path,
        scenario_path: Path,
        sys_param_path: Path,
        des_name: Path,
    ) -> None:
        handoff = {
            "temp_path": str(temp_path),
            "project_path": str(project_path),
            "geojson_path": str(geojson_path),
            "feature_path": str(feature_path),
            "scenario_path": str(scenario_path),
            "sys_param_path": str(sys_param_path),
            "des_name": str(des_name),
        }
        with open(self.run_phase_artifact, "w") as f:
            json.dump(handoff, f, indent=2)

    def _bootstrap_run_phase_artifact(self):
        """Generate run-phase handoff artifact when tests are run out of order."""
        wrapper = UOCliWrapper(
            self.temp_path,
            "scratch_project",
            self.template_dir,
            auto_initialize_python=False,
        )

        project_path, geojson_path, feature_path, scenario_path, sys_param_path, des_name = self._project_paths(self.temp_path)

        if self._run_phase_complete(project_path):
            self._prune_feature_ids_from_project(self.temp_path, self.pruned_feature_ids)
            simulated_ids = self._run_status_feature_ids(project_path)
            if simulated_ids == self.expected_simulated_feature_ids:
                self._write_run_phase_artifact(
                    self.temp_path,
                    project_path,
                    geojson_path,
                    feature_path,
                    scenario_path,
                    sys_param_path,
                    des_name,
                )
                return

            run_scenario_dir = self._run_scenario_dir(project_path)
            if run_scenario_dir.exists():
                shutil.rmtree(run_scenario_dir)

        if project_path.exists():
            shutil.rmtree(project_path)

        wrapper.create_project_at_path(project_path=project_path)
        self._prune_feature_ids_from_project(self.temp_path, self.pruned_feature_ids)
        wrapper.set_number_parallel(max(1, (os.cpu_count() or 1) - 1), project_path=project_path)
        wrapper.create_scenarios(geojson_path)
        wrapper.run(feature_path, scenario_path)
        wrapper.process_scenario(feature_path, scenario_path)

        self._write_run_phase_artifact(
            self.temp_path,
            project_path,
            geojson_path,
            feature_path,
            scenario_path,
            sys_param_path,
            des_name,
        )

    @pytest.mark.integration
    def test_01_from_scratch_workflow_run_uo(self):
        """Run create/create_scenarios/run/process and verify run artifacts exist."""
        wrapper = UOCliWrapper(
            self.temp_path,
            "scratch_project",
            self.template_dir,
            auto_initialize_python=False,
        )

        project_path, geojson_path, feature_path, scenario_path, sys_param_path, des_name = self._project_paths(self.temp_path)

        if self._run_phase_complete(project_path):
            self._prune_feature_ids_from_project(self.temp_path, self.pruned_feature_ids)
            simulated_ids = self._run_status_feature_ids(project_path)
            if simulated_ids == self.expected_simulated_feature_ids:
                self._write_run_phase_artifact(
                    self.temp_path,
                    project_path,
                    geojson_path,
                    feature_path,
                    scenario_path,
                    sys_param_path,
                    des_name,
                )
                run_scenario_dir = self._run_scenario_dir(project_path)
                assert run_scenario_dir.exists(), f"Expected run output missing: {run_scenario_dir}"
                return

            run_scenario_dir = self._run_scenario_dir(project_path)
            if run_scenario_dir.exists():
                shutil.rmtree(run_scenario_dir)

        if self.run_phase_artifact.exists():
            self.run_phase_artifact.unlink()

        # Only clear the shared project folder when the run outputs are incomplete.
        if project_path.exists():
            shutil.rmtree(project_path)

        wrapper.create_project_at_path(project_path=project_path)
        self._prune_feature_ids_from_project(self.temp_path, self.pruned_feature_ids)
        wrapper.set_number_parallel(max(1, (os.cpu_count() or 1) - 1), project_path=project_path)
        wrapper.create_scenarios(geojson_path)
        wrapper.run(feature_path, scenario_path)
        wrapper.process_scenario(feature_path, scenario_path)

        # Validate that the run command produced expected run output structure.
        run_scenario_dir = project_path / "run" / "baseline_scenario"
        assert run_scenario_dir.exists(), f"Expected run output missing: {run_scenario_dir}"

        simulated_ids = self._run_status_feature_ids(project_path)
        assert simulated_ids == self.expected_simulated_feature_ids, (
            f"Expected simulated ids {sorted(self.expected_simulated_feature_ids)}, got {sorted(simulated_ids)}"
        )

        with open(wrapper.log_file) as f:
            log_contents = f.read()

        assert f"Running command: uo run -f {feature_path} -s {scenario_path}" in log_contents
        assert f"Running command: uo process -d -f {feature_path} -s {scenario_path}" in log_contents

        self._write_run_phase_artifact(
            self.temp_path,
            project_path,
            geojson_path,
            feature_path,
            scenario_path,
            sys_param_path,
            des_name,
        )

    @pytest.mark.integration
    def test_02_from_scratch_workflow_des_create_model(self) -> None:
        """Run install_python through des_create; this test requires run-phase success."""
        if not self.run_phase_artifact.exists():
            self._bootstrap_run_phase_artifact()

        with open(self.run_phase_artifact) as f:
            handoff = json.load(f)

        temp_path = Path(handoff["temp_path"])
        project_path = Path(handoff["project_path"])
        feature_path = Path(handoff["feature_path"])
        scenario_path = Path(handoff["scenario_path"])
        sys_param_path = Path(handoff["sys_param_path"])
        des_name = Path(handoff["des_name"])

        wrapper = UOCliWrapper(
            temp_path,
            "scratch_project",
            self.template_dir,
            auto_initialize_python=False,
        )

        wrapper.install_python()
        wrapper.des_params(
            scenario_path=scenario_path,
            feature_path=feature_path,
            sys_param_path=sys_param_path,
            district_type="5G",
            overwrite=True,
        )

        with open(sys_param_path) as f:
            sys_params = json.load(f)
        fifth_generation = sys_params["district_system"]["fifth_generation"]
        building_flow_sum = sum(building["fifth_gen_ets_parameters"]["ets_pump_flow_rate"] for building in sys_params["buildings"])
        assert all(building["fifth_gen_ets_parameters"]["ets_pump_flow_rate"] > 0.0005 for building in sys_params["buildings"])
        assert fifth_generation["central_pump_parameters"]["pump_flow_rate"] == round(building_flow_sum, 6)
        assert fifth_generation["horizontal_piping_parameters"]["hydraulic_diameter"] > 0.089

        prev_max_buildings = os.environ.get("GMT_MAX_BUILDINGS")
        os.environ["GMT_MAX_BUILDINGS"] = str(self.des_building_limit)
        try:
            if des_name.exists():
                shutil.rmtree(des_name)
            wrapper.des_create(
                sys_param_path=sys_param_path,
                feature_path=feature_path,
                des_name=des_name,
                overwrite=True,
            )
        finally:
            if prev_max_buildings is None:
                os.environ.pop("GMT_MAX_BUILDINGS", None)
            else:
                os.environ["GMT_MAX_BUILDINGS"] = prev_max_buildings

        assert des_name.parent == project_path, f"DES model folder is not in project folder: {des_name}"
        assert des_name.exists(), f"DES model folder missing: {des_name}"
        assert des_name.is_dir(), f"DES model path is not a directory: {des_name}"

        required_paths = [
            sys_param_path,
            des_name / "package.mo",
            des_name / "Districts" / "package.mo",
            des_name / "Districts" / "DistrictEnergySystem.mo",
        ]
        missing_paths = [str(path) for path in required_paths if not path.exists()]
        assert not missing_paths, f"Missing expected DES artifacts: {missing_paths}"

        district_model = des_name / "Districts" / "DistrictEnergySystem.mo"
        with open(district_model) as f:
            district_model_text = f.read()
        num_limited_buildings = district_model_text.count("Begin Model Instance for TimeSerLoa_B")
        assert num_limited_buildings == self.des_building_limit, "Expected exactly 3 TimeSeries building instances in district model"
        assert "connect(dis_" in district_model_text, "Expected no-plant district network connections"
        assert "TNoPlant_" in district_model_text, "Expected no-plant loop temperature source"
        assert "heaNoPlant_" in district_model_text, "Expected no-plant heating source component"
        assert "cooNoPlant_" in district_model_text, "Expected no-plant cooling sink component"
        assert "allowFlowReversalBui = true" in district_model_text, "Expected standard 5G building flow reversal"
        assert "allowFlowReversalBui = false" not in district_model_text, "No-plant support should not disable flow reversal"
        assert f"conPum.TMix[1:{num_limited_buildings}]" in district_model_text, (
            "Expected conPum TMix connection for no-plant 5G loop; missing link causes under-determined DES model"
        )
        for building_index in range(1, num_limited_buildings + 1):
            assert f"connect(TimeSerLoa_B{building_index}.QCoo_flow, conPum.QCoo_flow[{building_index}])" in district_model_text, (
                "Expected conPum QCoo_flow connection for no-plant 5G loop; missing link causes under-determined DES model"
            )

    @pytest.mark.integration
    def test_03_from_scratch_workflow_des_run(self):
        """Run des_run after des_create for winter and summer windows."""
        assert self.run_phase_artifact.exists(), "Prerequisite test_01_from_scratch_workflow_run_phase must pass first"

        # check if docker is running
        modelica_runner = ModelicaRunner()
        assert modelica_runner.docker_configured, "Docker is not configured or running; required for des_run command"

        with open(self.run_phase_artifact) as f:
            handoff = json.load(f)

        temp_path = Path(handoff["temp_path"])
        des_name = Path(handoff["des_name"])

        wrapper = UOCliWrapper(
            temp_path,
            "scratch_project",
            self.template_dir,
            auto_initialize_python=False,
        )

        seconds_per_day = 24 * 60 * 60
        live_results_dir = des_name / "des_model.Districts.DistrictEnergySystem_results"
        archived_results_root = temp_path / "des_run_archives"
        winter_results_dir = archived_results_root / "winter_week"
        summer_results_dir = archived_results_root / "summer_week"

        if archived_results_root.exists():
            shutil.rmtree(archived_results_root)
        archived_results_root.mkdir(parents=True, exist_ok=True)

        for archived_results_dir in (winter_results_dir, summer_results_dir):
            if archived_results_dir.exists():
                shutil.rmtree(archived_results_dir)

        step_size_seconds = 900

        # Winter target window: first week of the year.
        winter_start = 0
        winter_stop = 7 * seconds_per_day
        if live_results_dir.exists():
            shutil.rmtree(live_results_dir)
        wrapper.run_des(des_name, start_time=winter_start, stop_time=winter_stop, step_size=step_size_seconds)
        assert live_results_dir.exists(), f"Expected live DES results folder missing: {live_results_dir}"
        shutil.move(live_results_dir, winter_results_dir)

        # Summer target window: one week starting at day 120.
        summer_start = 120 * seconds_per_day
        summer_stop = summer_start + (7 * seconds_per_day)
        if live_results_dir.exists():
            shutil.rmtree(live_results_dir)
        wrapper.run_des(des_name, start_time=summer_start, stop_time=summer_stop, step_size=step_size_seconds)
        assert live_results_dir.exists(), f"Expected live DES results folder missing: {live_results_dir}"
        shutil.move(live_results_dir, summer_results_dir)

        with open(wrapper.log_file) as f:
            log_contents = f.read()

        assert (
            f"Running command: uo des_run --model {des_name} --start-time {winter_start} --stop-time {winter_stop} --step-size {step_size_seconds}"
            in log_contents
        )

        # check that a .mat file was created
        legacy_mat_file = des_name / "Districts" / "DistrictEnergySystem.mat"
        winter_results_mat_file = winter_results_dir / "des_model.Districts.DistrictEnergySystem_res.mat"
        summer_results_mat_file = summer_results_dir / "des_model.Districts.DistrictEnergySystem_res.mat"
        assert legacy_mat_file.exists() or summer_results_mat_file.exists(), (
            "Expected .mat file not found in either legacy or archived summer results location: "
            f"{legacy_mat_file} or {summer_results_mat_file}"
        )
        assert winter_results_mat_file.exists(), f"Expected winter archived .mat file not found: {winter_results_mat_file}"
        assert summer_results_mat_file.exists(), f"Expected summer archived .mat file not found: {summer_results_mat_file}"

        winter_stdout_log = winter_results_dir / "stdout.log"
        summer_stdout_log = summer_results_dir / "stdout.log"
        for stdout_log in (winter_stdout_log, summer_stdout_log):
            assert stdout_log.exists(), f"Expected stdout log missing: {stdout_log}"
            with open(stdout_log) as f:
                stdout_text = f.read()
            assert "Simulation execution failed" not in stdout_text, f"DES simulation failed according to archived stdout log: {stdout_log}"
