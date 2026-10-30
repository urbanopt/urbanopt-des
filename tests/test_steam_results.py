# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

import math

import pytest

from tests.mock_modelica_reader import MockModelicaReader
from urbanopt_des.steam_results import SteamResults, compare_to_targets, steam_loss_parameters

HOURS = 25  # one day of hourly data, t = 0 ... 86400 s
SECONDS_INTEGRATED = (HOURS - 1) * 3600 - 3600  # first hour excluded as the startup transient


def _mock(building_style: str = "bldN") -> MockModelicaReader:
    def b(i: int, var: str) -> str:
        return f"bld{i}.{var}" if building_style == "bldN" else f"bld[{i}].{var}"

    data = {
        "pla.QFue_flow": [1000.0] * HOURS,
        "pla.boi.QWat_flow": [700.0] * HOURS,
        "pla.PPum": [10.0] * HOURS,
        b(1, "Q_flow"): [300.0] * HOURS,
        b(2, "Q_flow"): [390.0] * HOURS,
        b(1, "pumCNR.P"): [1.0] * HOURS,
        b(2, "pumCNR.P"): [2.0] * HOURS,
        "dis.nCon": 2,
    }
    # peak in hour 10 (after the startup period); a larger spike at t=0 must be ignored
    data["pla.QFue_flow"][10] = 4000.0
    data["pla.QFue_flow"][0] = 9000.0
    return MockModelicaReader(data)


@pytest.mark.parametrize("style", ["bldN", "bld[i]"])
def test_finds_variables_for_both_naming_styles(style):
    res = SteamResults(reader=_mock(style))
    assert res.variables["fuel"] == ["pla.QFue_flow"]
    assert res.variables["boiler_heat"] == ["pla.boi.QWat_flow"]
    assert len(res.variables["delivered"]) == 2
    assert len(res.variables["condensate_pumps"]) == 2
    assert res.number_of_buildings == 2


def test_annual_summary_energy_balance():
    s = SteamResults(reader=_mock()).annual_summary()
    t = SECONDS_INTEGRATED
    # fuel: 1000 W, plus the triangle from the 4000 W spike at hour 10 (3000 W x 3600 s)
    fuel_j = 1000 * t + 3000 * 3600
    assert s["Total energy in (fuel, LHV) [GJ]"] == pytest.approx(fuel_j / 1e9)
    assert s["Boiler useful heat [GJ]"] == pytest.approx(700 * t / 1e9)
    assert s["Delivered to buildings [GJ]"] == pytest.approx(690 * t / 1e9)
    assert s["Dist. + storage loss [GJ]"] == pytest.approx(10 * t / 1e9)
    assert s["Combustion loss [GJ]"] == pytest.approx((fuel_j - 700 * t) / 1e9)
    assert s["Feedwater pump electricity [kWh]"] == pytest.approx(10 * t / 3.6e6)
    assert s["Condensate pump electricity [kWh]"] == pytest.approx(3 * t / 3.6e6)
    fuel_kg = fuel_j / 50e6
    assert s["Natural gas [t]"] == pytest.approx(fuel_kg / 1000)
    assert s["Natural gas [m3, d=0.84]"] == pytest.approx(fuel_kg / 0.84)
    assert s["CO2 [t]"] == pytest.approx(fuel_kg * 2.23 / 1000)
    assert s["System efficiency [%]"] == pytest.approx(100 * 690 * t / fuel_j)


def test_peak_excludes_startup_transient():
    s = SteamResults(reader=_mock()).annual_summary()
    assert s["Peak fuel rate [kW]"] == pytest.approx(4.0)
    assert s["Peak delivered heat [kW]"] == pytest.approx(0.69)


def test_hourly_monthly_and_uo_des_columns():
    res = SteamResults(reader=_mock(), year=2017)
    h = res.hourly()
    assert len(h) == HOURS
    assert str(h.index[0]) == "2017-01-01 00:00:00"
    assert h["Building load served"].iloc[5] == pytest.approx(690.0)

    m = res.monthly()
    assert list(m.index.month) == [1]
    # months are integrated like the annual totals, so they sum to them
    assert m["Building load served"].iloc[0] == pytest.approx(690 * SECONDS_INTEGRATED / 1e9)
    assert m["Fuel input rate"].sum() == pytest.approx(res.annual_summary()["Total energy in (fuel, LHV) [GJ]"])

    uo = res.to_uo_des_columns()
    assert {"Total DES Natural Gas", "Total DES Electricity", "ETS Thermal Heating Total"} <= set(uo.columns)
    assert uo["Total DES Electricity"].iloc[3] == pytest.approx(13.0)


def test_missing_variables_raise():
    with pytest.raises(KeyError):
        SteamResults(reader=MockModelicaReader({"x": [1.0, 2.0]}))
    with pytest.raises(ValueError, match="mat_filename or reader"):
        SteamResults()


def test_save_writes_only_to_output_dir(tmp_path):
    paths = SteamResults(reader=_mock()).save(tmp_path / "steam", prefix="case")
    assert [p.name for p in paths] == ["case_summary.csv", "case_hourly.csv", "case_monthly.csv"]
    assert all(p.exists() and p.parent == tmp_path / "steam" for p in paths)


def test_compare_to_targets():
    s = {"A": 101.0, "B": 90.0}
    df = compare_to_targets(s, {"A": (100.0, 0.02), "B": (100.0, 0.05)})
    assert bool(df.loc["A", "Pass"]) is True
    assert bool(df.loc["B", "Pass"]) is False
    assert math.isclose(df.loc["B", "Diff %"], -10.0)


def _mock_with_losses() -> MockModelicaReader:
    reader = _mock()
    data = dict(reader._mock_data)
    data.update(
        {
            "losMak.QLos_flow": [50.0] * HOURS,
            "losMak.mLea_flow": [0.001] * HOURS,
            "losMak.mDum_flow": [0.002] * HOURS,
            "losMak.mMak_flow": [0.003] * HOURS,
        },
    )
    return MockModelicaReader(data)


def test_loss_metrics():
    res = SteamResults(reader=_mock_with_losses())
    assert res.has_losses
    s = res.annual_summary()
    t = SECONDS_INTEGRATED
    assert s["Supply main heat loss [GJ]"] == pytest.approx(50 * t / 1e9)
    assert s["Steam leaked [t]"] == pytest.approx(0.001 * t / 1000)
    assert s["Make-up water [m3]"] == pytest.approx(0.003 * t / 1000)
    assert s["Discharged condensate [m3]"] == pytest.approx(0.002 * t / 1000)
    m = res.monthly()
    assert m["Make-up water flow"].sum() == pytest.approx(s["Make-up water [m3]"])


def test_lossless_result_reports_zero_losses():
    s = SteamResults(reader=_mock()).annual_summary()
    assert s["Make-up water [m3]"] == 0.0
    assert s["Supply main heat loss [GJ]"] == 0.0


def test_steam_loss_parameters_calibration():
    reader = _mock()
    data = dict(reader._mock_data)
    data.update(
        {
            "pla.port_bSerHea.m_flow": [-0.5] * HOURS,  # leaves the plant
            "mDis_flow_nominal": 2.0,
            "QDis_flow_nominal": 7000.0,
        },
    )
    baseline = SteamResults(reader=MockModelicaReader(data))
    p = steam_loss_parameters(baseline, leak_share=0.10, heat_loss_share=0.08, condensate_return_fraction=0.9)
    # leak: 10% of 0.5 kg/s average = 0.05 kg/s = 0.025 of the 2 kg/s nominal
    assert p["steam_leak_fraction"] == pytest.approx(0.025)
    # heat: 8% of 700 W boiler heat = 56 W = 0.008 of the 7000 W nominal
    assert p["distribution_heat_loss_fraction"] == pytest.approx(0.008)
    assert p["condensate_return_fraction"] == 0.9
    assert p["makeup_water_temperature"] == 12.0

    with pytest.raises(ValueError, match="lossless"):
        steam_loss_parameters(SteamResults(reader=_mock_with_losses()), 0.1, 0.1)
    with pytest.raises(ValueError, match="leak_share"):
        steam_loss_parameters(baseline, 1.5, 0.1)
