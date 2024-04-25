import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Union

import numpy as np
import pandas as pd
from buildingspy.io.outputfile import Reader

from .emissions import HourlyEmissionsData

VariablesDict = Dict[str, Union[bool, str, int, str]]


class ModelicaResults:
    """Catch for modelica methods. This needs to be refactored"""

    def __init__(self, mat_filename: Path) -> None:
        """Class for holding the results of a Modelica simulation. This class will handle the post processing
        necessary to create data frames that can be easily compared with other simulation results including
        OpenStudio-based results.

        Args:
            mat_filename (Path): Fully qualified path to the .mat file to load and process
        """
        super().__init__()

        self.mat_filename = mat_filename
        # Resulting files will always be stored alongside the .mat file.
        self.path = self.mat_filename.parent
        # read in the mat file
        if self.mat_filename.exists():
            self.modelica_data = Reader(self.mat_filename, "dymola")
        else:
            raise Exception(f"Could not find {self.mat_filename}. Will not continue.")

        # initialize the analysis name to the scenario name, but this can be changed
        self.display_name = self.path.name

        # member variables in which to store downsampled data
        self.min_5 = None
        self.min_15 = None
        self.min_15_with_buildings = None
        self.min_60 = None
        self.min_60_with_buildings = None
        self.monthly = None
        self.annual = None
        self.end_use_summary = None
        self.grid_metrics_daily = None
        self.grid_metrics_annual = None

    def save_variables(self) -> dict:
        """Save the names of the Modelica variables, including the descriptions and units (if available).
        Returns a dataframe of the variables to enable look up of units and descriptions.

        Returns:
            dict: Dictionary of the variables
        """
        modelica_variables: VariablesDict = {}
        for var in self.modelica_data.varNames():
            description = self.modelica_data._data_.description(var)
            # parse out the variable, if it exists, it will be in square brackets
            if "[" in description:
                units = description.split("[")[-1].split("]")[0]

                # more cleanup should happen, e.g.,
                #   :#(type=Modelica.Blocks.Types.Init) -> ???
                #   Pa|Pa -> ???
            else:
                units = None

            modelica_variables[var] = {}
            modelica_variables[var]["description"] = description
            modelica_variables[var]["unit_original"] = units
            modelica_variables[var]["units"] = units
            modelica_variables[var]["conversion"] = 1
            modelica_variables[var]["name"] = var

            # if the variable is CPUtime, then add skip_renaming
            if var == "CPUtime":
                modelica_variables[var]["skip_renaming"] = True

        with open(self.path / "modelica_variables.json", "w") as f:
            json.dump(modelica_variables, f, indent=2)

        return modelica_variables

    def number_of_buildings(self, building_count_var: str = "nBui") -> int:
        """Return the number of buildings from the Modelica data

        Args:
            building_count_var (str, optional): Variable that defines the count of buildings. Defaults to 'nBui'.

        Returns:
            int: Number of buildings
        """
        _, n_buildings = self.modelica_data.values(building_count_var)
        return int(n_buildings[0])

    def resample_and_convert_to_df(
        self,
        building_ids: Union[list[str], None] = None,
        other_vars: Union[list[str], None] = None,
        year_of_data: int = 2017,
    ) -> None:
        """The Modelica data (self.modelica_data) are stored in a Reader object and the timesteps are non ideal for comparison across models. The method handles
        a very specific set of variables which are extracted from the Reader object. After the data are stored in a DataFrame with the correct timesteps and units,
        then the data will be resampled to 5min, 15min, and 60min.

        Args:
            building_ids (Union[list[str], None], optional): Name of the buildings to process out of the Modelica data. Defaults to None.
            other_vars (Union[list[str], None], optional): Other variables to extract and store in the dataframe. Defaults to None.
            year_of_data (int, optional): Year of the data, should match the URBANopt/OpenStudio/EnergyPlus value and correct starting day of week. Defaults to 2017.

        Raises:
            Exception: errors
        """
        # get the number of buildings
        n_buildings = self.number_of_buildings()

        # get the building names from the passed data, if it is there, else use the
        # index of the building number.
        if building_ids:
            if len(building_ids) != n_buildings:
                raise Exception(
                    f"The number of building names {len(building_ids)} does not match the number of buildings in the Modelica model {n_buildings}."
                )
        else:
            building_ids = [f"{i}" for i in range(1, n_buildings + 1)]

        (time1, total_energy) = self.modelica_data.values("ETot.y")

        # Plant/pumps
        (_, sewer_pump) = self.modelica_data.values("pla.PPum")
        (_, ghx_pump) = self.modelica_data.values("pumSto.P")
        (_, distribution_pump) = self.modelica_data.values("pumDis.P")

        # building related data
        building_data: dict[str, list[float]] = {}

        agg_columns: dict[str, list[str]] = {
            "ETS Heat Pump Electricity Total": [],
            "ETS Pump Electricity Total": [],
            "ETS Thermal Cooling Total": [],
            "ETS Thermal Heating Total": [],
        }
        for n_b in range(1, n_buildings + 1):
            # get the building name
            building_id = building_ids[n_b - 1]
            # Note that these P.*.u variables do not have units defined in the vars, but they are Watts
            (_, ets_pump_data) = self.modelica_data.values(f"PPumETS.u[{n_b}]")
            (_, ets_hp_data) = self.modelica_data.values(f"PHeaPump.u[{n_b}]")

            # Thermal Energy to buildings
            (_, ets_q_cooling) = self.modelica_data.values(f"bui[{n_b}].QCoo_flow")
            (_, ets_q_heating) = self.modelica_data.values(f"bui[{n_b}].QHea_flow")

            agg_columns["ETS Pump Electricity Total"].append(
                f"ETS Pump Electricity Building {building_id}"
            )
            agg_columns["ETS Heat Pump Electricity Total"].append(
                f"ETS Heat Pump Electricity Building {building_id}"
            )
            agg_columns["ETS Thermal Cooling Total"].append(
                f"ETS Thermal Cooling Building {building_id}"
            )
            agg_columns["ETS Thermal Heating Total"].append(
                f"ETS Thermal Heating Building {building_id}"
            )
            building_data[f"ETS Pump Electricity Building {building_id}"] = (
                ets_pump_data
            )
            building_data[f"ETS Heat Pump Electricity Building {building_id}"] = (
                ets_hp_data
            )
            building_data[f"ETS Thermal Cooling Building {building_id}"] = ets_q_cooling
            building_data[f"ETS Thermal Heating Building {building_id}"] = ets_q_heating

        # convert time to timestamps for pandas
        time = [
            datetime(year_of_data, 1, 1, 0, 0, 0) + timedelta(seconds=int(t))
            for t in time1
        ]

        # convert into data frame
        df_energy = pd.pandas.DataFrame(
            {"datetime": time, "Total DES Electricity": total_energy}
        )
        df_energy = df_energy.set_index("datetime")
        df_energy = df_energy.resample("60min").max()
        # set the index name so that it exports nicely
        df_energy.index.name = "datetime"

        # all data combined
        data = {
            "datetime": time,
            "Sewer Pump Electricity": sewer_pump,
            "GHX Pump Electricity": ghx_pump,
            "Distribution Pump Electricity": distribution_pump,
        } | building_data

        # add in the 'other variables' if they exist
        if other_vars is not None:
            for other_var in other_vars:
                if other_var in self.modelica_data.varNames():
                    (_, other_var_data) = self.modelica_data.values(other_var)
                    # check the length of the data
                    if len(other_var_data) == len(time):
                        data[other_var] = other_var_data
                    else:
                        print(
                            f'Other var "{other_var}" length does not match {len(other_var_data)} != {len(time)}'
                        )

        df_power = pd.pandas.DataFrame(data)

        # create aggregation columns for total pumps, total heat pumps, and total
        df_power["ETS Pump Electricity Total"] = df_power[
            agg_columns["ETS Pump Electricity Total"]
        ].sum(axis=1)
        df_power["ETS Heat Pump Electricity Total"] = df_power[
            agg_columns["ETS Heat Pump Electricity Total"]
        ].sum(axis=1)
        df_power["Total Thermal Cooling Energy"] = df_power[
            agg_columns["ETS Thermal Cooling Total"]
        ].sum(axis=1)
        df_power["Total Thermal Heating Energy"] = df_power[
            agg_columns["ETS Thermal Heating Total"]
        ].sum(axis=1)

        # Calculate the District Loop Power - if the columns exists
        # check if multiple columns are in a dataframe
        if all(
            column in df_power.columns
            for column in ["TDisWatRet.port_a.m_flow", "TDisWatRet.T", "TDisWatSup.T"]
        ):
            # \dot{m} * c_p * \Delta T with Water at (4186 J/kg/K)
            df_power["District Loop Energy"] = (
                df_power["TDisWatRet.port_a.m_flow"]
                * 4186
                * abs(df_power["TDisWatRet.T"] - df_power["TDisWatSup.T"])
            )

        column_names = [
            "ETS Pump Electricity Total",
            "ETS Heat Pump Electricity Total",
            "Sewer Pump Electricity",
            "GHX Pump Electricity",
            "Distribution Pump Electricity",
        ]
        df_power["Total DES Electricity"] = df_power[column_names].sum(axis=1)

        # sum up all ETS data (pump and heat pump)
        df_power.to_csv(self.path / "power_original.csv")
        df_power.drop_duplicates(subset="datetime", inplace=True)
        df_power = df_power.set_index("datetime")

        # upsample to 1min with filling the last. This will
        # give us more accuracy on the energy use since it weights
        # the power a bit more.
        df_power_1min = df_power.resample("1min").ffill()

        # now resample / downsample everything
        self.min_5 = df_power_1min.resample("5min").mean()
        self.min_15 = self.min_5.resample("15min").mean()
        self.min_60 = self.min_15.resample("60min").mean()

        return True

    def combine_with_openstudio_results(
        self,
        building_ids: Union[list[str], None],
        openstudio_df: pd.DataFrame,
        openstudio_df_15: pd.DataFrame,
    ) -> None:
        """Only combine the end uses, not the total energy since that needs to be
        recalculated based on the modelica results. Basically, this only looks at the columns that are not
        HVAC related.

        Args:
            building_ids (Union[list[str], None]): Name of the buildings
            openstudio_df (pd.DataFrame): dataframe of URBANopt/OpenStudio hourly results
            openstudio_df_15 (pd.DataFrame): dataframe of URBANopt/OpenStudio 15min results
        Returns:
            NoneType: None
        """
        # create the list of columns from the building name
        building_meter_names = [
            # by building end use and fuel type
            "InteriorLights:Electricity Building",
            "ExteriorLights:Electricity Building",
            "InteriorEquipment:Electricity Building",
            "ExteriorEquipment:Electricity Building",
            "InteriorEquipment:NaturalGas Building",
        ]
        meter_names = [
            f"{meter_name} {building_id}"
            for building_id in building_ids
            for meter_name in building_meter_names
        ]
        # add in the end use totals that are non-HVAC
        meter_names += [
            "Total Building Interior Lighting",
            "Total Building Exterior Lighting",
            "Total Building Interior Equipment Electricity",
            "Total Building Exterior Equipment Electricity",
            "Total Building Interior Equipment Natural Gas",
            "Total Building Interior Equipment",
        ]

        self.min_60_with_buildings = pd.concat(
            [self.min_60, openstudio_df[meter_names]], axis=1, join="inner"
        )
        self.min_60_with_buildings.index.name = "datetime"

        # also conduct this for the 15 minute time step
        self.min_15_with_buildings = pd.concat(
            [self.min_15, openstudio_df_15[meter_names]], axis=1, join="inner"
        )
        self.min_15_with_buildings.index.name = "datetime"

        # should we resort the columns?

        return None

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
            columns=["Units", self.display_name],
            data=np.zeros((len(columns), 2)),
        )

        # add the units column if it isn't already there
        self.end_use_summary["Units"] = [c["units"] for c in summary_columns]

        # create a CSV file for the summary table with
        # the columns as the rows and the results as the columns
        for column in summary_columns:
            # check if the column exists in the data frame and if not, then set the value to zero!
            if column["name"] in self.annual.columns:
                self.end_use_summary[self.display_name][column["display_name"]] = float(
                    self.annual[column["name"]].iloc[0]
                )
            else:
                self.end_use_summary[self.display_name][column["display_name"]] = 0.0

        return self.end_use_summary

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
        if len(hourly_emissions_data.data) != len(self.min_60_with_buildings):
            raise Exception(
                f"Length of emissions data {len(hourly_emissions_data.data)} does not match the length of the min_60_with_buildings data {len(self.min_60_with_buildings)}."
            )

        # also verify the length of the other_fuels
        if len(hourly_emissions_data.other_fuels) != len(self.min_60_with_buildings):
            raise Exception(
                f"Length of other fuel emission data {len(hourly_emissions_data.data)} does not match the length of the min_60_with_buildings data {len(self.min_60_with_buildings)}."
            )

        # Calculate the natural gas emissions, emissions data is in kg/MWh so Wh->MWh, then divide by another 1000 to get mtCO2e
        self.min_60_with_buildings["Total Building Natural Gas Carbon Emissions"] = (
            self.min_60_with_buildings["Total Building Natural Gas"]
            * hourly_emissions_data.other_fuels["natural_gas"]
            / 1e6
            / 1000
        )
        self.min_60_with_buildings["Total Natural Gas Carbon Emissions"] = (
            self.min_60_with_buildings["Total Building Natural Gas Carbon Emissions"]
        )

        # Calculate the electricity carbon emissions, emissions data is in kg/MWh, so Wh->Mwh, then divide by another 1000 to get mtCO2e
        self.min_60_with_buildings[
            f"Total Electricity Carbon Emissions {future_year}"
        ] = (
            self.min_60_with_buildings["Total Electricity"]
            * hourly_emissions_data.data[lookup_egrid_subregion]
            / 1e6
            / 1000
        )
        # Sum the total carbon emissions
        self.min_60_with_buildings[f"Total Carbon Emissions {future_year}"] = (
            self.min_60_with_buildings["Total Natural Gas Carbon Emissions"]
            + self.min_60_with_buildings[
                f"Total Electricity Carbon Emissions {future_year}"
            ]
        )

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
        """Calculate the grid metrics for this building."""
        # recreate the grid_metrics_daily data frame in case we are overwriting it.

        self.min_15_with_buildings_to_process = self.min_15_with_buildings.copy()

        # skip n-days at the beginning of the grid metrics, due to
        # warm up times that have yet to be resolved.
        n_days = 2
        skip_time = n_days * 96
        self.min_15_with_buildings_to_process = (
            self.min_15_with_buildings_to_process.iloc[skip_time:]
        )
        # # END NEED TO FIX

        # # THIS IS HARD CODED -- NEED TO FIX!
        # # Start with the latest in the year...

        # # remove 2017-02-06 -- 2017-02-07 from the data, as it is a warm up period
        # # convert 2/6 to hours
        # skip_time = 96 * (31)
        # # remove skip_time to skip_time + 96
        # print(f"Removing {skip_time} to {skip_time + 96} from the data")
        # # remove rows 96*31 to 96*38
        # self.min_15_with_buildings_to_process = self.min_15_with_buildings_to_process.drop(
        #     self.min_15_with_buildings_to_process.index[range(skip_time, skip_time + 168)]
        # )

        # END NEED TO FIX

        self.grid_metrics_daily = None
        for meter in meters:
            df_tmp = self.min_15_with_buildings_to_process.copy()
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
            df_tmp2 = self.min_15_with_buildings_to_process.copy()
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
            self.min_60_with_buildings["Total Electricity"].resample("1y").sum() / 1e6
        )  # MWh
        df_tmp["Total Natural Gas"] = (
            self.min_60_with_buildings["Total Natural Gas"].resample("1y").sum() / 1e6
        )  # MWh
        df_tmp["Total Thermal Cooling Energy"] = (
            self.min_60_with_buildings["Total Thermal Cooling Energy"]
            .resample("1y")
            .sum()
            / 1e6
        )  # MWh
        df_tmp["Total Thermal Heating Energy"] = (
            self.min_60_with_buildings["Total Thermal Heating Energy"]
            .resample("1y")
            .sum()
            / 1e6
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
            df_to_proc = self.min_15_with_buildings_to_process.copy()
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
        ],
    ):
        """Save all of the dataframes, assuming they are defined

        Args:
            dfs_to_save (list, optional): Which ones to save. Defaults to ['min_5', 'min_15', 'min_60', 'min_15_with_buildings', 'min_60_with_buildings', 'monthly', 'annual', 'summary'].
        """
        if self.min_5 is not None and "min_5" in dfs_to_save:
            self.min_5.to_csv(self.path / "power_5min.csv")
        if self.min_15 is not None and "min_15" in dfs_to_save:
            self.min_15.to_csv(self.path / "power_15min.csv")
        if self.min_60 is not None and "min_60" in dfs_to_save:
            self.min_60.to_csv(self.path / "power_60min.csv")
        if (
            self.min_15_with_buildings is not None
            and "min_15_with_buildings" in dfs_to_save
        ):
            self.min_15_with_buildings.to_csv(
                self.path / "power_15min_with_buildings.csv"
            )
        if (
            self.min_60_with_buildings is not None
            and "min_60_with_buildings" in dfs_to_save
        ):
            self.min_60_with_buildings.to_csv(
                self.path / "power_60min_with_buildings.csv"
            )

        # save the monthly and annual
        if self.monthly is not None and "monthly" in dfs_to_save:
            self.monthly.to_csv(self.path / "power_monthly.csv")
        if self.annual is not None and "annual" in dfs_to_save:
            self.annual.to_csv(self.path / "power_annual.csv")

        # save the summary
        if self.end_use_summary is not None and "end_use_summary" in dfs_to_save:
            self.end_use_summary.to_csv(self.path / "end_use_summary.csv")

        # save the metrics
        if self.grid_metrics_daily is not None and "grid_metrics_daily" in dfs_to_save:
            self.grid_metrics_daily.to_csv(self.path / "grid_metrics_daily.csv")
        if (
            self.grid_metrics_annual is not None
            and "grid_metrics_annual" in dfs_to_save
        ):
            self.grid_metrics_annual.to_csv(self.path / "grid_metrics_annual.csv")
