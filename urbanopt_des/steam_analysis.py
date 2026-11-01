# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

"""Build, run and collect 1st-generation (steam) district scenarios with the GMT.

Every scenario goes into its own new folder. Existing folders that this module did not create are never
touched, and a scenario is only simulated when it has no results yet (see ``results_guard``).

Example::

    sys_param = create_steam_sys_param(agg_dir / "FLXenabler_system_params_steam.json", feature_file, uo_run_dir)
    scenario = SteamScenario(agg_dir, "oneg_steam_v2", sys_param, feature_file)
    scenario.build()
    scenario.run()
    results = scenario.results()  # SteamResults
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geojson_modelica_translator.geojson_modelica_translator import GeoJsonModelicaTranslator
from geojson_modelica_translator.modelica.modelica_runner import ModelicaRunner
from geojson_modelica_translator.system_parameters.system_parameters import SystemParameters

from .logging_config import LoggingMixin
from .results_guard import guard_scenario_dir, mark_scenario_dir
from .steam_results import SteamResults

STEAM_MARKER = ".created_by_urbanopt_des_steam"
DEFAULT_DOCKER_IMAGE = "nrel/gmt-om-runner:4.1.1"
SECONDS_PER_YEAR = 365 * 24 * 3600
STEAM_PARAMS_KEYS = ("district_system", "first_generation", "central_steam_plant_parameters")


def create_steam_sys_param(sys_param_file: Path, feature_file: Path, scenario_dir: Path, **kwargs: Any) -> Path:
    """Create a new steam (1G) system parameter file with the GMT. An existing file is never overwritten.

    :param sys_param_file: path of the file to create
    :param feature_file: URBANopt feature (GeoJSON) file of the buildings to connect
    :param scenario_dir: URBANopt scenario run folder with the per-building Modelica load files
    :param kwargs: passed to ``SystemParameters.csv_to_sys_param`` (e.g., modelica_load_filename)
    :return: path of the system parameter file
    """
    sys_param_file = Path(sys_param_file)
    if sys_param_file.exists():
        return sys_param_file
    options = {"modelica_load_filename": "modelica.mos", "skip_weather_download": True} | kwargs
    SystemParameters().csv_to_sys_param(
        model_type="time_series",
        sys_param_filename=sys_param_file,
        scenario_dir=Path(scenario_dir),
        feature_file=Path(feature_file),
        district_type="steam",
        overwrite=False,
        **options,
    )
    return sys_param_file


def write_steam_variant_sys_param(base_sys_param: Path, new_sys_param: Path, steam_parameters: dict) -> Path:
    """Copy a steam system parameter file into a new file, updating ``central_steam_plant_parameters``.

    Use it for steam loss scenarios (see ``steam_results.steam_loss_parameters``) and sensitivities
    (e.g., ``boiler_efficiency``). The new file is written next to the base file so relative paths still resolve.

    :raises FileExistsError: if ``new_sys_param`` already exists with different content
    """
    data = json.loads(Path(base_sys_param).read_text())
    params = data
    for key in STEAM_PARAMS_KEYS:
        params = params.setdefault(key, {})
    params.update(steam_parameters)
    text = json.dumps(data, indent=2) + "\n"
    new_sys_param = Path(new_sys_param)
    if new_sys_param.exists():
        if new_sys_param.read_text() == text:
            return new_sys_param
        raise FileExistsError(f"{new_sys_param} exists with different content; choose a new name")
    new_sys_param.write_text(text)
    return new_sys_param


def results_mat_path(scenario_dir: Path) -> Path:
    """Path of the OpenModelica result file of a GMT district scenario."""
    scenario_dir = Path(scenario_dir)
    name = scenario_dir.name
    stem = f"{name}.Districts.DistrictEnergySystem"
    return scenario_dir / f"{stem}_results" / f"{stem}_res.mat"


def om_log_timing(scenario_dir: Path) -> dict[str, float]:
    """Compile and simulation times (s) reported by OpenModelica, when present in the logs."""
    results_dir = results_mat_path(scenario_dir).parent
    out: dict[str, float] = {}
    patterns = {
        "om_time_simulation_s": r"timeSimulation\s*=\s*([\d.eE+-]+)",
        "om_time_compile_s": r"timeCompile\s*=\s*([\d.eE+-]+)",
        "om_time_total_s": r"timeTotal\s*=\s*([\d.eE+-]+)",
    }
    for log in sorted(results_dir.glob("*.log")):
        text = log.read_text(errors="ignore")
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match and key not in out:
                out[key] = float(match.group(1))
    return out


@dataclass
class SteamScenario(LoggingMixin):
    """One steam district scenario in its own folder.

    :param root_dir: folder that holds scenario folders (e.g., des_analysis_agg)
    :param name: scenario (and Modelica package) name; must be a new folder or one created by this class
    :param sys_param_file: steam system parameter file
    :param feature_file: GeoJSON feature file with the connected buildings
    :param marker: marker file that identifies folders created by this class
    """

    root_dir: Path
    name: str
    sys_param_file: Path
    feature_file: Path
    marker: str = STEAM_MARKER

    @property
    def scenario_dir(self) -> Path:
        return Path(self.root_dir) / self.name

    @property
    def mat_path(self) -> Path:
        return results_mat_path(self.scenario_dir)

    @property
    def timing_file(self) -> Path:
        return self.scenario_dir / "timing.json"

    def build(self) -> Path:
        """Generate the Modelica package with the GMT, unless this class already generated it."""
        state = guard_scenario_dir(self.scenario_dir, self.marker)
        if state == "ours" and (self.scenario_dir / "package.mo").exists():
            self.logger.info(f"Model already generated, not rebuilding: {self.scenario_dir}")
            return self.scenario_dir
        GeoJsonModelicaTranslator(
            Path(self.feature_file), Path(self.sys_param_file), Path(self.root_dir), self.name, skip_validation=True
        ).to_modelica()
        mark_scenario_dir(self.scenario_dir, self.marker)
        (self.scenario_dir / "analysis_name.txt").write_text(self.name)
        return self.scenario_dir

    def run(
        self,
        *,
        start_time: float = 0,
        stop_time: float = SECONDS_PER_YEAR,
        number_of_intervals: int | None = None,
        docker_image: str = DEFAULT_DOCKER_IMAGE,
        simulation_flags: str | None = None,
        runner: Any = None,
    ) -> dict[str, Any]:
        """Simulate in docker if there are no results yet. Records the wall-clock time in timing.json.

        :param simulation_flags: OpenModelica simulation flags. Leave as None to use the flags in the generated
            model (GMT sets ``maxStepSize`` for steam districts); passing flags replaces them.
        :param runner: object with ``run_in_docker`` (defaults to the GMT ModelicaRunner)
        """
        guard_scenario_dir(self.scenario_dir, self.marker)
        if self.mat_path.exists():
            self.logger.info(f"Results exist, not re-running: {self.mat_path}")
            return self.timing()
        if runner is None:
            runner = ModelicaRunner()
        if number_of_intervals is None:
            number_of_intervals = int((stop_time - start_time) / 3600)
        t0 = time.perf_counter()
        success, results_path = runner.run_in_docker(
            "compile_and_run",
            f"{self.name}.Districts.DistrictEnergySystem",
            file_to_load=self.scenario_dir / "package.mo",
            run_path=self.scenario_dir,
            start_time=start_time,
            stop_time=stop_time,
            number_of_intervals=number_of_intervals,
            docker_image=docker_image,
            **({"simulation_flags": simulation_flags} if simulation_flags else {}),
        )
        timing = {
            "success": bool(success),
            "wall_clock_s": time.perf_counter() - t0,
            "docker_image": docker_image,
            "results_path": str(results_path),
            "start_time": start_time,
            "stop_time": stop_time,
            "simulation_flags": simulation_flags,
        }
        self.timing_file.write_text(json.dumps(timing, indent=2))
        return self.timing()

    def timing(self) -> dict[str, Any]:
        """Wall-clock timing from timing.json plus the OpenModelica log timings."""
        timing = json.loads(self.timing_file.read_text()) if self.timing_file.exists() else {}
        return timing | om_log_timing(self.scenario_dir)

    def results(self, **kwargs: Any) -> SteamResults:
        """SteamResults of this scenario (kwargs passed to SteamResults)."""
        return SteamResults(self.mat_path, **kwargs)
