from modelica_builder.measures.measure_base import MeasureBase
from modelica_builder.modelica_project import ModelicaProject


class SetExtendedTypeArgumentValue(MeasureBase):
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
        return "set_extended_type_argument_value"

    def description(self):
        return "Set an argument value of an extended object."

    def modeler_description(self):
        return "Set an argument value of an extended object."

    def arguments(self):
        self.measure_args.add_argument(
            "model_name",
            "Name of the model to perturb",
            "The model_name in the ModelicaProject passed into the run method.",
            units="string",
        )
        self.measure_args.add_argument("extended_type", "Name of the extended type being modified", units="string")
        self.measure_args.add_argument("type", "Name of the type being modified", units="string")
        self.measure_args.add_argument("identifier", "Name of the type identifier being modified", units="string")
        self.measure_args.add_argument("object_name", "Name of the data object being modified", units="string")
        self.measure_args.add_argument("argument_name", "Name of the argument to set", units="string")
        self.measure_args.add_argument("value", "Value to set the argument to", units="float")
        return self.measure_args

    def run(self, project: ModelicaProject, user_arguments: list[dict]):
        super().run(project, user_arguments)

        # get the args
        model_name = user_arguments.get_value("model_name")
        extended_type = user_arguments.get_value("extended_type")
        type_ = user_arguments.get_value("type")
        identifier = user_arguments.get_value("identifier")
        object_name = user_arguments.get_value("object_name")
        argument_name = user_arguments.get_value("argument_name")
        new_value = user_arguments.get_value("value")

        # get the model
        model = project.get_model(model_name)

        # add actions to manipulate the model
        model.update_extended_component_modification(extended_type, type_, identifier, object_name, argument_name, str(new_value))

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


# ai = AnalysisInstance()
# ai.add_variable_instance('mPumDis_flow_nominal', dis_flo, short_name='dis')
# ai.add_variable_instance('mSto_flow_nominal', ghx_flo, short_name='ghx')
# ai.add_variable_instance('dp_length_nominal', dp_len, short_name='dp')
# analysis_name = ai.create_unique_variable_instance_name()

# new_analysis_dir = analysis_dir / analysis_name
# if new_analysis_dir.exists():
#     shutil.rmtree(new_analysis_dir)
# ai.save_variables_to_file(new_analysis_dir / 'analysis_variables.csv')
# ai.save_analysis_name_to_file(new_analysis_dir / 'analysis_name.txt')

# # read in the entire baseline project to duplicate the project directory
# modelica_project = ModelicaProject(analysis_baseline_dir / 'package.mo')
# modelica_project.save_as(analysis_name, analysis_dir)

# modelica_project = ModelicaProject(new_analysis_dir / 'package.mo')

# # When running save_as, all the models are pointed to the new location, so
# # now you can update them.
# model = modelica_project.get_model('Districts.district')
# model.update_extended_component_modification(
#             'Buildings.Experimental.DHC.Examples.Combined.BaseClasses.PartialSeries',
#             'Buildings.Experimental.DHC.Loads.Combined.BuildingTimeSeriesWithETS', 'bui',
#             'datDes',
#             'mPumDis_flow_nominal', str(dis_flo)
#         )
# model.update_extended_component_modification(
#             'Buildings.Experimental.DHC.Examples.Combined.BaseClasses.PartialSeries',
#             'Buildings.Experimental.DHC.Loads.Combined.BuildingTimeSeriesWithETS', 'bui',
#             'datDes',
#             'mSto_flow_nominal', str(ghx_flo)
#         )
# model.update_extended_component_modification(
#             'Buildings.Experimental.DHC.Examples.Combined.BaseClasses.PartialSeries',
#             'Buildings.Experimental.DHC.Loads.Combined.BuildingTimeSeriesWithETS', 'bui',
#             'datDes',
#             'dp_length_nominal', str(dp_len)
#         )

# model.execute()
# model.save()
