# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

import json
import shutil
import unittest
from pathlib import Path
from unittest import mock

import pytest

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

    def test_builds_expected_command_sequence(self):
        """Verify command ordering and arguments without executing the real CLI."""
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

        with mock.patch.object(wrapper, "_run_command") as run_cmd:
            wrapper.create_project_at_path(project_path=project_path)
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
            wrapper.des_create(sys_param_path=sys_param_path, feature_path=feature_path, des_name=des_name)

        expected_commands = [
            f"uo create -p {project_path}",
            f"uo create -s {geojson_path}",
            f"uo run -f {feature_path} -s {scenario_path}",
            f"uo process -d -f {feature_path} -s {scenario_path}",
            "uo install_python",
            (
                f"uo des_params --scenario {scenario_path} --feature {feature_path} "
                f"--sys-param {sys_param_path} --district-type 5G"
            ),
            f"uo des_create --sys-param {sys_param_path} --feature {feature_path} --des-name {des_name}",
        ]

        assert [call.args[0] for call in run_cmd.call_args_list] == expected_commands

    @pytest.mark.integration
    def test_01_from_scratch_workflow_run_phase(self):
        """Run create/create_scenarios/run and verify run artifacts exist."""
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
        wrapper.create_scenarios(geojson_path)
        wrapper.run(feature_path, scenario_path)

        # Validate that the run command produced expected run output structure.
        run_scenario_dir = project_path / "run" / "baseline_scenario"
        assert run_scenario_dir.exists(), f"Expected run output missing: {run_scenario_dir}"

        with open(wrapper.log_file) as f:
            log_contents = f.read()

        assert f"Running command: uo run -f {feature_path} -s {scenario_path}" in log_contents

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
        """Run post-run steps; this test requires run-phase success."""
        if not self.run_phase_artifact.exists():
            pytest.skip("Prerequisite test_01_from_scratch_workflow_run_phase must pass first")

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

        wrapper.process_scenario(feature_path, scenario_path)
        wrapper.install_python()
        wrapper.des_params(
            scenario_path=scenario_path,
            feature_path=feature_path,
            sys_param_path=sys_param_path,
            district_type="5G",
        )
        wrapper.des_create(sys_param_path=sys_param_path, feature_path=feature_path, des_name=des_name)
