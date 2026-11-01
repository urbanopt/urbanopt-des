# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

"""Annual site-energy comparison of district systems (Non-Connected, 4G, 5G and 1G steam).

All systems share the same building end uses that the district system does not serve (lighting, plug
loads, fans, pumps, water systems). The comparison isolates the energy used to provide space heating and
cooling, then adds the shared end uses back for the site total.

The 1G steam system serves heating only, so it is paired with a cooling option: the Non-Connected building
cooling, or the cooling side of a 4G run (chiller plant plus chilled-water ETS pumps). The two systems share
no equipment, so adding them is equivalent to one combined model.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .steam_results import J_PER_MWH, SteamResults

# end_use_summary_all.csv columns (MWh) that are the same in every scenario
COMMON_END_USES = [
    "Interior Lighting",
    "Exterior Lighting",
    "Plug Loads",
    "Building Fans",
    "Building Pumps",
    "Building Water Systems",
]
BUILDING_HEATING = ["Building Heating"]
BUILDING_COOLING = ["Building Cooling", "Building Heat Rejection"]

# power_60min_with_buildings.csv columns (W, hourly) of a 4G run
FOURG_HEATING_GAS = "Total Heating Natural Gas Plant"
FOURG_HEATING_ELECTRICITY = ["Total Heating Electricity Plant", "ETS Pump HHW Electricity Building"]
FOURG_COOLING_ELECTRICITY = ["Total Cooling Plant", "ETS Pump CHW Electricity Building"]


def read_hourly_results(scenario_dir: Path | str) -> pd.DataFrame:
    """Read the hourly UO DES results (power_60min_with_buildings.csv) of an existing scenario, read only."""
    scenario_dir = Path(scenario_dir)
    for candidate in [scenario_dir / "output" / "power_60min_with_buildings.csv", scenario_dir / "power_60min_with_buildings.csv"]:
        if candidate.exists():
            return pd.read_csv(candidate, index_col=0, parse_dates=True)
    raise FileNotFoundError(f"No power_60min_with_buildings.csv in {scenario_dir}")


def _sum_mwh(df: pd.DataFrame, prefixes: list[str]) -> float:
    """Annual MWh of hourly W columns whose names start with any prefix."""
    cols = [c for c in df.columns if any(c.startswith(p) for p in prefixes)]
    return float(df[cols].sum().sum() / 1e6)


def fourg_service_energy(hourly: pd.DataFrame) -> dict[str, float]:
    """Heating and cooling service energy (MWh) of a 4G run from its hourly results."""
    return {
        "heating_gas": _sum_mwh(hourly, [FOURG_HEATING_GAS]),
        "heating_electricity": _sum_mwh(hourly, FOURG_HEATING_ELECTRICITY),
        "cooling_electricity": _sum_mwh(hourly, FOURG_COOLING_ELECTRICITY),
    }


def steam_service_energy(results: SteamResults, heating_load_mwh: float | None = None) -> dict[str, float]:
    """Heating service energy (MWh) of a steam run.

    :param heating_load_mwh: when given, scale fuel and pump energy so the steam system delivers this heat
        (at its simulated system efficiency). Use the building heating load of the other systems to compare
        like for like when the steam run serves extra standby load.
    """
    s = results.annual_summary()
    delivered = s["Delivered to buildings [GJ]"] * 1e9 / J_PER_MWH
    scale = heating_load_mwh / delivered if heating_load_mwh else 1.0
    pumps = (s["Feedwater pump electricity [kWh]"] + s["Condensate pump electricity [kWh]"]) / 1e3
    return {
        "heating_gas": s["Total energy in (fuel, LHV) [GJ]"] * 1e9 / J_PER_MWH * scale,
        "heating_electricity": pumps * scale,
        "delivered_heat": delivered * scale,
        "scale": scale,
    }


def system_energy_comparison(
    end_use_summary: pd.DataFrame,
    fourg_hourly: pd.DataFrame | None = None,
    steam: SteamResults | None = None,
    steam_heating_load_mwh: float | None = None,
    names: dict[str, str] | None = None,
    *,
    steam_name: str = "1G steam",
) -> pd.DataFrame:
    """Annual site energy (MWh/yr) by system.

    :param end_use_summary: end_use_summary_all.csv (rows: scenarios, MWh) with rows for Non-Connected, 4G and 5G
    :param fourg_hourly: hourly results of the 4G run, to split its heating and cooling
    :param steam: SteamResults of the steam run
    :param steam_heating_load_mwh: building heating load to match for the "load-matched" steam rows
    :param names: row names in ``end_use_summary`` for keys "non_connected", "4g", "5g"
    :param steam_name: label of the steam rows (e.g., the scenario name)
    :return: DataFrame indexed by scenario with gas, electricity, heating, cooling, heating+cooling, common
        end uses, site total and the change vs Non-Connected
    """
    names = {"non_connected": "Non-Connected", "4g": "4G DES", "5g": "5G DES HP Trio"} | (names or {})
    eus = end_use_summary
    columns = list(eus.columns)

    def row_sum(row: str, cols: list[str]) -> float:
        return float(sum(eus.loc[row, c] for c in cols if c in columns))

    nc = names["non_connected"]
    common = row_sum(nc, COMMON_END_USES)
    rows: list[dict] = []

    def add(name: str, *, gas: float | None, elec: float | None, heating: float | None, cooling: float | None, service: float):
        rows.append(
            {
                "Scenario": name,
                "Plant/HVAC natural gas [MWh]": gas,
                "Plant/HVAC electricity [MWh]": elec,
                "Heating [MWh]": heating,
                "Cooling [MWh]": cooling,
                "Heating + cooling [MWh]": service,
                "Common building end uses [MWh]": common,
                "Site total [MWh]": common + service,
            }
        )

    nc_heating = row_sum(nc, BUILDING_HEATING)
    nc_cooling = row_sum(nc, BUILDING_COOLING)
    add(nc, gas=None, elec=None, heating=nc_heating, cooling=nc_cooling, service=nc_heating + nc_cooling)

    fourg_cooling = None
    if names["4g"] in eus.index:
        service = float(eus.loc[names["4g"]].sum()) - common
        if fourg_hourly is not None:
            e = fourg_service_energy(fourg_hourly)
            heating = e["heating_gas"] + e["heating_electricity"]
            fourg_cooling = e["cooling_electricity"]
            add(
                names["4g"],
                gas=e["heating_gas"],
                elec=e["heating_electricity"] + fourg_cooling,
                heating=heating,
                cooling=fourg_cooling,
                service=service,
            )
        else:
            add(names["4g"], gas=None, elec=None, heating=None, cooling=None, service=service)

    if names["5g"] in eus.index:
        service = float(eus.loc[names["5g"]].sum()) - common
        add(names["5g"], gas=0.0, elec=service, heating=None, cooling=None, service=service)

    if steam is not None:
        variants = [("as simulated", None)]
        if steam_heating_load_mwh:
            variants.append(("load-matched", steam_heating_load_mwh))
        cooling_options = [("building cooling", nc_cooling)]
        if fourg_cooling is not None:
            cooling_options.append(("4G district cooling", fourg_cooling))
        for cooling_name, cooling in cooling_options:
            for variant, load in variants:
                e = steam_service_energy(steam, load)
                heating = e["heating_gas"] + e["heating_electricity"]
                add(
                    f"{steam_name} + {cooling_name} ({variant})",
                    gas=e["heating_gas"],
                    elec=e["heating_electricity"] + cooling,
                    heating=heating,
                    cooling=cooling,
                    service=heating + cooling,
                )

    df = pd.DataFrame(rows).set_index("Scenario")
    baseline = df.loc[nc, "Site total [MWh]"]
    df["Site total vs Non-Connected [%]"] = 100 * (df["Site total [MWh]"] - baseline) / baseline
    return df
