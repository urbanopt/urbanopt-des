from modelica_builder.measures.measure_base import MeasureBase
from modelica_builder.modelica_project import ModelicaProject


class SetParameterValue(MeasureBase):
    def __init__(self, measure_unique_name: str) -> None:
        """Pass in the name of the measure as defined by the user. This is needed
        because this measure (and others) can be used many times to manipulate the
        Modelica project and model and we want to keep track of the name as seen
        by the user.

        Args:
            measure_unique_name (str): Machine readable name of the measure that is unique to the analysis.
        """
        super().__init__()

        self.unique_name = measure_unique_name

    def name(self):
        return "set_parameter_value"

    def description(self):
        return "Set the value of a model's parameter to the specified value."

    def modeler_description(self):
        return "Parse the Modelica file and set the value of the specified parameter to the specified value."

    def arguments(self):
        self.measure_args.add_argument(
            "model_name",
            "Name of the model to perturb",
            "The model_name in the ModelicaProject passed into the run method.",
            units="string",
        )
        self.measure_args.add_argument("type", "Name of the type being modified", units="string")
        self.measure_args.add_argument("identifier", "Name of the type identifier being modified", units="string")
        self.measure_args.add_argument("value", "Value to set the argument to", units="float")
        return self.measure_args

    def run(self, project: ModelicaProject, user_arguments: list[dict]):
        super().run(project, user_arguments)

        # get the args
        model_name = user_arguments.get_value("model_name")
        type_ = user_arguments.get_value("type")
        identifier = user_arguments.get_value("identifier")
        new_value = user_arguments.get_value("value")

        # get the model
        model = project.get_model(model_name)

        previous_value = model.get_parameter_value(type_, identifier)

        model.update_parameter(type_, identifier, new_value)

        self.measure_attributes.register_value(model_name, self.unique_name, f"{identifier}_previous_value", previous_value)

        for args in user_arguments.get_args_with_register_values():
            # register the value that was set after the fact
            self.measure_attributes.register_value(model_name, self.unique_name, args["name"], args["value"])

        # execute the actions
        model.execute()

        # save the model to disk
        model.save()

        # save the measure attributes
        self.measure_attributes.save(project.root_directory)
        return True
