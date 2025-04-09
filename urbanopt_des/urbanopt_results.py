import json
from pathlib import Path
from typing import Union

import pandas as pd
from modelica_builder.modelica_mos_file import ModelicaMOS

from .emissions import HourlyEmissionsData
from .results_base import ResultsBase

# Allow use of chained pandas operations (df[df['A'] > 1]['B'] instead of df.loc[df['A'] > 1, 'B'] = 10 )
# This prevents multiple warnings from being displayed
pd.options.mode.chained_assignment = None


class URBANoptResults(ResultsBase):
    """Catch for URBANopt results. This needs to be refactored.

    This class handles loading, parsing, and saving the UO results into a format that
    can be leveraged downstream. This is needed for the DES side of the analysis because
    the detailed building end uses are not part of the DES results, so they need to be
    concatenated with the Modelica results."""

    def __init__(self, uo_path: Path, scenario_name: str) -> None:
        """Class for holding the results of an URBANopt SDK simulation. This class will handle the post processing
        necessary to create data frames that can be easily compared with other simulation.

        Args:
            uo_path (Path): Path to the URBANopt project directory, where the feature file and Gemfile are located.
            scenario_name (str): Name of the scenario to load the results from.

        """
        super().__init__()

        self.path = uo_path
        self.scenario_name = scenario_name
        if not self.path.exists():
            raise Exception(f"Could not find {self.path} for the URBANopt results. Will not continue.")

        # check if the run with the scenario name exists
        self.scenario_path = self.path / "run" / scenario_name
        if not self.scenario_path.exists():
            raise Exception(f"Could not find {self.path / 'run' / scenario_name} for the URBANopt results. Will not continue.")

        # path to store scenario specific outputs
        self.scenario_output_path = self.scenario_path / "output"

        # path to store outputs not specific to the scenario
        self.output_path = self.path / "output"

        # make sure the output paths exists
        for path in [self.output_path, self.scenario_output_path]:
            path.mkdir(parents=True, exist_ok=True)

        # initialize the analysis display name to the scenario name, but this can be changed
        self.display_name = scenario_name
        print(f"URBANopt analysis name {self.display_name}")

        # This is the default data resolution, which has to be 60 minutes!
        self.data = None
        self.data_15min = None
        self.data_monthly = None
        self.data_annual = None

        # objects to store building loads
        self.data_loads = None
        self.data_loads_15min = None
        self.data_loads_monthly = None
        self.data_loads_annual = None

        # end use summaries
        self.end_use_summary = None

        # grid metrics
        self.grid_metrics_daily = None
        self.grid_metrics_annual = None

        self.building_characteristics = {}

    def calculate_grid_metrics(
        self,
        meters: list[str] = [
            "Total Building Electricity",
            "Total Building Natural Gas",
            "Total Electricity",
            "Total Thermal Cooling Energy",
            "Total Thermal Heating Energy",
            "District Loop Energy",
        ],
    ):
        # TODO: move this to a base class!!!

        """Calculate the grid metrics for this building."""
        # recreate the grid_metrics_daily data frame in case we are overwriting it.
        self.grid_metrics_daily = None

        # skip n-days at the beginning of the grid metrics, due to
        # warm up times that have yet to be resolved.
        self.data_15min_to_process = self.data_15min.copy()
        n_days = 2
        skip_time = n_days * 96
        self.data_15min_to_process = self.data_15min_to_process.iloc[skip_time:]
        # # END NEED TO FIX

        for meter in meters:
            df_tmp = self.data_15min_to_process.copy()
            df_tmp = df_tmp.groupby([pd.Grouper(freq="1d")])[meter].agg(["max", "idxmax", "min", "idxmin", "mean", "sum"])

            # update the column names and save back into the results data frame
            df_tmp.columns = [
                f"{meter} Max",
                f"{meter} Max Datetime",
                f"{meter} Min",
                f"{meter} Min Datetime",
                f"{meter} Mean",
                f"{meter} Sum",
            ]

            # calculate the peak to valley ratio
            df_tmp[f"{meter} PVR"] = df_tmp[f"{meter} Max"] / df_tmp[f"{meter} Min"]

            # calculate the load factor
            df_tmp[f"{meter} Load Factor"] = df_tmp[f"{meter} Mean"] / df_tmp[f"{meter} Max"]

            # add in the system ramping, which has to be calculated from the original data frame
            df_tmp2 = self.data_15min_to_process.copy()
            df_tmp2[f"{meter} System Ramping"] = df_tmp2[meter].diff().abs().fillna(0)
            df_tmp2 = df_tmp2.groupby([pd.Grouper(freq="1d")])[f"{meter} System Ramping"].agg(["sum"]) / 1e6
            df_tmp2.columns = [f"{meter} System Ramping"]

            df_tmp = pd.concat([df_tmp, df_tmp2], axis=1, join="inner")
            if self.grid_metrics_daily is None:
                self.grid_metrics_daily = df_tmp
            else:
                self.grid_metrics_daily = pd.concat([self.grid_metrics_daily, df_tmp], axis=1, join="inner")

        # aggregate the df_daily daily data to annual metrics. For the maxes/mins, we only want the max of the max
        # and the min of the min.
        df_tmp = self.grid_metrics_daily.copy()
        aggs = {}
        for meter in meters:
            aggs[f"{meter} Max"] = ["max", "idxmax", "sum"]
            aggs[f"{meter} Min"] = ["min", "idxmin"]
            aggs[f"{meter} PVR"] = ["max", "min", "sum", "mean"]
            aggs[f"{meter} Load Factor"] = ["max", "min", "sum", "mean"]
            aggs[f"{meter} System Ramping"] = ["max", "min", "sum", "mean"]

        df_tmp = df_tmp.groupby([pd.Grouper(freq="YE")]).agg(aggs)
        # rename the columns
        df_tmp.columns = [f"{c[0]} {c[1]}" for c in df_tmp.columns]
        # this is a strange section, the idxmax/idxmin are the indexes where the max/min values
        # were found, but we want the timestamps from the original dataframe, so go get them!
        for meter in meters:
            # there is only one year of data, so grab the idmax/idmin of the first element. If
            # we expand to multiple years, then this will need to be updated
            id_lookup = df_tmp[f"{meter} Max idxmax"][0]
            df_tmp[f"{meter} Max idxmax"] = self.grid_metrics_daily.loc[id_lookup][f"{meter} Max Datetime"]
            id_lookup = df_tmp[f"{meter} Min idxmin"][0]
            df_tmp[f"{meter} Min idxmin"] = self.grid_metrics_daily.loc[id_lookup][f"{meter} Min Datetime"]
            # rename these two columns to remove the idxmax/idxmin nomenclature
            df_tmp = df_tmp.rename(
                columns={
                    f"{meter} Max idxmax": f"{meter} Max Datetime",
                    f"{meter} Min idxmin": f"{meter} Min Datetime",
                }
            )

        # Add the MWh related metrics, can't sum up the 15 minute data, so we have to sum up the hourly
        df_tmp["Total Electricity"] = self.data["Total Electricity"].resample("YE").sum() / 1e6  # MWh
        df_tmp["Total Natural Gas"] = self.data["Total Natural Gas"].resample("YE").sum() / 1e6  # MWh
        df_tmp["Total Thermal Cooling Energy"] = self.data["Total Thermal Cooling Energy"].resample("YE").sum() / 1e6  # MWh
        df_tmp["Total Thermal Heating Energy"] = self.data["Total Thermal Heating Energy"].resample("YE").sum() / 1e6  # MWh

        # graph the top 5 peak values for each of the meters
        meters = [
            "Total Natural Gas",
            "Total Electricity",
            "Total Thermal Cooling Energy",
            "Total Thermal Heating Energy",
        ]
        for meter in meters:
            peaks = []
            df_to_proc = self.data_15min_to_process.copy()
            if "Cooling" in meter:
                # values are negative, so ascending is actually descending
                df_to_proc = df_to_proc.sort_values(by=meter, ascending=True)
            else:
                df_to_proc = df_to_proc.sort_values(by=meter, ascending=False)
            df_to_proc = df_to_proc.head(50)

            # save the top 5 values to the df_tmp
            i = 0
            for dt, row in df_to_proc.iterrows():
                peak_value = row[meter] / 1e6  # MWh
                if peak_value not in peaks or peak_value == 0:
                    peaks.append(peak_value)
                    df_tmp[f"{meter} Peak {i + 1}"] = peak_value
                    if peak_value != 0:
                        df_tmp[f"{meter} Peak Date Time {i + 1}"] = dt
                    else:
                        df_tmp[f"{meter} Peak Date Time {i + 1}"] = "N/A"
                    i += 1

                if i == 5:
                    break

        # transpose and save
        df_tmp = df_tmp.T
        df_tmp.index.name = "Grid Metric"
        self.grid_metrics_annual = df_tmp

        return self.grid_metrics_annual

    def save_dataframes(self) -> None:
        """Save the data and data_15min dataframes to the outputs directory."""
        self.data.to_csv(self.output_path / "power_60min.csv")
        self.data_15min.to_csv(self.output_path / "power_15min.csv")
        if self.data_monthly is not None:
            self.data_monthly.to_csv(self.output_path / "power_monthly.csv")

        if self.data_annual is not None:
            self.data_annual.to_csv(self.output_path / "power_annual.csv")

        # loads
        if self.data_loads is not None:
            self.data_loads.to_csv(self.output_path / "loads_60min.csv")

        if self.data_loads_15min is not None:
            self.data_loads_15min.to_csv(self.output_path / "loads_15min.csv")

        if self.data_loads_monthly is not None:
            self.data_loads_monthly.to_csv(self.output_path / "loads_monthly.csv")

        if self.data_loads_annual is not None:
            self.data_loads_annual.to_csv(self.output_path / "loads_annual.csv")

        if self.grid_metrics_daily is not None:
            self.grid_metrics_daily.to_csv(self.output_path / "grid_metrics_daily.csv")

        if self.grid_metrics_annual is not None:
            self.grid_metrics_annual.to_csv(self.output_path / "grid_metrics_annual.csv")

    def create_aggregations(self, building_names: list[str]) -> None:
        """Aggregate the results from all the buildings together to get the totals

        Args:
            building_names (list): List of building ids/names, should come from GeoJSON
        """
        # try block is here for folding in IDE :)
        # This list needs to be the same in the modelica_results.py file as well--which
        # means that we should refactor this to be a base method. And note that there
        # are more fields defined at the end of this method.
        try:
            building_aggs: dict[str, dict] = {
                "Total Building Electricity": {},
                "Total Building Natural Gas": {},
                "Total Building Cooling Electricity": {},
                "Total Building Heating Electricity": {},
                "Total Building Heating Natural Gas": {},
                "Total Building Fans Electricity": {},
                "Total Building Pumps Electricity": {},
                "Total Building Heat Rejection Electricity": {},
                "Total Building Heat Rejection Natural Gas": {},
                "Total Building Water Systems Natural Gas": {},
                "Total Building Water Systems Electricity": {},
                "Total Building Interior Lighting": {},
                "Total Building Exterior Lighting": {},
                "Total Building Interior Equipment Electricity": {},
                "Total Building Interior Equipment Natural Gas": {},
                "Total Building Interior Equipment": {},  # electric and gas
                "Total Building Exterior Equipment Electricity": {},
                # HVAC Aggregations
                "Total Building HVAC Electricity": {},
                "Total Building HVAC Natural Gas": {},
                "Total Building HVAC Cooling Energy": {},
                "Total Building HVAC Heating Energy": {},
                "Total Building HVAC Energy": {},
                # Water
                "Total Building Water Systems": {},
                # Not sure we are gathering this in OpenStudio/EnergyPlus
                # "Total Building Thermal Energy Cooling": {},
                # "Total Building Thermal Energy Heating": {},
            }

            # add agg columns for each building
            for key, _ in building_aggs.items():
                building_aggs[key]["agg_columns"] = []

            for i in building_names:
                # By fuels
                building_aggs["Total Building Electricity"]["agg_columns"].append(f"Electricity:Facility Building {i}")
                building_aggs["Total Building Natural Gas"]["agg_columns"].append(f"NaturalGas:Facility Building {i}")
                # Building level HVAC aggregations
                building_aggs["Total Building Cooling Electricity"]["agg_columns"].append(f"Cooling:Electricity Building {i}")
                building_aggs["Total Building Heating Electricity"]["agg_columns"].append(f"Heating:Electricity Building {i}")
                building_aggs["Total Building Heating Natural Gas"]["agg_columns"].append(
                    f"Heating:NaturalGas Building {i}",
                )
                building_aggs["Total Building Fans Electricity"]["agg_columns"].append(f"Fans:Electricity Building {i}")
                building_aggs["Total Building Pumps Electricity"]["agg_columns"].append(f"Pumps:Electricity Building {i}")
                building_aggs["Total Building Heat Rejection Electricity"]["agg_columns"].append(f"HeatRejection:Electricity Building {i}")
                building_aggs["Total Building Heat Rejection Natural Gas"]["agg_columns"].append(f"HeatRejection:NaturalGas Building {i}")
                building_aggs["Total Building Water Systems Natural Gas"]["agg_columns"].append(f"WaterSystems:NaturalGas Building {i}")
                building_aggs["Total Building Water Systems Electricity"]["agg_columns"].append(f"WaterSystems:Electricity Building {i}")

                # Interior and exterior lighting
                building_aggs["Total Building Interior Lighting"]["agg_columns"].append(f"InteriorLights:Electricity Building {i}")
                building_aggs["Total Building Exterior Lighting"]["agg_columns"].append(f"ExteriorLights:Electricity Building {i}")

                # Interior and exterior equipment
                building_aggs["Total Building Interior Equipment Electricity"]["agg_columns"].append(
                    f"InteriorEquipment:Electricity Building {i}"
                )
                building_aggs["Total Building Interior Equipment Natural Gas"]["agg_columns"].append(
                    f"InteriorEquipment:NaturalGas Building {i}"
                )
                building_aggs["Total Building Exterior Equipment Electricity"]["agg_columns"].append(
                    f"ExteriorEquipment:Electricity Building {i}"
                )
                building_aggs["Total Building Interior Equipment"]["agg_columns"] += [
                    f"InteriorEquipment:Electricity Building {i}",
                    f"InteriorEquipment:NaturalGas Building {i}",
                ]

            building_aggs["Total Building HVAC Electricity"]["agg_columns"] = [
                "Total Building Cooling Electricity",
                "Total Building Heating Electricity",
                "Total Building Fans Electricity",
                "Total Building Pumps Electricity",
                "Total Building Heat Rejection Electricity",
            ]
            building_aggs["Total Building HVAC Natural Gas"]["agg_columns"] = [
                "Total Building Heating Natural Gas",
                "Total Building Heat Rejection Natural Gas",
            ]
            building_aggs["Total Building HVAC Cooling Energy"]["agg_columns"] = [
                "Total Building Cooling Electricity",
            ]
            building_aggs["Total Building HVAC Heating Energy"]["agg_columns"] = [
                "Total Building Heating Electricity",
                "Total Building Heating Natural Gas",
            ]
            building_aggs["Total Building HVAC Energy"]["agg_columns"] = [
                "Total Building HVAC Electricity",
                "Total Building HVAC Natural Gas",
            ]
            building_aggs["Total Building Water Systems"]["agg_columns"] = [
                "Total Building Water Systems Electricity",
                "Total Building Water Systems Natural Gas",
            ]

            # Go through each building_aggs and create the aggregation
            for key, value in building_aggs.items():
                # check to make sure that each of the agg_columns have been defined
                if not value["agg_columns"]:
                    raise Exception(f"Agg columns for {key} have not been defined")

                # sum up the columns in the agg_columns defined above
                self.data[key] = self.data[value["agg_columns"]].sum(axis=1)
                self.data_15min[key] = self.data_15min[value["agg_columns"]].sum(axis=1)

            # Since the dataframe needs to be consistent with the Modelica and DES dataframes, add in the
            # following columns, which have no totaling or aggregating
            self.data["Total Electricity"] = self.data["Total Building Electricity"]
            self.data_15min["Total Electricity"] = self.data_15min["Total Building Electricity"]
            self.data["Total Natural Gas"] = self.data["Total Building Natural Gas"]
            self.data_15min["Total Natural Gas"] = self.data_15min["Total Building Natural Gas"]
            self.data["Total ETS Electricity"] = 0
            self.data_15min["Total ETS Electricity"] = 0
            self.data["Total Thermal Cooling Energy"] = 0
            self.data_15min["Total Thermal Cooling Energy"] = 0
            self.data["Total Thermal Heating Energy"] = 0
            self.data_15min["Total Thermal Heating Energy"] = 0
            self.data["District Loop Energy"] = 0
            self.data_15min["District Loop Energy"] = 0
            # Now mix energy types for the totals
            self.data["Total Energy"] = self.data["Total Electricity"] + self.data["Total Natural Gas"]
            self.data_15min["Total Energy"] = self.data_15min["Total Electricity"] + self.data_15min["Total Natural Gas"]
            self.data["Total Building and ETS Energy"] = (
                self.data["Total Building Electricity"] + self.data["Total Building Natural Gas"] + self.data["Total ETS Electricity"]
            )
            self.data_15min["Total Building and ETS Energy"] = (
                self.data_15min["Total Building Electricity"]
                + self.data_15min["Total Building Natural Gas"]
                + self.data_15min["Total ETS Electricity"]
            )

        finally:
            pass

    def process_results(self, building_names: list[str], year_of_data: int = 2017) -> None:
        """The building-by-building end uses are only available in each run directory's feature
        report. This method will create a dataframe with the end uses for each building.

        The column names can change slightly (with or without units).

        Args:
            scenario_name (str): Name of the scenario that was run with URBANopt
            building_name (list): Must be passed since the names come from the GeoJSON which we don't load
            year_of_data (int): Year of the data. This is used to set the year of the datetime index. Defaults to 2017
        """
        # reset the data to None in case we are reprocessing
        self.data = None
        # TODO: I think we should None out all of the data_* objects too

        # reset the building characteristics
        self.building_characteristics = {}
        for building_id in building_names:
            print(f"Reading building characteristics for {building_id}")
            # read in the JSON file with the feature results, these are the building characteristics such
            # as square footages, window areas, etc.
            feature_json = self.get_urbanopt_default_feature_report_json(self.path / "run" / f"{self.scenario_name}" / f"{building_id}")
            # Read the JSON as dictionary to the building characteristics
            # Use a context manager for opening files
            self.building_characteristics[building_id] = json.loads(feature_json.read_text())

            print(f"Processing building time series results {building_id}")
            feature_report = self.get_urbanopt_default_feature_report(self.path / "run" / f"{self.scenario_name}" / f"{building_id}")

            # rename and convert units in the feature_report before concatenating with the others
            for (
                column_name,
                feature_column,
            ) in self.get_urbanopt_feature_report_columns().items():
                if feature_column.get("skip_renaming", False):
                    continue
                # set the new column name to include the building number
                new_column_name = f"{feature_column['name']} Building {building_id}"
                feature_report[new_column_name] = feature_report[column_name] * feature_column["conversion"]
                feature_report = feature_report.drop(columns=[column_name])

            # convert Datetime column in data frame to be datetime from the string. The year
            # should be set to a year that has the day of week starting correctly for the real data
            # This defaults to year_of_data
            feature_report["Datetime"] = pd.to_datetime(feature_report["Datetime"], format="%Y/%m/%d %H:%M:%S")
            feature_report["Datetime"] = feature_report["Datetime"].apply(lambda x: x.replace(year=year_of_data))

            # set the datetime column and make it the index
            feature_report = feature_report.set_index("Datetime")

            if self.data is None:
                self.data = feature_report
            else:
                # remove the datetime from the second data frame
                self.data = pd.concat([self.data, feature_report], axis=1, join="inner")

        self.save_urbanopt_variables("urbanopt_single_feature_file_variables.json")

        # Upsample to 15 minutes, provides a higher resolution date for
        # the end uses for comparison sake. This only works for specific
        # variables such as energy (kWh, Btu, etc.)
        self.data_15min = self.data.resample("15min").ffill()

        # create the aggregations for the data
        self.create_aggregations(building_names)

        # TODO: add variables to the urbanopt_single_feature_file_variables.json

        return True

    def process_load_results(self, building_names: list[str], year_of_data: int = 2017) -> None:
        """The building-by-building loads are results of an OpenStudio measure. The data are only
        available in each run directory's modelica_report. This method will create a dataframe with
        the end uses for each building.

        Args:
            scenario_name (str): Name of the scenario that was run with URBANopt
            building_name (list): Must be passed since the names come from the GeoJSON which we don't load
            year_of_data (int): Year of the data. This is used to set the year of the datetime index. Defaults to 2017
        """
        self.data_loads = None  # TODO: init this above and make a note what it is

        for building_id in building_names:
            print(f"Processing building time series loads for {building_id}")
            load_report = self.get_urbanopt_export_building_loads(self.path / "run" / f"{self.scenario_name}" / f"{building_id}")

            # update the column names to include the building id
            for column in load_report.columns:
                # skip if Datetime
                if column == "Datetime":
                    continue
                load_report = load_report.rename(columns={column: f"{column} Building {building_id}"})

            # convert Datetime column in data frame to be datetime from the string. The year
            # should be set to a year that has the day of week starting correctly for the real data
            # This defaults to year_of_data
            load_report["Datetime"] = pd.to_datetime(load_report["Datetime"], format="%m/%d/%Y %H:%M")
            load_report["Datetime"] = load_report["Datetime"].apply(lambda x: x.replace(year=year_of_data))

            # set the datetime column and make it the index
            load_report = load_report.set_index("Datetime")

            if self.data_loads is None:
                self.data_loads = load_report
            else:
                # remove the datetime from the second data frame
                self.data_loads = pd.concat([self.data_loads, load_report], axis=1, join="inner")

        # aggregate the data to create totals
        self.data_loads["TotalCoolingSensibleLoad"] = self.data_loads.filter(like="TotalCoolingSensibleLoad").sum(axis=1)
        self.data_loads["TotalHeatingSensibleLoad"] = self.data_loads.filter(like="TotalHeatingSensibleLoad").sum(axis=1)
        self.data_loads["TotalWaterHeating"] = self.data_loads.filter(like="TotalWaterHeating").sum(axis=1)
        self.data_loads["TotalSensibleLoad"] = self.data_loads["TotalCoolingSensibleLoad"] + self.data_loads["TotalHeatingSensibleLoad"]
        self.data_loads["TotalSensibleLoadWithWaterHeating"] = self.data_loads["TotalSensibleLoad"] + self.data_loads["TotalWaterHeating"]

        # self.data_loads["Total Building Natural Gas"] = self.data_loads.filter(like="NaturalGas").sum(axis=1)

        # Upsample to 15 minutes, provides a higher resolution date for
        # the end uses for comparison sake. This only works for specific
        # variables such as energy (kWh, Btu, etc.)
        self.data_loads_15min = self.data_loads.resample("15min").ffill()

        return True

    def calculate_carbon_emissions(
        self,
        hourly_emissions_data: HourlyEmissionsData,
        egrid_subregion: str = "RFCE",
        future_year: int = 2045,
    ):
        """Calculate the carbon emissions for system as a whole. The data are
        passed in as an object called hourly_emissions_data which contains the already selected marginal/average emissions
        for the correct year, but all the regions.

        Args:
            hourly_emissions_data (HourlyEmissionsData): Data object with the emissions.
            egrid_subregion (str): EPA's 4-letter identifier for the emissions subregion.
            future_year (int, optional): Year of the emission data, used to assign the correct column name, that is all. Defaults to 2045.
        """
        # for some reason, the datafile has a `c` appended to the end of the subregion, probably for Cambium
        lookup_egrid_subregion = egrid_subregion + "c"

        # multiply the hourly emissions hourly data by the min_60_with_buildings data, but first, verify that the lengths are the same.
        if len(hourly_emissions_data.data) != len(self.data):
            raise Exception(
                f"Length of emissions data {len(hourly_emissions_data.data)} does not match the length of the min_60_with_buildings data {len(self.data)}."
            )

        # also verify the length of the other_fuels
        if len(hourly_emissions_data.other_fuels) != len(self.data):
            raise Exception(
                f"Length of other fuel emission data {len(hourly_emissions_data.data)} does not match the length of the min_60_with_buildings data {len(self.min_60_with_buildings)}."
            )

        # Calculate the natural gas emissions, emissions data is in kg/MWh so Wh->MWh, then divide by another 1000 to get mtCO2e
        self.data["Total Building Natural Gas Carbon Emissions"] = (
            self.data["Total Building Natural Gas"] * hourly_emissions_data.other_fuels["natural_gas"] / 1e6 / 1000
        )
        self.data["Total Natural Gas Carbon Emissions"] = self.data["Total Building Natural Gas Carbon Emissions"]

        # Calculate the electricity carbon emissions, emissions data is in kg/MWh, so Wh->Mwh, then divide by another 1000 to get mtCO2e
        self.data[f"Total Electricity Carbon Emissions {future_year}"] = (
            self.data["Total Electricity"] * hourly_emissions_data.data[lookup_egrid_subregion] / 1e6 / 1000
        )
        # units are in kg, convert to metric tons
        self.data[f"Total Carbon Emissions {future_year}"] = (
            self.data["Total Natural Gas Carbon Emissions"] + self.data[f"Total Electricity Carbon Emissions {future_year}"]
        )

    def scale_results(
        self,
        scalars: pd.DataFrame,
        year_of_data: int = 2017,
        year_of_meters: int = 2021,
    ) -> None:
        """Scale all of the OpenStudio results by a set of scalars. This should only be used
        if there are no calibrated models and we need to keep the magnitude of the results within
        range for comparison."""
        # create a list of meter names that will be scaled. These are hard coded and will
        # have the building ID appended to the name for each building
        meter_names = [
            # totals by fuel type
            "Electricity:Facility Building",
            "ElectricityProduced:Facility Building",
            "NaturalGas:Facility Building",
            # by building end use and fuel type
            "Cooling:Electricity Building",
            "Heating:Electricity Building",
            "InteriorLights:Electricity Building",
            "ExteriorLights:Electricity Building",
            "InteriorEquipment:Electricity Building",
            "ExteriorEquipment:Electricity Building",
            "Fans:Electricity Building",
            "Pumps:Electricity Building",
            "WaterSystems:Electricity Building",
            "HeatRejection:Electricity Building",
            "HeatRejection:NaturalGas Building",
            "Heating:NaturalGas Building",
            "WaterSystems:NaturalGas Building",
            "InteriorEquipment:NaturalGas Building",
            "DistrictCooling:Facility Building",  # not scaled, yet
            "DistrictHeating:Facility Building",  # not scaled, yet
        ]

        meter_names_for_building = []
        for building_id in scalars["building_id"].unique():
            meter_names_for_building = [meter_name + f" {building_id}" for meter_name in meter_names]

        for df in [self.data, self.data_15min]:
            # for each building_id in the scalar dataframe. Be careful not
            # to apply scaling factors to the same building twice from multiple
            # files.
            elec_meters = [meter_name for meter_name in meter_names_for_building if "Electricity" in meter_name]
            ng_meters = [meter_name for meter_name in meter_names_for_building if "NaturalGas" in meter_name]
            for meter_type in ["Electricity", "NaturalGas"]:
                # for each row in the analysis results dataframe, grab the scalar and multiply it by the meter
                # print(f"Applying scalars for meter year {year_of_meters}, sim year {year_of_data}, building {building_id}, and meter {meter_type}")
                for _, scalar in scalars[scalars["start_time"].dt.year == year_of_meters].iterrows():
                    # this is strange, but we compare the year of the meter with the year of the simulation, which
                    # can be different. So convert the 'start_time' and 'end_time' of the meters to be the year of the
                    # dataframe data
                    scalar["start_time"] = scalar["start_time"].replace(year=year_of_data)
                    scalar["end_time"] = scalar["end_time"].replace(year=year_of_data)
                    row_filter = (df.index >= scalar["start_time"]) & (df.index <= scalar["end_time"])
                    elec_scalar = scalar["scaling_factor_electricity"]
                    ng_scalar = scalar["scaling_factor_natural_gas"]
                    # print(f"data range: {scalar['start_time']} to {scalar['end_time']} with elec scalar {elec_scalar} and ng scalar {ng_scalar}")
                    if meter_type == "Electricity" and elec_scalar is not None and not pd.isna(elec_scalar):
                        df.loc[row_filter, elec_meters] = df.loc[row_filter, elec_meters] * elec_scalar
                    elif meter_type == "NaturalGas" and ng_scalar is not None and not pd.isna(ng_scalar):
                        df.loc[row_filter, ng_meters] = df.loc[row_filter, ng_meters] * ng_scalar

    def get_urbanopt_feature_report_columns(self) -> dict[str, dict[str, object]]:
        """Return the feature report columns with the metadata such as
        units and conversion factors."""
        # create a structure that enables some metadata to be added to the columns for
        # plotting and unit conversion

        # TODO: There are cases where the units aren't present in the column name, so
        # we need to handle both cases.
        columns = {
            "Datetime": {
                "skip_renaming": True,
                "unit_original": "Datetime",
                "units": "Datetime",
                "conversion": 1,
                "name": "Datetime",
                "description": "timestamp of step",
            },
            "Electricity:Facility": {},
            "ElectricityProduced:Facility": {},
            "NaturalGas:Facility": {},
            "Cooling:Electricity": {},
            "Heating:Electricity": {},
            "InteriorLights:Electricity": {},
            "ExteriorLights:Electricity": {},
            "InteriorEquipment:Electricity": {},
            "ExteriorEquipment:Electricity": {},
            "Fans:Electricity": {},
            "Pumps:Electricity": {},
            "WaterSystems:Electricity": {},
            "HeatRejection:Electricity": {},
            "HeatRejection:NaturalGas": {},
            "Heating:NaturalGas": {},
            "WaterSystems:NaturalGas": {},
            "InteriorEquipment:NaturalGas": {},
            # 'Propane:Facility': {},
            # 'FuelOilNo2:Facility': {},
            # 'OtherFuels:Facility': {},
            # 'HeatRejection:Propane': {},
            # 'Heating:Propane': {},
            # 'WaterSystems:Propane': {},
            # 'InteriorEquipment:Propane': {},
            # 'HeatRejection:FuelOilNo2': {},
            # 'Heating:FuelOilNo2': {},
            # 'WaterSystems:FuelOilNo2': {},
            # 'InteriorEquipment:FuelOilNo2': {},
            # 'HeatRejection:OtherFuels': {},
            # 'Heating:OtherFuels': {},
            # 'WaterSystems:OtherFuels': {},
            # 'InteriorEquipment:OtherFuels': {},
            "DistrictCooling:Facility": {},
            "DistrictHeating:Facility": {},
            # "Future_Annual_Electricity_Emissions": {},
            # "Future_Hourly_Electricity_Emissions": {},
            # # 'Historical_Annual_Electricity_Emissions': {},
            # 'Historical_Hourly_Electricity_Emissions': {},
            # 'Future_Annual_Electricity_Emissions_Intensity': {},
            # 'Future_Hourly_Electricity_Emissions_Intensity': {},
            # 'Historical_Annual_Electricity_Emissions_Intensity': {},
            # 'Historical_Hourly_Electricity_Emissions_Intensity': {},
            # "Natural_Gas_Emissions": {},
            # 'Natural_Gas_Emissions_Intensity': {},
        }

        # fill in the unit conversions based on the parenthetical units in the key
        for key, _ in columns.items():
            # units_original is the units in the column name from URBANopt's default feature report
            # units is the name that we want to use for the units in the data frame
            # conversion is the conversion factor to convert the units_original to the units

            # The order of the items below is important!
            if key.endswith("Emissions_Intensity"):
                columns[key]["unit_original"] = "KG/FT2"
                columns[key]["units"] = "kgCO2e/m2"
                columns[key]["conversion"] = 10.7639
                columns[key]["name"] = key
                columns[key]["description"] = key
            elif key.endswith("Emissions"):
                columns[key]["unit_original"] = "MT"
                columns[key]["units"] = "mtCO2e"
                columns[key]["conversion"] = 1.0
                columns[key]["name"] = key
                columns[key]["description"] = key
            elif "Electricity" in key:
                columns[key]["unit_original"] = "kWh"
                columns[key]["units"] = "Wh"
                columns[key]["conversion"] = 1000.0
                columns[key]["name"] = key
                columns[key]["description"] = key
            elif "NaturalGas" in key or ("DistrictCooling" in key or "DistrictHeating" in key):
                columns[key]["unit_original"] = "kBtu"
                columns[key]["units"] = "Wh"
                columns[key]["conversion"] = 293.071  # 1 kBtu = 293.071 Wh
                columns[key]["name"] = key
                columns[key]["description"] = key
            elif key == "Datetime":
                continue
            else:
                raise Exception(f"Could not find units for {key}")

        return columns

    def get_urbanopt_default_feature_report_columns(self) -> list:
        """Return the default columns for the URBANopt / EnergyPlus simulation."""
        return [key for key, _ in self.get_urbanopt_feature_report_columns().items()]

    def save_urbanopt_variables(self, save_filename: Path) -> None:
        """Save off the name of the variables into the directory."""
        with open(self.path / save_filename, "w") as f:
            json.dump(self.get_urbanopt_feature_report_columns(), f, indent=2)

    def create_abstract_run(self, run_id: str, load_dataframe: pd.DataFrame) -> None:
        """Create an abstract run within the URBANopt structure. This will enable
        the DES CLI to easily grab the data for a non-real run such as an aggregation.

        Args:
            run_id (str): Unique identifier for the run, this will appear as a building_name
            load_dataframe (pd.DataFrame): Dataframe with the loads for the building
        """
        # for now we are forcing the data into a specific measure directory
        new_run_path = self.path / "run" / f"{self.scenario_name}" / f"{run_id}"
        if new_run_path.exists():
            print(f"Run directory {new_run_path} already exists, will overwrite files")
        new_run_path.mkdir(parents=True, exist_ok=True)

        # create an export_modelica_loads path, random number for the directory name
        new_run_path_export = new_run_path / "01_export_modelica_loads"
        new_run_path_export.mkdir(parents=True, exist_ok=True)
        # save data frame as CSV, but only the columns that are needed

        # duplicate the load_dataframe so that we can calculate the seconds in the year
        tmp_dataframe = load_dataframe.copy()
        # time column is seconds from the start of the year, as integers
        tmp_dataframe["time"] = (tmp_dataframe.index - tmp_dataframe.index[0]).total_seconds()
        # the last timestamp is weird as it will be negative. Take the second to last value and add 3600
        tmp_dataframe["time"].iloc[-1] = tmp_dataframe["time"].iloc[-2] + 3600
        # the first value of the hot water must be zero, else there will be an error
        tmp_dataframe["TotalWaterHeating"].iloc[0] = 0

        # coerce time into int
        tmp_dataframe["time"] = tmp_dataframe["time"].astype(int)
        header = "#1\n"
        header += "#Created from results of URBANopt\n\n"
        header += "#First column: Seconds in the year (loads are hourly)\n"
        header += "#Second column: cooling loads in Watts (as negative numbers).\n"
        header += "#Third column: space heating loads in Watts\n"
        header += "#Fourth column: water heating loads in Watts\n\n"
        header += f"#Peak space cooling load = {tmp_dataframe['TotalCoolingSensibleLoad'].min()} Watts\n"
        header += f"#Peak space heating load = {tmp_dataframe['TotalHeatingSensibleLoad'].max()} Watts\n"
        header += f"#Peak water heating load = {tmp_dataframe['TotalWaterHeating'].max()} Watts\n"

        columns = [
            "time",
            "TotalCoolingSensibleLoad",
            "TotalHeatingSensibleLoad",
            "TotalWaterHeating",
        ]

        list_data = tmp_dataframe[columns].values.tolist()  # noqa: PD011
        # make the first column integers
        list_data = [[int(x) if i == 0 else x for i, x in enumerate(row)] for row in list_data]
        modelica_mos = ModelicaMOS.from_list(list_data, header_data=header)

        # save the mos file and CSV file
        modelica_mos.save_as(new_run_path_export / "modelica.mos")
        tmp_dataframe.to_csv(
            new_run_path_export / "building_loads.csv",
            columns=["TotalCoolingSensibleLoad", "TotalHeatingSensibleLoad", "TotalWaterHeating"],
            index_label="time",
        )

    def _search_for_file_in_reports(self, search_dir: Path, filename: str, measure_name: Union[str, None] = None) -> Path:
        """Search for a report file in a directory and return the path, if exists.

        If the filename has more than one period, e.g., .tar.gz, then this will not work
        as expected.

        Args:
            search_dir (Path): Path for where to start looking for the file
            filename (str): Name of the file to search for
            measure_name (str): Name of the measure directory to search in. Defaults to None.
        """
        # FIXME, this method needs some tests and can be cleaned up... for sure
        report_file = search_dir / "feature_reports" / filename
        if not report_file.exists():
            filename = Path(filename)
            # OpenStudio puts the results in the filename without the extension
            dirs = list(search_dir.glob(f"*_{filename.stem}"))
            if len(dirs) == 1:
                report_file = dirs[0] / filename
            elif len(dirs) == 0:
                # If we are here, then it is likely that the report is in
                # another measure directory which we need to find. This is
                # when the measure_name is used, to make sure we return the
                # file from the appropriate measure since it could be in multiple
                # measure directories.
                dirs_2 = list(search_dir.glob(f"*_{measure_name}"))
                if len(dirs_2) == 1:
                    report_file = dirs_2[0] / filename
                elif len(dirs_2) == 0:
                    raise Exception(f"Could not find {filename} in {search_dir} with measure name {measure_name}")
                else:
                    raise Exception(f"More than one {filename} found in dirs: {dirs_2}")
            else:
                raise Exception(f"More than one {filename} found in dirs: {dirs}")

        return report_file

    def get_urbanopt_default_feature_report_json(self, search_dir: Path) -> dict:
        """Return the default_feature_report.json file with building characteristics and high
        level results. The file can be located in a measure directory (maybe in just older versions
        of URBANopt), so this method will search for it in the run directory.

        Args:
            search_dir (Path): Path for where to start looking for the file

        Returns:
            dict: dictionary of the default_feature_report.json file
        """
        report_file = self._search_for_file_in_reports(search_dir, "default_feature_report.json")
        return report_file

    def get_urbanopt_default_feature_report(self, search_dir: Path) -> pd.DataFrame:
        """Return the default report from the URBANopt / EnergyPlus simulation."""
        # get the default report
        report_file = self._search_for_file_in_reports(search_dir, "default_feature_report.csv")

        if report_file.exists():
            # read the header row of the CSV file and grab the column names
            columns = pd.read_csv(report_file, nrows=0).columns

            # check the columns against the `get_urbanopt_default_feature_report_columns` to
            # make sure the units are consistent, then remove the units from the column names. There
            # can be a lot of columns and we don't want them all (for now)
            desired_columns = self.get_urbanopt_feature_report_columns()
            rename_mapping = {}
            for column in columns:
                column_wo_units = column.split("(")[0]
                units = column.split("(")[-1].split(")")[0]
                if column_wo_units not in desired_columns:
                    # then move on, because we don't care about this column
                    # print(f'Column {column_wo_units} not desired.')
                    continue

                # extract the units if they exist and check against desired. It is okay if units are blank, we
                # just assume that they are what we wanted.
                if units not in ["", None, desired_columns[column_wo_units]["unit_original"]]:
                    raise Exception(f"Units of {units} for {column_wo_units} are not {desired_columns[column_wo_units]['unit_original']}")

                # add the column to the rename mapping
                rename_mapping[column] = column_wo_units

            # re-read the file with the column names and rename the columns to not have the units
            report = pd.read_csv(report_file, usecols=rename_mapping.keys())
            report = report.rename(columns=rename_mapping)

            # convert all values to floats except the first column which is the date time
            cols = report.columns
            report[cols[1:]] = report[cols[1:]].apply(pd.to_numeric, errors="coerce")
            return report
        else:
            raise Exception(f"Could not find default_feature_report.csv in {search_dir}")

    def get_urbanopt_export_building_loads(self, search_dir: Path) -> pd.DataFrame:
        """Return the building_loads.csv file path.

        Args:
            search_dir (Path): Path for where to start looking for the file

        Returns:
            dict: dictionary of the default_feature_report.json file
        """
        report_file = self._search_for_file_in_reports(search_dir, "building_loads.csv", measure_name="export_modelica_loads")
        if report_file.exists():
            print(f"Processing building loads from {report_file}")

            # only grab the columns that we care about
            columns_to_keep_and_map = {
                "Date Time": "Datetime",
                "TotalSensibleLoad": "TotalSensibleLoad (W)",
                "TotalCoolingSensibleLoad": "TotalCoolingSensibleLoad (W)",
                "TotalHeatingSensibleLoad": "TotalHeatingSensibleLoad (W)",
                "TotalWaterHeating": "TotalWaterHeating (W)",
            }

            # re-read the file with the column names and rename the columns to not have the units
            report = pd.read_csv(report_file, usecols=columns_to_keep_and_map.keys())
            report = report.rename(columns=columns_to_keep_and_map)

            # convert all values to floats except the first column which is the date time
            cols = report.columns
            report[cols[1:]] = report[cols[1:]].apply(pd.to_numeric, errors="coerce")
            return report
        else:
            raise Exception(f"Could not find building_loads.csv in {search_dir}")
