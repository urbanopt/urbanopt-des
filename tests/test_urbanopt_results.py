import shutil
import unittest
import warnings
from pathlib import Path

from urbanopt_des.urbanopt_analysis import URBANoptAnalysis
from urbanopt_des.urbanopt_geojson import DESGeoJSON as URBANoptGeoJSON

# suppress some warnings -- mostly from pandas
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.simplefilter(action="ignore", category=FutureWarning)


class UrbanOptResultsTest(unittest.TestCase):
    """Test that end use energy rows have the correct color mappings."""

    def setUp(self):
        """Set up the test by running the post-processing script."""
        self.data_dir = Path(__file__).parent / "data" / "three_building_5G"

        # if the three_building_test output directory exists then delete it
        if (self.data_dir / "three_building_test" / "output").exists():
            shutil.rmtree(self.data_dir / "three_building_test" / "output")

        # delete the modelica_variables.json in any subfolder
        for path in (self.data_dir / "three_building_test_des_agg").rglob("modelica_variables.json"):
            if path.is_file():
                path.unlink()

        # Run the post-processing to generate the data
        modelica_results, _ = URBANoptAnalysis.get_list_of_valid_result_folders(self.data_dir / "three_building_test_des_agg")

        uo_geojson_filename = self.data_dir / "three_building_test" / "FLXenabler.json"
        uo_des_analysis_dir = self.data_dir / "three_building_test_des_agg"
        uo_analysis_baseline_dir = self.data_dir / "three_building_test"
        uo_analysis_baseline_scenario_name = "baseline"
        self.uo_analysis = URBANoptAnalysis(uo_geojson_filename, uo_des_analysis_dir, 2017)

        self.uo_analysis.add_urbanopt_results(uo_analysis_baseline_dir, uo_analysis_baseline_scenario_name)

        # Process the building load measure reports
        self.uo_analysis.urbanopt.process_load_results(self.uo_analysis.geojson.get_building_ids())
        self.uo_analysis.urbanopt.create_aggregations(self.uo_analysis.geojson.get_building_ids())

        self.uo_analysis.urbanopt.save_dataframes()
        self.uo_analysis.urbanopt.display_name = "Non-Connected"

        # add the analysis from the results search
        for key, value in modelica_results.items():
            self.uo_analysis.add_modelica_results(value["name"], value["mat_path"])
            self.uo_analysis.modelica[key].display_name = key.title().replace("_", " ").replace("Des", "DES")
            self.uo_analysis.modelica[key].save_variables()

        # this test has an aggregation of the modelica results
        geojson_agg = URBANoptGeoJSON(self.data_dir / "three_building_test_des_agg" / "FLXenabler.json", skip_validation=True)

        other_vars_to_gather = [
            "borFie.Q_flow",
        ]
        self.uo_analysis.resample_and_convert_modelica_results(geojson_agg.get_building_ids(), other_vars_to_gather)
        self.uo_analysis.save_modelica_variables()

        self.uo_analysis.save_urbanopt_results_in_modelica_paths()
        self.uo_analysis.combine_modelica_and_openstudio_results()

        self.uo_analysis.resample_actual_data()

        # aggregations across columns
        self.uo_analysis.create_modelica_aggregations()

        # run carbon calculations
        self.uo_analysis.calculate_carbon_emissions("RFCE", 2024, analysis_year=2017, emissions_type="marginal", with_td_losses=True)
        self.uo_analysis.calculate_carbon_emissions("RFCE", 2045, analysis_year=2017, emissions_type="marginal", with_td_losses=True)

        # now roll up to combine rows to monthly, annual, etc.
        self.uo_analysis.create_rollups()

        # create the building summary table for URBANopt and each Modelica analysis
        self.uo_analysis.create_building_summaries()

        # save the resulting dataframes
        self.uo_analysis.save_dataframes()

        self.uo_analysis.calculate_all_grid_metrics()

        # save the dataframes, grid metrics only
        self.uo_analysis.save_dataframes(["grid_metrics_daily", "grid_metrics_annual"])

        self.uo_analysis.create_summary_results()

        self.uo_analysis.save_dataframes(["grid_summary", "end_use_summary"])

    def test_energy_end_use_exist_in_urbanopt(self):
        """Test that the energy_end_use_rows dictionary has the correct structure and colors."""
        # Expected energy end use rows with their color mappings
        expected_energy_end_use_rows = {
            "Interior Lighting": "#FFFFCC",
            "Exterior Lighting": "lightblue",
            "Plug Loads": "brown",
            "Building Cooling": "blue",
            "District Cooling": "blue",
            "District Heating": "orange",
            "Building Heating": "orange",
            "Building Fans": "lightgray",
            "Building Pumps": "lightblue",
            "Building Heat Rejection": "royalblue",
            "Building Water Systems": "#FFBB78",
            "ETS Pump Total": "lightgreen",
            "ETS Heat Pump": "gold",
            "Sewer Pump": "darkgray",
            "GHX Pump": "darkgreen",
            "Distribution Pump": "darkblue",
        }.keys()

        # Verify that the expected keys exist in the end_use_summary
        end_use_summary = self.uo_analysis.end_use_summary
        self.assertIsNotNone(end_use_summary, "end_use_summary should not be None")

        # Get the list of display names from the end_use_summary_dict
        display_names = [item["display_name"] for item in self.uo_analysis.urbanopt.end_use_summary_dict]

        # Check that all expected end use categories are present in the display names
        for end_use_name in expected_energy_end_use_rows:
            self.assertIn(
                end_use_name,
                display_names,
                f"'{end_use_name}' should be present in the end use summary display names",
            )

        # Check that the end_use_summary index contains the expected end use names
        for end_use_name in expected_energy_end_use_rows:
            self.assertIn(
                end_use_name,
                end_use_summary.index,
                f"'{end_use_name}' should be present in the end use summary index",
            )

    def test_energy_end_use_exist_in_modelica_results(self):
        """Test that the energy end use variables also exist in the modelica results."""
        # Expected energy end use rows
        expected_energy_end_use_rows = {
            "Interior Lighting": "#FFFFCC",
            "Exterior Lighting": "lightblue",
            "Plug Loads": "brown",
            "Building Cooling": "blue",
            "District Cooling": "blue",
            "District Heating": "orange",
            "Building Heating": "orange",
            "Building Fans": "lightgray",
            "Building Pumps": "lightblue",
            "Building Heat Rejection": "royalblue",
            "Building Water Systems": "#FFBB78",
            "ETS Pump Total": "lightgreen",
            "ETS Heat Pump": "gold",
            "Sewer Pump": "darkgray",
            "GHX Pump": "darkgreen",
            "Distribution Pump": "darkblue",
        }.keys()

        # Verify that modelica results exist
        self.assertGreater(len(self.uo_analysis.modelica), 0, "Should have at least one modelica result")

        # Get the first modelica result
        modelica_key = next(iter(self.uo_analysis.modelica.keys()))
        modelica_result = self.uo_analysis.modelica[modelica_key]

        # Get the list of display names from the modelica end_use_summary_dict
        modelica_display_names = [item["display_name"] for item in modelica_result.end_use_summary_dict]

        # Check that all expected end use categories are present in the modelica display names
        for end_use_name in expected_energy_end_use_rows:
            self.assertIn(
                end_use_name,
                modelica_display_names,
                f"'{end_use_name}' should be present in the modelica end use summary display names",
            )

        # Check that the modelica end_use_summary index contains the expected end use names
        modelica_end_use_summary = modelica_result.end_use_summary
        self.assertIsNotNone(modelica_end_use_summary, "modelica end_use_summary should not be None")

        for end_use_name in expected_energy_end_use_rows:
            self.assertIn(
                end_use_name,
                modelica_end_use_summary.index,
                f"'{end_use_name}' should be present in the modelica end use summary index",
            )
