# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

import unittest
from pathlib import Path
from unittest.mock import patch

from tests.mock_modelica_reader import MockModelicaReader
from urbanopt_des.modelica_results import ModelicaResults


class TestModelicaResampleAndConvert(unittest.TestCase):
    """Test the mathematical calculations in resample_and_convert_to_df."""

    def setUp(self):
        self.output_dir = Path(__file__).parent / "test_output"
        if not self.output_dir.exists():
            self.output_dir.mkdir()

    def test_simple_aggregation_single_building(self):
        """Test that aggregations work correctly with simple known values."""
        # Create simple test data: 24 hours of hourly data
        n_hours = 24

        # Simple constant values for testing aggregation math
        chiller_power = [100.0] * n_hours  # 100 W constant
        boiler_power = [200.0] * n_hours  # 200 W constant

        mock_data = {
            # Building count
            "nBui": 1,
            # Time variable (using ETot.y as reference)
            "ETot.y": [150.0] * n_hours,  # Should be sum of various components
            # Plant pumps
            "pla.PPum": [10.0] * n_hours,
            "pumSto.P": [5.0] * n_hours,
            "pumDis.P": [5.0] * n_hours,
            # Cooling plant
            "cooPla_test.mulChiSys.P": chiller_power,
            "cooPla_test.pumCW.P[1]": [15.0] * n_hours,
            "cooPla_test.pumCHW.P[1]": [20.0] * n_hours,
            "cooPla_test.cooTowWitByp.PFan[1]": [10.0] * n_hours,
            # Heating plant
            "heaPla_test.boiHotWat.boi[1].QFue_flow": boiler_power,
            "heaPla_test.pumHW.P[1]": [25.0] * n_hours,
            # Building ETS data
            "PHeaPump.u[1]": [30.0] * n_hours,
            "PPumETS.u[1]": [8.0] * n_hours,
            "TimeSerLoa_bldg1.disFloCoo.PPum": [6.0] * n_hours,
            "TimeSerLoa_bldg1.disFloHea.PPum": [7.0] * n_hours,
            "bui[1].QCoo_flow": [-500.0] * n_hours,  # Negative for cooling
            "bui[1].QHea_flow": [600.0] * n_hours,
        }

        # Create a mock ModelicaResults instance
        with patch("urbanopt_des.modelica_results.Reader") as mock_reader_class:
            mock_reader_instance = MockModelicaReader(mock_data)
            mock_reader_class.return_value = mock_reader_instance

            # Create a temporary mock file
            mock_file = self.output_dir / "mock_test.mat"
            mock_file.touch()

            try:
                # Create ModelicaResults instance
                results = ModelicaResults(mock_file, self.output_dir)
                results.modelica_data = mock_reader_instance

                # Run the resample and convert method
                results.resample_and_convert_to_df(building_ids=["bldg1"], year_of_data=2017)

                # Verify the aggregations
                df = results.min_60

                # Test individual components
                self.assertEqual(df["Chiller 1"].iloc[0], 100.0, "Chiller power should match input")
                self.assertEqual(df["Boiler 1"].iloc[0], 200.0, "Boiler power should match input")
                self.assertEqual(df["Sewer Pump Electricity"].iloc[0], 10.0, "Sewer pump should match input")

                # Test aggregations
                # Total Chillers should equal sum of all chillers (just 1 in this case)
                self.assertEqual(df["Total Chillers"].iloc[0], 100.0, "Total chillers aggregation incorrect")

                # Total Cooling Plant = Chiller + CW Pump + CHW Pump + Cooling Tower Fan
                expected_cooling_plant = 100.0 + 15.0 + 20.0 + 10.0
                self.assertEqual(df["Total Cooling Plant"].iloc[0], expected_cooling_plant, "Total cooling plant aggregation incorrect")

                # Total Boilers
                self.assertEqual(df["Total Boilers"].iloc[0], 200.0, "Total boilers aggregation incorrect")

                # Total Heating Electricity Plant = HW Pump
                self.assertEqual(
                    df["Total Heating Electricity Plant"].iloc[0], 25.0, "Total heating electricity plant aggregation incorrect"
                )

                # Total Heating Natural Gas Plant = Boilers
                self.assertEqual(
                    df["Total Heating Natural Gas Plant"].iloc[0], 200.0, "Total heating natural gas plant aggregation incorrect"
                )

                # ETS Pump Electricity Total = ambient pump + CHW pump + HHW pump
                expected_ets_pump = 8.0 + 6.0 + 7.0
                self.assertEqual(
                    df["ETS Pump Electricity Total"].iloc[0], expected_ets_pump, "ETS pump electricity total aggregation incorrect"
                )

                # ETS Heat Pump Electricity Total
                self.assertEqual(
                    df["ETS Heat Pump Electricity Total"].iloc[0], 30.0, "ETS heat pump electricity total aggregation incorrect"
                )

                # Total DES Electricity = ETS Pumps + Heat Pumps + Sewer + GHX + Distribution + Cooling Plant + Heating Plant Electricity
                expected_des_elec = 10.0 + 5.0 + 5.0 + expected_cooling_plant + 25.0
                self.assertAlmostEqual(
                    df["Total DES Electricity"].iloc[0], expected_des_elec, places=2, msg="Total DES electricity aggregation incorrect"
                )

                # Total DES Natural Gas = Total Heating Natural Gas Plant
                self.assertEqual(df["Total DES Natural Gas"].iloc[0], 200.0, "Total DES natural gas aggregation incorrect")

                # Thermal energy aggregations
                self.assertEqual(df["Total Thermal Cooling Energy"].iloc[0], -500.0, "Total thermal cooling energy aggregation incorrect")
                self.assertEqual(df["Total Thermal Heating Energy"].iloc[0], 600.0, "Total thermal heating energy aggregation incorrect")

            finally:
                # Cleanup
                if mock_file.exists():
                    mock_file.unlink()

    def test_multiple_buildings_aggregation(self):
        """Test aggregation with multiple buildings"""
        n_hours = 12

        mock_data = {
            "nBui": 2,
            "ETot.y": [300.0] * n_hours,
            # Plant pumps
            "pla.PPum": [10.0] * n_hours,
            "pumSto.P": [5.0] * n_hours,
            "pumDis.P": [5.0] * n_hours,
            # Cooling plant
            "cooPla_test.mulChiSys.P": [100.0] * n_hours,
            "cooPla_test.pumCW.P[1]": [10.0] * n_hours,
            "cooPla_test.pumCHW.P[1]": [10.0] * n_hours,
            "cooPla_test.cooTowWitByp.PFan[1]": [5.0] * n_hours,
            # Heating plant
            "heaPla_test.boiHotWat.boi[1].QFue_flow": [200.0] * n_hours,
            "heaPla_test.pumHW.P[1]": [15.0] * n_hours,
            # Building 1 ETS
            "PHeaPump.u[1]": [20.0] * n_hours,
            "PPumETS.u[1]": [5.0] * n_hours,
            "TimeSerLoa_bldg1.disFloCoo.PPum": [3.0] * n_hours,
            "TimeSerLoa_bldg1.disFloHea.PPum": [4.0] * n_hours,
            "bui[1].QCoo_flow": [-300.0] * n_hours,
            "bui[1].QHea_flow": [400.0] * n_hours,
            # Building 2 ETS
            "PHeaPump.u[2]": [25.0] * n_hours,
            "PPumETS.u[2]": [6.0] * n_hours,
            "TimeSerLoa_bldg2.disFloCoo.PPum": [3.5] * n_hours,
            "TimeSerLoa_bldg2.disFloHea.PPum": [4.5] * n_hours,
            "bui[2].QCoo_flow": [-350.0] * n_hours,
            "bui[2].QHea_flow": [450.0] * n_hours,
        }

        with patch("urbanopt_des.modelica_results.Reader") as mock_reader_class:
            mock_reader_instance = MockModelicaReader(mock_data)
            mock_reader_class.return_value = mock_reader_instance

            mock_file = self.output_dir / "mock_test_multi.mat"
            mock_file.touch()

            try:
                results = ModelicaResults(mock_file, self.output_dir)
                results.modelica_data = mock_reader_instance

                results.resample_and_convert_to_df(building_ids=["bldg1", "bldg2"], year_of_data=2017)

                df = results.min_60

                # Verify building-specific values
                self.assertEqual(df["ETS Heat Pump Electricity Building bldg1"].iloc[0], 20.0)
                self.assertEqual(df["ETS Heat Pump Electricity Building bldg2"].iloc[0], 25.0)

                # Verify aggregations across buildings
                # Total ETS Heat Pump = sum of both buildings
                expected_total_hp = 20.0 + 25.0
                self.assertEqual(
                    df["ETS Heat Pump Electricity Total"].iloc[0],
                    expected_total_hp,
                    "Total heat pump electricity should sum both buildings",
                )

                # Total ETS Pump = sum of all pumps from both buildings
                expected_total_pump = (5.0 + 3.0 + 4.0) + (6.0 + 3.5 + 4.5)
                self.assertEqual(
                    df["ETS Pump Electricity Total"].iloc[0],
                    expected_total_pump,
                    "Total pump electricity should sum all pumps from both buildings",
                )

                # Total Thermal Cooling = sum of both buildings
                expected_cooling = -300.0 + -350.0
                self.assertEqual(
                    df["Total Thermal Cooling Energy"].iloc[0], expected_cooling, "Total thermal cooling should sum both buildings"
                )

                # Total Thermal Heating = sum of both buildings
                expected_heating = 400.0 + 450.0
                self.assertEqual(
                    df["Total Thermal Heating Energy"].iloc[0], expected_heating, "Total thermal heating should sum both buildings"
                )

            finally:
                if mock_file.exists():
                    mock_file.unlink()

    def test_fallback_to_bui_pattern(self):
        """Test that the method falls back to bui[n].bui.disFloCoo.PPum pattern when TimeSerLoa pattern doesn't exist."""
        n_hours = 12

        mock_data = {
            "nBui": 1,
            "ETot.y": [100.0] * n_hours,
            # Plant pumps
            "pla.PPum": [10.0] * n_hours,
            "pumSto.P": [5.0] * n_hours,
            "pumDis.P": [5.0] * n_hours,
            # Cooling plant
            "cooPla_test.mulChiSys.P": [50.0] * n_hours,
            "cooPla_test.pumCW.P[1]": [5.0] * n_hours,
            "cooPla_test.pumCHW.P[1]": [5.0] * n_hours,
            "cooPla_test.cooTowWitByp.PFan[1]": [5.0] * n_hours,
            # Heating plant
            "heaPla_test.boiHotWat.boi[1].QFue_flow": [100.0] * n_hours,
            "heaPla_test.pumHW.P[1]": [10.0] * n_hours,
            # Building ETS - using bui pattern instead of TimeSerLoa
            "PHeaPump.u[1]": [15.0] * n_hours,
            "PPumETS.u[1]": [4.0] * n_hours,
            "bui[1].bui.disFloCoo.PPum": [2.5] * n_hours,  # Using bui pattern
            "bui[1].bui.disFloHea.PPum": [3.5] * n_hours,  # Using bui pattern
            "bui[1].QCoo_flow": [-200.0] * n_hours,
            "bui[1].QHea_flow": [300.0] * n_hours,
        }

        with patch("urbanopt_des.modelica_results.Reader") as mock_reader_class:
            mock_reader_instance = MockModelicaReader(mock_data)
            mock_reader_class.return_value = mock_reader_instance

            mock_file = self.output_dir / "mock_test_fallback.mat"
            mock_file.touch()

            try:
                results = ModelicaResults(mock_file, self.output_dir)
                results.modelica_data = mock_reader_instance

                results.resample_and_convert_to_df(building_ids=["bldg1"], year_of_data=2017)

                df = results.min_60

                # Verify that the bui pattern values were retrieved correctly
                self.assertEqual(df["ETS Pump CHW Electricity Building bldg1"].iloc[0], 2.5, "Should retrieve CHW pump from bui pattern")
                self.assertEqual(df["ETS Pump HHW Electricity Building bldg1"].iloc[0], 3.5, "Should retrieve HHW pump from bui pattern")

                # Verify aggregation
                expected_total_pump = 4.0 + 2.5 + 3.5
                self.assertEqual(
                    df["ETS Pump Electricity Total"].iloc[0],
                    expected_total_pump,
                    "Total pump electricity should sum correctly with bui pattern",
                )

            finally:
                if mock_file.exists():
                    mock_file.unlink()


if __name__ == "__main__":
    unittest.main()
