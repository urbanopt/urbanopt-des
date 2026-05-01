# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

import json
import os
import shutil
import subprocess
from pathlib import Path


class UOCliWrapper:
    """Wrapper for running the UO CLI from within Python.

    If you are testing this locally, then you might need to configure your URBANopt CLI.
    After installing the CLI, you need to run the following command:
        /Applications/URBANoptCLI_0.X.Y/setup-env.sh
        . ~/.env_uo.sh
    """

    _python_bootstrap_attempted = False

    def __init__(self, working_dir: Path, uo_project: str, template_dir: Path, auto_initialize_python=True):
        """uo_project is the name of the project which is also the project folder

        Args:
            working_dir (Path): The base directory for where UO will be executed
            uo_project (str): Name of the UO project to create
            template_dir (Path): Directory where template files are located
            auto_initialize_python (bool): If True, attempt a one-time `uo install_python`
                bootstrap when URBANopt Python paths are not initialized.
        """
        self.template_dir = template_dir
        self.working_dir = working_dir
        self.uo_project = uo_project
        self.project_path = self.working_dir / self.uo_project
        self.log_file = self.working_dir / f"{uo_project}.log"

        # self.uo_version = "0.9.3"
        # self.uo_version = "0.11.1"
        # self.uo_version = "0.13.0"
        # self.uo_version = "0.14.0"
        # self.uo_version = "1.0.1"
        self.uo_version = "1.1.0"
        # Versions 1.1 does not work. There have been changes to the
        #   default measures (e.g., model articulation multistory key, default reporting).
        #   There also seems to be an issue with the weather file setting.
        # Version 1.2 does not work on Mac as the openstudio.bundle is built incorrectly for ARM.

        # if windows, then the path is different
        if os.name == "nt":
            self.uo_directory = f"C:/URBANopt-cli-{self.uo_version}"  # ***replaced path name based on how it autoinstalls for windows
        else:
            self.uo_directory = f"/Applications/URBANoptCLI_{self.uo_version}"

        if auto_initialize_python:
            self._bootstrap_python_if_needed()

    def _python_config_files(self):
        ruby_base_version = "3.2.0"
        gems_dir = Path(self.uo_directory) / "gems" / "ruby" / ruby_base_version / "gems"
        if not gems_dir.exists():
            return []
        return list(gems_dir.glob("*/example_files/python_deps/python_config.json"))

    def _bootstrap_python_if_needed(self):
        """Attempt to initialize URBANopt python paths if they are missing.

        This runs once per process to avoid repeated expensive bootstrap attempts.
        """
        if UOCliWrapper._python_bootstrap_attempted:
            return

        if self._python_config_files():
            return

        UOCliWrapper._python_bootstrap_attempted = True
        print("URBANopt python paths not initialized, attempting one-time bootstrap via 'uo install_python'.")
        self._run_command("uo install_python")

    def _run_command(self, command):
        current_dir = os.getcwd()
        try:
            os.chdir(self.working_dir)
            with open(self.log_file, "a") as log:
                log.write(f"Running command: {command}\n")
                new_env = os.environ.copy()
                # These env vars come directly from the ~/.env_uo.sh file. Update if a new version is installed. The .env_uo.sh
                # file is created by calling /Applications/URBANoptCLI_X.Y.Z/setup-env.sh
                ruby_base_version = "3.2.0"
                miniconda_base_version = "24.9.2-0"
                uo_dir_name = Path(self.uo_directory).name

                new_env["GEM_HOME"] = f"{self.uo_directory}/gems/ruby/{ruby_base_version}"
                new_env["GEM_PATH"] = f"{self.uo_directory}/gems/ruby/{ruby_base_version}"
                new_env["UO_GEMFILE_PATH"] = f"{self.uo_directory}/gems/Gemfile"
                new_env["UO_BUNDLE_INSTALL_PATH"] = f"{self.uo_directory}/gems"
                new_env["PATH"] = (
                    f"{self.uo_directory}/ruby/bin:{self.uo_directory}/gems/ruby/{ruby_base_version}/bin:{self.uo_directory}/gems/ruby/{ruby_base_version}/gems/{uo_dir_name}/example_files/python_deps/Miniconda-{miniconda_base_version}/bin:{os.environ['PATH']}"
                )
                new_env["RUBYLIB"] = f"{self.uo_directory}/OpenStudio/Ruby"
                new_env["RUBY_DLL_PATH"] = f"{self.uo_directory}/OpenStudio/Ruby"
                # For REopt
                if os.name != "nt":
                    # for some reason, this doesn't work on windows, need to test, this should not cause
                    # an issue to simple set
                    if os.environ.get("GEM_DEVELOPER_KEY"):
                        new_env["GEM_DEVELOPER_KEY"] = os.environ["GEM_DEVELOPER_KEY"]
                result = subprocess.run(  # noqa: S602
                    command,
                    capture_output=True,
                    shell=True,
                    env=new_env,
                    check=False,
                )
                log.write(result.stdout.decode("utf-8"))
                log.write(result.stderr.decode("utf-8"))
                print(result.stdout.decode("utf-8"))
                print(result.stderr.decode("utf-8"))
        finally:
            os.chdir(current_dir)

    def create(self, remove_example_project=False):
        if not (self.working_dir / self.uo_project).exists():
            self._run_command(f"uo create -p {self.uo_project}")
        else:
            print(f"Project {self.uo_project} already exists, skipping creation")
            print(f"Remove the project folder if you want to recreate it, {self.working_dir / self.uo_project}")

        if (self.working_dir / self.uo_project / "example_project.json").exists():
            os.remove(self.working_dir / self.uo_project / "example_project.json")

    def create_example_coincident_project(self):
        """Create an example project file with coincident data"""
        if not (self.working_dir / self.uo_project).exists():
            self._run_command(f"uo create -p {self.uo_project} -C")
        else:
            print(f"Project {self.uo_project} already exists, skipping creation")

    def create_example_diverse_project(self):
        """Create an example project file with diverse data"""
        if not (self.working_dir / self.uo_project).exists():
            self._run_command(f"uo create -p {self.uo_project} -D")
        else:
            print(f"Project {self.uo_project} already exists, skipping creation")

    def create_scenarios(self, feature_file):
        """Create a scenario file for each mapper file"""
        self._run_command(f"uo create -s {self.uo_project}/{feature_file}")

    def create_reopt_scenario(self, feature_file, baseline_scenario):
        """Create a scenario file for REopt assumptions based on the baseline scenario"""
        self._run_command(f"uo create -f {self.uo_project}/{feature_file} -r {self.uo_project}/{baseline_scenario}")

    def run(self, feature_file, scenario_name):
        self._run_command(f"uo run -f {self.uo_project}/{feature_file} -s {self.uo_project}/{scenario_name}")

    def _build_des_optional_args(self, **kwargs):
        """Build optional CLI args for DES-related commands.

        Args:
            **kwargs: Mapping of flag names to values (None values are omitted)

        Returns:
            str: Space-prefixed optional arguments, or empty string when no args are provided.
        """
        args = []
        for flag_name, value in kwargs.items():
            if value is None:
                continue
            cli_flag_name = flag_name.replace("_", "-")
            args.append(f"--{cli_flag_name} {value}")

        if not args:
            return ""

        return f" {' '.join(args)}"

    def des_params(self, scenario_path, feature_path, sys_param_path):
        """Run uo des_params command.

        args:
            scenario_path (str): Path to scenario CSV.
            feature_path (str): Path to feature JSON.
            sys_param_path (str): Path/name for the system-parameter JSON file.
        """
        final_run_command = f"uo des_params --scenario {scenario_path} --feature {feature_path} --sys-param {sys_param_path}"
        # print the current path
        print(f"Running command: {final_run_command}")
        
        self._run_command(final_run_command)

    def des_create(self, sys_param_path, feature_path, des_name=None, overwrite=False):
        """Run uo des_create command.

        args:
            sys_param_path (str): Path to system parameters JSON file.
            feature_path (str): Path to feature file.
            des_name (str): Optional path/name for Modelica project directory.
            overwrite (bool): If True, delete and rebuild existing model directory.
        """
        optional_args = self._build_des_optional_args(des_name=des_name)
        overwrite_flag = " --overwrite" if overwrite else ""
        final_run_command = f"uo des_create --sys-param {sys_param_path} --feature {feature_path}{optional_args}{overwrite_flag}"
        print(f"Running command: {final_run_command}")
        self._run_command(final_run_command)

    def des_run(self, model_path, start_time=None, stop_time=None, step_size=None, interval=None):
        """Run uo des_run command.

        args:
            model_path (str): Path to Modelica model directory.
            start_time (int): Optional start time in seconds of year.
            stop_time (int): Optional stop time in seconds of year.
            step_size (int): Optional simulation step size in seconds.
            interval (int): Optional number of intervals (alternative to step_size).
        """
        optional_args = self._build_des_optional_args(
            start_time=start_time,
            stop_time=stop_time,
            step_size=step_size,
            interval=interval,
        )
        final_run_command = f"uo des_run --model {model_path}{optional_args}"
        print(f"Running command: {final_run_command}")
        self._run_command(final_run_command)

    def run_des(self, des_folder_path, start_time=None, stop_time=None, step_size=None, output_variables=None):
        """Backwards-compatible alias for DES model runs.

        args:
            des_folder_path (str): Path to the folder containing Districts/DistrictEnergySystem.mo
            start_time (int): Start time of the simulation in seconds. Default is None, which defaults to simulation default.
            stop_time (int): Stop time of the simulation in seconds. Default is None, which defaults to simulation default.
            step_size (int): Step size of the simulation in seconds. Default is None, which defaults to simulation default.
            output_variables (list): List of output variables to include in the simulation. Default is None, which defaults to simulation default (all variables)

        Note: The modelica file to run has to be called DistrictEnergySystem.mo and in the Districts subfolder.
        """
        # output_variables is retained for API compatibility but not used by `uo des_run`.
        _ = output_variables
        self.des_run(
            des_folder_path,
            start_time=start_time,
            stop_time=stop_time,
            step_size=step_size,
        )

    def process_des(self, des_folder_path):
        """Run uo des_process command.

        args:
            des_folder_path (str): Path to Modelica model directory.
        """
        final_run_command = f"uo des_process --model {des_folder_path}"
        print(f"Running command: {final_run_command}")
        self._run_command(final_run_command)

    def create_des(self, sys_param_path, feature_path=None, des_name=None, overwrite=False):
        """Backwards-compatible alias for `des_create`."""
        if feature_path is None:
            raise Exception("feature_path is required for des_create")
        self.des_create(sys_param_path, feature_path, des_name=des_name, overwrite=overwrite)

    def info(self):
        print(f"Template path: {self.template_dir}")
        print(f"Working dir: {self.working_dir}")
        print(f"UO project: {self.uo_project}")
        print(f"Log file: {self.log_file}")
        self._run_command("uo -h")

    def process_scenario(self, feature_file, scenario_name):
        # -d is for the default settings and needs to be used (most of the time)
        self._run_command(f"uo process -d -f {self.uo_project}/{feature_file} -s {self.uo_project}/{scenario_name}")

    def process_reopt_scenario(self, feature_file, scenario_name, individual_features=False):
        # In UO, the -r flag is used for the aggregated load analysis, whereas
        # the -e flag if for (e)ach individual feature.
        if not individual_features:
            self._run_command(f"uo process -r -f {self.uo_project}/{feature_file} -s {self.uo_project}/{scenario_name}")
        else:
            self._run_command(f"uo process -e -f {self.uo_project}/{feature_file} -s {self.uo_project}/{scenario_name}")

    def visualize_scenario(self, feature_file, scenario_name):
        self._run_command(f"uo visualize -f {self.uo_project}/{feature_file} -s {self.uo_project}/{scenario_name}")

    def visualize_feature(self, feature_file):
        # -d is for the default settings
        self._run_command(f"uo visualize -f {self.uo_project}/{feature_file}")

        # for some reason, the uo cli doesn't copy over the scenarioData.js file
        if (self.working_dir / self.uo_project / "run" / "scenarioData.js").exists():
            shutil.copy(
                self.working_dir / self.uo_project / "run" / "scenarioData.js",
                self.working_dir / self.uo_project / "visualization" / "scenarioData.js",
            )

    def set_number_parallel(self, num):
        data = None
        with open(self.working_dir / self.uo_project / "runner.conf") as f:
            data = json.load(f)
            data["num_parallel"] = num

        with open(self.working_dir / self.uo_project / "runner.conf", "w") as f:
            json.dump(data, f, indent=2)

    def replace_weather_file_in_feature_and_mapper_file(self, weather_file_name, climate_zone):
        """Replace weather settings in mapper workflows and feature files.

        Args:
            weather_file_name (str): The name of the weather file without extension
            climate_zone (str): The climate zone to set
        """
        mappers_dir = self.working_dir / self.uo_project / "mappers"
        if not mappers_dir.exists():
            raise Exception(f"Mappers directory {mappers_dir} does not exist")

        # Verify that the weather_file exists in the weather path
        weather_dir = self.working_dir / self.uo_project / "weather"
        if not (weather_dir / f"{weather_file_name}.epw").exists():
            raise Exception(f"Weather file {weather_file_name}.epw does not exist in the weather path")
        if not (weather_dir / f"{weather_file_name}.ddy").exists():
            raise Exception(f"Weather file {weather_file_name}.ddy does not exist in the weather path")
        if not (weather_dir / f"{weather_file_name}.stat").exists():
            raise Exception(f"Weather file {weather_file_name}.stat does not exist in the weather path")

        # Update all mapper files in the mappers directory
        for mapper_filepath in mappers_dir.glob("*.osw"):
            with open(mapper_filepath) as f:
                data = json.load(f)

            # find the step that has "ChangeBuildingLocation"
            for step in data.get("steps", []):
                if step.get("measure_dir_name") == "ChangeBuildingLocation":
                    step["arguments"]["weather_file_name"] = f"{weather_file_name}.epw"
                    step["arguments"]["climate_zone"] = f"ASHRAE 169-2013-{climate_zone}"

            with open(mapper_filepath, "w") as f:
                json.dump(data, f, indent=2)

        # Update feature files in the project root
        project_dir = self.working_dir / self.uo_project
        feature_files = list(project_dir.glob("*.json")) + list(project_dir.glob("*.geojson"))
        updated_feature_file = False

        for feature_filepath in feature_files:
            with open(feature_filepath) as f:
                feature_data = json.load(f)

            # Skip non-feature JSON files
            if feature_data.get("type") != "FeatureCollection" or "project" not in feature_data:
                continue

            feature_data["project"]["weather_filename"] = f"{weather_file_name}.epw"
            feature_data["project"]["climate_zone"] = climate_zone

            # Keep Site Origin properties in sync when present
            for feature in feature_data.get("features", []):
                properties = feature.get("properties", {})
                if properties.get("type") == "Site Origin":
                    properties["weather_filename"] = f"{weather_file_name}.epw"
                    properties["climate_zone"] = climate_zone

            with open(feature_filepath, "w") as f:
                json.dump(feature_data, f, indent=2)

            updated_feature_file = True

        if not updated_feature_file:
            raise Exception(f"No feature file found in {project_dir} to update weather settings")

    def enable_measures_in_mapper(self, mapper_file, measure_names):
        """Simple string replacement method to enable measures"""

    def copy_over_weather(self):
        """Copy over the weather file from the example project"""
        src = self.template_dir / "weather"
        files = os.listdir(src)

        print("copying over weather files")
        for file in files:
            if file == ".DS_Store":
                continue
            dest = self.working_dir / self.uo_project / "weather" / file
            # print(f"copying weather {src / file} to {dest}")
            shutil.copy2(src / file, dest)

    def fix_dependencies_20260420(self, workflow_file):
        """Fix compatibility issues with URBANopt version after 4/20/2026
        after some dependency update happened. This broke all the old versions of URBANopt.

        Changes made:
        - Rename 'story_multiplier' to 'story_multiplier_method' in the workflow
        - Remove all 'check_*' keys from the generic_qaqc measure arguments

        Args:
            workflow_file (str): The name of the workflow file to fix (e.g., 'base_workflow.osw')
        """
        workflow_filepath = self.working_dir / self.uo_project / "mappers" / workflow_file
        if not workflow_filepath.exists():
            raise Exception(f"Workflow file {workflow_filepath} does not exist")

        with open(workflow_filepath) as f:
            data = json.load(f)

        # Process all steps in the workflow
        for step in data.get("steps", []):
            arguments = step.get("arguments", {})

            # Change story_multiplier to story_multiplier_method
            if "story_multiplier" in arguments:
                arguments["story_multiplier_method"] = arguments.pop("story_multiplier")

            # Remove all check_* keys from generic_qaqc measure
            if step.get("measure_dir_name") == "generic_qaqc":
                keys_to_remove = [key for key in arguments if key.startswith("check_")]
                for key in keys_to_remove:
                    del arguments[key]

        # Write the updated workflow file
        with open(workflow_filepath, "w") as f:
            json.dump(data, f, indent=2)
