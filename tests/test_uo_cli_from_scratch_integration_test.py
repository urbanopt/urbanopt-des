# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

import json
import os
import shutil
import unittest
from pathlib import Path

import pytest
from geojson_modelica_translator.modelica_runner import ModelicaRunner

from urbanopt_des.uo_cli_wrapper import UOCliWrapper


class TestUOCliFromScratchWorkflow(unittest.TestCase):
    """Tests for the from-scratch URBANopt command chain."""

    output_root = Path(__file__).parent / "output" / "from_scratch_workflow"
    shared_workspace = output_root / "shared_workspace"
    run_phase_artifact = output_root / "run_phase_artifact.json"

    def setUp(self):
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.temp_path = self.shared_workspace
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.template_dir = Path(__file__).parent
        print(f"Test artifacts directory: {self.temp_path}")

    def tearDown(self):
        # Keep artifacts for post-run inspection under tests/output.
        pass

    def _bootstrap_run_phase_artifact(self):
        """Generate run-phase handoff artifact when tests are run out of order."""
        wrapper = UOCliWrapper(
            self.temp_path,
            "scratch_project",
            self.template_dir,
            auto_initialize_python=False,
        )

        project_path = self.temp_path / "scratch_project"
        geojson_path = project_path / "example_project.json"
        feature_path = project_path / "example_project.json"
        scenario_path = project_path / "baseline_scenario.csv"
        sys_param_path = project_path / "sysparams.json"
        des_name = project_path / "des_model"

        if project_path.exists():
            shutil.rmtree(project_path)

        wrapper.create_project_at_path(project_path=project_path)
        wrapper.set_number_parallel(max(1, (os.cpu_count() or 1) - 1), project_path=project_path)
        wrapper.create_scenarios(geojson_path)
        wrapper.run(feature_path, scenario_path)
        wrapper.process_scenario(feature_path, scenario_path)

        handoff = {
            "temp_path": str(self.temp_path),
            "project_path": str(project_path),
            "geojson_path": str(geojson_path),
            "feature_path": str(feature_path),
            "scenario_path": str(scenario_path),
            "sys_param_path": str(sys_param_path),
            "des_name": str(des_name),
        }
        with open(self.run_phase_artifact, "w") as f:
            json.dump(handoff, f, indent=2)

    @pytest.mark.integration
    def test_builds_expected_command_sequence(self):
        """Verify command ordering and arguments using real CLI execution."""
        wrapper = UOCliWrapper(
            self.temp_path,
            "scratch_project",
            self.template_dir,
            auto_initialize_python=False,
        )

        project_path = self.temp_path / "scratch_project"
        geojson_path = project_path / "example_project.json"
        feature_path = project_path / "example_project.json"
        scenario_path = project_path / "baseline_scenario.csv"
        sys_param_path = project_path / "sysparams.json"
        des_name = project_path / "des_model"

        if project_path.exists():
            shutil.rmtree(project_path)

        if wrapper.log_file.exists():
            wrapper.log_file.unlink()

        wrapper.create_project_at_path(project_path=project_path)
        n_minus_1_cores = max(1, (os.cpu_count() or 1) - 1)
        wrapper.set_number_parallel(n_minus_1_cores, project_path=project_path)
        wrapper.create_scenarios(geojson_path)
        wrapper.run(feature_path, scenario_path)
        wrapper.process_scenario(feature_path, scenario_path)
        wrapper.install_python()
        wrapper.des_params(
            scenario_path=scenario_path,
            feature_path=feature_path,
            sys_param_path=sys_param_path,
            district_type="5G",
        )
        prev_max_buildings = os.environ.get("GMT_MAX_BUILDINGS")
        os.environ["GMT_MAX_BUILDINGS"] = "3"
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

        expected_commands = [
            f"uo create -p {project_path}",
            f"uo create -s {geojson_path}",
            f"uo run -f {feature_path} -s {scenario_path}",
            f"uo process -d -f {feature_path} -s {scenario_path}",
            "uo install_python",
            (f"uo des_params --scenario {scenario_path} --feature {feature_path} --sys-param {sys_param_path} --district-type 5G"),
            f"uo des_create --sys-param {sys_param_path} --feature {feature_path} --des-name {des_name}",
        ]

        with open(wrapper.log_file) as f:
            running_commands = [line.replace("Running command: ", "").strip() for line in f if line.startswith("Running command:")]

        assert running_commands[: len(expected_commands)] == expected_commands

        with open(project_path / "runner.conf") as f:
            runner_conf_data = json.load(f)

        assert runner_conf_data["num_parallel"] == n_minus_1_cores

    @pytest.mark.integration
    def test_01_from_scratch_workflow_run_phase(self):
        """Run create/create_scenarios/run/process and verify run artifacts exist."""
        wrapper = UOCliWrapper(
            self.temp_path,
            "scratch_project",
            self.template_dir,
            auto_initialize_python=False,
        )

        project_path = self.temp_path / "scratch_project"
        geojson_path = project_path / "example_project.json"
        feature_path = project_path / "example_project.json"
        scenario_path = project_path / "baseline_scenario.csv"
        sys_param_path = project_path / "sysparams.json"
        des_name = project_path / "des_model"

        if self.run_phase_artifact.exists():
            self.run_phase_artifact.unlink()

        # Always start from a clean project folder in the shared workspace.
        if project_path.exists():
            shutil.rmtree(project_path)

        wrapper.create_project_at_path(project_path=project_path)
        wrapper.set_number_parallel(max(1, (os.cpu_count() or 1) - 1), project_path=project_path)
        wrapper.create_scenarios(geojson_path)
        wrapper.run(feature_path, scenario_path)
        wrapper.process_scenario(feature_path, scenario_path)

        # Validate that the run command produced expected run output structure.
        run_scenario_dir = project_path / "run" / "baseline_scenario"
        assert run_scenario_dir.exists(), f"Expected run output missing: {run_scenario_dir}"

        with open(wrapper.log_file) as f:
            log_contents = f.read()

        assert f"Running command: uo run -f {feature_path} -s {scenario_path}" in log_contents
        assert f"Running command: uo process -d -f {feature_path} -s {scenario_path}" in log_contents

        handoff = {
            "temp_path": str(self.temp_path),
            "project_path": str(project_path),
            "geojson_path": str(geojson_path),
            "feature_path": str(feature_path),
            "scenario_path": str(scenario_path),
            "sys_param_path": str(sys_param_path),
            "des_name": str(des_name),
        }
        with open(self.run_phase_artifact, "w") as f:
            json.dump(handoff, f, indent=2)

    @pytest.mark.integration
    def test_02_from_scratch_workflow_post_run_phase(self):
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
        )
        prev_max_buildings = os.environ.get("GMT_MAX_BUILDINGS")
        os.environ["GMT_MAX_BUILDINGS"] = "3"
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
        assert district_model_text.count("Begin Model Instance for TimeSerLoa_B") == 3, (
            "Expected exactly 3 TimeSeries building instances in district model"
        )
        assert "conPum.TMix[1:datDes.nBui]" in district_model_text, (
            "Expected conPum TMix connection for no-plant 5G loop; missing link causes under-determined DES model"
        )

    @pytest.mark.integration
    def test_03_from_scratch_workflow_des_run_phase(self):
        """Run des_run after des_create; this test requires post-run phase success."""
        assert self.run_phase_artifact.exists(), "Prerequisite test_01_from_scratch_workflow_run_phase must pass first"

        # check if docker is running
        assert ModelicaRunner.docker_configured, "Docker is not configured or running; required for des_run command"

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

        wrapper.run_des(des_name)

        with open(wrapper.log_file) as f:
            log_contents = f.read()

        assert f"Running command: uo des_run --model {des_name}" in log_contents
