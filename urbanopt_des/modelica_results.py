import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from buildingspy.io.outputfile import Reader

from .emissions import HourlyEmissionsData
from .results_base import ResultsBase

_log = logging.getLogger(__name__)

VariablesDict = dict[str, bool | str | int]


class ModelicaResults(ResultsBase):
    """Catch for modelica methods. This needs to be refactored"""

    def __init__(self, mat_filename: Path, output_path: Path | None = None) -> None:
        """Class for holding the results of a Modelica simulation. This class will handle the post processing
        necessary to create data frames that can be easily compared with other simulation results including
        OpenStudio-based results.

        Args:
            mat_filename (Path): Fully qualified path to the .mat (or zipped .mat) file to load and process
            output_path (Path, optional): Path to save the post-processed data. Defaults to None.

        Raises:
            FileNotFoundError: If the path to a results file does not exist
            TypeError: If a results file type is neither .mat or a zip of a .mat file
        """
        super().__init__()

        if mat_filename.exists():
            # zip files are used for tests, and this
            if mat_filename.suffix == ".zip":
                from tempfile import TemporaryDirectory
                from zipfile import ZipFile

                # Extract the DistrictEnergySystem.mat file from the zip file to a temporary directory,
                # which will be deleted when the context manager exits
                with TemporaryDirectory() as temp_dir, ZipFile(mat_filename) as the_zip:
                    extracted_path = the_zip.extract(mat_filename.stem, path=temp_dir)
                    # Create a ModelicaResults object
                    self.mat_filename = Path(extracted_path)
                    self.modelica_data = Reader(extracted_path, "dymola")
            elif mat_filename.suffix == ".mat":
                self.mat_filename = mat_filename
                # read in the mat file
                self.modelica_data = Reader(self.mat_filename, "dymola")
            else:
                raise TypeError(f"File type {mat_filename.suffix} not supported. Will not continue.")
        else:
            raise FileNotFoundError(f"Could not find {mat_filename}. Will not continue.")

        # Determine where the outputs of the Modelica results post-processing will be stored.
        # Typically this is alongside the .mat file, but can be user defined.
        if output_path:
            self.path = output_path
        else:
            self.path = self.mat_filename.parent

        # initialize the analysis name to the scenario name, but this can be changed
        self.display_name = self.path.name

        # member variables in which to store downsampled data
        self.min_5 = None
        self.min_15 = None
        self.min_15_with_buildings = None
        self.min_60 = None
        self.min_60_with_buildings = None
        self.monthly = None
        self.data_annual = None
        self.end_use_summary = None
        self.grid_metrics_daily = None
        self.grid_metrics_annual = None

    def save_variables(self, path_to_save: Path | None = None) -> dict:
        """Save the names of the Modelica variables, including the descriptions and units (if available).
        Returns a dataframe of the variables to enable look up of units and descriptions.

        Args:
            path_to_save (Path, optional): Path to save the variables. Defaults to the default path of the .mat file.

        Returns:
            dict: Dictionary of the variables
        """
        if path_to_save is None:
            path_to_save = self.path

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

        with open(path_to_save / "modelica_variables.json", "w") as f:
            json.dump(modelica_variables, f, indent=2)

        return modelica_variables

    def number_of_buildings(self, building_count_var: str = "nBui") -> int:
        """Return the number of buildings from the Modelica data, if running aggregated results then
        this value is allowed to be a mismatch with the number of buildings in the GeoJSON file.

        Args:
            building_count_var (str, optional): Variable that defines the count of buildings. Defaults to 'nBui'.

        Returns:
            int: Number of buildings
        """
        # first check if the key appears in the variables
        if building_count_var in self.modelica_data.varNames():
            _, n_buildings = self.modelica_data.values(building_count_var)
            n_buildings = int(n_buildings[0])
        else:
            # find all of the nBui_disNet_* in the varNames. There is one for heating and cooling,
            # so the number of buildings should be equal (for now).
            n_buildings = 0
            for var in self.modelica_data.varNames():
                if "nBui_disNet" in var:
                    _, n_b = self.modelica_data.values(var)
                    n_b = int(n_b[0])
                    if n_buildings == 0:
                        n_buildings = n_b
                    elif n_b != n_buildings:
                        raise Exception(f"Number of buildings on the multiple distribution networks do not match: {n_b} != {n_buildings}")

        # TODO: implement a debugging method and then report this value
        # print(f"DEBUG: the .mat files has {n_buildings}")
        return n_buildings

    def retrieve_time_variable_list(self) -> list:
        """Retrieve the time variable from the .mat file which is tied to a variable. There are cases
        where the time on a variable is of different length than the other variables, so this method
        looks at the time variable and returns the time data."""
        lengths_of_time = []
        variables_of_time = []

        # Extend these with RegEx's as needed to look for other time dimensions in
        # .mat files.
        variables_for_time_array = [
            "TimeSerLoa_.*.PPum",
            "^heaPla.*.boiHotWat.boi.*.QWat_flow$",
            "^cooPla_.*mulChiSys.P.*",
            "ETot.y",
        ]

        for var in variables_for_time_array:
            time_var = None
            if var in self.modelica_data.varNames():
                print("DEBUG: found variable {var}")
                time_var = var
            else:
                # check if the variable is found in the varNames
                time_vars = self.modelica_data.varNames(var)
                if len(time_vars) == 0:
                    # there is no time variables found, so just continue
                    continue
                elif len(time_vars) > 1:
                    # pick the first if there is more than one
                    time_var = time_vars[0]

            if time_var:
                (time1, _) = self.modelica_data.values(time_var)
                lengths_of_time.append(len(time1))
                variables_of_time.append(time_var)
                print(f"DEBUG: found time var {time_var} of length {len(time1)}")

        # if empty throw error
        if len(variables_of_time) == 0:
            raise Exception("No time variables found in the Modelica data.")

        # do a quick check on the collected time variables. If they are not the same lengths, then
        # throw an error
        if len(set(lengths_of_time)) != 1:
            raise Exception(f"Time variables are not the same length: {lengths_of_time} for {variables_of_time}")

        return time1

    def retrieve_variable_data(self, variable_name: str, len_of_time: int, default_value: float = 0) -> list:
        """Retrieve the variable data from the .mat file. If the data doesn't exist,
        then fill a dataframe with default 0 values.

        Args:
            variable_name (str): Name of the variable to retrieve
            len_of_time (int): Length of the time variable to fill the dataframe with if not found
            default_value (int, optional): Default value to fill the dataframe with. Defaults to 0.

        Returns:
            list: List of the variable data
        """
        if variable_name in self.modelica_data.varNames():
            (time1, data1) = self.modelica_data.values(variable_name)
            # check that the length of time is the same in the data
            if len(time1) != len_of_time:
                raise Exception(
                    f"Length of time variable {len(time1)} does not match the length of the data {len_of_time} for {variable_name}"
                )
        else:
            print(f"DEBUG: variable {variable_name} not found, filling with default value")
            data1 = [default_value] * len_of_time

        return data1

    def resample_and_convert_to_df(
        self,
        building_ids: list[str] | None = None,
        other_vars: list[str] | None = None,
        year_of_data: int = 2017,
    ) -> None:
        """The Modelica data (self.modelica_data) are stored in a Reader object and the timesteps are non ideal for comparison across models. The method handles
        a very specific set of variables which are extracted from the Reader object. After the data are stored in a DataFrame with the correct timesteps and units,
        then the data will be resampled to 5min, 15min, and 60min.

        Args:
            building_ids (list[str] | None): Name of the buildings to process out of the Modelica data. Defaults to None.
            other_vars (list[str] | None): Other variables to extract and store in the dataframe. Defaults to None.
            year_of_data (int): Year of the data, should match the URBANopt/OpenStudio/EnergyPlus value and correct starting day of week. Defaults to 2017.

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

        time1 = self.retrieve_time_variable_list()
        print(f"Found time variable of length {len(time1)}")

        # variables for 5G
        total_energy = self.retrieve_variable_data("ETot.y", len(time1))

        # Plant/pumps
        sewer_pump = self.retrieve_variable_data("pla.PPum", len(time1))
        ghx_pump = self.retrieve_variable_data("pumSto.P", len(time1))
        distribution_pump = self.retrieve_variable_data("pumDis.P", len(time1))

        ### COOLING PLANT ###
        # Keep track of all the components, so that we can create the aggregation at the end
        cooling_plant_components = []
        chiller_data: dict[str, list[float]] = {}
        # 1. get the variables of all the chillers
        chiller_vars = self.modelica_data.varNames(r"cooPla_.*mulChiSys.P.*")
        # 2. get the data for all the chillers or default to 1 pump set to 0
        if len(chiller_vars) > 0:
            for var_id, chiller_var in enumerate(chiller_vars):
                energy = self.retrieve_variable_data(chiller_var, len(time1))
                chiller_data[f"Chiller {var_id + 1}"] = energy
                cooling_plant_components.append(f"Chiller {var_id + 1}")
        else:
            chiller_data["Chiller 1"] = [0] * len(time1)
            cooling_plant_components.append("Chiller 1")

        # Other cooling plant data
        cooling_plant_pumps: dict[str, list[float]] = {}

        # 1. get the variables of all the condenser water pumps, which is in e.g., cooPla_67e4a0e1.pumCW.P[1]
        cooling_plant_pumps_vars = self.modelica_data.varNames(r"cooPla_.*pumCW.P.\d.")
        # 2. get the data for all the pumps or default to 1 pump set to 0
        if len(cooling_plant_pumps_vars) > 0:
            for var_id, cooling_plant_pumps_var in enumerate(cooling_plant_pumps_vars):
                energy = self.retrieve_variable_data(cooling_plant_pumps_var, len(time1))
                cooling_plant_components.append(f"CW Pump {var_id + 1}")
                cooling_plant_pumps[f"CW Pump {var_id + 1}"] = energy
        else:
            print("DEBUG: no CW pumps found")
            cooling_plant_pumps["CW Pump"] = [0] * len(time1)
            cooling_plant_components.append("CW Pump")
        # 3. get the variables of all the chilled water pumps, which is in e.g., cooPla_67e4a0e1.pumCHW.P[1]
        cooling_plant_pumps_vars = self.modelica_data.varNames(r"cooPla_.*pumCHW.P.\d.")
        # 4. get the data for all the pumps or default to 1 pump set to 0
        if len(cooling_plant_pumps_vars) > 0:
            for var_id, cooling_plant_pumps_var in enumerate(cooling_plant_pumps_vars):
                energy = self.retrieve_variable_data(cooling_plant_pumps_var, len(time1))
                cooling_plant_components.append(f"CHW Pump {var_id + 1}")
                cooling_plant_pumps[f"CHW Pump {var_id + 1}"] = energy
        else:
            print("DEBUG: no CHW pumps found")
            cooling_plant_pumps["CHW Pump"] = [0] * len(time1)
            cooling_plant_components.append("CHW Pump")
        # 5. get the variables of the cooling tower fans
        cooling_plant_pumps_vars = self.modelica_data.varNames(r"cooPla_.*cooTowWitByp.PFan.\d.")
        # 6. get the data for all the fans or default to 1 pump set to 0
        if len(cooling_plant_pumps_vars) > 0:
            for var_id, cooling_plant_pumps_var in enumerate(cooling_plant_pumps_vars):
                energy = self.retrieve_variable_data(cooling_plant_pumps_var, len(time1))
                cooling_plant_components.append(f"Cooling Tower Fan {var_id + 1}")
                cooling_plant_pumps[f"Cooling Tower Fan {var_id + 1}"] = energy
        else:
            print("DEBUG: no cooling tower fans found")
            cooling_plant_pumps["Cooling Tower Fan"] = [0] * len(time1)
            cooling_plant_components.append("Cooling Tower Fan")

        ### HEATING PLANT ###
        # Keep track of all the components, so that we can create the aggregation at the end
        heating_plant_components = []
        boiler_data: dict[str, list[float]] = {}
        # 1. get the variables of all the boilers
        boiler_vars = self.modelica_data.varNames(r"heaPla.*boiHotWat.boi.\d..QFue_flow")
        # 2. get the data for all the chillers or default to 1 pump set to 0
        if len(boiler_vars) > 0:
            for var_id, boiler_var in enumerate(boiler_vars):
                energy = self.retrieve_variable_data(boiler_var, len(time1))
                boiler_data[f"Boiler {var_id + 1}"] = energy
                heating_plant_components.append(f"Boiler {var_id + 1}")
        else:
            boiler_data["Boiler 1"] = [0] * len(time1)
            heating_plant_components.append("Boiler 1")

        # Other heating plant data
        heating_plant_pumps: dict[str, list[float]] = {}
        # 1. get the variables of all the condenser water pumps, which is in e.g., cooPla_67e4a0e1.pumCW.P[1]
        heating_plant_pumps_vars = self.modelica_data.varNames(r"heaPla.*pumHW.P.\d.")
        # 2. get the data for all the pumps or default to 1 pump set to 0
        if len(heating_plant_pumps_vars) > 0:
            for var_id, heating_plant_pumps_var in enumerate(heating_plant_pumps_vars):
                energy = self.retrieve_variable_data(heating_plant_pumps_var, len(time1))
                heating_plant_components.append(f"HW Pump {var_id + 1}")
                heating_plant_pumps[f"HW Pump {var_id + 1}"] = energy
        else:
            print("DEBUG: no HW pumps found")
            heating_plant_pumps["HW Pump"] = [0] * len(time1)
            heating_plant_components.append("HW Pump")

        # building related data
        building_data: dict[str, list[float]] = {}

        agg_columns: dict[str, list[str]] = {
            "ETS Heat Pump Electricity Total": [],
            "ETS Pump CHW Electricity Total": [],
            "ETS Pump HHW Electricity Total": [],
            "ETS Pump Electricity Total": [],
            "ETS Thermal Cooling Total": [],
            "ETS Thermal Heating Total": [],
        }
        for n_b in range(1, n_buildings + 1):
            # get the building name as this is what is in the Modelica results
            building_id = building_ids[n_b - 1]

            # ETS heat pump power
            ets_hp_data = self.retrieve_variable_data(f"PHeaPump.u[{n_b}]", len(time1))

            # ETS pump data - disFloCoo is on the building_id, not the building number.
            ets_pump_data = self.retrieve_variable_data(f"PPumETS.u[{n_b}]", len(time1))  # This is ambient / 5g pump
            ets_pump_chw_data = self.retrieve_variable_data(f"TimeSerLoa_{building_id}.disFloCoo.PPum", len(time1))
            ets_pump_hhw_data = self.retrieve_variable_data(f"TimeSerLoa_{building_id}.disFloHea.PPum", len(time1))

            # Thermal energy to buildings
            ets_q_cooling = self.retrieve_variable_data(f"bui[{n_b}].QCoo_flow", len(time1))
            ets_q_heating = self.retrieve_variable_data(f"bui[{n_b}].QHea_flow", len(time1))

            building_data[f"ETS Pump Electricity Building {building_id}"] = ets_pump_data
            building_data[f"ETS Pump CHW Electricity Building {building_id}"] = ets_pump_chw_data
            building_data[f"ETS Pump HHW Electricity Building {building_id}"] = ets_pump_hhw_data
            building_data[f"ETS Heat Pump Electricity Building {building_id}"] = ets_hp_data
            building_data[f"ETS Thermal Cooling Building {building_id}"] = ets_q_cooling
            building_data[f"ETS Thermal Heating Building {building_id}"] = ets_q_heating

            # Add variables to aggregations - these keys have to be defined above too.
            # ETS Pump has CHW, HHW, and then total. -- total includes ambient + hhw + chw
            agg_columns["ETS Heat Pump Electricity Total"].append(f"ETS Heat Pump Electricity Building {building_id}")
            agg_columns["ETS Pump CHW Electricity Total"].append(f"ETS Pump CHW Electricity Building {building_id}")
            agg_columns["ETS Pump HHW Electricity Total"].append(f"ETS Pump CHW Electricity Building {building_id}")
            agg_columns["ETS Pump Electricity Total"].append(f"ETS Pump Electricity Building {building_id}")
            agg_columns["ETS Pump Electricity Total"].append(f"ETS Pump CHW Electricity Building {building_id}")
            agg_columns["ETS Pump Electricity Total"].append(f"ETS Pump HHW Electricity Building {building_id}")
            agg_columns["ETS Thermal Cooling Total"].append(f"ETS Thermal Cooling Building {building_id}")
            agg_columns["ETS Thermal Heating Total"].append(f"ETS Thermal Heating Building {building_id}")

        # Add in chiller aggregations
        agg_columns["Chillers Total"] = []
        for n_c in range(1, len(chiller_data.keys()) + 1):
            agg_columns["Chillers Total"].append(f"Chiller {n_c}")

        # Add in all of the cooling plant variables
        agg_columns["Cooling Plant Total"] = cooling_plant_components.copy()

        # Add in boiler aggregations
        agg_columns["Boilers Total"] = []
        for n_c in range(1, len(boiler_data.keys()) + 1):
            agg_columns["Boilers Total"].append(f"Boiler {n_c}")

        # Add in all of the heating plant variables
        agg_columns["Heating Plant Total"] = heating_plant_components.copy()

        # convert time to timestamps for pandas
        time = [datetime(year_of_data, 1, 1, 0, 0, 0) + timedelta(seconds=int(t)) for t in time1]

        # convert into data frame
        df_energy = pd.pandas.DataFrame({"datetime": time, "Total DES Electricity": total_energy})
        df_energy = df_energy.set_index("datetime")
        df_energy = df_energy.resample("60min").max()
        # set the index name so that it exports nicely
        df_energy.index.name = "datetime"

        # all data combined
        data = (
            {
                "datetime": time,
                "Sewer Pump Electricity": sewer_pump,
                "GHX Pump Electricity": ghx_pump,
                "Distribution Pump Electricity": distribution_pump,
            }
            | building_data
            | chiller_data
            | cooling_plant_pumps
            | boiler_data
            | heating_plant_pumps
        )

        # add in the 'other variables' if they exist
        if other_vars is not None:
            for other_var in other_vars:
                if other_var in self.modelica_data.varNames():
                    other_var_data = self.retrieve_variable_data(other_var, len(time1))
                    data[other_var] = other_var_data

        df_power = pd.DataFrame(data)

        # create aggregations for the cooling plant
        df_power["Total Chillers"] = df_power[agg_columns["Chillers Total"]].sum(axis=1)
        df_power["Total Cooling Plant"] = df_power[agg_columns["Cooling Plant Total"]].sum(axis=1)

        # create aggregations for the heating plant
        df_power["Total Boilers"] = df_power[agg_columns["Boilers Total"]].sum(axis=1)
        df_power["Total Heating Plant"] = df_power[agg_columns["Heating Plant Total"]].sum(axis=1)

        # create aggregation columns for total pumps, total heat pumps, and total
        df_power["ETS Pump Electricity Total"] = df_power[agg_columns["ETS Pump Electricity Total"]].sum(axis=1)
        df_power["ETS Heat Pump Electricity Total"] = df_power[agg_columns["ETS Heat Pump Electricity Total"]].sum(axis=1)
        df_power["Total Thermal Cooling Energy"] = df_power[agg_columns["ETS Thermal Cooling Total"]].sum(axis=1)
        df_power["Total Thermal Heating Energy"] = df_power[agg_columns["ETS Thermal Heating Total"]].sum(axis=1)

        # Calculate the District Loop Power - Default to zero to start with
        df_power["District Loop Energy"] = 0
        # check if multiple columns are in a dataframe
        if all(column in df_power.columns for column in ["TDisWatRet.port_a.m_flow", "TDisWatRet.T", "TDisWatSup.T"]):
            # \dot{m} * c_p * \Delta T with Water at (4186 J/kg/K)
            df_power["District Loop Energy"] = (
                df_power["TDisWatRet.port_a.m_flow"] * 4186 * abs(df_power["TDisWatRet.T"] - df_power["TDisWatSup.T"])
            )

        column_names = [
            "ETS Pump Electricity Total",
            "ETS Heat Pump Electricity Total",
            "Sewer Pump Electricity",
            "GHX Pump Electricity",
            "Distribution Pump Electricity",
            "Total Cooling Plant",
            "Total Heating Plant",
        ]
        df_power["Total DES Electricity"] = df_power[column_names].sum(axis=1)

        # TODO: Add in total DES Natural Gas

        # sum up all ETS data (pump and heat pump)
        # df_power.to_csv(self.path / "power_original.csv")
        df_power = df_power.drop_duplicates(subset="datetime")
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
        building_ids: list[str] | None,
        openstudio_df: pd.DataFrame,
        openstudio_df_15: pd.DataFrame,
    ) -> None:
        """Only combine the end uses, not the total energy since that needs to be
        recalculated based on the modelica results. Basically, this only looks at the columns that are not
        HVAC related.

        Args:
            building_ids (list[str] | None): Name of the buildings
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
        meter_names = [f"{meter_name} {building_id}" for building_id in building_ids for meter_name in building_meter_names]
        # add in the end use totals that are non-HVAC
        meter_names += [
            "Total Building Interior Lighting",
            "Total Building Exterior Lighting",
            "Total Building Interior Equipment Electricity",
            "Total Building Exterior Equipment Electricity",
            "Total Building Interior Equipment Natural Gas",
            "Total Building Interior Equipment",
        ]

        self.min_60_with_buildings = pd.concat([self.min_60, openstudio_df[meter_names]], axis=1, join="inner")
        self.min_60_with_buildings.index.name = "datetime"

        # also conduct this for the 15 minute time step
        self.min_15_with_buildings = pd.concat([self.min_15, openstudio_df_15[meter_names]], axis=1, join="inner")
        self.min_15_with_buildings.index.name = "datetime"

        # should we resort the columns?

    def agg_for_reopt(self):
        """Aggregate building-level results from the Modelica data.

        Requires a full year Modelica simulation at hourly (8760) or 15-minute (8760 * 4) resolution

        Parameters
        ----------
        None
        """

        # Define patterns and output variable names
        patterns = {
            "heating_electric_power": r"^TimeSerLoa_\w+\.PHea$",
            "cooling_electric_power": r"^TimeSerLoa_\w+\.PCoo$",
            "pump_power": r"^TimeSerLoa_\w+\.PPum$",
            "ets_pump_power": r"^TimeSerLoa_\w+\.PPumETS$",
            "Heating system capacity": r"^TimeSerLoa_\w+\.ets.QHeaWat_flow_nominal$",
            "Cooling system capacity": r"^TimeSerLoa_\w+\.ets.QChiWat_flow_nominal$",
            "electrical_power_consumed": "pumDis.P",
        }

        key_value_pairs = {}
        time_values = None

        for name, pattern in patterns.items():
            for var in self.modelica_data.varNames(pattern):
                time, values = self.modelica_data.values(var)  # Unpack the tuple
                if time_values is None:
                    time_values = time.tolist()  # Initialize time_values from the first variable
                key_value_pairs[var] = values.tolist()

        # Convert seconds to timezone-aware datetime and adjust year to 2017
        def adjust_year(dt):
            return dt.replace(year=2017)

        # Convert timestamps to timezone-aware datetime objects in UTC
        time_values = [datetime.fromtimestamp(t, tz=timezone.utc) for t in time_values]
        adjusted_time_values = [adjust_year(dt) for dt in time_values]

        data_for_df = {
            "Datetime": adjusted_time_values,
            "TimeInSeconds": [int(dt.timestamp()) for dt in adjusted_time_values],
        }

        for var, values in key_value_pairs.items():
            if len(values) < len(adjusted_time_values):
                values.extend([None] * (len(adjusted_time_values) - len(values)))
            elif len(values) > len(adjusted_time_values):
                trimmed_values = values[: len(adjusted_time_values)]
                data_for_df[var] = trimmed_values
            else:
                data_for_df[var] = values

        df_values = pd.DataFrame(data_for_df)

        # Convert 'Datetime' to datetime and set it as index
        df_values["Datetime"] = pd.to_datetime(df_values["Datetime"])
        df_values = df_values.set_index("Datetime")

        # Resample to 1 hour data, taking the first occurrence for each interval
        df_resampled = df_values.resample("1h").first().reset_index()

        # Format datetime to desired format
        df_resampled["Datetime"] = df_resampled["Datetime"].dt.strftime("%m/%d/%Y %H:%M")

        # Interpolate only numeric columns
        numeric_columns = df_resampled.select_dtypes(include=["number"]).columns
        df_resampled[numeric_columns] = df_resampled[numeric_columns].interpolate(method="linear", inplace=False)

        # Check if the number of rows is not equal to 8760 (hourly) or 8760 * 4 (15-minute)
        if df_resampled.shape[0] != 8760 or df_resampled.shape[0] != 8760 * 4:
            _log.warning(
                "Data length is incorrect. Expected 8760 (hourly) or 8760 * 4 (15-minute) entries. "
                f"Actual length is {df_resampled.shape[0]}."
            )

        # Define patterns with placeholders
        patterns = {
            "heating_electric_power_#{building_id}": r"^TimeSerLoa_(\w+)\.PHea$",
            "cooling_electric_power_#{building_id}": r"^TimeSerLoa_(\w+)\.PCoo$",
            "pump_power_#{building_id}": r"^TimeSerLoa_(\w+)\.PPum$",
            "ets_pump_power_#{building_id}": r"^TimeSerLoa_(\w+)\.PPumETS$",
            "heating_system_capacity_#{building_id}": r"^TimeSerLoa_(\w+)\.ets.QHeaWat_flow_nominal$",
            "cooling_system_capacity_#{building_id}": r"^TimeSerLoa_(\w+)\.ets.QChiWat_flow_nominal$",
            "electrical_power_consumed": "pumDis.P",
        }

        # Function to rename columns based on patterns
        def rename_column(col_name):
            for key, pattern in patterns.items():
                match = re.match(pattern, col_name)
                if match:
                    if key == "electrical_power_consumed":
                        return key
                    try:
                        building_id = match.group(1)
                        return key.replace("#{building_id}", building_id)
                    except IndexError:
                        print(f"Error: Column '{col_name}' does not match expected pattern.")
                        return col_name
            # If no pattern matches, return the original column name
            return col_name

        # Rename columns
        df_resampled.columns = [rename_column(col) for col in df_resampled.columns]

        df_resampled.to_csv(self.path / "reopt_input.csv", index=False)

        print(f"Results saved at: {self.path / 'reopt_input.csv'}")

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
            self.min_60_with_buildings["Total Building Natural Gas"] * hourly_emissions_data.other_fuels["natural_gas"] / 1e6 / 1000
        )
        self.min_60_with_buildings["Total Natural Gas Carbon Emissions"] = self.min_60_with_buildings[
            "Total Building Natural Gas Carbon Emissions"
        ]

        # Calculate the electricity carbon emissions, emissions data is in kg/MWh, so Wh->Mwh, then divide by another 1000 to get mtCO2e
        self.min_60_with_buildings[f"Total Electricity Carbon Emissions {future_year}"] = (
            self.min_60_with_buildings["Total Electricity"] * hourly_emissions_data.data[lookup_egrid_subregion] / 1e6 / 1000
        )
        # Sum the total carbon emissions
        self.min_60_with_buildings[f"Total Carbon Emissions {future_year}"] = (
            self.min_60_with_buildings["Total Natural Gas Carbon Emissions"]
            + self.min_60_with_buildings[f"Total Electricity Carbon Emissions {future_year}"]
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
        self.min_15_with_buildings_to_process = self.min_15_with_buildings_to_process.iloc[skip_time:]
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
            df_tmp2 = self.min_15_with_buildings_to_process.copy()
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
            # FIXME: this id_lookup produces Pandas FutureWarning
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
        df_tmp["Total Electricity"] = self.min_60_with_buildings["Total Electricity"].resample("YE").sum() / 1e6  # MWh
        df_tmp["Total Natural Gas"] = self.min_60_with_buildings["Total Natural Gas"].resample("YE").sum() / 1e6  # MWh
        df_tmp["Total Thermal Cooling Energy"] = (
            self.min_60_with_buildings["Total Thermal Cooling Energy"].resample("YE").sum() / 1e6
        )  # MWh
        df_tmp["Total Thermal Heating Energy"] = (
            self.min_60_with_buildings["Total Thermal Heating Energy"].resample("YE").sum() / 1e6
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

    def save_dataframes(
        self,
        dfs_to_save: list = [
            "min_5",
            "min_15",
            "min_60",
            "min_15_with_buildings",
            "min_60_with_buildings",
            "monthly",
            "data_annual",
            "end_use_summary",
            "grid_metrics_daily",
            "grid_metrics_annual",
        ],
    ):
        """Save all of the dataframes, assuming they are defined

        Args:
            dfs_to_save (list, optional): Which ones to save. Defaults to: ['min_5', 'min_15', 'min_60',
            'min_15_with_buildings', 'min_60_with_buildings', 'monthly', 'data_annual', 'end_use_summary',
            'grid_metrics_daily', 'grid_metrics_annual'].
        """
        if self.min_5 is not None and "min_5" in dfs_to_save:
            self.min_5.to_csv(self.path / "power_5min.csv")
        if self.min_15 is not None and "min_15" in dfs_to_save:
            self.min_15.to_csv(self.path / "power_15min.csv")
        if self.min_60 is not None and "min_60" in dfs_to_save:
            self.min_60.to_csv(self.path / "power_60min.csv")
        if self.min_15_with_buildings is not None and "min_15_with_buildings" in dfs_to_save:
            self.min_15_with_buildings.to_csv(self.path / "power_15min_with_buildings.csv")
        if self.min_60_with_buildings is not None and "min_60_with_buildings" in dfs_to_save:
            self.min_60_with_buildings.to_csv(self.path / "power_60min_with_buildings.csv")

        # save the monthly and annual
        if self.monthly is not None and "monthly" in dfs_to_save:
            self.monthly.to_csv(self.path / "power_monthly.csv")
        if self.data_annual is not None and "annual" in dfs_to_save:
            self.data_annual.to_csv(self.path / "power_annual.csv")

        # save the summary
        if self.end_use_summary is not None and "end_use_summary" in dfs_to_save:
            self.end_use_summary.to_csv(self.path / "end_use_summary.csv")

        # save the metrics
        if self.grid_metrics_daily is not None and "grid_metrics_daily" in dfs_to_save:
            self.grid_metrics_daily.to_csv(self.path / "grid_metrics_daily.csv")
        if self.grid_metrics_annual is not None and "grid_metrics_annual" in dfs_to_save:
            self.grid_metrics_annual.to_csv(self.path / "grid_metrics_annual.csv")
