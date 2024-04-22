
require 'openstudio-analysis'

# read in the first argument
building_id = ARGV[0]
puts "ARG:building_id is #{building_id}"

# HARD CODED for now
analysis_dir = File.expand_path(File.join("/Users/nlong/working/dissertation-analysis/dc/analysis", "seed_to_uo", "baseline"))
sim_dir = File.join(analysis_dir, "run", "dc_block_1_baseline_scenario", building_id)
sim_dir_save = File.join(analysis_dir, "run", "dc_block_1_baseline_scenario_calibrated", building_id)
osw_filename = 'in.osw'
weather_file_name = 'VA_WASHINGTON-DC-REAGAN-AP_724050S_21.epw'

puts "Analysis dir: #{analysis_dir}"
puts "Sim dir: #{sim_dir}"

if not File.exists?(sim_dir)
    puts "Could not find #{sim_dir}"
    exit(1)
end

osw_file = File.join(sim_dir, osw_filename)
if not File.exists?(osw_file)
    puts "Could not find #{osw_file}"
    exit(1)
end


# Silly shenaningans to get the analysis to work. It appears that some
# of the measures don't have up to date measure.xml files, so they are failing
# to convert!

# read in the osw file as a JSON file, remove the step that has add_chilled_water_storage_tank,
# then save back to a JSON file as in.updated.osw
require 'json'
osw = JSON.parse(File.read(osw_file))

# Since this is for calibration, then remove a bunch of the measures that are for model generation,
# we have already generated the model Note that these are the values that are in the OSW (NOT OSA)
measures_to_remove = [
    'add_chilled_water_storage_tank',
    'create_bar_from_building_type_ratios',
    'create_typical_building_from_model',
    'blended_space_type_from_model',
    'add_ev_load',
    'add_ems_to_control_ev_charging',
    'ReduceElectricEquipmentLoadsByPercentage',
    'ReduceLightingLoadsByPercentage',
    'PredictedMeanVote',
    'urban_geometry_creation_zoning',
    'create_typical_building_from_model_2',
    'add_central_ice_storage',
    'add_hpwh',
    'add_packaged_ice_storage',
]
measures_to_remove.each do |measure|
    osw['steps'].delete_if { |step| step['measure_dir_name'] == measure }
end

# hack, the verification of default_feature_reports fails because
# the feature_loation argument is not in the measure.xml file. So,
# remove the "default_feature_reports" argument of "feature_location".
# We add it back in later
feature_location = nil
osw['steps'].each_with_index do |step, index|
    if osw['steps'][index]['measure_dir_name'] == 'default_feature_reports'
        feature_location = osw['steps'][index]['arguments'].delete('feature_location')
    end
end

osw_updated = File.join(sim_dir, 'in.updated.osw')
File.write(osw_updated, JSON.pretty_generate(osw))

# recheck the osw file existence
osw_file = File.join(sim_dir, 'in.updated.osw')
if not File.exists?(osw_file)
    puts "Could not find updated #{osw_file}"
    exit(1)
end

puts "Converting OSW to OSA"

a = OpenStudio::Analysis.create("Building #{building_id}")
output = a.convert_osw(osw_file)

# LHS Settings
# a.analysis_type = 'lhs'
# a.algorithm.set_attribute('number_of_samples', 10)
# a.algorithm.set_attribute('sample_method', 'all_variables')
# a.algorithm.set_attribute('seed', 1973)

# Calibration Settings
a.analysis_type = 'rgenoud'
a.algorithm.set_attribute('popsize', 20)  # set to 100 by default, must be even
a.algorithm.set_attribute('generations', 10)
a.algorithm.set_attribute('bfgs', 0)
a.algorithm.set_attribute('solution_tolerance', 0.0001)
a.algorithm.set_attribute('max_queued_jobs', 40)
a.display_name = "Building #{building_id}: #{a.analysis_type}"

# For now, skip the default_feature_reports measure -- during calibration,
# as it creats too much data
m = a.workflow.find_measure('set_run_period')  # Not recommended using this for calibration
m.argument_value('__SKIP__', true)
m = a.workflow.find_measure('change_building_location')
m.argument_value('weather_file_name', weather_file_name)
m = a.workflow.find_measure('default_feature_reports')
m.argument_value('__SKIP__', true)
m = a.workflow.find_measure('export_modelica_loads')
m.argument_value('__SKIP__', true)
m = a.workflow.find_measure('export_time_series_loads_csv')
m.argument_value('__SKIP__', true)
# enable default openstudio reports
m = a.workflow.find_measure('openstudio_results')
m.argument_value('__SKIP__', false)

# add some calibration / pertubation measures
m = a.workflow.add_measure_from_path('general_calibration_measure', 'General Calibration Measure', File.join(File.dirname(__FILE__), 'measures/GeneralCalibrationMeasurePercentChange'))
m.argument_value('space_type', '*All SpaceTypes*')
m.argument_value('space', '*All Spaces*')
a.workflow.move_measure_after('general_calibration_measure', 'increase_insulation_r_value_for_exterior_walls')

m = a.workflow.add_measure_from_path('add_monthly_json_utility_data_electricity', 'Add Monthly JSON Utility Data Electricity', File.join(File.dirname(__FILE__), 'measures/AddMonthlyJSONUtilityData'))
m.argument_value('json','../../../lib/calibration_data/electricity_data.json')
# For building 3, only have data from 2021-01-01 to 2021-07-31!
m.argument_value('start_date','2021-01-01')
if building_id == '3'
    m.argument_value('end_date','2021-07-31')
else
    m.argument_value('end_date','2021-12-31')
end
m.argument_value('remove_existing_data',true)  # DO NOT RUN THIS THE SECOND TIME!
m.argument_value('set_runperiod',true)         # COMMENT OUT THE SECOND TIME!

a.workflow.move_measure_after('add_monthly_json_utility_data_electricity', 'general_calibration_measure')

# check if there is a natural gas file in the
if File.exists?(File.join(sim_dir_save, 'calibration_data', 'natural_gas_data.json'))
    m = a.workflow.add_measure_from_path('add_monthly_json_utility_data_natural_gas', 'Add Monthly JSON Utility Data Natural Gas', File.join(File.dirname(__FILE__), 'measures/AddMonthlyJSONUtilityData'))
    m.argument_value('json','../../../lib/calibration_data/natural_gas_data.json')
    m.argument_value('start_date','2021-01-01')
    if building_id == '3'
        m.argument_value('end_date','2021-07-31')
    else
        m.argument_value('end_date','2021-12-31')
    end
    m.argument_value('fuel_type','Gas')
    m.argument_value('consumption_unit','therms')
    m.argument_value('data_key_name','tot_therms')
    m.argument_value('variable_name','Gas Bill')
    m.argument_value('remove_existing_data', false)  # DO NOT RUN THIS THE SECOND TIME!
    # m.argument_value('set_runperiod',true)         # COMMENT OUT THE SECOND TIME!
    a.workflow.move_measure_after('add_monthly_json_utility_data_natural_gas', 'add_monthly_json_utility_data_electricity')
end

# add in the Calibration reports
m = a.workflow.add_measure_from_path('calibration_reports_enhanced', 'Calibration Reports Enhanced', File.join(File.dirname(__FILE__), 'measures/CalibrationReportsEnhanced'))

# set the weather file and osm
a.weather_file = File.join(sim_dir_save, weather_file_name)
a.seed_model = File.join(sim_dir_save, 'in.osm')

# add in the Gemfiles with the required depended gems. For example, the urbanopt-reporting gem is
# required to generate the same results as the UO CLI
a.gem_files.add(File.join(File.dirname(__FILE__), 'Gemfile'))
a.gem_files.add(File.join(File.dirname(__FILE__), 'openstudio-gems.gemspec'))

# SEt some variables
m = a.workflow.find_measure('general_calibration_measure')
m.argument_value('__SKIP__', false)
d = {
    type: 'uniform',
    minimum: -40,
    maximum: 40,
    mean: 0
}
# 4 variables with the same ranges
m.make_variable('ElectricEquipment_perc_change', 'Electric Equipment Percent Change', d)
m.make_variable('infil_perc_change', 'Infiltration Percent Change', d)
m.make_variable('vent_perc_change', 'Ventilation Percent Change', d)
m.make_variable('mass_perc_change', 'Mass Percent Change', d)
m.make_variable('lights_perc_change', 'Lights Percent Change', d)


# add in FansPercentChange
# add in Walls
# add in Roofs


# add calibration outputs
o = a.add_output(
      display_name: 'electricity_consumption_cvrmse',
      name: 'calibration_reports_enhanced.electricity_consumption_cvrmse',
      units: '%',
      objective_function: true
    )

o = a.add_output(
      display_name: 'electricity_consumption_nmbe',
      name: 'calibration_reports_enhanced.electricity_consumption_nmbe',
      units: '%',
      objective_function: true,
      objective_function_group: 2
    )

if File.exists?(File.join(sim_dir_save, 'calibration_data', 'natural_gas_data.json'))
    o = a.add_output(
        display_name: 'natural_gas_consumption_cvrmse',
        name: 'calibration_reports_enhanced.natural_gas_consumption_cvrmse',
        units: '%',
        objective_function: true,
        objective_function_group: 3
        )

    o = a.add_output(
        display_name: 'natural_gas_consumption_nmbe',
        name: 'calibration_reports_enhanced.natural_gas_consumption_nmbe',
        units: '%',
        objective_function: true,
        objective_function_group: 4
        )
end

# Other outputs that are not part of the calibration, but useful to have
o = a.add_output(
    display_name: 'total_site_eui',
    name: 'openstudio_results.total_site_eui',
    units: 'kBtu/ft^2',
    visualize: true,
    objective_function: false
)

a.libraries.add(File.join(sim_dir_save, 'calibration_data'), {library_name: 'calibration_data'})
analysis_json_file = File.join(sim_dir_save, 'analysis.json')
analysis_zip_file = File.join(sim_dir_save, 'analysis.zip')

# turn off a bunch of the reporting -- specifically for calibration because this will
# generate a lot of data
a.download_zip = false
a.cli_verbose = ""
a.cli_debug = ""

a.save(analysis_json_file)
a.save_osa_zip(analysis_zip_file)

# ugh, hack. place back in the feature_location
# analysis.json file and add the server scripts to it
analysis_json = JSON.parse(File.read(analysis_json_file))
analysis_json['analysis']['problem']['workflow'].each_with_index do |step, index|
    puts("Step: #{step['name']}")
    if step['name'] == 'default_feature_reports'
        analysis_json['analysis']['problem']['workflow'][index]['arguments'].append({
              "display_name": "URBANopt Feature Location",
              "display_name_short": "URBANopt Feature Location",
              "name": "feature_location",
              "value_type": "string",
              "default_value": "0",
              "value": feature_location
            })
    end
end
File.write(analysis_json_file, JSON.pretty_generate(analysis_json))
