require 'json'

# Pure JSON/OSW manipulation helpers used by uo_building_to_osa.rb when converting a
# calibration OSW (produced by the URBANopt CLI) into an OpenStudio Analysis (OSA).
#
# Kept free of any 'openstudio-analysis' (or other OpenStudio) gem dependency so that
# this logic can be exercised directly by plain-Ruby tests without installing OpenStudio.
module OswTransform
  # Measures that are only needed for model generation (the seed model has already been
  # generated) or that fail OSA conversion due to stale measure.xml files. These are
  # stripped from the OSW before converting it to an OSA.
  MEASURES_TO_REMOVE = [
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
  ].freeze

  # Removes MEASURES_TO_REMOVE steps from osw['steps'] in place. Returns osw.
  def self.filter_measures(osw, measures_to_remove: MEASURES_TO_REMOVE)
    osw['steps'].delete_if { |step| measures_to_remove.include?(step['measure_dir_name']) }
    osw
  end

  # The OSA conversion fails to validate the 'feature_location' argument on the
  # 'default_feature_reports' measure (it isn't declared in that measure's measure.xml),
  # so it must be removed from the OSW before conversion. Returns the removed value (or
  # nil if not present) so it can be spliced back into the generated analysis.json later
  # (see reinsert_feature_location).
  def self.extract_feature_location(osw)
    feature_location = nil
    osw['steps'].each do |step|
      next unless step['measure_dir_name'] == 'default_feature_reports'

      feature_location = step['arguments'].delete('feature_location')
    end
    feature_location
  end

  # Loads osw_path, applies filter_measures + extract_feature_location, and writes the
  # result to dest_path as pretty-printed JSON. Returns the extracted feature_location.
  def self.transform_osw_file(osw_path, dest_path)
    osw = JSON.parse(File.read(osw_path))
    filter_measures(osw)
    feature_location = extract_feature_location(osw)
    File.write(dest_path, JSON.pretty_generate(osw))
    feature_location
  end

  # Splices feature_location back into the 'default_feature_reports' step's arguments
  # within a generated analysis.json (OSA conversion drops it, see
  # extract_feature_location above). Mutates and returns analysis_json.
  def self.reinsert_feature_location(analysis_json, feature_location)
    analysis_json['analysis']['problem']['workflow'].each do |step|
      next unless step['name'] == 'default_feature_reports'

      step['arguments'] << {
        'display_name' => 'URBANopt Feature Location',
        'display_name_short' => 'URBANopt Feature Location',
        'name' => 'feature_location',
        'value_type' => 'string',
        'default_value' => '0',
        'value' => feature_location,
      }
    end
    analysis_json
  end

  # Loads analysis_json_path, applies reinsert_feature_location, and writes the result
  # back to the same path as pretty-printed JSON. Returns the updated analysis_json.
  def self.reinsert_feature_location_file(analysis_json_path, feature_location)
    analysis_json = JSON.parse(File.read(analysis_json_path))
    reinsert_feature_location(analysis_json, feature_location)
    File.write(analysis_json_path, JSON.pretty_generate(analysis_json))
    analysis_json
  end
end
