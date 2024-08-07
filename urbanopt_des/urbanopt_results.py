import json
from pathlib import Path

import numpy as np
import pandas as pd

from .emissions import HourlyEmissionsData

# TODO: what is this for?
pd.options.mode.chained_assignment = None


class URBANoptResults:
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
            raise Exception(
                f"Could not find {self.path} for the URBANopt results. Will not continue."
            )

        # check if the run with the scenario name exists
        if not (self.path / "run" / f"{scenario_name}").exists():
            raise Exception(
                f"Could not find {self.path / 'run' / scenario_name} for the URBANopt results. Will not continue."
            )

        # path to store outputs not specific to the scenario
        self.output_path = self.path / "output"

        # initialize the analysis display name to the scenario name, but this can be changed
        self.display_name = scenario_name
        print(f"URBANopt analysis name {self.display_name}")

        # This is the default data resolution, which has to be 60 minutes!
        self.data = None
        # create object to store 15min data.
        self.data_15min = None

        self.data_monthly = None
        self.data_annual = None
        self.end_use_summary = None

        self.grid_metrics_daily = None
        self.grid_metrics_annual = None

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
            df_tmp = df_tmp.groupby([pd.Grouper(freq="1d")])[meter].agg(
                ["max", "idxmax", "min", "idxmin", "mean", "sum"]
            )

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
            df_tmp[f"{meter} Load Factor"] = (
                df_tmp[f"{meter} Mean"] / df_tmp[f"{meter} Max"]
            )

            # add in the system ramping, which has to be calculated from the original data frame
            df_tmp2 = self.data_15min_to_process.copy()
            df_tmp2[f"{meter} System Ramping"] = df_tmp2[meter].diff().abs().fillna(0)
            df_tmp2 = (
                df_tmp2.groupby([pd.Grouper(freq="1d")])[f"{meter} System Ramping"].agg(
                    ["sum"]
                )
                / 1e6
            )
            df_tmp2.columns = [f"{meter} System Ramping"]

            df_tmp = pd.concat([df_tmp, df_tmp2], axis=1, join="inner")
            if self.grid_metrics_daily is None:
                self.grid_metrics_daily = df_tmp
            else:
                self.grid_metrics_daily = pd.concat(
                    [self.grid_metrics_daily, df_tmp], axis=1, join="inner"
                )

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

        df_tmp = df_tmp.groupby([pd.Grouper(freq="1y")]).agg(aggs)
        # rename the columns
        df_tmp.columns = [f"{c[0]} {c[1]}" for c in df_tmp.columns]
        # this is a strange section, the idxmax/idxmin are the indexes where the max/min values
        # were found, but we want the timestamps from the original dataframe, so go get them!
        for meter in meters:
            # there is only one year of data, so grab the idmax/idmin of the first element. If
            # we expand to multiple years, then this will need to be updated
            id_lookup = df_tmp[f"{meter} Max idxmax"][0]
            df_tmp[f"{meter} Max idxmax"] = self.grid_metrics_daily.loc[id_lookup][
                f"{meter} Max Datetime"
            ]
            id_lookup = df_tmp[f"{meter} Min idxmin"][0]
            df_tmp[f"{meter} Min idxmin"] = self.grid_metrics_daily.loc[id_lookup][
                f"{meter} Min Datetime"
            ]
            # rename these two columns to remove the idxmax/idxmin nomenclature
            df_tmp = df_tmp.rename(
                columns={
                    f"{meter} Max idxmax": f"{meter} Max Datetime",
                    f"{meter} Min idxmin": f"{meter} Min Datetime",
                }
            )

        # Add the MWh related metrics, can't sum up the 15 minute data, so we have to sum up the hourly
        df_tmp["Total Electricity"] = (
            self.data["Total Electricity"].resample("1y").sum() / 1e6
        )  # MWh
        df_tmp["Total Natural Gas"] = (
            self.data["Total Natural Gas"].resample("1y").sum() / 1e6
        )  # MWh
        df_tmp["Total Thermal Cooling Energy"] = (
            self.data["Total Thermal Cooling Energy"].resample("1y").sum() / 1e6
        )  # MWh
        df_tmp["Total Thermal Heating Energy"] = (
            self.data["Total Thermal Heating Energy"].resample("1y").sum() / 1e6
        )  # MWh

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
                df_to_proc.sort_values(by=meter, ascending=True, inplace=True)
            else:
                df_to_proc.sort_values(by=meter, ascending=False, inplace=True)
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

    def create_summary(self):
        """Create an annual summary by selecting key variables and values and transposing them for easy comparison"""
        # now create the summary table
        summary_columns = [
            {
                "name": "Total Building Interior Lighting",
                "units": "Wh",
                "display_name": "Interior Lighting",
            },
            {
                "name": "Total Building Exterior Lighting",
                "units": "Wh",
                "display_name": "Exterior Lighting",
            },
            {
                "name": "Total Building Interior Equipment",
                "units": "Wh",
                "display_name": "Plug Loads",
            },
            {
                "name": "Total Building HVAC Cooling Energy",
                "units": "Wh",
                "display_name": "Building Cooling",
            },
            {
                "name": "Total Building HVAC Heating Energy",
                "units": "Wh",
                "display_name": "Building Heating",
            },
            {
                "name": "Total Building Fans Electricity",
                "units": "Wh",
                "display_name": "Building Fans",
            },
            {
                "name": "Total Building Pumps Electricity",
                "units": "Wh",
                "display_name": "Building Pumps",
            },
            {
                "name": "Total Building Heat Rejection Electricity",
                "units": "Wh",
                "display_name": "Building Heat Rejection",
            },
            {
                "name": "Total Building Water Systems",
                "units": "Wh",
                "display_name": "Building Water Systems",
            },
            {
                "name": "ETS Pump Electricity Total",
                "units": "Wh",
                "display_name": "ETS Pump Total",
            },
            {
                "name": "ETS Heat Pump Electricity Total",
                "units": "Wh",
                "display_name": "ETS Heat Pump",
            },
            {
                "name": "Sewer Pump Electricity",
                "units": "Wh",
                "display_name": "Sewer Pump",
            },
            {
                "name": "GHX Pump Electricity",
                "units": "Wh",
                "display_name": "GHX Pump",
            },
            {
                "name": "Distribution Pump Electricity",
                "units": "Wh",
                "display_name": "Distribution Pump",
            },
            {
                "name": "Total Electricity",
                "units": "Wh",
                "display_name": "Total Electricity",
            },
            {
                "name": "Total Natural Gas",
                "units": "Wh",
                "display_name": "Total Natural Gas",
            },
            {
                "name": "Total Thermal Cooling Energy",
                "units": "Wh",
                "display_name": "Thermal Cooling",
            },
            {
                "name": "Total Thermal Heating Energy",
                "units": "Wh",
                "display_name": "Thermal Heating",
            },
            {
                "name": "District Loop Energy",
                "units": "Wh",
                "display_name": "District Loop Energy",
            },
            {
                "name": "Total Natural Gas Carbon Emissions",
                "units": "mtCO2e",
                "display_name": "Total Natural Gas Carbon Emissions",
            },
            {
                "name": "Total Electricity Carbon Emissions 2024",
                "units": "mtCO2e",
                "display_name": "Total Electricity Carbon Emissions 2024",
            },
            {
                "name": "Total Electricity Carbon Emissions 2045",
                "units": "mtCO2e",
                "display_name": "Total Electricity Carbon Emissions 2045",
            },
            {
                "name": "Total Carbon Emissions 2024",
                "units": "mtCO2e",
                "display_name": "Total Carbon Emissions 2024",
            },
            {
                "name": "Total Carbon Emissions 2045",
                "units": "mtCO2e",
                "display_name": "Total Carbon Emissions 2045",
            },
        ]

        # get the list of all the columns to allocate the data frame correctly
        columns = [c["display_name"] for c in summary_columns]

        # Create a single column of data
        self.end_use_summary = pd.DataFrame(
            index=columns,
            columns=["Units", "Non-Connected"],
            data=np.zeros((len(columns), 2)),
        )

        # add the units column if it isn't already there
        self.end_use_summary["Units"] = [c["units"] for c in summary_columns]

        # create a CSV file for the summary table with
        # the columns as the rows and the results as the columns
        for column in summary_columns:
            # check if the column exists in the data frame and if not, then set the value to zero!
            if column["name"] in self.data_annual.columns:
                self.end_use_summary["Non-Connected"][column["display_name"]] = float(
                    self.data_annual[column["name"]].iloc[0]
                )
            else:
                self.end_use_summary["Non-Connected"][column["display_name"]] = 0.0

        return self.end_use_summary

    def save_dataframes(self) -> None:
        """Save the data and data_15min dataframes to the outputs directory."""
        self.data.to_csv(self.output_path / "power_60min.csv")
        self.data_15min.to_csv(self.output_path / "power_15min.csv")
        if self.data_monthly is not None:
            self.data_monthly.to_csv(self.output_path / "power_monthly.csv")

        if self.data_annual is not None:
            self.data_annual.to_csv(self.output_path / "power_annual.csv")

        if self.grid_metrics_daily is not None:
            self.grid_metrics_daily.to_csv(self.output_path / "grid_metrics_daily.csv")

        if self.grid_metrics_annual is not None:
            self.grid_metrics_annual.to_csv(
                self.output_path / "grid_metrics_annual.csv"
            )

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
                building_aggs["Total Building Electricity"]["agg_columns"].append(
                    f"Electricity:Facility Building {i}"
                )
                building_aggs["Total Building Natural Gas"]["agg_columns"].append(
                    f"NaturalGas:Facility Building {i}"
                )
                # Building level HVAC aggregations
                building_aggs["Total Building Cooling Electricity"][
                    "agg_columns"
                ].append(f"Cooling:Electricity Building {i}")
                building_aggs["Total Building Heating Electricity"][
                    "agg_columns"
                ].append(f"Heating:Electricity Building {i}")
                building_aggs["Total Building Heating Natural Gas"][
                    "agg_columns"
                ].append(
                    f"Heating:NaturalGas Building {i}",
                )
                building_aggs["Total Building Fans Electricity"]["agg_columns"].append(
                    f"Fans:Electricity Building {i}"
                )
                building_aggs["Total Building Pumps Electricity"]["agg_columns"].append(
                    f"Pumps:Electricity Building {i}"
                )
                building_aggs["Total Building Heat Rejection Electricity"][
                    "agg_columns"
                ].append(f"HeatRejection:Electricity Building {i}")
                building_aggs["Total Building Heat Rejection Natural Gas"][
                    "agg_columns"
                ].append(f"HeatRejection:NaturalGas Building {i}")
                building_aggs["Total Building Water Systems Natural Gas"][
                    "agg_columns"
                ].append(f"WaterSystems:NaturalGas Building {i}")
                building_aggs["Total Building Water Systems Electricity"][
                    "agg_columns"
                ].append(f"WaterSystems:Electricity Building {i}")

                # Interior and exterior lighting
                building_aggs["Total Building Interior Lighting"]["agg_columns"].append(
                    f"InteriorLights:Electricity Building {i}"
                )
                building_aggs["Total Building Exterior Lighting"]["agg_columns"].append(
                    f"ExteriorLights:Electricity Building {i}"
                )

                # Interior and exterior equipment
                building_aggs["Total Building Interior Equipment Electricity"][
                    "agg_columns"
                ].append(f"InteriorEquipment:Electricity Building {i}")
                building_aggs["Total Building Interior Equipment Natural Gas"][
                    "agg_columns"
                ].append(f"InteriorEquipment:NaturalGas Building {i}")
                building_aggs["Total Building Exterior Equipment Electricity"][
                    "agg_columns"
                ].append(f"ExteriorEquipment:Electricity Building {i}")
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
            self.data_15min["Total Electricity"] = self.data_15min[
                "Total Building Electricity"
            ]
            self.data["Total Natural Gas"] = self.data["Total Building Natural Gas"]
            self.data_15min["Total Natural Gas"] = self.data_15min[
                "Total Building Natural Gas"
            ]
            self.data["Total ETS Electricity"] = 0
            self.data_15min["Total ETS Electricity"] = 0
            self.data["Total Thermal Cooling Energy"] = 0
            self.data_15min["Total Thermal Cooling Energy"] = 0
            self.data["Total Thermal Heating Energy"] = 0
            self.data_15min["Total Thermal Heating Energy"] = 0
            self.data["District Loop Energy"] = 0
            self.data_15min["District Loop Energy"] = 0
            # Now mix energy types for the totals
            self.data["Total Energy"] = (
                self.data["Total Electricity"] + self.data["Total Natural Gas"]
            )
            self.data_15min["Total Energy"] = (
                self.data_15min["Total Electricity"]
                + self.data_15min["Total Natural Gas"]
            )
            self.data["Total Building and ETS Energy"] = (
                self.data["Total Building Electricity"]
                + self.data["Total Building Natural Gas"]
                + self.data["Total ETS Electricity"]
            )
            self.data_15min["Total Building and ETS Energy"] = (
                self.data_15min["Total Building Electricity"]
                + self.data_15min["Total Building Natural Gas"]
                + self.data_15min["Total ETS Electricity"]
            )

        finally:
            pass

    def process_results(
        self, building_names: list[str], year_of_data: int = 2017
    ) -> None:
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
        for building_id in building_names:
            print(f"Processing building {building_id}")
            feature_report = self.get_urbanopt_default_feature_report(
                self.path / "run" / f"{self.scenario_name}" / f"{building_id}"
            )
            # print(feature_report.head())
            # rename and convert units in the feature_report before concatenating with the others
            for (
                column_name,
                feature_column,
            ) in self.get_urbanopt_feature_report_columns().items():
                if feature_column.get("skip_renaming", False):
                    continue
                # set the new column name to include the building number
                new_column_name = f"{feature_column['name']} Building {building_id}"
                feature_report[new_column_name] = (
                    feature_report[column_name] * feature_column["conversion"]
                )
                feature_report = feature_report.drop(columns=[column_name])

            # convert Datetime column in data frame to be datetime from the string. The year
            # should be set to a year that has the day of week starting correctly for the real data
            # This defaults to year_of_data
            feature_report["Datetime"] = pd.to_datetime(
                feature_report["Datetime"], format="%Y/%m/%d %H:%M:%S"
            )
            feature_report["Datetime"] = feature_report["Datetime"].apply(
                lambda x: x.replace(year=year_of_data)
            )

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
            self.data["Total Building Natural Gas"]
            * hourly_emissions_data.other_fuels["natural_gas"]
            / 1e6
            / 1000
        )
        self.data["Total Natural Gas Carbon Emissions"] = self.data[
            "Total Building Natural Gas Carbon Emissions"
        ]

        # Calculate the electricity carbon emissions, emissions data is in kg/MWh, so Wh->Mwh, then divide by another 1000 to get mtCO2e
        self.data[f"Total Electricity Carbon Emissions {future_year}"] = (
            self.data["Total Electricity"]
            * hourly_emissions_data.data[lookup_egrid_subregion]
            / 1e6
            / 1000
        )
        # units are in kg, convert to metric tons
        self.data[f"Total Carbon Emissions {future_year}"] = (
            self.data["Total Natural Gas Carbon Emissions"]
            + self.data[f"Total Electricity Carbon Emissions {future_year}"]
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
            meter_names_for_building = [
                meter_name + f" {building_id}" for meter_name in meter_names
            ]

        for df in [self.data, self.data_15min]:
            # for each building_id in the scalar dataframe. Be careful not
            # to apply scaling factors to the same building twice from multiple
            # files.
            elec_meters = [
                meter_name
                for meter_name in meter_names_for_building
                if "Electricity" in meter_name
            ]
            ng_meters = [
                meter_name
                for meter_name in meter_names_for_building
                if "NaturalGas" in meter_name
            ]
            for meter_type in ["Electricity", "NaturalGas"]:
                # for each row in the analysis results dataframe, grab the scalar and multiply it by the meter
                # print(f"Applying scalars for meter year {year_of_meters}, sim year {year_of_data}, building {building_id}, and meter {meter_type}")
                for _, scalar in scalars[
                    scalars["start_time"].dt.year == year_of_meters
                ].iterrows():
                    # this is strange, but we compare the year of the meter with the year of the simulation, which
                    # can be different. So convert the 'start_time' and 'end_time' of the meters to be the year of the
                    # dataframe data
                    scalar["start_time"] = scalar["start_time"].replace(
                        year=year_of_data
                    )
                    scalar["end_time"] = scalar["end_time"].replace(year=year_of_data)
                    row_filter = (df.index >= scalar["start_time"]) & (
                        df.index <= scalar["end_time"]
                    )
                    elec_scalar = scalar["scaling_factor_electricity"]
                    ng_scalar = scalar["scaling_factor_natural_gas"]
                    # print(f"data range: {scalar['start_time']} to {scalar['end_time']} with elec scalar {elec_scalar} and ng scalar {ng_scalar}")
                    if (
                        meter_type == "Electricity"
                        and elec_scalar is not None
                        and not pd.isna(elec_scalar)
                    ):
                        df.loc[row_filter, elec_meters] = (
                            df.loc[row_filter, elec_meters] * elec_scalar
                        )
                    elif (
                        meter_type == "NaturalGas"
                        and ng_scalar is not None
                        and not pd.isna(ng_scalar)
                    ):
                        df.loc[row_filter, ng_meters] = (
                            df.loc[row_filter, ng_meters] * ng_scalar
                        )

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
            elif "NaturalGas" in key:
                columns[key]["unit_original"] = "kBtu"
                columns[key]["units"] = "Wh"
                columns[key]["conversion"] = 293.071  # 1 kBtu = 293.071 Wh
                columns[key]["name"] = key
                columns[key]["description"] = key
            elif "DistrictCooling" in key or "DistrictHeating" in key:
                columns[key]["unit_original"] = "kBtu"
                columns[key]["units"] = "Wh"
                columns[key]["conversion"] = 293.071  # 1 kBtu = 293.071 Wh
                columns[key]["name"] = key
                columns[key]["description"] = key
            elif "Datetime" == key:
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

    def get_urbanopt_default_feature_report(self, search_dir: Path):
        """Return the default report from the URBANopt / EnergyPlus simulation."""
        # get the default report
        report_file = search_dir / "feature_reports" / "default_feature_report.csv"
        if not report_file.exists():
            # check if it is in a named directory in the form of XXX_default_feature_report/
            dirs = list(search_dir.glob("*_default_feature_reports"))
            if len(dirs) == 1:
                report_file = dirs[0] / "default_feature_reports.csv"
            elif len(dirs) == 0:
                raise Exception(
                    f"Could not find default_feature_report.csv in {search_dir}"
                )
            else:
                raise Exception(
                    f"More than one default_feature_reports.csv found in dirs: {dirs}"
                )

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
                if column_wo_units not in desired_columns.keys():
                    # then move on, because we don't care about this column
                    # print(f'Column {column_wo_units} not desired.')
                    continue

                # extract the units if they exist and check against desired. It is okay if units are blank, we
                # just assume that they are what we wanted.
                if not units == "" and units is not None:
                    if units != desired_columns[column_wo_units]["unit_original"]:
                        raise Exception(
                            f"Units of {units} for {column_wo_units} are not {desired_columns[column_wo_units]['unit_original']}"
                        )

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
            raise Exception(
                f"Could not find default_feature_report.csv in {search_dir}"
            )
