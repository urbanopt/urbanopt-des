import unittest
from pathlib import Path

from urbanopt_des.urbanopt_geojson import DESGeoJSON


class GeoJsonTest(unittest.TestCase):
    # This is a simple test to ensure we can extend at a later time
    def setUp(self):
        self.data_dir = Path(__file__).parent / "data"

    def test_load_geojson(self):
        """Simple test to make sure we can load the geojson file"""
        filename = self.data_dir / "nrel_campus.json"
        geojson = DESGeoJSON(filename)

        assert "Outdoor Test Facility" in geojson.get_building_names()
        assert "Research Support Facility" in geojson.get_building_names()
