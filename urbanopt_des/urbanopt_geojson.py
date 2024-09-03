import json
from pathlib import Path
from typing import Union


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

    def get_buildings(self, ids: Union[list[str], None] = None, keep_properties: Union[list[str], None] = None) -> list:
        """Return a list of all the properties of type Building"""
        result = []
        for feature in self.data["features"]:
            if feature["properties"]["type"] == "Building" and (ids is None or feature["properties"]["id"] in ids):
                # only keep the fields that in the keep_properties list
                result.append(feature)

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

    def set_property_on_building_id(self, building_id: str, property_name: str, property_value: str, overwrite=True) -> None:
        """Set a property on a building_id"""
        for feature in self.data["features"]:
            if (
                feature["properties"]["type"] == "Building"
                and feature["properties"]["id"] == building_id
                and (overwrite or property_name not in feature["properties"])
            ):
                feature["properties"][property_name] = property_value

    def get_property_on_building_id(self, building_id: str, property_name: str) -> str:
        """Get a property on a building_id"""
        for feature in self.data["features"]:
            if feature["properties"]["type"] == "Building" and feature["properties"]["id"] == building_id:
                return feature["properties"].get(property_name, None)

    def get_site_lat_lon(self) -> tuple:
        """Return the site's latitude and longitude"""
        for feature in self.data["features"]:
            if feature["properties"]["name"] == "Site Origin":
                # reverse the order of the coordinates
                return feature["geometry"]["coordinates"][::-1]

    def create_aggregated_representation(self, building_names: list[str]) -> None:
        """Go through the GeoJSON file and if it is of type Building, then aggregate the characteristics.

        #TODO: This is a work in progress and can more easily be accomplished with GeoPandas."""
        # fields that are summed in the aggregations
        sum_fields = ["floor_area", "footprint_area"]
        avg_fields = [
            "year_built",
            "number_of_stories",
            "window_wall_ratio",
        ]

        # create a dictionary to hold the aggregated values
        aggregated_values = {}
        for field in sum_fields:
            aggregated_values[field] = 0
        for field in avg_fields:
            aggregated_values[field] = 0

        for building_id in building_names:
            pass

    def save(self) -> None:
        """Save the GeoJSON file"""
        self.save_as(self._filename)

    def save_as(self, filename: Path) -> None:
        """Save the GeoJSON file"""
        with open(filename, "w") as f:
            json.dump(self.data, f, indent=2)
