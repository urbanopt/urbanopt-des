# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

import pandas as pd
import pytest

from tests.mock_modelica_reader import MockModelicaReader
from urbanopt_des.steam_results import SteamResults
from urbanopt_des.system_comparison import (
    fourg_service_energy,
    read_hourly_results,
    steam_service_energy,
    system_energy_comparison,
)

COMMON = {
    "Interior Lighting": 10.0,
    "Exterior Lighting": 1.0,
    "Plug Loads": 20.0,
    "Building Fans": 5.0,
    "Building Pumps": 2.0,
    "Building Water Systems": 12.0,
}  # 50 MWh


def _end_uses():
    nc = COMMON | {"Building Cooling": 30.0, "Building Heating": 40.0, "Building Heat Rejection": 1.0}
    g4 = COMMON | {"District Cooling": 15.0, "District Heating": 25.0, "ETS Pump Total": 3.0}
    g5 = COMMON | {"ETS Pump Total": 6.0, "ETS Heat Pump": 20.0, "Sewer Pump": 1.0}
    return pd.DataFrame([nc, g4, g5], index=["Non-Connected", "4G DES", "5G DES HP Trio"]).fillna(0.0)


def _fourg_hourly():
    idx = pd.date_range("2017-01-01", periods=10, freq="h")
    # W per hour -> sums: gas 22 MWh, heating elec 2 MWh, cooling 18 MWh
    return pd.DataFrame(
        {
            "Total Heating Natural Gas Plant": [2.2e6] * 10,
            "Total Heating Electricity Plant": [0.1e6] * 10,
            "ETS Pump HHW Electricity Building all_buildings": [0.1e6] * 10,
            "Total Cooling Plant": [1.5e6] * 10,
            "ETS Pump CHW Electricity Building all_buildings": [0.3e6] * 10,
            "Total Boilers": [2.2e6] * 10,
        },
        index=idx,
    )


def _steam():
    n = 25
    data = {
        "pla.QFue_flow": [1e6] * n,  # 1 MW for 23 h counted -> 23 MWh
        "pla.boi.QWat_flow": [0.7e6] * n,
        "pla.PPum": [1e3] * n,
        "bld1.Q_flow": [0.69e6] * n,
        "bld1.pumCNR.P": [0.0] * n,
    }
    return SteamResults(reader=MockModelicaReader(data))


def test_fourg_and_steam_service_energy():
    e = fourg_service_energy(_fourg_hourly())
    assert e == pytest.approx({"heating_gas": 22.0, "heating_electricity": 2.0, "cooling_electricity": 18.0})
    s = steam_service_energy(_steam())
    assert s["heating_gas"] == pytest.approx(23.0)
    assert s["delivered_heat"] == pytest.approx(0.69 * 23)
    matched = steam_service_energy(_steam(), heating_load_mwh=0.69 * 23 / 2)
    assert matched["heating_gas"] == pytest.approx(11.5)
    assert matched["scale"] == pytest.approx(0.5)


def test_system_energy_comparison():
    df = system_energy_comparison(_end_uses(), _fourg_hourly(), _steam(), steam_heating_load_mwh=0.69 * 23 / 2)
    assert df.loc["Non-Connected", "Heating + cooling [MWh]"] == pytest.approx(71.0)
    assert df.loc["Non-Connected", "Site total [MWh]"] == pytest.approx(121.0)
    assert df.loc["4G DES", "Heating + cooling [MWh]"] == pytest.approx(43.0)
    assert df.loc["4G DES", "Cooling [MWh]"] == pytest.approx(18.0)
    assert df.loc["5G DES HP Trio", "Plant/HVAC electricity [MWh]"] == pytest.approx(27.0)
    row = df.loc["1G steam + 4G district cooling (as simulated)"]
    assert row["Heating [MWh]"] == pytest.approx(23.0 + 0.023)
    assert row["Cooling [MWh]"] == pytest.approx(18.0)
    row = df.loc["1G steam + building cooling (load-matched)"]
    assert row["Heating [MWh]"] == pytest.approx(11.5 + 0.0115)
    assert row["Cooling [MWh]"] == pytest.approx(31.0)
    assert df.loc["4G DES", "Site total vs Non-Connected [%]"] == pytest.approx(100 * (93 - 121) / 121)
    assert len(df) == 7


def test_read_hourly_results(tmp_path):
    out = tmp_path / "fourg_system" / "output"
    out.mkdir(parents=True)
    _fourg_hourly().to_csv(out / "power_60min_with_buildings.csv")
    df = read_hourly_results(tmp_path / "fourg_system")
    assert len(df) == 10
    with pytest.raises(FileNotFoundError):
        read_hourly_results(tmp_path / "missing")


def test_steam_name_labels_rows():
    df = system_energy_comparison(_end_uses(), _fourg_hourly(), _steam(), steam_name="S2 typical")
    assert "S2 typical + 4G district cooling (as simulated)" in df.index
