import shutil
import unittest
from pathlib import Path

from urbanopt_des.urbanopt_analysis import URBANoptAnalysis
from urbanopt_des.urbanopt_geojson import DESGeoJSON as URBANoptGeoJSON


class UrbanoptDesResultsTest(unittest.TestCase):
    # More comprehensive test with 3 buildings and a 5G district energy system.
    # This file requires the OpenStudio/EnergyPlus results
    # for each building to be present in the tests/data/three_building_5G directory.
    def setUp(self):
        self.data_dir = Path(__file__).parent / "data" / "three_building_5G"

        # if the three"building_test output directory exists then delete it
        if (self.data_dir / "three_building_test" / "output").exists():
            shutil.rmtree(self.data_dir / "three_building_test" / "output")

        # delete the modelica_variables.json in any subfolder
        for path in (self.data_dir / "three_building_test_des_agg").rglob("modelica_variables.json"):
            if path.is_file():
                path.unlink()

    def test_valid_results(self):
        """Test the modelica results"""
        modelica_results, bad_or_empty_results = URBANoptAnalysis.get_list_of_valid_result_folders(
            self.data_dir / "three_building_test_des_agg"
        )

        self.assertEqual(len(modelica_results), 1)
        modelica_key = "five_g_controlled_flow.Districts.DistrictEnergySystem_results"
        # verify that the mat_path is a real file and exists
        self.assertTrue(modelica_results[modelica_key]["mat_path"].is_file())
        self.assertTrue(modelica_results[modelica_key]["mat_path"].exists())

        # Check that the no_results error shows up in the bad_or_empty_results
        no_results_folder = self.data_dir / "three_building_test_des_agg" / "no_results"
        self.assertEqual(bad_or_empty_results[no_results_folder]["name"], "no_results")
        self.assertEqual(bad_or_empty_results[no_results_folder]["error"], "No result .mat file in root directory")

    def test_post_process_data(self):
        """Test the post processing of the data"""
        modelica_results, _ = URBANoptAnalysis.get_list_of_valid_result_folders(self.data_dir / "three_building_test_des_agg")

        uo_geojson_filename = self.data_dir / "three_building_test" / "FLXenabler.json"
        uo_des_analysis_dir = self.data_dir / "three_building_test_des_agg"
        uo_analysis_baseline_dir = self.data_dir / "three_building_test"
        uo_analysis_baseline_scenario_name = "baseline"
        uo_analysis = URBANoptAnalysis(uo_geojson_filename, uo_des_analysis_dir, 2017)

        uo_analysis.add_urbanopt_results(uo_analysis_baseline_dir, uo_analysis_baseline_scenario_name)
        self.assertTrue(uo_analysis.urbanopt.data is not None)  # verify that uo data exists
        self.assertEqual(uo_analysis.geojson.get_building_ids(), ["11", "14", "26"])

        # Process the building load measure reports
        uo_analysis.urbanopt.process_load_results(uo_analysis.geojson.get_building_ids())
        uo_analysis.urbanopt.create_aggregations(uo_analysis.geojson.get_building_ids())

        uo_analysis.urbanopt.save_dataframes()  # save the URBANopt dataframes
        self.assertTrue((self.data_dir / "three_building_test" / "output" / "loads_15min.csv").exists())
        self.assertTrue((self.data_dir / "three_building_test" / "output" / "loads_60min.csv").exists())
        self.assertTrue((self.data_dir / "three_building_test" / "output" / "power_15min.csv").exists())
        self.assertTrue((self.data_dir / "three_building_test" / "output" / "power_60min.csv").exists())
        uo_analysis.urbanopt.display_name = "Non-Connected"

        # add the analysis from the results search -- should only be one in this case
        for key, value in modelica_results.items():
            uo_analysis.add_modelica_results(value["name"], value["mat_path"])
            # maybe need to be smarter with display names.
            uo_analysis.modelica[key].display_name = key.title().replace("_", " ").replace("Des", "DES")
            # save the variables from the modelica results
            uo_analysis.modelica[key].save_variables()

        # get the names of the modelica results
        modelica_key = next(iter(uo_analysis.modelica.keys()))
        self.assertTrue(modelica_key is not None)
        # check if the variables were saved
        results_path = self.data_dir / "three_building_test_des_agg" / "five_g_controlled_flow" / modelica_key
        self.assertTrue((results_path / "modelica_variables.json").exists())

        # this test has an aggregation of the modelica results, so one building which lives in a
        # different geojson file (in the agg directory).
        geojson_agg = URBANoptGeoJSON(self.data_dir / "three_building_test_des_agg" / "FLXenabler.json", skip_validation=True)

        other_vars_to_gather = [
            "borFie.Q_flow",
        ]
        uo_analysis.resample_and_convert_modelica_results(geojson_agg.get_building_ids(), other_vars_to_gather)
        # call this again, which is just a wrapper to save for each modelica result.
        uo_analysis.save_modelica_variables()

        uo_analysis.save_urbanopt_results_in_modelica_paths()
        uo_analysis.combine_modelica_and_openstudio_results()

        uo_analysis.resample_actual_data()

        # save the combined data frames for testing
        uo_analysis.save_dataframes("min_60_with_buildings")

        # aggregations across columns
        uo_analysis.create_modelica_aggregations()

        # run carbon calculations on the aggregations -
        #       **** length of data are not matching up... skipping for now. ***
        # uo_analysis.calculate_carbon_emissions("RFCE", 2024, analysis_year=2017, emissions_type="marginal", with_td_losses=True)
        # uo_analysis.calculate_carbon_emissions("RFCE", 2045, analysis_year=2017, emissions_type="marginal", with_td_losses=True)

        # now roll up to combine rows to monthly, annual, etc.
        uo_analysis.create_rollups()

        # create the building summary table for URBANopt and each Modelica analysis
        uo_analysis.create_building_summaries()

        # save the resulting dataframes, which now includes carbon metrics
        uo_analysis.save_dataframes()

        uo_analysis.calculate_all_grid_metrics()

        # save the dataframes, grid metrics only
        uo_analysis.save_dataframes(["grid_metrics_daily", "grid_metrics_annual"])

        uo_analysis.create_summary_results()

        uo_analysis.save_dataframes(["grid_summary", "end_use_summary"])

        buildings_df = uo_analysis.create_building_level_results()
        buildings_df.to_csv(uo_analysis.urbanopt.scenario_output_path / "building_metrics_annual.csv", index=True)
