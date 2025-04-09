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

    def __init__(self, working_dir: Path, uo_project: str, template_dir: Path):
        """uo_project is the name of the project which is also the project folder

        Args:
            working_dir (Path): The base directory for where UO will be executed
            uo_project (str): Name of the UO project to create
            template_dir (Path): Directory where template files are located
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
        self.uo_version = "1.0.1"

        # if windows, then the path is different
        if os.name == "nt":
            self.uo_directory = f"C:/URBANoptCLI_{self.uo_version}"
        else:
            self.uo_directory = f"/Applications/URBANoptCLI_{self.uo_version}"

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

                new_env["GEM_HOME"] = f"{self.uo_directory}/gems/ruby/{ruby_base_version}"
                new_env["GEM_PATH"] = f"{self.uo_directory}/gems/ruby/{ruby_base_version}"
                new_env["PATH"] = (
                    f"{self.uo_directory}/ruby/bin:{self.uo_directory}/gems/ruby/{ruby_base_version}/bin:${self.uo_directory}/gems/ruby/{ruby_base_version}/gems/{self.uo_directory}/example_files/python_deps/Miniconda-{miniconda_base_version}/bin:{os.environ['PATH']}"
                )
                new_env["RUBYLIB"] = f"{self.uo_directory}/OpenStudio/Ruby"
                new_env["RUBY_DLL_PATH"] = f"{self.uo_directory}/OpenStudio/Ruby"
                # For REopt
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

    def run_des(self, des_folder_path, start_time=None, stop_time=None, step_size=None, output_variables=None):
        """Run uo_des CLI command, which comes from the GMT. This requires Docker to run.

        args:
            des_folder_path (str): Path to the folder containing Districts/DistrictEnergySystem.mo
            start_time (int): Start time of the simulation in seconds. Default is None, which defaults to simulation default.
            stop_time (int): Stop time of the simulation in seconds. Default is None, which defaults to simulation default.
            step_size (int): Step size of the simulation in seconds. Default is None, which defaults to simulation default.
            output_variables (list): List of output variables to include in the simulation. Default is None, which defaults to simulation default (all variables)

        Note: The modelica file to run has to be called DistrictEnergySystem.mo and in the Districts subfolder.
        """
        # construct the string to run the command, if there is no start_time, stop_time, or step_size then leave out
        # the argument
        if start_time is None:
            start_time = ""
        else:
            start_time = f"--start_time {start_time}"
        if stop_time is None:
            stop_time = ""
        else:
            stop_time = f"--stop_time {stop_time}"
        if step_size is None:
            step_size = ""
        else:
            step_size = f"--step_size {step_size}"
        if output_variables is None:
            output_variables = ""
        else:
            output_variables = f"--output_variables {','.join(output_variables)}"

        final_run_command = f"uo_des run-model {des_folder_path} {start_time} {stop_time} {step_size} {output_variables}"
        print(f"Running command: {final_run_command}")
        self._run_command(final_run_command)

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

    def replace_weather_file_in_mapper(self, mapper_file, weather_file_name, climate_zone):
        """Replace the weather file in the mapper file with the given weather file name"""
        mapper_filepath = self.working_dir / self.uo_project / "mappers" / mapper_file
        if not mapper_filepath.exists():
            raise Exception(f"Mapper file {mapper_filepath} does not exist")

        # verify that the weather_file exists in the weather path
        if not (self.working_dir / self.uo_project / "weather" / f"{weather_file_name}.epw").exists():
            raise Exception(f"Weather file {weather_file_name}.epw does not exist in the weather path")
        if not (self.working_dir / self.uo_project / "weather" / f"{weather_file_name}.ddy").exists():
            raise Exception(f"Weather file {weather_file_name}.ddy does not exist in the weather path")
        if not (self.working_dir / self.uo_project / "weather" / f"{weather_file_name}.stat").exists():
            raise Exception(f"Weather file {weather_file_name}.stat does not exist in the weather path")

        with open(mapper_filepath) as f:
            data = json.load(f)
            # find the step that has "ChangeBuildingLocation"
            for step in data["steps"]:
                if step["measure_dir_name"] == "ChangeBuildingLocation":
                    step["arguments"]["weather_file_name"] = f"{weather_file_name}.epw"
                    step["arguments"]["climate_zone"] = climate_zone

        with open(mapper_filepath, "w") as f:
            json.dump(data, f, indent=2)

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
