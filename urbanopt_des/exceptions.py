# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

"""Custom exceptions for the urbanopt-des package."""


class URBANoptDESError(Exception):
    """Base exception for all urbanopt-des errors."""


class URBANoptFileNotFoundError(URBANoptDESError):
    """Raised when a required file is not found (urbanopt-des specific)."""


class FileTypeError(URBANoptDESError):
    """Raised when a file type is not supported."""


class ModelicaDataError(URBANoptDESError):
    """Base exception for Modelica data processing errors."""


class TimeSeriesMismatchError(ModelicaDataError):
    """Raised when time series lengths don't match expected values."""

    def __init__(self, actual_length: int, expected_length: int, variable_name: str | None = None):
        self.actual_length = actual_length
        self.expected_length = expected_length
        self.variable_name = variable_name

        message = f"Time series length mismatch: expected {expected_length}, got {actual_length}"
        if variable_name:
            message += f" for variable '{variable_name}'"
        super().__init__(message)


class VariableNotFoundError(ModelicaDataError):
    """Raised when a Modelica variable is not found in the data."""

    def __init__(self, variable_name: str):
        self.variable_name = variable_name
        super().__init__(f"Variable '{variable_name}' not found in Modelica data")


class NoTimeVariablesError(ModelicaDataError):
    """Raised when no time variables are found in Modelica data."""


class BuildingCountMismatchError(ModelicaDataError):
    """Raised when building counts don't match between sources."""

    def __init__(self, geojson_count: int, modelica_count: int):
        self.geojson_count = geojson_count
        self.modelica_count = modelica_count
        super().__init__(f"Building count mismatch: GeoJSON has {geojson_count} buildings, Modelica data has {modelica_count} buildings")


class DataValidationError(URBANoptDESError):
    """Raised when data validation fails."""


class MissingColumnsError(DataValidationError):
    """Raised when required columns are missing from a DataFrame."""

    def __init__(self, missing_columns: list[str], dataframe_name: str | None = None):
        self.missing_columns = missing_columns
        self.dataframe_name = dataframe_name

        message = f"Missing required columns: {', '.join(missing_columns)}"
        if dataframe_name:
            message = f"{dataframe_name}: {message}"
        super().__init__(message)


class InvalidLengthError(DataValidationError):
    """Raised when data has an invalid length."""

    def __init__(self, actual_length: int, expected_length: int, data_name: str | None = None):
        self.actual_length = actual_length
        self.expected_length = expected_length
        self.data_name = data_name

        message = f"Invalid length: expected {expected_length}, got {actual_length}"
        if data_name:
            message = f"{data_name}: {message}"
        super().__init__(message)


class ConfigurationError(URBANoptDESError):
    """Raised when there is a configuration error."""


class ResultsNotProcessedError(URBANoptDESError):
    """Raised when attempting to access results before processing."""

    def __init__(self, operation: str | None = None):
        message = "Results have not been processed yet"
        if operation:
            message = f"Cannot perform '{operation}': {message.lower()}"
        super().__init__(message)
