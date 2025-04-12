# helpers to build an analysis
import copy
import datetime
import json
import math
from pathlib import Path

import pandas as pd

from .emissions import HourlyEmissionsData
from .modelica_results import ModelicaResults
from .urbanopt_geojson import DESGeoJSON
from .urbanopt_results import URBANoptResults


class URBANoptAnalysis:
    def __init__(self, geojson_file: Path, analysis_dir: Path, year_of_data: int = 2017, **kwargs) -> None:
        """Class to hold contents from a comprehensive UO analysis. The analysis can
        include contents from both URBANopt (OpenStudio/EnergyPlus) and URBANopt
        DES (Modelica).

        This class is unique as it handles multiple Modelica based results to be
        analyzed that are derived from a single URBANopt project. Since Modelica
        does not model the end uses of buildings, those values are loaded from
        OpenStudio and stored alongside each Modelica analysis.

        Args:
            geojson_file (Path): Path to the GeoJSON feature file
            analysis_dir (Path): Path to the analysis directory where the combined results will be stored.
            year_of_data (int, optional): year to use for the data. Defaults to 2017.

        Raises:
            Exception: File does not exist
        """
        self.geojson_file = geojson_file
        if geojson_file.exists():
            self.geojson = DESGeoJSON(geojson_file, **kwargs)
        else:
            raise Exception(f"GeoJSON file does not exist: {geojson_file}")

        self.analysis_dir = analysis_dir
        self.analysis_output_dir = analysis_dir / "_results_summary"
        if not self.analysis_output_dir.exists():
            self.analysis_output_dir.mkdir(parents=True)

        # High level info about the analysis that is common across all the
        # results
        self.year_of_data = year_of_data
        # This is the number of buildings in the GeoJSON file
        self.number_of_buildings = len(self.geojson.get_building_ids())

        # Container for URBANopt results
        # TODO: make this a list in the future to hold multiple URBANopt results
        self.urbanopt = None

        # Container for Modelica results
        self.modelica: dict[str, ModelicaResults] = {}

        # dataframe to summarize the grid metrics summary
        self.grid_summary = None
        self.end_use_summary = None

        # Dataframes of the actual meter data
        self.actual_data = None
        self.actual_data_monthly = None
        self.actual_data_yearly = None

    def display_name_mappings(self) -> dict:
        """Return the list of analysis names to display names"""
        display_names = {}
        for key, value in self.modelica.items():
            display_names[key] = value.display_name
        # add in the urbanopt results
        display_names["urbanopt"] = self.urbanopt.display_name
        # add in 'openstudio' as it is used in the grid summaries
        display_names["OpenStudio"] = self.urbanopt.display_name
        # add in 'Individual' as it is used in the end use summaries
        display_names["Individual"] = self.urbanopt.display_name

        display_names["Non-Connected"] = self.urbanopt.display_name

        # add in the 'Actual' data
        display_names["Metered"] = "Metered"

        return display_names

    def retrieve_scaling_factors(self, df_scaling, year, building_id):
        """From the scaling dataframe, return a dict of the start, end, and factor for each meter type.

        Needs to return list of [
            {'electricity_start_time': start_time, 'electricity_end_time': end_time, 'electricity_scaling_factor': scaling_factor},
            {'electricity_start_time': start_time, 'electricity_end_time': end_time, 'electricity_scaling_factor': scaling_factor},
            ...
            {'natural_gas_start_time': start_time, 'natural_gas_end_time': end_time, 'natural_gas_scaling_factor': scaling_factor}
        ]
        """
        # make sure to operate on a copy of the dataframe
        df_scaling = df_scaling.copy()

        scaling_factors = {
            "heating": [],
            "cooling": [],
            "variables": {},
            "raw": [],
        }

        # collect some statistics about the meter readings to inform which are heating and cooling variables
        filter = (df_scaling["building_id"] == building_id) & (df_scaling.index.year == year)
        ng_filter = df_scaling["meter_type"] == "Natural Gas"
        el_filter = df_scaling["meter_type"] == "Electric - Grid"
        number_of_meters = len(df_scaling[df_scaling["building_id"] == building_id]["meter_type"].unique())
        if number_of_meters == 1:
            # then just heating, so the scaling should apply to both heating and cooling
            fields = ["end_time", "scaling_factor_electricity"]
            scaling_factors["heating"] += df_scaling[filter & el_filter][fields].reset_index().to_dict("records", index=True)
            for item in scaling_factors["heating"]:
                item["scaling_factor"] = item.pop("scaling_factor_electricity")
            scaling_factors["cooling"] += df_scaling[filter & el_filter][fields].reset_index().to_dict("records", index=True)
            for item in scaling_factors["cooling"]:
                item["scaling_factor"] = item.pop("scaling_factor_electricity")

            # set the variables to the be max scaling factor
            scaling_factors["variables"]["Peak space cooling load"] = df_scaling[filter & el_filter]["scaling_factor_electricity"].max()
            scaling_factors["variables"]["Peak space heating load"] = df_scaling[filter & el_filter]["scaling_factor_electricity"].max()
        elif number_of_meters == 2:
            # exclude zero values in the calculation
            zero_filter = df_scaling["converted_value"] != 0

            min_ng_non_zero = df_scaling[filter & zero_filter & (df_scaling["meter_type"] == "Natural Gas")]["converted_value"].min()
            max_ng_non_zero = df_scaling[filter & zero_filter & (df_scaling["meter_type"] == "Natural Gas")]["converted_value"].max()
            ng_pvr = max_ng_non_zero / min_ng_non_zero
            # max_ng = df_scaling[filter & (df_scaling['meter_type'] == 'Natural Gas')]['converted_value'].max()
            # max_el = df_scaling[filter & (df_scaling['meter_type'] == 'Electric - Grid')]['converted_value'].max()
            # ratio = max_ng / max_el

            # print(f"Building {building_id} has a ratio of max natural gas to electricity is {ratio} and a peak to value of {ng_pvr}")
            # fields = ['end_time', 'scaling_factor_natural_gas']
            # sf_ng = df_scaling[filter & ng_filter][fields].reset_index().to_dict('records', index=True)
            # just get a list of the scaling_factor_natural_gas
            # sf_ng_list = [x['scaling_factor_natural_gas'] for x in sf_ng]
            # fields = ['end_time', 'scaling_factor_electricity']
            # sf_el = df_scaling[filter & el_filter][fields].reset_index().to_dict('records', index=True)
            # sf_el_list = [x['scaling_factor_electricity'] for x in sf_el]

            if ng_pvr > 1.5:
                # if the peak to valley ration of the natural gas is high, then assume that it has an impact on the heating load only
                fields = ["end_time", "scaling_factor_natural_gas"]
                scaling_factors["heating"] += df_scaling[filter & ng_filter][fields].reset_index().to_dict("records", index=True)
                for item in scaling_factors["heating"]:
                    item["scaling_factor"] = item.pop("scaling_factor_natural_gas")
                scaling_factors["variables"]["Peak space heating load"] = df_scaling[filter & ng_filter]["scaling_factor_natural_gas"].max()
            else:
                # just use the electric load scaling factors for everything
                fields = ["end_time", "scaling_factor_electricity"]
                scaling_factors["heating"] += df_scaling[filter & el_filter][fields].reset_index().to_dict("records", index=True)
                for item in scaling_factors["heating"]:
                    item["scaling_factor"] = item.pop("scaling_factor_electricity")
                scaling_factors["variables"]["Peak space heating load"] = df_scaling[filter & el_filter]["scaling_factor_electricity"].max()

            fields = ["end_time", "scaling_factor_electricity"]
            scaling_factors["cooling"] += df_scaling[filter & el_filter][fields].reset_index().to_dict("records", index=True)
            for item in scaling_factors["cooling"]:
                item["scaling_factor"] = item.pop("scaling_factor_electricity")
            scaling_factors["variables"]["Peak space cooling load"] = df_scaling[filter & el_filter]["scaling_factor_electricity"].max()

            # # plot sf_ng vs sf_el
            # plt.clf()
            # plt.figure(figsize=(6, 6))
            # ax = plt.gca()
            # sns.scatterplot(x=sf_el_list, y=sf_ng_list, ax=ax)
            # plt.show()
        return scaling_factors

    def add_urbanopt_results(self, path_to_urbanopt: Path, scenario_name: str) -> None:
        """Read in the results from all of the URBANopt buildings in OpenStudio
        that have been simulated.

        Args:
            path_to_urbanopt (Path): URBANopt project directory where the feature file and Gemfile are located. Only processes feature file.
            scenario_name (str): Name of the scenario that was run with URBANopt.
        """
        self.urbanopt = URBANoptResults(path_to_urbanopt, scenario_name)
        self.urbanopt.process_results(self.geojson.get_building_ids(), year_of_data=self.year_of_data)

        # note that the number of buildings in the geojson will match here since the file being passed
        # into the process_results method is the geojson file that was used to run the analysis. So no need
        # to double check (this was a problem before).

    def scale_urbanopt_results(self, path_to_urbanopt: Path) -> None:
        """Go through the buildings in the URBANopt results and scale the values based on the
        scaling factors that are saved in the `output` directory within the UO results.

        The name of the scaling CSV files and format is very specific to this method."""
        if not self.urbanopt:
            raise Exception("URBANopt results are not loaded, run `add_urbanopt_results` method")

        for building_id in self.geojson.get_building_ids():
            # retrieve the scaling factors, fixed at electric_grid and natural_gas
            for meter_type in ["electric_grid", "natural_gas"]:
                filepath = path_to_urbanopt / "output"
                filepath = filepath / f"building_{building_id}_scaling_factors_{meter_type}.csv"

                if filepath.exists():
                    # load into a data frame, and load only the columns that
                    # we care about, start_time, end_time, scaling...
                    df_scalars = pd.read_csv(
                        filepath,
                        usecols=[
                            "start_time",
                            "end_time",
                            "building_id",
                            "meter_type",
                            "scaling_factor_electricity",
                            "scaling_factor_natural_gas",
                        ],
                    )
                    # set start_time and end time to be datetime objects
                    df_scalars["start_time"] = pd.to_datetime(df_scalars["start_time"])
                    # add midnight to the start_time
                    df_scalars["start_time"] = df_scalars["start_time"].apply(lambda x: x.replace(hour=0, minute=0, second=0))
                    df_scalars["end_time"] = pd.to_datetime(df_scalars["end_time"])
                    df_scalars = df_scalars.reset_index()

                    self.urbanopt.scale_results(df_scalars, self.year_of_data, 2021)

    def add_modelica_results(self, analysis_name: str, path_to_mat_file: Path) -> None:
        """Read in the results from the modelica analysis into a dict of dicts. There can be more than
        one modelica results per URBANoptAnalysis instance since the modelica results are not tied to the
        URBANopt buildings.

        The Modelica results contain the .mat file which get converted into a set of down sampled
        data frames (5 min, 15 min, 60 min, monthly, yearly), for each analysis_name.

        Args:
            analysis_name (str): Name of the analysis, ideally lower snake case for ease of access.
            path_to_mat_file (Path): Path of the .mat file that was generated from the Modelica analysis.
        """
        self.modelica[analysis_name] = ModelicaResults(path_to_mat_file)

        print(f"Modelica analysis name {self.modelica[analysis_name].display_name}")

    def sort_modelica_results_order(self, analysis_names: list[str]) -> None:
        """Sort the modelica results in the order of the analysis_names"""
        # create a new dict with the analysis_names in the order of the list
        new_dict: dict[str, ModelicaResults] = {}
        for analysis_name in analysis_names:
            new_dict[analysis_name] = self.modelica[analysis_name]

        self.modelica = new_dict

    def save_urbanopt_results_in_modelica_paths(self):
        """Iterate through each of the modelica result paths and save a copy of the URBANopt OpenStudio data frames into
        the path."""
        for analysis_name in self.modelica:
            self.urbanopt.data.to_csv(self.modelica[analysis_name].path / "openstudio_df.csv")

    def combine_modelica_and_openstudio_results(self) -> None:
        """Combine the modelica and openstudio results into a single data frame for each analysis_name"""
        for analysis_name in self.modelica:
            self.modelica[analysis_name].combine_with_openstudio_results(
                self.geojson.get_building_ids(),
                self.urbanopt.data,
                self.urbanopt.data_15min,
            )

    def resample_actual_data(self) -> None:
        """Convert the GeoJSON meters to the monthly and annual dataframes. Note that the monthly dataframe does not
        do any calendarization at the moment. It is strictly the aggregation of the meter readings based on the start
        time index"""
        # Reset the actual dataframes
        self.actual_data = None
        self.actual_data_monthly = None
        self.actual_data_yearly = None

        for building_id in self.geojson.get_building_ids():
            meters = self.geojson.get_meters_for_building(building_id)
            for meter in meters:
                meter_readings = self.geojson.get_meter_readings_for_building(building_id, meter)
                # add the meter_type to all the json objects
                [meter_reading.update({"meter_type": meter, "building_id": building_id}) for meter_reading in meter_readings]
                # print(f"Found {len(meter_readings)} meter readings")

                # save the readings into a dataframe with end_time as the index
                self.actual_data = pd.concat([self.actual_data, pd.DataFrame(meter_readings)])

        if self.actual_data is not None:
            self.actual_data["start_time"] = pd.to_datetime(self.actual_data["start_time"])
            self.actual_data["start_time"] = self.actual_data["start_time"].apply(lambda x: x.replace(tzinfo=None))
            self.actual_data["end_time"] = pd.to_datetime(self.actual_data["end_time"])
            self.actual_data["end_time"] = self.actual_data["end_time"].apply(lambda x: x.replace(tzinfo=None))
            # check if there is a time on the end_time and if not make it 23:59:59
            self.actual_data["end_time"] = self.actual_data["end_time"].apply(lambda x: x.replace(hour=23, minute=59, second=59))
            self.actual_data = self.actual_data.set_index(["start_time"])

            # monthly agg across each building_id, meter_type (and other non-important fields)
            groupby_cols = [
                "meter_type",
                "building_id",
                "source_unit",
                "conversion_factor",
                "units",
                "converted_units",
            ]
            drop_cols = ["end_time", "id"]
            # drop the columns first, then run the groupby
            self.actual_data_monthly = self.actual_data.drop(columns=drop_cols).groupby([pd.Grouper(freq="ME"), *groupby_cols]).sum()
            self.actual_data_monthly.reset_index()
            self.actual_data_monthly.set_index(["start_time"])
            self.actual_data_yearly = self.actual_data.drop(columns=drop_cols).groupby([pd.Grouper(freq="Y"), *groupby_cols]).sum()
            self.actual_data_yearly.reset_index()
            self.actual_data_yearly.set_index(["start_time"])

            # for each building, create a new row with the building_id and new meter called 'total' which has the
            # converted_value for all the meters for that building summed together
            groupby_cols = [
                "start_time",
                "building_id",
                "source_unit",
                "conversion_factor",
                "units",
                "converted_units",
            ]
            new_data = self.actual_data_monthly.groupby(groupby_cols).sum()
            new_data.reset_index()
            new_data.set_index(["start_time"])
            new_data["meter_type"] = "Total"
            self.new_data = new_data
            # add the new_data rows to the existing self.actual_monthly dataframe, mapping the common columns
            self.actual_data_monthly = pd.concat([self.actual_data_monthly, new_data])

            # now do the same for the yearly data for the totals
            new_data = self.actual_data_yearly.groupby(groupby_cols).sum()
            new_data.reset_index()
            new_data.set_index(["start_time"])
            new_data["meter_type"] = "Total"
            self.new_data = new_data
            # add the new_data rows to the existing self.actual_monthly dataframe, mapping the common columns
            self.actual_data_yearly = pd.concat([self.actual_data_yearly, new_data])

    def resample_and_convert_modelica_results(
        self,
        building_ids: list[str] | None = None,
        other_vars: list[str] | None = None,
    ) -> None:
        """Run the resample and convert method for each of the analyses in the modelica object

        Args:
            building_ids (Union[list[str], None], optional): Name of the buildings to process out of the Modelica data. Defaults to None.
            other_vars (Union[list[str], None], optional): Other variables to extract and store in the dataframe. Defaults to None.
            year_of_data (int, optional): Year of the data, should match the URBANopt/OpenStudio/EnergyPlus value and correct starting day of week. Defaults to 2017.

        Raises:
            Exception: errors"""
        for analysis_name in self.modelica:
            self.modelica[analysis_name].resample_and_convert_to_df(building_ids, other_vars, self.year_of_data)

    def create_building_summaries(self) -> None:
        """Create the summary of the results for URBANopt and each modelica simulation. This stores the data on the
        model object. To combine the results, call the `create_building_summaries` method."""
        # create summary of URBANopt
        self.urbanopt.create_summary()

        # create summary for each Modelica result
        for analysis_name in self.modelica:
            self.modelica[analysis_name].create_summary()

    def save_modelica_variables(self) -> None:
        """For each Modelica analysis, save the variables in the location alongside the .mat file"""
        for analysis_name in self.modelica:
            self.modelica[analysis_name].save_variables()

    def save_dataframes(
        self,
        dfs_to_save: list = [
            "min_5",
            "min_15",
            "min_60",
            "min_15_with_buildings",
            "min_60_with_buildings",
            "monthly",
            "annual",
            "end_use_summary",
            "grid_metrics_daily",
            "grid_metrics_annual",
            "grid_summary",
            "end_use_summary",
        ],
    ) -> None:
        """For all of the analyses, save the dataframes. Does NOT save the URBANopt results in the modelica paths."""

        self.urbanopt.save_dataframes()

        for analysis_name in self.modelica:
            self.modelica[analysis_name].save_dataframes(dfs_to_save)

        # save the UO Analysis dataframes, which go into a summary directory
        if self.grid_summary is not None and "grid_summary" in dfs_to_save:
            self.grid_summary.to_csv(self.analysis_output_dir / "grid_summary.csv")
            self.grid_metrics_annual.to_csv(self.analysis_output_dir / "grid_metrics_annual_all.csv")

        if self.end_use_summary is not None and "end_use_summary" in dfs_to_save:
            self.end_use_summary.to_csv(self.analysis_output_dir / "annual_end_use_summary.csv")

    def calculate_carbon_emissions(
        self,
        egrid_subregion: str,
        future_year: int = 2045,
        analysis_year: int = 2017,
        **kwargs,
    ) -> None:
        """Call the Modelica results methods to calculate the carbon emissions. This will create new columns in
        the self.modelica dataframes for carbon emissions for the future_year.

        Uses https://www.epa.gov/egrid/power-profiler#/RFCE and
        https://github.com/NREL/openstudio-common-measures-gem/tree/develop/lib/measures/add_ems_emissions_reporting

        Args:
            egrid_subregion (str): EPA's 4-letter identifier for the emissions subregion.
            future_year (int, optional): Year of the emission data. Defaults to 2045.
            analysis_year (int, optional): Year that the simulation/analysis data is representing, does not have to match future_year. Defaults to 2017.
            kwargs:
                emissions_type (str, optional): Type of emissions to load. Options are 'marginal' and 'average'. Defaults to 'marginal'.
                with_td_losses (bool, optional): Include transmission and distribution losses. Defaults to True.
        """
        emissions_type = kwargs.get("emissions_type", "marginal")
        with_td_losses = kwargs.get("with_td_losses", True)

        # load in the hourly emissions data
        hourly_emissions_data = HourlyEmissionsData(
            egrid_subregion,
            future_year,
            analysis_year=analysis_year,
            emissions_type=emissions_type,
            with_td_losses=with_td_losses,
        )

        # calculate the carbon emission on the URBANopt results
        self.urbanopt.calculate_carbon_emissions(hourly_emissions_data, future_year=future_year)

        # Now for each of the modelica results
        for analysis_name in self.modelica:
            self.modelica[analysis_name].calculate_carbon_emissions(hourly_emissions_data, future_year=future_year)

    def calculate_all_grid_metrics(self) -> None:
        """Call each Modelica analysis to create the grid metric"""
        self.urbanopt.calculate_grid_metrics()

        # skip n-days at the beginning of the grid metrics, due to
        # warm up times that have yet to be resolved.

        for analysis_name in self.modelica:
            self.modelica[analysis_name].calculate_grid_metrics()

    def calculate_utility_cost(self, **kwargs) -> None:
        """Stub for calculating the utility cost at each building and
        aggregated for the entire system.
        """
        # calculate the utility costs

        # create three columns of utility costs, hot water, chilled water, and ambient water
        # 1 ton-hour = 3.5 kWh, 1 ton=3.5kW
        # energy, energy charges, demand charges, transition rate, and taxes
        #   - Demand is based on a building's multiple one-hour peaks from June through September of the previous two 12-month periods.
        # hot water, 0.094 per ton-hour, 30.02 per ton per month, 0.394 per ton-hour, 3.5%

        # get the utility rates for thermal host water and chilled water

        # https://www.eia.gov/electricity/data/eia861m/

    def create_modelica_aggregations(self) -> None:
        """Aggregate the dataframes for each analysis_name and df_15min_with_buildings and
        df_60min_with_buildings. This does not act on the URBANopt results since this method
        must be called after the combine_modelica_and_openstudio_results method."""
        # First check that the data are in the dataframes
        for analysis_name in self.modelica:
            if self.modelica[analysis_name].min_15_with_buildings is None:
                raise Exception("Must call combine_modelica_and_openstudio_results() before calling create_aggregations()")

            if self.modelica[analysis_name].min_60_with_buildings is None:
                raise Exception("Must call combine_modelica_and_openstudio_results() before calling create_aggregations()")

        # try block is here for folding in IDE :)
        # Note that the order of aggregations matter if a new aggregation is dependent on another
        try:
            building_aggs: dict[str, dict] = {
                "Total Building Electricity": {},
                "Total Building Natural Gas": {},
                # Below is a list of values pulled from openstudio, that are
                # used in the calculations here, not new aggregations
                # "Total Building Cooling Electricity": {},
                # "Total Building Heating Electricity": {},
                # "Total Building Heating Natural Gas": {},
                # "Total Building Fans Electricity": {},
                # "Total Building Pumps Electricity": {},
                # "Total Building Heat Rejection Electricity": {},
                # "Total Building Heat Rejection Natural Gas": {},
                # "Total Building Water Systems Natural Gas": {},
                # "Total Building Interior Lighting": {},
                # "Total Building Exterior Lighting": {},
                # "Total Building Interior Equipment Electricity": {},
                # "Total Building Interior Equipment Natural Gas": {},
                # "Total Building Interior Equipment": {},  # electric and gas
                # "Total Building Exterior Equipment Electricity": {},
                # HVAC Aggregations used in OpenStudio/EnergyPlus
                # "Total Building HVAC Electricity": {},
                # "Total Building HVAC Natural Gas": {},
                # "Total Building HVAC Cooling Energy": {},
                # "Total Building HVAC Heating Energy": {},
                # "Total Building HVAC Energy": {},
                # Total by energies
                "Total ETS Electricity": {},
                "Total Building and ETS Energy": {},
                "Total Electricity": {},
                "Total Natural Gas": {},
                "Total Thermal Energy Cooling": {},
                "Total Thermal Energy Heating": {},
                "Total Energy": {},  # not thermal
            }

            # add agg columns for each building
            for key, _ in building_aggs.items():
                building_aggs[key]["agg_columns"] = []

            building_aggs["Total ETS Electricity"]["agg_columns"] = [
                "ETS Pump Electricity Total",
                "ETS Heat Pump Electricity Total",
            ]
            building_aggs["Total Building Electricity"]["agg_columns"] = [
                "Total Building Interior Lighting",
                "Total Building Exterior Lighting",
                "Total Building Interior Equipment Electricity",
                "Total Building Exterior Equipment Electricity",
            ]
            building_aggs["Total Building Natural Gas"]["agg_columns"] = [
                "Total Building Interior Equipment Natural Gas",
            ]
            building_aggs["Total Building and ETS Energy"]["agg_columns"] = [
                "Total Building Electricity",
                "Total ETS Electricity",
            ]
            building_aggs["Total Electricity"]["agg_columns"] = [
                "Total Building and ETS Energy",
                "Total DES Electricity",
            ]
            building_aggs["Total Natural Gas"]["agg_columns"] = ["Total Building Natural Gas"]
            building_aggs["Total Energy"]["agg_columns"] = [
                "Total Electricity",
                "Total Natural Gas",
            ]
            building_aggs["Total Thermal Energy Cooling"]["agg_columns"] = ["Total Thermal Cooling Energy"]
            building_aggs["Total Thermal Energy Heating"]["agg_columns"] = ["Total Thermal Heating Energy"]
        finally:
            pass

        # Do this for each of the analyses' 15 and 60 min dataframes
        for analysis_name in self.modelica:
            for resolution in ["min_15_with_buildings", "min_60_with_buildings"]:
                temp_df = getattr(self.modelica[analysis_name], resolution)

                # Go through each building_aggs and create the aggregation
                for key, value in building_aggs.items():
                    # check to make sure that each of the agg_columns have been defined
                    if not value["agg_columns"]:
                        raise Exception(f"Agg columns for {key} have not been defined")

                    # sum up the columns in the agg_columns defined above for the dataframe of
                    # the analysis
                    temp_df[key] = temp_df[value["agg_columns"]].sum(axis=1)

    def create_rollups(self) -> None:
        """Rollups take the 60 minute data sets and roll up to monthly and annual"""
        # make sure that the data exist in the correct dataframes
        for analysis_name in self.modelica:
            if self.modelica[analysis_name].min_60_with_buildings is None:
                raise Exception(f"Data do not exist in {analysis_name} for min_60_with_buildings.")

        # confirm that URBANopt has the results too
        if self.urbanopt.data is None:
            raise Exception("Data do not exist in URBANopt for min_60_with_buildings.")

        # roll up the urbanopt results (single analysis)
        self.urbanopt.data_monthly = self.urbanopt.data.resample("ME").sum()
        self.urbanopt.data_annual = self.urbanopt.data.resample("YE").sum()
        # loads
        self.urbanopt.data_loads_monthly = self.urbanopt.data_loads.resample("ME").sum()
        self.urbanopt.data_loads_annual = self.urbanopt.data_loads.resample("YE").sum()

        # roll up the Modelica results (each analysis)
        for analysis_name in self.modelica:
            self.modelica[analysis_name].monthly = self.modelica[analysis_name].min_60_with_buildings.resample("ME").sum()
            self.modelica[analysis_name].data_annual = self.modelica[analysis_name].min_60_with_buildings.resample("YE").sum()

    def create_building_level_results(self) -> None:
        """Save off building level totals for mapping for each scenario. The results are
        not stored anywhere and need to be persisted or called again if needed.

        The data will look similar to this and include DES, as that is a "building/property".

        # Metric,Units,Building1,Building2,BuildingN,DES
        # Total Energy, MWh, 100, 200, 300, 600
        # Total Electricity, MWh, x, y, z
        # Total Natural Gas, MWh, x, y, z
        # Gross Floor Area, m2, 1000, 2000, 3000, SUM of all buildings
        # Total Carbon, mtCO2e, 10, 20, 30, 60
        # Building EUI, kWh/m2, 100, 200, 300, 123
        # Building EUI, kBtu/ft2, 100, 200, 300, 123
        # Building Peak Demand, kW, 100, 200, 300, 123
        # Building Peak Demand Time, hr, 12, 13, 14, 13.5
        """
        if self.urbanopt.data_annual is None:
            raise Exception("There are no annual results calculated, did you run create_rollups()")

        # iterate through each building and create the building level results
        data = {
            "property_type": {
                "Metric": "Property Type",
                "Unit": "",
            },
            "building_type": {
                "Metric": "Building Type",
                "Unit": "",
            },
            "total_natural_gas": {
                "Metric": "Total Natural Gas",
                "Unit": "Wh",
            },
            "total_electricity": {
                "Metric": "Total Electricity",
                "Unit": "Wh",
            },
            "total_energy": {
                "Metric": "Total Energy",
                "Unit": "Wh",
            },
            "gross_floor_area": {
                "Metric": "Gross Floor Area",
                "Unit": "m2",
            },
            "gross_floor_area_ft2": {
                "Metric": "Gross Floor Area",
                "Unit": "ft2",
            },
            "total_site_eui": {
                "Metric": "Building EUI",
                "Unit": "kWh/m2",
            },
            "total_site_eui_ft2": {
                "Metric": "Building EUI",
                "Unit": "kBtu/ft2",
            },
        }
        for building_id in self.geojson.get_building_ids():
            geojson_data = self.geojson.get_building_properties_by_id(building_id)

            # assume property type is in "Property Type" and that the modeling type is in "building_type"
            data["property_type"][building_id] = geojson_data.get("Property Type", "Unknown [not in GeoJSON Property Type]")
            data["building_type"][building_id] = geojson_data.get("building_type", "Unknown [not in GeoJSON building_type]")

            data["total_natural_gas"][building_id] = self.urbanopt.data_annual[f"NaturalGas:Facility Building {building_id}"][0]
            data["total_electricity"][building_id] = self.urbanopt.data_annual[f"Electricity:Facility Building {building_id}"][0]
            data["total_energy"][building_id] = data["total_natural_gas"][building_id] + data["total_electricity"][building_id]

            # read the square footage out of the default_feature_report.json
            data["gross_floor_area"][building_id] = (
                self.urbanopt.building_characteristics[building_id]["program"]["floor_area_sqft"] / 10.76
            )
            data["gross_floor_area_ft2"][building_id] = self.urbanopt.building_characteristics[building_id]["program"]["floor_area_sqft"]

            # calculate the EUI
            data["total_site_eui"][building_id] = (data["total_energy"][building_id] * 0.001) / data["gross_floor_area"][building_id]
            data["total_site_eui_ft2"][building_id] = (data["total_energy"][building_id] * 0.00341214) / data["gross_floor_area_ft2"][
                building_id
            ]

        # combine all the data together for the final dataframe. The list comprehension here
        # will create the table that is shown in the docstring above
        return_df = pd.DataFrame([data[key] for key in data])
        # set the index to be the metric and the unit
        return_df.set_index(["Metric", "Unit"])

        return return_df

    def __getitem__(self, key: str) -> ModelicaResults:
        # Accessor to the self.modelica dictionary that takes the key value as in the input
        # and returns the ModelicaResults object
        return self.modelica[key]

    def _find_data_location(self, obj: dict, fields_to_search: list[str]) -> str:
        """Return the first location where the data is found in the fields_to_search list.

        The fields to search is a prioritized list of fields to search for the data. The first field that is found and
        not none will be returned.

        Args:
            obj (dict): dict object to look for the value
            fields_to_search (list[str]): field names to search

        Returns:
            str: name of the field that exists with non-none data
        """
        for field in fields_to_search:
            if field in obj and obj[field] is not None:
                return field

        return None

    def update_geojson_from_seed_data(self, **kwargs) -> dict:
        """Update the GeoJSON contents to be compatible with URBANopt. This step should eventually be
        handled entirely in the SEED interface, but for now, we are manually adding in this information.

        Args:
            kwargs:
                project_name (str): Name of the project, defaults to "SEED DC Block 1"
                weather_filename (str): Name of the weather file, defaults to "USA_VA_Arlington-Ronald.Reagan.Washington.Natl.AP.724050_TMY3.epw"
                site_origin (list): List of the site origin coordinates in [long, lat], defaults to [-77.03896375997412, 38.901950685284746]


        Returns:
            dict: geojson compatible dictionary compatible with URBANopt
        """
        project_name = kwargs.get("project_name", "SEED DC Block 1")
        weather_filename = kwargs.get(
            "weather_filename",
            "USA_VA_Arlington-Ronald.Reagan.Washington.Natl.AP.724050_TMY3.epw",
        )
        site_origin = kwargs.get("site_origin", [-77.03896375997412, 38.901950685284746])

        # Add in the Project information
        project_info = {
            # "id": "fce0aefb-163d-4efe-bcb4-25b886e2dcb8",
            "name": project_name,
            "surface_elevation": 125,  # meters
            "import_surrounding_buildings_as_shading": None,
            "weather_filename": weather_filename,
            "climate_zone": "4A",
            "begin_date": "2017-01-01T07:00:00.000Z",
            "end_date": "2017-12-31T07:00:00.000Z",
            "timesteps_per_hour": 1,
            "default_template": "90.1-2013",
        }

        site_info = {
            "type": "Feature",
            "properties": {
                "name": "Site Origin",
                "type": "Site Origin",
                "cec_climate_zone": None,
                "only_lv_customers": None,
                "underground_cables_ratio": None,
                "max_number_of_lv_nodes_per_building": None,
            },
            "geometry": {"type": "Point", "coordinates": site_origin},
        }

        new_dict = None
        # load the GeoJSON file as a dictionary, NOT an DESGeoJSON object.
        with open(self.geojson_file) as f:
            geojson = json.load(f)
            # insert project dict and move to after the type object
            geojson["project"] = project_info

            # order the keys
            # Skip the
            new_dict = {
                "type": geojson["type"],  # ignore for now since FeatureCollection doesn't validate in URBANopt
                "name": geojson["name"],
                "project": geojson["project"],
                "features": [],
            }

            # 1. Copy the "Property Name" to the "name" key, add the "type" key of "building"
            # 2. Flatten the geometry collection to just the polygon (that is remove the point)
            # 3. Add in an id, which is just the index count of the object
            # 4. Copy over the floor area, since the field name has to be `floor_area`
            # 5. Calculate the number of stories, and take the ceiling (max at 18 for the sake of DC)
            # 6. Select a system type based on the meters that are available
            feature_count = 0
            for index, feature in enumerate(geojson["features"]):
                # skip if it is a taxlot
                if (
                    feature["properties"].get("taxlot_state_id")
                    or feature["properties"].get("taxlot_view_id")
                    or feature["properties"].get("taxlot_state_id")
                ):
                    continue

                # skip if there is no property type defines
                if "Property Type" not in feature["properties"]:
                    print(f"WARNING: No property type for building {index}, skipping.")
                    continue

                feature_count += 1

                # if we are this far, then we will want new_feature
                new_feature = copy.deepcopy(feature)

                # remove the ID if it exists, we will create a new one
                if "ID" in new_feature["properties"]:
                    del new_feature["properties"]["ID"]

                new_feature["properties"]["type"] = "Building"
                # set the property name if it is empty
                if "Property Name" not in new_feature["properties"]:
                    new_feature["properties"]["Property Name"] = f"Building {index}"

                # find locations of the data that might have been exported or mapped from SEED.
                gfa_location = self._find_data_location(
                    new_feature["properties"],
                    [
                        "Gross Floor Area",
                        "Gross Floor Area (ft2)",
                        "gross_floor_area_ft2",
                    ],
                )
                footprint_location = self._find_data_location(
                    new_feature["properties"],
                    [
                        "Footprint Area",
                        "Footprint Area (ft2)",
                        "footprint_area_ft2",
                    ],
                )
                stories_location = self._find_data_location(
                    new_feature["properties"],
                    [
                        "Number of Stories",
                        "Number of Stories Above Grade",
                        "Building Levels",
                        "number_of_stories",
                    ],
                )

                # map to the terms that UO expects
                new_feature["properties"]["name"] = new_feature["properties"]["Property Name"]
                new_feature["properties"]["id"] = f"{feature_count}"

                # process the floor area
                if gfa_location:
                    new_feature["properties"]["floor_area"] = new_feature["properties"][gfa_location]
                else:
                    raise Exception("No GFA found in the data, which is required!")

                # check which column has the footprint area. Look in Footprint Area, then Footprint Area (ft2)
                if footprint_location and stories_location:
                    # print("Found footprint area and number of stories, using those values.")
                    # We know everything about the building areas, so just store the data in the right location
                    new_feature["properties"]["footprint_area"] = new_feature["properties"][footprint_location]
                    new_feature["properties"]["number_of_stories"] = new_feature["properties"][stories_location]
                elif footprint_location and not stories_location:
                    new_feature["properties"]["footprint_area"] = new_feature["properties"][footprint_location]

                    # Calculate the stories by dividing out the GFA by the footprint area
                    number_of_stories = math.ceil(new_feature["properties"]["floor_area"] / new_feature["properties"]["Footprint Area"])
                    if number_of_stories > 18:
                        print(
                            f"WARNING: number of stories ({number_of_stories}) is greater than 18, which is not likely in Washington DC!, setting to 18 for this analysis."
                        )
                        number_of_stories = 18
                    new_feature["properties"]["number_of_stories"] = number_of_stories
                elif not footprint_location and stories_location:
                    new_feature["properties"]["number_of_stories"] = number_of_stories

                    # Calculate the footprint area from the GFA and number of stories
                    new_feature["properties"]["floor_area"] / number_of_stories
                else:
                    print("Unknown footprint area and number of stories, inferring from GFA and 18 stories.")
                    new_feature["properties"]["number_of_stories"] = 18
                    new_feature["properties"]["footprint_area"] = new_feature["properties"]["floor_area"] / number_of_stories

                # Data for residential properties
                new_feature["properties"]["number_of_stories_above_ground"] = new_feature["properties"]["number_of_stories"]
                new_feature["properties"]["foundation_type"] = "slab"
                new_feature["properties"]["attic_type"] = "flat roof"

                # how to infer this?
                new_feature["properties"]["number_of_bedrooms"] = 50
                new_feature["properties"]["number_of_residential_units"] = 18

                if new_feature["properties"].get("Property Type"):
                    # map SEED to UO building type
                    mapping = {
                        "apartments": "Lodging",
                        "Apartments": "Lodging",
                        "Cinema": "Retail other than mall",
                        "Covered Parking": "Covered Parking",
                        "Education": "Education",
                        "Enclosed mall": "Enclosed mall",
                        "fast_food": "Food service",
                        "Food sales": "Food sales",
                        "Food service": "Food service",
                        "Inpatient health care": "Inpatient health care",
                        "K-12": "Education",
                        "K-12 School": "Education",
                        "Laboratory": "Laboratory",
                        "Lodging": "Lodging",
                        "Mixed use": "Mixed use",
                        # "Multifamily": "Multifamily",  # multifamily wasn't working
                        # "Multifamily (2 to 4 units)": "Multifamily (2 to 4 units)",
                        # "Multifamily (5 or more units)": "Multifamily (5 or more units)",
                        "Multifamily Housing": "Lodging",
                        "Nonrefrigerated warehouse": "Nonrefrigerated warehouse",
                        "Nursing": "Nursing",
                        "Office": "Office",
                        "office": "Office",
                        "Other - Education": "Education",
                        "Outpatient health care": "Outpatient health care",
                        "place_of_worship": "Religious worship",
                        "Public assembly": "Public assembly",
                        "Public order and safety": "Public order and safety",
                        "Refrigerated warehouse": "Refrigerated warehouse",
                        "Religious worship": "Religious worship",
                        "retail": "Strip shopping mall",
                        "Retail": "Strip shopping mall",
                        "Retail other than mall": "Retail other than mall",
                        "Service": "Service",
                        "Single-Family": "Single-Family",
                        "Single-Family Detached": "Single-Family Detached",
                        "Strip Mall": "Strip shopping mall",
                        "Strip shopping mall": "Strip shopping mall",
                        "Uncovered Parking": "Uncovered Parking",
                        "Vacant": "Vacant",
                        "Worship Facility": "Religious worship",
                    }
                    lookup_value = new_feature["properties"]["Property Type"]
                    if lookup_value in mapping:
                        new_feature["properties"]["building_type"] = mapping[lookup_value]
                    else:
                        raise Exception(f"No property type mapping for building type: {lookup_value}")

                if new_feature["properties"].get("Year Built"):
                    new_feature["properties"]["year_built"] = new_feature["properties"]["Year Built"]

                if new_feature.get("geometry"):
                    if new_feature.get("geometry").get("type") == "GeometryCollection":
                        # grab the one that is a polygon and save to the new_dict
                        index_geom = next(i for i, x in enumerate(new_feature["geometry"]["geometries"]) if x["type"] == "Polygon")
                        new_feature["geometry"] = new_feature["geometry"]["geometries"][index_geom]
                    elif new_feature.get("geometry").get("type") == "Point":
                        # remove the point
                        del new_feature["geometry"]

                # make sure that a geometry.geometries exists, regardless if it is empty
                if "geometry" not in new_feature:
                    # well, going to have to skip for now
                    print(f"WARNING: No geometry for building {index}, skipping.")
                    continue

                    # new_feature["geometry"] = {}
                    # if "geometries" not in new_feature["geometry"]:
                    #     new_feature["geometry"]["geometries"] = []

                meter_info = {
                    "number_of_electricity_meters": 0,
                    "number_of_gas_meters": 0,
                    "number_of_district_heating_meters": 0,
                    "number_of_district_cooling_meters": 0,
                    "number_of_district_steam_meters": 0,
                    "number_of_other_meters": 0,
                }

                no_meters = True
                if new_feature["properties"].get("meters"):
                    # determine the peak load and month for each meter and store into the
                    # properties section
                    peaks = {
                        "electricity": 0,
                        "electricity_month": None,
                        "natural_gas": 0,
                        "natural_gas_month": None,
                    }
                    for meter in new_feature["properties"]["meters"]:
                        if meter["type"] == "Electric - Grid":
                            meter_info["number_of_electricity_meters"] += 1
                            for reading in meter["readings"]:
                                # print(reading)
                                if reading["converted_value"] > peaks["electricity"]:
                                    # kwh
                                    peaks["electricity"] = reading["converted_value"]
                                    peaks["electricity_month"] = datetime.datetime.fromisoformat(reading["start_time"]).month
                        elif meter["type"] == "Natural Gas":
                            meter_info["number_of_gas_meters"] += 1
                            for reading in meter["readings"]:
                                if reading["converted_value"] > peaks["natural_gas"]:
                                    peaks["natural_gas"] = reading["converted_value"]
                                    peaks["natural_gas_month"] = datetime.datetime.fromisoformat(reading["start_time"]).month
                        else:
                            meter_info["number_of_other_meters"] += 1
                            print(f"WARNING: Not calculating peak for meter type: {meter['type']}")

                    new_feature["properties"]["electricity_peak"] = peaks["electricity"]
                    new_feature["properties"]["electricity_peak_month"] = peaks["electricity_month"]
                    new_feature["properties"]["natural_gas_peak"] = peaks["natural_gas"]
                    new_feature["properties"]["natural_gas_peak_month"] = peaks["natural_gas_month"]
                    no_meters = False
                else:
                    print(f"WARNING: No meters found for building {index}, assuming NG heating.")

                if no_meters:
                    # determine the system type by floor_area only, assume Gas is
                    # available
                    if new_feature["properties"].get("floor_area", 0) > 125000:
                        new_feature["properties"]["system_type"] = "VAV chiller with gas boiler reheat"
                    elif new_feature["properties"].get("floor_area", 0) > 75000:
                        new_feature["properties"]["system_type"] = "PVAV with gas heat with electric reheat"
                    else:
                        new_feature["properties"]["system_type"] = "PSZ-AC with gas coil"
                elif new_feature["properties"].get("floor_area", 0) > 125000:
                    if meter_info["number_of_gas_meters"] > 0:
                        new_feature["properties"]["system_type"] = "VAV chiller with gas boiler reheat"
                    else:
                        # no gas
                        new_feature["properties"]["system_type"] = "VAV chiller with PFP boxes"
                elif new_feature["properties"].get("floor_area", 0) > 75000:
                    if meter_info["number_of_gas_meters"] > 0:
                        new_feature["properties"]["system_type"] = "PVAV with gas heat with electric reheat"
                    else:
                        # no gas
                        new_feature["properties"]["system_type"] = "PVAV with PFP boxes"
                elif meter_info["number_of_gas_meters"] > 0:
                    new_feature["properties"]["system_type"] = "PSZ-AC with gas coil"
                else:
                    # no gas
                    new_feature["properties"]["system_type"] = "PSZ-HP"

                # # set the construction template based on the year built
                if new_feature["properties"].get("year_built"):
                    year_built = new_feature["properties"]["year_built"]
                    if year_built < 1980:
                        new_feature["properties"]["template"] = "DOE Ref Pre-1980"
                    elif year_built < 2004:
                        new_feature["properties"]["template"] = "DOE Ref 1980-2004"
                    elif year_built < 2007:
                        new_feature["properties"]["template"] = "90.1-2004"
                    elif year_built < 2010:
                        new_feature["properties"]["template"] = "90.1-2007"
                    elif year_built < 2013:
                        new_feature["properties"]["template"] = "90.1-2010"
                    elif year_built < 2016:
                        new_feature["properties"]["template"] = "90.1-2013"
                    elif year_built < 2019:
                        new_feature["properties"]["template"] = "90.1-2016"
                    else:
                        # pick the worst case
                        new_feature["properties"]["template"] = "DOE Ref Pre-1980"

                new_dict["features"].append(new_feature)
            # insert the site data into the features within the new_dict
            new_dict["features"].insert(0, site_info)

        return new_dict

    def create_summary_results(self) -> None:
        """Create a summary dataframe across all of the loaded results. This includes adding in the results
        from the URBANopt version only (renamed to OpenStudio)."""

        # Create annual grid metric summary -- try block for folding in IDE
        try:
            summary_data = {
                "Electricity Consumption": ["MWh/year"],
                "Electricity Peak Demand": ["MW (15-min peak)"],
                "Electricity Peak Demand Date Time": ["Datetime"],
                "Natural Gas Consumption": ["MWh/year"],
                "Natural Gas Peak Demand": ["MW (15-min peak)"],
                "Natural Gas Peak Demand Date Time": ["Datetime"],
                "Thermal Cooling": ["MWh/year"],
                "Thermal Heating": ["MWh/year"],
                "Peak to Valley Ratio (Max)": ["Ratio"],
                "Peak to Valley Ratio (Min)": ["Ratio"],
                "Peak to Valley Ratio (Mean)": ["Ratio"],
                "Load Factor (Max)": ["Ratio"],
                "Load Factor (Min)": ["Ratio"],
                "Load Factor (Mean)": ["Ratio"],
                "System Ramping (Max)": ["MW/day"],
                "System Ramping (Sum)": ["MW/year"],
                "System Ramping Cooling (Max)": ["MW/day"],
                "System Ramping Cooling (Sum)": ["MW/year"],
                "System Ramping Heating (Max)": ["MW/day"],
                "System Ramping Heating (Sum)": ["MW/year"],
            }

            # only save off the useful columns for the summary table
            year_end = f"{self.year_of_data}-12-31"
            summary_data_columns = ["Metric", "Units"]
            for analysis_name in ["Non-Connected", *list(self.modelica.keys())]:
                summary_data_columns.append(analysis_name)
                if analysis_name == "Non-Connected":
                    self.urbanopt.grid_metrics_daily
                    df_annual = self.urbanopt.grid_metrics_annual
                else:
                    self.modelica[analysis_name].grid_metrics_daily
                    df_annual = self.modelica[analysis_name].grid_metrics_annual

                # print(df_annual)
                summary_data["Electricity Consumption"].append(df_annual[year_end]["Total Electricity"])
                summary_data["Electricity Peak Demand"].append(df_annual[year_end]["Total Electricity Peak 1"])
                summary_data["Electricity Peak Demand Date Time"].append(df_annual[year_end]["Total Electricity Peak Date Time 1"])

                summary_data["Natural Gas Consumption"].append(df_annual[year_end]["Total Natural Gas"])
                summary_data["Natural Gas Peak Demand"].append(df_annual[year_end]["Total Natural Gas Peak 1"])
                summary_data["Natural Gas Peak Demand Date Time"].append(df_annual[year_end]["Total Natural Gas Peak Date Time 1"])

                summary_data["Thermal Cooling"].append(df_annual[year_end]["Total Thermal Cooling Energy"])
                summary_data["Thermal Heating"].append(df_annual[year_end]["Total Thermal Heating Energy"])

                summary_data["Peak to Valley Ratio (Max)"].append(df_annual[year_end]["Total Electricity PVR max"])
                summary_data["Peak to Valley Ratio (Min)"].append(df_annual[year_end]["Total Electricity PVR min"])
                summary_data["Peak to Valley Ratio (Mean)"].append(df_annual[year_end]["Total Electricity PVR mean"])
                summary_data["Load Factor (Max)"].append(df_annual[year_end]["Total Electricity Load Factor max"])
                summary_data["Load Factor (Min)"].append(df_annual[year_end]["Total Electricity Load Factor min"])
                summary_data["Load Factor (Mean)"].append(df_annual[year_end]["Total Electricity Load Factor mean"])
                summary_data["System Ramping (Max)"].append(df_annual[year_end]["Total Electricity System Ramping max"])
                summary_data["System Ramping (Sum)"].append(df_annual[year_end]["Total Electricity System Ramping sum"])
                summary_data["System Ramping Cooling (Max)"].append(df_annual[year_end]["Total Thermal Cooling Energy System Ramping max"])
                summary_data["System Ramping Cooling (Sum)"].append(df_annual[year_end]["Total Thermal Cooling Energy System Ramping sum"])
                summary_data["System Ramping Heating (Max)"].append(df_annual[year_end]["Total Thermal Heating Energy System Ramping max"])
                summary_data["System Ramping Heating (Sum)"].append(df_annual[year_end]["Total Thermal Heating Energy System Ramping sum"])

            # need to convert the summary_data into format: [['tom', 10, 15], ['nicholas', 15, 17], ['julian', 14, 30]]
            new_summary_data = []
            for key, value in summary_data.items():
                new_summary_data.append([key, *value])

            self.grid_summary = pd.DataFrame(data=new_summary_data, columns=summary_data_columns)
            self.grid_summary = self.grid_summary.set_index(["Metric", "Units"])
        finally:
            pass

        # Combine the annual end use summary
        try:
            # grab the end_use_summary data from each analysis, starting with urbanopt then each modelica analysis
            self.end_use_summary = self.urbanopt.end_use_summary
            for analysis_name in self.modelica:
                self.end_use_summary = pd.concat(
                    [
                        self.end_use_summary,
                        self.modelica[analysis_name].end_use_summary,
                    ],
                    axis=1,
                )

            # check if there are duplicate units columns, and if so, only keep the first
            self.end_use_summary = self.end_use_summary.loc[:, ~self.end_use_summary.columns.duplicated()]
        finally:
            pass

        # Combine the grid metrics -0- but the data aren't used a the moment
        try:
            self.grid_metrics_annual = self.urbanopt.grid_metrics_annual
            # set the column name to the analysis name
            self.grid_metrics_annual.columns = ["Non-Connected"]

            for analysis_name in self.modelica:
                self.grid_metrics_annual = pd.concat(
                    [
                        self.grid_metrics_annual,
                        self.modelica[analysis_name].grid_metrics_annual,
                    ],
                    axis=1,
                )
                # rename the column to the analysis name
                self.grid_metrics_annual = self.grid_metrics_annual.rename(columns={self.grid_metrics_annual.columns[-1]: analysis_name})
        finally:
            pass

        return True

    @classmethod
    def _check_dymola_results(cls, sim_folder: Path) -> dict:
        """Check if the simulation has valid dymola results.

        Args:
            sim_folder (Path): Path to the simulation folder.

        Returns:
            dict: Dictionary of bad or empty results.
        """
        bad_or_empty_results = {}
        error = False
        mat_file = None

        dslog_file = sim_folder.parent / "dslog.txt"
        with open(dslog_file) as f:
            lines = f.readlines()
            for line in lines:
                if "Error" in line:
                    error = True
                    bad_or_empty_results[sim_folder.parent] = {}
                    bad_or_empty_results[sim_folder.parent]["path_to_analysis"] = sim_folder.parent
                    bad_or_empty_results[sim_folder.parent]["name"] = sim_folder.parent.name
                    bad_or_empty_results[sim_folder.parent]["error"] = "Error in dslog.txt"
                    break
                if 'Integration terminated before reaching "StopTime"' in line:
                    error = True
                    bad_or_empty_results[sim_folder.parent] = {}
                    bad_or_empty_results[sim_folder.parent]["path_to_analysis"] = sim_folder.parent
                    bad_or_empty_results[sim_folder.parent]["name"] = sim_folder.parent.name
                    bad_or_empty_results[sim_folder.parent]["error"] = "Error did not reach the stop time"
                    break

        if not error:
            # Find the first .mat file in the sim_folder.parent
            mat_file = list(sim_folder.parent.glob("*.mat"))
            if not mat_file:
                error = True
                bad_or_empty_results[sim_folder.parent] = {}
                bad_or_empty_results[sim_folder.parent]["path_to_analysis"] = sim_folder.parent
                bad_or_empty_results[sim_folder.parent]["name"] = sim_folder.parent.name
                bad_or_empty_results[sim_folder.parent]["error"] = "No result .mat file in root directory"
                mat_file = None
            elif len(mat_file) > 1:
                print(f"Warning: multiple .mat files found in {sim_folder.parent}. Using the first one.")
                mat_file = mat_file[0]
            else:
                # grab the first mat_file
                mat_file = mat_file[0]

        return error, bad_or_empty_results, mat_file

    @classmethod
    def _check_openmodelica_results(cls, sim_folder: Path) -> dict:
        """Check if the OpenModelica simulation results are valid.

        Args:
            sim_folder (Path): Path to the simulation folder.

        Returns:
            dict: Dictionary of the bad or empty results.
        """
        bad_or_empty_results = {}
        error = False
        mat_file = None

        # find if there is a directory with *_results
        om_results_folder = list(sim_folder.parent.glob("*_results"))
        if not om_results_folder:
            # no results folder
            error = True
            bad_or_empty_results[sim_folder.parent] = {}
            bad_or_empty_results[sim_folder.parent]["path_to_analysis"] = sim_folder.parent
            bad_or_empty_results[sim_folder.parent]["name"] = sim_folder.parent.name
            bad_or_empty_results[sim_folder.parent]["error"] = "No _results folder"
        elif len(om_results_folder) > 1:
            print(f"Warning: multiple _results folders found in {sim_folder.parent}. Please delete others.")
        else:
            # see if there is a .mat file in the results folder
            mat_file = list(om_results_folder[0].glob("*.mat"))
            if not mat_file:
                # no .mat file, then this is an empty folder
                error = True
                bad_or_empty_results[sim_folder.parent] = {}
                bad_or_empty_results[sim_folder.parent]["path_to_analysis"] = sim_folder.parent
                bad_or_empty_results[sim_folder.parent]["name"] = sim_folder.parent.name
                bad_or_empty_results[sim_folder.parent]["error"] = "No result .mat file in _results directory"
            elif len(mat_file) > 1:
                print(f"Warning: multiple .mat files found in {om_results_folder[0]}. Using the first one.")
                # grab the first mat_file
                mat_file = mat_file[0]
            else:
                # grab the first mat_file
                mat_file = mat_file[0]
                # check if the .mat file is empty
                if mat_file.stat().st_size == 0:
                    error = True
                    bad_or_empty_results[sim_folder.parent] = {}
                    bad_or_empty_results[sim_folder.parent]["path_to_analysis"] = sim_folder.parent
                    bad_or_empty_results[sim_folder.parent]["name"] = sim_folder.parent.name
                    bad_or_empty_results[sim_folder.parent]["error"] = "Empty .mat file in _results directory"
                else:
                    # check if the .mat file is a valid result file
                    # this is a placeholder for now, but we can add more checks later
                    pass

        return error, bad_or_empty_results, mat_file

    @classmethod
    def get_list_of_valid_result_folders(cls, root_analysis_path: Path) -> (dict, dict):
        """Parse through the root_analysis_path and return a dict of valid
        result folders that can be loaded and processed. Also return dict of
        folders that have simulation errors or empty results

        Args:
            root_analysis_path (Path): Analysis folder to analyze.

        Returns:
            (dict, dict): Tuple of dicts, first is a dict of valid results, second is bad or empty results
        """
        results = {}
        bad_or_empty_results = {}

        # Find the completed simulations by looking for directories that have a district.mat file result
        sim_folders = list(root_analysis_path.glob("*/package.mo"))
        for sim_folder in sim_folders:
            mat_file = None
            # now go and check the dslog.txt file (assuming dymola was used) to
            # find if there were errors
            dslog_file = sim_folder.parent / "dslog.txt"

            # search for any folder in the sim_folder with a prepended _results to the name
            om_results_folder = list(sim_folder.parent.glob("*_results"))

            error = False
            if dslog_file.exists():
                error, result, mat_file = cls._check_dymola_results(sim_folder)
                # merge the bad_or_empty_results from the dymola check
                bad_or_empty_results.update(result)
            elif len(om_results_folder) > 0:
                error, result, mat_file = cls._check_openmodelica_results(sim_folder)
                # merge the bad_or_empty_results from the openmodelica check
                bad_or_empty_results.update(result)
            else:
                # if here, then we don't know how to process the folder
                error = True
                bad_or_empty_results[sim_folder.parent] = {}
                bad_or_empty_results[sim_folder.parent]["path_to_analysis"] = sim_folder.parent
                bad_or_empty_results[sim_folder.parent]["name"] = sim_folder.parent.name
                bad_or_empty_results[sim_folder.parent]["error"] = "No valid results found"

            if error:
                continue

            # If we are here then there is likely a successful simulation. Now store it in a
            # dictionary for later loading/processing

            # Get the simulation name from the analysis_name.txt file
            analysis_name_file = sim_folder.parent / "analysis_name.txt"
            if analysis_name_file.exists():
                with open(analysis_name_file) as f:
                    analysis_name = f.read().strip()
            else:
                print(f"Warning: could not load analysis_name.txt file for {mat_file.parent}. Setting to directory name.")
                analysis_name = mat_file.parent.name

            results[analysis_name] = {
                "path_to_analysis": sim_folder.parent,
                "name": analysis_name,
                "mat_path": mat_file,
            }

        return results, bad_or_empty_results
