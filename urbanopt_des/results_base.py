import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Union

import numpy as np
import pandas as pd
from buildingspy.io.outputfile import Reader

from .emissions import HourlyEmissionsData

VariablesDict = Dict[str, Union[bool, str, int, str]]


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
                "name": "Total DES Electricity",
                "units": "Wh",
                "display_name": "District Cooling",
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