import json
from pathlib import Path


class URBANoptGeoJSON:
    def __init__(self, filename: Path):
        self._filename = filename
        self.data = None

        # read in the JSON file and store it in data
        with open(filename) as f:
            self.data = json.load(f)

    def get_building_paths(self, scenario_name: str) -> list[Path]:
        """Return a list of Path objects for the building GeoJSON files"""
        result = []
        for feature in self.data["features"]:
            if feature["properties"]["type"] == "Building":
                building_path = self._filename.parent / "run" / scenario_name / feature["properties"]["id"]
                result.append(building_path)
                # result.append(Path(feature["properties"]["file"]))

        # verify that the paths exist
        for path in result:
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")

        return result

    def get_building_ids(self) -> list:
        """Return a list of building names"""
        result = []
        for feature in self.data["features"]:
            if "type" in feature["properties"] and feature["properties"]["type"] == "Building":
                result.append(feature["properties"]["id"])
            elif "name" in feature["properties"] and feature["properties"]["name"] == "Site Origin":
                pass
            else:
                # need to implement a reasonable logger.
                pass
                # print(f"Feature does not have a type Building: {feature}")
                # print("Did you forget to call the `update_geojson_from_seed_data` method?")

        return result

    def get_building_names(self) -> list:
        """Return a list of building names. Typically this field is only used for visual display name only."""
        result = []
        for feature in self.data["features"]:
            if feature["properties"]["type"] == "Building":
                result.append(feature["properties"]["name"])

        return result

    def get_building_properties_by_id(self, building_id: str) -> dict:
        """Get the list of building ids in the GeoJSON file. The Building id is what
        is used in URBANopt as the identifier. It is common that this is used to name
        the building, more than the GeoJSON's building name field.

        Args:
            building_id (str): building id, this is the property.id values in the geojson's feature

        Returns:
            dict: building properties
        """
        result = {}
        for feature in self.data["features"]:
            if feature["properties"]["type"] == "Building" and feature["properties"]["id"] == building_id:
                result = feature["properties"]

        return result

    def get_meters_for_building(self, building_id: str) -> list:
        """Return a list of meters for the building_id"""
        result = []
        for feature in self.data["features"]:
            if feature["properties"]["type"] == "Building" and feature["properties"]["id"] == building_id:
                for meter in feature["properties"].get("meters", []):
                    result.append(meter["type"])

        return result

    def get_meter_readings_for_building(self, building_id: str, meter_type: str) -> list:
        """Return a list of meter readings for the building_id"""
        result = []
        for feature in self.data["features"]:
            if feature["properties"]["type"] == "Building" and feature["properties"]["id"] == building_id:
                for meter in feature["properties"].get("meters", []):
                    if meter["type"] == meter_type:
                        result = meter["readings"]

        return result

    def get_monthly_readings(self, building_id: str, meter_type: str) -> list:
        """Return a list of monthly electricity consumption for the building_id"""
        result = []
        for feature in self.data["features"]:
            if feature["properties"]["type"] == "Building" and feature["properties"]["id"] == building_id:
                result = feature["properties"]["monthly_electricity"]

        return result
