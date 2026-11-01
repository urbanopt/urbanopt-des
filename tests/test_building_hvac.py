# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

import json

from urbanopt_des.building_hvac import (
    classify_hvac,
    cooling_rejection_from_idf,
    default_idf_path,
    hvac_class_counts,
    summarize_building_hvac,
)


def test_classify_hvac():
    assert classify_hvac("VAV chiller with gas boiler reheat") == ("VAV + Chiller + Boiler Reheat", "Natural Gas", "Electricity")
    assert classify_hvac("PSZ-AC with gas coil") == ("Packaged Single Zone (PSZ-AC)", "Natural Gas", "Electricity")
    assert classify_hvac("PVAV with gas heat with electric reheat")[0] == "Packaged VAV"
    assert classify_hvac("Residential heat pump") == ("Other/Unmapped", "Electricity", "Electricity")
    assert classify_hvac(None) == ("Other/Unmapped", "Unknown", "Unknown")


def test_cooling_rejection_from_idf(tmp_path):
    assert cooling_rejection_from_idf(None) == (None, "Unknown")
    idf = tmp_path / "in.idf"
    idf.write_text("CoolingTower:VariableSpeed,\n")
    assert cooling_rejection_from_idf(idf) == (True, "Cooling Tower / Water-Cooled Condenser")
    idf.write_text("Coil:Cooling:DX:SingleSpeed, AirCooled;\n")
    assert cooling_rejection_from_idf(idf) == (False, "Air-Cooled Condenser")


def test_summarize_building_hvac(tmp_path):
    feature_file = tmp_path / "project.json"
    features = [
        {
            "type": "Feature",
            "properties": {"type": "Building", "id": "1", "name": "A", "system_type": "VAV chiller with gas boiler reheat"},
        },
        {"type": "Feature", "properties": {"type": "Building", "id": "2", "name": "B", "system_type": "PSZ-AC with gas coil"}},
        {"type": "Feature", "properties": {"type": "Site Origin"}},
    ]
    feature_file.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    idf = default_idf_path(feature_file, "2")
    idf.parent.mkdir(parents=True)
    idf.write_text("AirCooled")

    df = summarize_building_hvac(feature_file)
    assert list(df["building_id"]) == ["1", "2"]
    row1 = df.set_index("building_id").loc["1"]
    assert bool(row1["water_based_cooling"]) is True  # heuristic: chiller
    assert row1["cooling_rejection_type"] == "Heuristic (from system_type)"
    row2 = df.set_index("building_id").loc["2"]
    assert bool(row2["water_based_cooling"]) is False
    assert row2["cooling_rejection_type"] == "Air-Cooled Condenser"
    assert hvac_class_counts(df)["building_count"].sum() == 2
