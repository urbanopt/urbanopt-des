# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

"""Constants used throughout the urbanopt-des package."""

# Time and resampling
SECONDS_PER_HOUR = 3600
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24
DAYS_PER_WEEK = 7
HOURS_PER_YEAR = 8760
QUARTERS_PER_YEAR = 8760 * 4  # 15-minute intervals

# Resampling intervals
RESAMPLE_1MIN = "1min"
RESAMPLE_5MIN = "5min"
RESAMPLE_15MIN = "15min"
RESAMPLE_60MIN = "60min"
RESAMPLE_1HOUR = "1h"
RESAMPLE_1DAY = "1d"
RESAMPLE_1MONTH = "1ME"  # Month end
RESAMPLE_1YEAR = "YE"  # Year end

# Physical constants
WATER_SPECIFIC_HEAT = 4186  # J/kg/K
KG_PER_MWH_TO_MTCO2E = 1e-9  # Convert kg/MWh to metric tons CO2e
WH_TO_MWH = 1e6  # Convert Wh to MWh

# Default values
DEFAULT_YEAR = 2017
DEFAULT_VALUE = 0.0
DEFAULT_EGRID_SUBREGION = "RFCE"
DEFAULT_FUTURE_YEAR = 2045

# Grid metrics
GRID_METRICS_WARMUP_DAYS = 2
GRID_METRICS_TOP_PEAKS = 5

# File extensions
MAT_FILE_EXTENSION = ".mat"
ZIP_FILE_EXTENSION = ".zip"
CSV_FILE_EXTENSION = ".csv"
JSON_FILE_EXTENSION = ".json"

# Output file names
OUTPUT_MODELICA_VARIABLES = "modelica_variables.json"
OUTPUT_POWER_5MIN = "power_5min.csv"
OUTPUT_POWER_15MIN = "power_15min.csv"
OUTPUT_POWER_60MIN = "power_60min.csv"
OUTPUT_POWER_15MIN_WITH_BUILDINGS = "power_15min_with_buildings.csv"
OUTPUT_POWER_60MIN_WITH_BUILDINGS = "power_60min_with_buildings.csv"
OUTPUT_POWER_MONTHLY = "power_monthly.csv"
OUTPUT_POWER_ANNUAL = "power_annual.csv"
OUTPUT_END_USE_SUMMARY = "end_use_summary.csv"
OUTPUT_GRID_METRICS_DAILY = "grid_metrics_daily.csv"
OUTPUT_GRID_METRICS_ANNUAL = "grid_metrics_annual.csv"
OUTPUT_REOPT_INPUT = "reopt_input.csv"
