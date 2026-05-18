# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

import json
import shutil
import tempfile
import unittest
from pathlib import Path

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

    def test_fix_dependencies_20260420_story_multiplier(self):
        """Test that story_multiplier is renamed to story_multiplier_method."""
        # Create a test project structure
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()
        (project_path / "mappers").mkdir()

        # Copy the test workflow file to the mappers directory
        test_workflow = project_path / "mappers" / "base_workflow.osw"
        shutil.copy(self.base_workflow_path, test_workflow)

        # Verify story_multiplier exists before fix
        with open(test_workflow) as f:
            data_before = json.load(f)

        found_story_multiplier_before = False
        for step in data_before.get("steps", []):
            if "story_multiplier" in step.get("arguments", {}):
                found_story_multiplier_before = True
                break

        self.assertTrue(found_story_multiplier_before, "story_multiplier not found in test data")

        # Create wrapper and apply fix
        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)
        wrapper.fix_dependencies_20260420("base_workflow.osw")

        # Verify story_multiplier was renamed to story_multiplier_method
        with open(test_workflow) as f:
            data_after = json.load(f)

        found_old_key = False
        found_new_key = False
        for step in data_after.get("steps", []):
            arguments = step.get("arguments", {})
            if "story_multiplier" in arguments:
                found_old_key = True
            if "story_multiplier_method" in arguments:
                found_new_key = True

        self.assertFalse(found_old_key, "story_multiplier should have been renamed")
        self.assertTrue(found_new_key, "story_multiplier_method should exist after fix")

    def test_fix_dependencies_20260420_generic_qaqc_check_keys(self):
        """Test that all check_* keys are removed from generic_qaqc measure."""
        # Create a test project structure
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()
        (project_path / "mappers").mkdir()

        # Copy the test workflow file to the mappers directory
        test_workflow = project_path / "mappers" / "base_workflow.osw"
        shutil.copy(self.base_workflow_path, test_workflow)

        # Verify check_* keys exist before fix
        with open(test_workflow) as f:
            data_before = json.load(f)

        check_keys_before = []
        for step in data_before.get("steps", []):
            if step.get("measure_dir_name") == "generic_qaqc":
                arguments = step.get("arguments", {})
                check_keys_before = [key for key in arguments if key.startswith("check_")]
                break

        self.assertTrue(len(check_keys_before) > 0, "check_* keys not found in test data")

        # Create wrapper and apply fix
        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)
        wrapper.fix_dependencies_20260420("base_workflow.osw")

        # Verify all check_* keys were removed from generic_qaqc
        with open(test_workflow) as f:
            data_after = json.load(f)

        check_keys_after = []
        for step in data_after.get("steps", []):
            if step.get("measure_dir_name") == "generic_qaqc":
                arguments = step.get("arguments", {})
                check_keys_after = [key for key in arguments if key.startswith("check_")]
                break

        self.assertEqual(len(check_keys_after), 0, f"check_* keys still exist: {check_keys_after}")

    def test_fix_dependencies_20260420_preserves_other_keys(self):
        """Test that the fix preserves non-check_* keys in generic_qaqc measure."""
        # Create a test project structure
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()
        (project_path / "mappers").mkdir()

        # Copy the test workflow file to the mappers directory
        test_workflow = project_path / "mappers" / "base_workflow.osw"
        shutil.copy(self.base_workflow_path, test_workflow)

        # Get the original template value
        with open(test_workflow) as f:
            data_before = json.load(f)

        template_value_before = None
        for step in data_before.get("steps", []):
            if step.get("measure_dir_name") == "generic_qaqc":
                template_value_before = step.get("arguments", {}).get("template")
                break

        # Create wrapper and apply fix
        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)
        wrapper.fix_dependencies_20260420("base_workflow.osw")

        # Verify template value is preserved
        with open(test_workflow) as f:
            data_after = json.load(f)

        template_value_after = None
        for step in data_after.get("steps", []):
            if step.get("measure_dir_name") == "generic_qaqc":
                template_value_after = step.get("arguments", {}).get("template")
                break

        self.assertEqual(template_value_before, template_value_after, "template value should be preserved")

    def test_fix_dependencies_20260420_file_not_found(self):
        """Test that fix_dependencies_20260420 raises exception for non-existent file."""
        # Create a test project structure
        project_name = "test_project"
        project_path = self.temp_path / project_name
        project_path.mkdir()
        (project_path / "mappers").mkdir()

        # Create wrapper with a non-existent workflow file
        wrapper = UOCliWrapper(self.temp_path, project_name, Path(__file__).parent)

        # Verify exception is raised
        with pytest.raises(Exception, match="does not exist"):
            wrapper.fix_dependencies_20260420("nonexistent_workflow.osw")

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


if __name__ == "__main__":
    unittest.main()
