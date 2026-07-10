# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

import json
import os
import shutil
import subprocess
import sys
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
        self.uo_version = "1.2.0"
        # UO Version 1.2 for Mac had a new installer on 4/28/2026 that fixed a load error.

        # Select the path based on the platform
        if sys.platform == "win32":
            self.uo_directory = f"C:/URBANopt-cli-{self.uo_version}"
        elif sys.platform == "darwin":
            self.uo_directory = f"/Applications/URBANoptCLI_{self.uo_version}"
        else:  # linux and other unix
            self.uo_directory = f"/usr/local/urbanopt-cli-{self.uo_version}"

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
                workspace_root = Path(__file__).resolve().parents[2]
                translator_source = workspace_root / "geojson-modelica-translator"
                if translator_source.exists():
                    new_env["PYTHONPATH"] = (
                        f"{translator_source}:{new_env['PYTHONPATH']}" if new_env.get("PYTHONPATH") else str(translator_source)
                    )
                # For REopt
                if os.name != "nt":  # noqa: SIM102
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

    def _project_scoped_path(self, file_path):
        """Return a CLI-ready path scoped to project when possible.

        Relative paths are interpreted as inside ``self.uo_project``.
        Absolute paths are passed through unchanged.
        """
        path_obj = Path(file_path)
        if path_obj.is_absolute():
            return str(path_obj)

        return f"{self.uo_project}/{path_obj.as_posix()}"

    def create_scenarios(self, feature_file):
        """Create a scenario file for each mapper file"""
        scoped_feature_path = self._project_scoped_path(feature_file)
        self._run_command(f"uo create -s {scoped_feature_path}")

    def install_python(self):
        """Run uo install_python."""
        self._run_command("uo install_python")

    def create_project_at_path(self, project_path, create_flags=None):
        """Run uo create -p for an explicit project path.

        Args:
            project_path (str or Path): Path to the project directory to create.
            create_flags (list[str] or None): Optional extra flags to append.
                This can be used for installed-version-specific options such as
                mixed residential/commercial project generation.
        """
        optional_flags = ""
        if create_flags:
            optional_flags = f" {' '.join(create_flags)}"
        self._run_command(f"uo create -p {project_path}{optional_flags}")
        cpu_count = os.cpu_count() or 1
        self.set_number_parallel(max(1, cpu_count - 2), project_path=project_path)

    def create_scenarios_at_path(self, geojson_path):
        """Run uo create -s for an explicit GeoJSON path."""
        self.create_scenarios(geojson_path)

    def run_at_path(self, feature_path, scenario_path):
        """Run uo run with explicit feature/scenario paths."""
        self.run(feature_path, scenario_path)

    def process_scenario_at_path(self, feature_path, scenario_path):
        """Run uo process -d with explicit feature/scenario paths."""
        self.process_scenario(feature_path, scenario_path)

    def create_reopt_scenario(self, feature_file, baseline_scenario):
        """Create a scenario file for REopt assumptions based on the baseline scenario"""
        self._run_command(f"uo create -f {self.uo_project}/{feature_file} -r {self.uo_project}/{baseline_scenario}")

    def run(self, feature_file, scenario_name):
        scoped_feature_path = self._project_scoped_path(feature_file)
        scoped_scenario_path = self._project_scoped_path(scenario_name)
        self._run_command(f"uo run -f {scoped_feature_path} -s {scoped_scenario_path}")

    def update_project_files(self, new_project_name):
        """Run uo update command to create a new project and return a new UOCliWrapper for the new project.

        uo update --existing-project-folder <existing_project_folder> --new-project-directory <new_project_directory>

        Args:
            new_project_name (str): New project folder to write updated content to.

        Returns:
            UOCliWrapper: A new wrapper instance for the updated project directory.
        """
        final_run_command = f"uo update --existing-project-folder {self.uo_project} --new-project-directory {new_project_name}"
        print(f"Running command: {final_run_command}")
        self._run_command(final_run_command)
        # Return a new UOCliWrapper for the new project directory
        return UOCliWrapper(self.working_dir, new_project_name, self.template_dir)

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

    def des_params(self, scenario_path, feature_path, sys_param_path, district_type=None, overwrite=False):
        """Run uo des_params command.

        args:
            scenario_path (str): Path to scenario CSV.
            feature_path (str): Path to feature JSON.
            sys_param_path (str): Path/name for the system-parameter JSON file.
            district_type (str): Optional district type, e.g. "5G".
            overwrite (bool): If True, regenerate the sys-param file when it exists.
        """
        optional_args = self._build_des_optional_args(district_type=district_type)
        overwrite_flag = " --overwrite" if overwrite else ""
        final_run_command = f"uo des_params --scenario {scenario_path} --feature {feature_path} --sys-param {sys_param_path}{optional_args}"
        final_run_command = f"{final_run_command}{overwrite_flag}"
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

    def des_create_from_sys_params(self, sys_param_path, des_name):
        """Run uo des_create with only sys-param and des-name.

        Some URBANopt CLI versions support this form without --feature.
        """
        final_run_command = f"uo des_create --sys-param {sys_param_path} --des-name {des_name}"
        print(f"Running command: {final_run_command}")
        self._run_command(final_run_command)

    def from_scratch_workflow(
        self,
        project_path,
        geojson_path,
        feature_path,
        scenario_path,
        sys_param_path,
        des_name,
        district_type="5G",
        create_flags=None,
    ):
        """Execute a from-scratch URBANopt command sequence.

        The sequence is:
            uo create -p
            uo create -s
            uo run
            uo process -d
            uo install_python
            uo des_params
            uo des_create
        """
        self.create_project_at_path(project_path, create_flags=create_flags)
        self.create_scenarios_at_path(geojson_path)
        self.run_at_path(feature_path, scenario_path)
        self.process_scenario_at_path(feature_path, scenario_path)
        self.install_python()
        self.des_params(
            scenario_path=scenario_path,
            feature_path=feature_path,
            sys_param_path=sys_param_path,
            district_type=district_type,
        )
        self.des_create_from_sys_params(sys_param_path=sys_param_path, des_name=des_name)

    def info(self):
        print(f"Template path: {self.template_dir}")
        print(f"Working dir: {self.working_dir}")
        print(f"UO project: {self.uo_project}")
        print(f"Log file: {self.log_file}")
        self._run_command("uo -h")

    def process_scenario(self, feature_file, scenario_name):
        # -d is for the default settings and needs to be used (most of the time)
        scoped_feature_path = self._project_scoped_path(feature_file)
        scoped_scenario_path = self._project_scoped_path(scenario_name)
        self._run_command(f"uo process -d -f {scoped_feature_path} -s {scoped_scenario_path}")

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

    def set_number_parallel(self, num, project_path=None):
        if project_path is None:
            runner_conf_path = self.working_dir / self.uo_project / "runner.conf"
        else:
            runner_conf_path = Path(project_path) / "runner.conf"

        if not runner_conf_path.exists():
            return

        with open(runner_conf_path) as f:
            data = json.load(f)
            data["num_parallel"] = num

        with open(runner_conf_path, "w") as f:
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
        """Flip ``__SKIP__`` from ``true`` to ``false`` for the named measures.

        Each entry in ``measure_names`` is matched against the canonical
        ``OpenStudio::Extension.set_measure_argument(osw, '<measure>', '__SKIP__', true)``
        line emitted by the URBANopt CLI mapper templates. When the line is
        found, the value is replaced with ``false`` so the measure runs.

        Args:
            mapper_file (str or Path): The mapper file name (e.g. ``ClassProject.rb``)
                or a path relative to ``project_path / "mappers"``. Absolute paths
                are accepted and used as-is.
            measure_names (list[str]): List of measure class names to enable.

        Returns:
            list[str]: The measures that were actually toggled in this file
            (entries that were not found are silently skipped — the caller can
            compare against ``measure_names`` to detect typos).

        Raises:
            FileNotFoundError: When the resolved mapper file does not exist.
        """
        mapper_path = Path(mapper_file)
        if not mapper_path.is_absolute():
            mapper_path = self.project_path / "mappers" / mapper_path

        if not mapper_path.exists():
            raise FileNotFoundError(f"Mapper file not found: {mapper_path}")

        text = mapper_path.read_text(encoding="utf-8")

        changed_measures = []
        for measure in measure_names:
            old = f"OpenStudio::Extension.set_measure_argument(osw, '{measure}', '__SKIP__', true)"
            new = f"OpenStudio::Extension.set_measure_argument(osw, '{measure}', '__SKIP__', false)"
            if old in text:
                text = text.replace(old, new)
                changed_measures.append(measure)

        mapper_path.write_text(text, encoding="utf-8")
        print(f"Enabled measures in {mapper_path.name}: {changed_measures}")
        return changed_measures

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

    def copy_template_mappers(self, mapper_filenames):
        """Copy one or more files from ``template_dir/mappers`` to the project's mappers dir.

        Useful for patching in updated ``Baseline.rb``, ``base_workflow.osw``, or
        other template overrides after a project has been created by the URBANopt
        CLI. Files are overwritten if they already exist.

        Args:
            mapper_filenames (str or list[str]): Single filename or list of filenames
                relative to ``template_dir / "mappers"``.

        Returns:
            list[Path]: The destination paths of the files that were copied.

        Raises:
            FileNotFoundError: When a source file does not exist in the template
                mappers directory.
        """
        if isinstance(mapper_filenames, (str, Path)):
            mapper_filenames = [mapper_filenames]

        dest_mappers_dir = self.project_path / "mappers"
        dest_mappers_dir.mkdir(parents=True, exist_ok=True)

        copied = []
        for name in mapper_filenames:
            src = self.template_dir / "mappers" / name
            if not src.exists():
                raise FileNotFoundError(f"Template mapper not found: {src}")
            dest = dest_mappers_dir / Path(name).name
            shutil.copy2(src, dest)
            copied.append(dest)
        return copied

    def bootstrap_project(
        self,
        feature_file,
        new_project_name,
        project_type="coincident",
        num_parallel=None,
        weather=None,
        mappers_to_copy=None,
    ):
        """Run the common "set up a new URBANopt project" sequence.

        This wraps the boilerplate that recurs throughout analysis
        notebooks: create an example project of a given kind (coincident or
        diverse), create scenarios from its feature file, run ``uo update`` to
        produce a renamed project copy, optionally bump parallelism, copy the
        weather files in, optionally drop in template mapper overrides, and
        optionally override the weather location.

        Args:
            feature_file (str): The feature/GeoJSON file name (e.g.
                ``"class_project_coincident.json"``) used by
                :meth:`create_scenarios`.
            new_project_name (str): Target project folder name passed to
                :meth:`update_project_files` (e.g. ``"coincident"`` or ``"diverse"``).
                The returned wrapper points at this new directory.
            project_type (str): ``"coincident"`` (default) or ``"diverse"``.
                Selects between :meth:`create_example_coincident_project` and
                :meth:`create_example_diverse_project`.
            num_parallel (int or None): If provided, passed to
                :meth:`set_number_parallel`. ``None`` skips the call.
            weather (tuple[str, str] or None): ``(epw_name, climate_zone)`` to
                pass to :meth:`replace_weather_file_in_feature_and_mapper_file`.
                ``None`` leaves the default project weather in place.
            mappers_to_copy (list[str] or None): Optional list of mapper
                filenames in ``template_dir/mappers`` to copy on top of the
                generated project (e.g. ``["Baseline.rb", "base_workflow.osw"]``).

        Returns:
            UOCliWrapper: A wrapper pointing at ``new_project_name`` that is
            ready to ``run`` / ``process_scenario``.

        Raises:
            ValueError: If ``project_type`` is not ``"coincident"`` or ``"diverse"``.
        """
        if project_type == "coincident":
            self.create_example_coincident_project()
        elif project_type == "diverse":
            self.create_example_diverse_project()
        else:
            raise ValueError(f"project_type must be 'coincident' or 'diverse', got {project_type!r}")

        self.create_scenarios(feature_file)

        new_wrapper = self.update_project_files(new_project_name)

        if num_parallel is not None:
            new_wrapper.set_number_parallel(num_parallel)

        new_wrapper.copy_over_weather()

        if mappers_to_copy:
            new_wrapper.copy_template_mappers(mappers_to_copy)

        if weather is not None:
            epw_name, climate_zone = weather
            new_wrapper.replace_weather_file_in_feature_and_mapper_file(epw_name, climate_zone)

        return new_wrapper
