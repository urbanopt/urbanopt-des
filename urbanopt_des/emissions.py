# Create a class to load in the CSV files in the emissions folder and
# convert hours to a datetime object.

import datetime
from pathlib import Path
from typing import Union

import pandas as pd


class HourlyEmissionsData:
    def __init__(
        self,
        egrid_subregion: str,
        future_year: int,
        analysis_year: Union[int, None] = None,
        emissions_type: str = "marginal",
        with_td_losses: bool = True,
    ):
        """Create an instance of a pandas dataframe that is loaded with correct hourly emissions data.
        Note that the future year of emissions data and the year of analysis do not have to match, that is we can run an
        analysis in 2017 with the desire to see how it would emit in 2025.

        Args:
            egrid_subregion (str): eGRID subregion, as defined by the EPA
            future_year (int): Future year of the emission data to load.
            analysis_year (Union[int, None], optional): The year that the analysis data will be in, this will be the year in the analysis_date field. Defaults to None which sets the analysis_year to the future_year.
            emissions_type (str, optional): Type of emissions to load. Options are 'marginal' and 'average'. Defaults to 'marginal'.
            with_td_losses (bool, optional): Include transmission and distribution losses. Defaults to True.

        Raises:
            Exception: File not found
            Exception: Invalid eGRID subregion
        """
        # Get the name of the file to load based on the eGRID subregion and future year.
        # The file is in the emissions folder which is relative to this class
        path = Path(__file__).parent / "emissions"
        if with_td_losses:
            path = path / "with_distribution_losses"
        else:
            path = path / "without_distribution_losses"
        path = path / "future" / "hourly" / f"future_hourly_{emissions_type}_co2e_{future_year}.csv"

        if not path.exists():
            raise Exception(f"Future emissions data file does not exist: {path}")

        # verify that the eGRID subregion is valid
        if egrid_subregion not in self.region_names():
            raise Exception(f"Invalid eGRID subregion: {egrid_subregion}, expected one of {self.region_names()}")

        if analysis_year is None:
            analysis_year = future_year

        self.data = pd.read_csv(path, header=0)

        # create two new columns, one for the datetime based on the future_year and one based on the analysis_year.
        self.data["datetime"] = datetime.datetime(future_year, 1, 1) + pd.to_timedelta(self.data["hour"], unit="h")
        # If the year is a leap year, then shift the datetime by one day, effectively eliminating the leap day.
        # This isn't working yet, moving on...
        # if self.data['datetime'][0].is_leap_year:
        # after 2/28/future_year, shift all hours back by 24 hours
        # self.data.loc[self.data['datetime'] > datetime.datetime(future_year, 3, 1), 'datetime'] = self.data.loc[self.data['datetime'] > datetime.datetime(future_year, 3, 1), 'datetime'] - pd.to_timedelta(1, unit='d')

        self.data["analysis_datetime_end"] = datetime.datetime(analysis_year, 1, 1) + pd.to_timedelta(self.data["hour"], unit="h")
        self.data["analysis_datetime_start"] = self.data["analysis_datetime_end"] - pd.to_timedelta(1, unit="h")

        # move the datetime columns to the front
        cols = self.data.columns.tolist()
        cols = cols[-2:] + cols[:-2]
        self.data = self.data[cols]
        # swap the first two columns
        cols = self.data.columns.tolist()
        cols = cols[1:2] + cols[0:1] + cols[2:]
        self.data = self.data[cols]

        # index on the analysis_datetime
        self.data = self.data.set_index(["analysis_datetime_start"])

        # load in the other_fuels.csv file and fill down for every hour that
        # exists in the self.data. These data are non-location dependent
        # and non-time dependent.
        other_fuels_path = Path(__file__).parent / "emissions" / "other_fuels.csv"
        self.other_fuel_data = pd.read_csv(other_fuels_path, header=0)

        # remove the MBtu column, and then transpose
        # if the column exists, then drop it
        if "emission_kg_per_mbtu" in self.other_fuel_data.columns:
            self.other_fuel_data = self.other_fuel_data.drop(columns=["emission_kg_per_mbtu"])

        self.other_fuel_data = self.other_fuel_data.T
        # make the first row the column names
        self.other_fuel_data.columns = self.other_fuel_data.iloc[0]
        # drop the first row
        self.other_fuel_data = self.other_fuel_data.drop(self.other_fuel_data.index[0])
        self.other_fuel_data = self.other_fuel_data.reset_index()
        self.other_fuel_data = self.other_fuel_data.drop(columns=["index"])

        # copy the self.data and remove all the columns except
        self.other_fuels = self.data.copy()
        # drop all columns except 'analysis_datetime_start', 'analysis_datetime_end', 'hour'
        to_drop = [col for col in self.other_fuels.columns if col not in ["analysis_datetime_start", "analysis_datetime_end", "hour"]]
        self.other_fuels = self.other_fuels.drop(columns=to_drop)

        # merge in the other_fuels_data with the self.other_fuels and fill down
        # the columns for each row
        for column in self.other_fuel_data.columns:
            self.other_fuels[column] = self.other_fuel_data[column][0]

    def region_names(self):
        """Return the list of eGRID subregions to check against the incoming requests"""
        return [
            "AZNM",
            "CAMX",
            "ERCT",
            "FRCC",
            "MROE",
            "MROW",
            "NEWE",
            "NWPP",
            "NYST",
            "RFCE",
            "RFCM",
            "RFCW",
            "RMPA",
            "SPNO",
            "SPSO",
            "SRMV",
            "SRMW",
            "SRSO",
            "SRTV",
            "SRVC",
        ]
