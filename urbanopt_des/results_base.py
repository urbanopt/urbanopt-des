import numpy as np
import pandas as pd


class ResultsBase:
    def __init__(self) -> None:
        """Base class for processing results. This is used for the Modelica and OpenStudio results to create
        common methods/datasets that can be used for easy comparison."""

    @property
    def end_use_summary_dict(self) -> dict:
        """Return a dictionary with the end use summary data structure."""

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
                "name": "Total Cooling Plant",
                "units": "Wh",
                "display_name": "District Cooling",
            },
            {
                "name": "Total Heating Plant",
                "units": "Wh",
                "display_name": "District Heating",
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

        return summary_columns

    def create_summary(self):
        """Create an annual end use summary by selecting key variables and values and transposing them for easy comparison.
        In the dict the following conventions are used:
            * `name` is the name of the variable in the data frame
            * `units` is the units of the variable
            * `display_name` will be the new name of the variable in the end use summary table.
        """
        # get the list of all the columns to allocate the data frame correctly
        columns = [c["display_name"] for c in self.end_use_summary_dict]

        # Create a single column of data
        self.end_use_summary = pd.DataFrame(
            index=columns,
            columns=["Units", self.display_name],
            data=np.zeros((len(columns), 2)),
        )

        # add the units column if it isn't already there
        self.end_use_summary["Units"] = [c["units"] for c in self.end_use_summary_dict]

        # create a CSV file for the summary table with
        # the columns as the rows and the results as the columns
        for column in self.end_use_summary_dict:
            # check if the column exists in the data frame and if not, then set the value to zero!
            # TODO: rename data_annual to annual to be consistent with the other *results* processing.
            if column["name"] in self.data_annual.columns:
                self.end_use_summary.loc[column["display_name"], self.display_name] = float(self.data_annual[column["name"]].iloc[0])
            else:
                self.end_use_summary.loc[column["display_name"], self.display_name] = 0.0

        return self.end_use_summary
