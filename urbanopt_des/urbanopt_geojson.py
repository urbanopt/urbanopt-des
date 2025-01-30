import json
import tempfile
from pathlib import Path

from geojson_modelica_translator.geojson.urbanopt_geojson import UrbanOptGeoJson
from geopandas import GeoDataFrame
from shapely.geometry import box


class DESGeoJSON(UrbanOptGeoJson):
    def __init__(self, filename: Path, building_ids=None, skip_validation=False):
        super().__init__(filename, building_ids, skip_validation)

    def create_aggregated_representation(self, building_names: list[str]) -> None:
        """Go through the GeoJSON file and if it is of type Building, then aggregate the characteristics.

        #TODO: This is a work in progress and can more easily be accomplished with GeoPandas."""

        # pull out the project data, because it will need to be stitched into
        # the geojson file at the end
        project_data = self.data["project"]

        # read into geodataframe
        gdf = GeoDataFrame.from_features(self.data)

        # related is a list typically, which isn't supported in geodataframes
        if "related" in gdf.columns:
            gdf = gdf.drop(columns=["related"])

        # init new obj, can delete this once the if statement below is
        # fully fleshed out.
        gdf_2 = None

        # add a new field to "enable/disable"
        gdf["enabled"] = True
        if len(building_names) == 1 and building_names[0] == "all":
            # dissolve
            gdf_2 = gdf.dissolve(
                by="type",
                aggfunc={
                    "footprint_area": "sum",
                    # "Footprint Area (m2)": "sum",
                    # "Footprint Area (ft2)": "sum",
                    "height": "mean",
                    "floor_area": "sum",
                    # "Gross Floor Area": "sum",
                    "gross_floor_area_m2": "sum",
                    "gross_floor_area_ft2": "sum",
                    "number_of_stories": "mean",
                    "number_of_stories_above_ground": "mean",
                    # "Building Levels": "mean",
                    "attic_type": "first",
                    "foundation_type": "first",
                    "number_of_bedrooms": "mean",
                    "number_of_residential_units": "mean",
                    "enabled": "first",
                    "id": "first",
                    "building_type": "first",
                },
            )

            # splat the total_bounds into a box (total_bounds returns minx, miny, maxx, maxy)
            gdf_2["geometry"] = box(*gdf_2.total_bounds)

            # Set the id on the first element to "all""
            gdf_2.loc[gdf_2.index == "Building", "id"] = "all_buildings"
        else:
            print("This still needs to be implemented")

        # save the gdf_2 to a temp geojson file
        temp_dir = Path(tempfile.mkdtemp())

        if gdf_2 is not None:
            gdf_2.to_file(temp_dir / "temp.geojson", driver="GeoJSON")

        # read it back in as a dict
        with open(temp_dir / "temp.geojson") as f:
            gdf_2 = json.load(f)

            # update the project data
            gdf_2["project"] = project_data

        return gdf_2
