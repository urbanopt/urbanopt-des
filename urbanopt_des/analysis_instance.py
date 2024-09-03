from pathlib import Path
from typing import Any, Union


class AnalysisInstance:
    # class is used to help define an instance of an analysis such
    # as the variables that were set and to what values
    def __init__(self) -> None:
        # The structure of the data is a dictionary of dictionaries with the key being the
        # the machine name of the variable
        self.variables: dict = {}

    def add_variable_instance(self, variable_name: str, variable_value: Any, **kwargs) -> None:
        """Store the variable instance and value in a dictionary. There can only
        be one variable_name per instance of the analysis

        Args:
            variable_name (str): Machine name of the variable to add
            variable_value (any): Value that was set.

        kwargs:
            short_name (str): Short name of the variable, used for directories
        """
        # TODO: need to add in other fields such as variable display name, units, etc

        # check if variable_name already exists
        if variable_name in self.variables:
            # check if the value has been set
            if self.variables[variable_name]["value"] is None:
                self.variables[variable_name]["value"] = variable_value
            else:
                raise Exception(f"Variable {variable_name} already has a value set")
        else:
            self.variables[variable_name] = {"value": variable_value}

        # save the other kwargs, note that this will overwrite any existing values
        for key, value in kwargs.items():
            self.variables[variable_name][key] = value

        # check if the short_name is set, if not, set it to the variable_name
        for variable, variable_data in self.variables.items():
            if "short_name" not in variable_data:
                self.variables[variable]["short_name"] = variable

    def create_unique_variable_instance_name(self, prepend_str: str = "sim") -> str:
        """Return a nicely formatted string that is unique and
        as short as possible to define the parameters of the analysis
        that this instance represents. This is used to create a directory
        name for the analysis instance.

            var1_1_0_var2_2_0

        At some point, this definition will be too long and the user
        should look into the "variables file" to understand the variables

        Args:
            prepend_str (str, optional): what to prepend to the name, if anything.
                                         Defaults to 'sim'.

        Returns:
            str: short, unique version of the analysis definition
        """
        result = prepend_str

        for _, variable in self.variables.items():
            # clean up the variable value to not include periods and other characters
            value = str(variable["value"]).replace(".", "_")
            result += f"_{variable['short_name']}_{value}"

        return result

    def save_analysis_name_to_file(self, filename: Path, override_name: Union[None, str] = None) -> None:
        """Save off the analysis name to a file that can be used for
        later reference and post processing. Right now this is a simple file
        but ideally the instance of the analysis that is written should be the same
        format as the OpenStudio Analysis Framework and ComStock-related files."""
        analysis_name = self.create_unique_variable_instance_name()
        if override_name is not None:
            analysis_name = override_name

        with open(filename, "w") as f:
            f.write(analysis_name)

    def save_variables_to_file(self, filename: Path) -> None:
        """Save the variable values to a CSV-like file in the form of
        variable_name, variable_value

        Args:
            filename (str): Name of the file to save to
        """
        if filename.exists():
            filename.unlink()
        if not filename.parent.exists():
            filename.parent.mkdir(parents=True)

        with open(filename, "w") as f:
            for variable_name in self.variables:
                f.write(f"{variable_name},{self.variables[variable_name]['value']},{self.variables[variable_name]['short_name']}\n")
