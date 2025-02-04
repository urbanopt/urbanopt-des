import unittest
from pathlib import Path

from urbanopt_des.modelica_results import ModelicaResults


class ModelicaResultsTest(unittest.TestCase):
    # This is a simple test to ensure we can extend at a later time
    def setUp(self):
        self.data_dir = Path(__file__).parent / "data"
        self.output_dir = Path(__file__).parent / "test_output"
        if not self.output_dir.exists():
            self.output_dir.mkdir()

    def test_load_mat_zip(self):
        """Simple test to make sure we can load the geojson file"""
        mat_filename = self.data_dir / "DistrictEnergySystem.mat.zip"
        modelica_variables = self.output_dir / "modelica_variables.json"
        if modelica_variables.exists():
            modelica_variables.unlink()

        data = ModelicaResults(mat_filename)
        data.save_variables(self.output_dir)

        # verify that the modelica_variables was created
        self.assertTrue(modelica_variables.exists())

    def test_number_of_buildings(self):
        """Simple test to make sure we can load the geojson file"""
        mat_filename = self.data_dir / "DistrictEnergySystem.mat.zip"
        data = ModelicaResults(mat_filename)
        self.assertEqual(data.number_of_buildings(), 1)

    def test_resample_and_convert_to_df(self):
        """Simple test to make sure we can load the geojson file"""
        mat_filename = self.data_dir / "DistrictEnergySystem.mat.zip"
        # remove any of the previous outputs
        for interval in [5, 15, 60]:
            if (self.output_dir / f"power_{interval}min.csv").exists():
                (self.output_dir / f"power_{interval}min.csv").unlink()

        data = ModelicaResults(mat_filename, self.output_dir)
        data.resample_and_convert_to_df(["all_buildings"])
        # Should have hourly data for a full year
        self.assertEqual(data.min_60.shape[0], 8761)

        # save the dataframes
        data.save_dataframes()

        # ensure that the power_5, 15, and 60 minutes were persisted
        for interval in [5, 15, 60]:
            self.assertTrue((self.output_dir / f"power_{interval}min.csv").exists())

        # check the sum of the Total Boilers, should be 1376600000 +/- 1E6
        self.assertAlmostEqual(data.min_60["Total Boilers"].sum(), 1400000000, delta=1e8)

        # verify that the ETS Pump Electricity is reported in this model since
        # the 4G systems should have ETS pumps now (which are in the building)
        self.assertTrue("ETS Pump Electricity Total" in data.min_60.columns)
        print(data.min_60["ETS Pump Electricity Total"].sum())
        self.assertGreater(data.min_60["ETS Pump Electricity Total"].sum(), 0)
