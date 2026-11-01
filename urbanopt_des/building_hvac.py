# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

"""Summarize each building's primary HVAC system from an URBANopt feature file."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

UNKNOWN = "Unknown"


def classify_hvac(system_type: str | None) -> tuple[str, str, str]:
    """Generic system name, heating fuel and cooling fuel from an URBANopt ``system_type`` string."""
    s = (system_type or "").strip().lower()

    if "vav" in s and "chiller" in s and "boiler" in s:
        return ("VAV + Chiller + Boiler Reheat", "Natural Gas", "Electricity")
    if "pvav" in s and "gas" in s and "electric reheat" in s:
        return ("Packaged VAV", "Natural Gas + Electricity (reheat)", "Electricity")
    if "psz" in s and "gas coil" in s:
        return ("Packaged Single Zone (PSZ-AC)", "Natural Gas", "Electricity")

    if "gas" in s and "electric" in s:
        heating_fuel = "Natural Gas + Electricity"
    elif "gas" in s or "boiler" in s:
        heating_fuel = "Natural Gas"
    elif "electric" in s or "heat pump" in s:
        heating_fuel = "Electricity"
    else:
        heating_fuel = UNKNOWN

    cooling_fuel = "Electricity" if any(k in s for k in ["chiller", "dx", "ac", "cool", "heat pump"]) else UNKNOWN
    return ("Other/Unmapped", heating_fuel, cooling_fuel)


def cooling_rejection_from_idf(idf_path: Path | str | None) -> tuple[bool | None, str]:
    """(water-based cooling, cooling rejection type) from a generated EnergyPlus IDF, when it exists."""
    if idf_path is None or not Path(idf_path).exists():
        return None, UNKNOWN
    text = Path(idf_path).read_text(errors="ignore").lower()
    if "coolingtower:" in text or "watercooled" in text:
        return True, "Cooling Tower / Water-Cooled Condenser"
    if "aircooled" in text:
        return False, "Air-Cooled Condenser"
    return None, UNKNOWN


def default_idf_path(feature_file: Path | str, building_id: str | int, scenario: str = "baseline") -> Path:
    """IDF written by the URBANopt create-typical-building measure for a building."""
    return Path(feature_file).parent / "run" / scenario / str(building_id) / "009_create_typical_building_from_model" / "SR1" / "in.idf"


def summarize_building_hvac(feature_file: Path | str, scenario: str = "baseline") -> pd.DataFrame:
    """One row per building: raw system type, generic class, heating and cooling fuel, cooling rejection.

    The IDF of each building (if present in the scenario run folder) takes precedence over name
    heuristics for the cooling rejection type.
    """
    geojson = json.loads(Path(feature_file).read_text())
    records = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        if props.get("type") != "Building":
            continue
        system_type = props.get("system_type", "")
        building_id = props.get("id")
        generic, heating_fuel, cooling_fuel = classify_hvac(system_type)
        idf = default_idf_path(feature_file, building_id, scenario) if building_id is not None else None
        water_based, rejection = cooling_rejection_from_idf(idf)
        if water_based is None:
            s = (system_type or "").lower()
            water_based = any(k in s for k in ["chiller", "chilled water", "chw", "district cooling", "water loop"])
            rejection = "Heuristic (from system_type)"
        records.append(
            {
                "building_id": building_id,
                "building_name": props.get("name"),
                "building_type": props.get("building_type"),
                "gross_floor_area_m2": props.get("Gross Floor Area (m2)"),
                "system_type_raw": system_type,
                "primary_hvac_generic": generic,
                "heating_fuel": heating_fuel,
                "cooling_fuel": cooling_fuel,
                "water_based_cooling": water_based,
                "cooling_rejection_type": rejection,
            }
        )
    df = pd.DataFrame(records)
    return df.sort_values("building_id") if not df.empty else df


def hvac_class_counts(summary: pd.DataFrame) -> pd.DataFrame:
    """Building counts by HVAC class, fuels and cooling rejection."""
    keys = ["primary_hvac_generic", "heating_fuel", "cooling_fuel", "water_based_cooling", "cooling_rejection_type"]
    return summary.groupby(keys).size().reset_index(name="building_count")
