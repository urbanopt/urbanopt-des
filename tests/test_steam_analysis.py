# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

import json

import pytest

from urbanopt_des.results_guard import ExistingResultsError
from urbanopt_des.steam_analysis import (
    STEAM_MARKER,
    SteamScenario,
    om_log_timing,
    results_mat_path,
    write_steam_variant_sys_param,
)

BASE_SYS_PARAM = {
    "weather": "weather.mos",
    "buildings": [{"geojson_id": "1", "ets_model": "Steam"}],
    "district_system": {"first_generation": {"central_steam_plant_parameters": {"boiler_efficiency": 0.7}}},
}


def test_write_steam_variant_sys_param(tmp_path):
    base = tmp_path / "steam.json"
    base.write_text(json.dumps(BASE_SYS_PARAM))
    new = write_steam_variant_sys_param(base, tmp_path / "steam_s2.json", {"steam_leak_fraction": 0.01, "boiler_efficiency": 0.75})
    params = json.loads(new.read_text())["district_system"]["first_generation"]["central_steam_plant_parameters"]
    assert params == {"boiler_efficiency": 0.75, "steam_leak_fraction": 0.01}
    # base file untouched; same content can be written again, different content cannot
    assert json.loads(base.read_text()) == BASE_SYS_PARAM
    write_steam_variant_sys_param(base, new, {"steam_leak_fraction": 0.01, "boiler_efficiency": 0.75})
    with pytest.raises(FileExistsError):
        write_steam_variant_sys_param(base, new, {"steam_leak_fraction": 0.02})


def test_results_mat_path_and_log_timing(tmp_path):
    scenario = tmp_path / "oneg_steam"
    mat = results_mat_path(scenario)
    assert mat == scenario / "oneg_steam.Districts.DistrictEnergySystem_results" / "oneg_steam.Districts.DistrictEnergySystem_res.mat"
    mat.parent.mkdir(parents=True)
    (mat.parent / "stdout.log").write_text("    timeCompile = 3.85,\n    timeSimulation = 1633.6,\n    timeTotal = 1639.5\n")
    assert om_log_timing(scenario) == {"om_time_compile_s": 3.85, "om_time_simulation_s": 1633.6, "om_time_total_s": 1639.5}


class FakeRunner:
    def __init__(self):
        self.calls = []

    def run_in_docker(self, action, model_name, file_to_load=None, run_path=None, **kwargs):
        self.calls.append((action, model_name, kwargs))
        mat = results_mat_path(run_path)
        mat.parent.mkdir(parents=True, exist_ok=True)
        mat.write_bytes(b"")
        return True, mat.parent


def test_scenario_run_only_once_and_only_in_own_folder(tmp_path):
    scenario = SteamScenario(tmp_path, "oneg_steam_v2", tmp_path / "sp.json", tmp_path / "f.json")
    # a folder this class did not create is refused
    scenario.scenario_dir.mkdir()
    with pytest.raises(ExistingResultsError):
        scenario.run(runner=FakeRunner())

    (scenario.scenario_dir / STEAM_MARKER).write_text("created")
    runner = FakeRunner()
    timing = scenario.run(stop_time=86400, runner=runner)
    assert timing["success"] is True
    assert runner.calls[0][1] == "oneg_steam_v2.Districts.DistrictEnergySystem"
    assert runner.calls[0][2]["number_of_intervals"] == 24
    # results exist: not re-run
    scenario.run(runner=runner)
    assert len(runner.calls) == 1


def test_scenario_build_refuses_existing_folder(tmp_path):
    scenario = SteamScenario(tmp_path, "fourg_system", tmp_path / "sp.json", tmp_path / "f.json")
    scenario.scenario_dir.mkdir()
    (scenario.scenario_dir / "package.mo").write_text("existing 4G model")
    with pytest.raises(ExistingResultsError):
        scenario.build()
    assert (scenario.scenario_dir / "package.mo").read_text() == "existing 4G model"
