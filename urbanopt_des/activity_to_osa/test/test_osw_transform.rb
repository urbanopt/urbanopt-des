require 'minitest/autorun'
require 'json'
require 'tmpdir'
require_relative '../lib/osw_transform'

# Exercises OswTransform against real production files on disk (test/fixtures/) -- no
# mocking/stubbing of File/JSON. Only needs plain Ruby (json + minitest are part of the
# standard library), no OpenStudio/openstudio-analysis gem or `bundle install` required:
#
#   ruby test/test_osw_transform.rb
#
# Fixtures come from an actual URBANopt calibration run (DC building "1"):
#   sample_in.osw               -- real in.osw from dc_block_1_baseline_scenario/1
#                                   (26 real workflow steps, sanitized of local file paths)
#   sample_analysis.json        -- the real, OSA-converted analysis.json for the same
#                                   building, with the 'feature_location' argument
#                                   removed from 'default_feature_reports' (its state
#                                   right after `a.save`, before the reinsert hack runs)
#   sample_analysis_expected.json -- the same real analysis.json with 'feature_location'
#                                   already reinserted, i.e. the real final output
class TestOswTransform < Minitest::Test
  FIXTURES_DIR = File.join(__dir__, 'fixtures')
  OSW_FIXTURE = File.join(FIXTURES_DIR, 'sample_in.osw')
  ANALYSIS_FIXTURE = File.join(FIXTURES_DIR, 'sample_analysis.json')
  ANALYSIS_EXPECTED_FIXTURE = File.join(FIXTURES_DIR, 'sample_analysis_expected.json')
  # The real feature_location value for this building (a lat/lng pair), present in both
  # fixtures above -- confirms in.osw and analysis.json agree, as they do in production.
  FEATURE_LOCATION = '[-77.04016140781235, 38.90210768151801]'

  def test_filter_measures_removes_only_listed_measures
    osw = JSON.parse(File.read(OSW_FIXTURE))
    original_count = osw['steps'].size

    OswTransform.filter_measures(osw)
    remaining_names = osw['steps'].map { |s| s['measure_dir_name'] }

    OswTransform::MEASURES_TO_REMOVE.each do |measure|
      refute_includes remaining_names, measure
    end
    # unrelated steps from the real workflow must be preserved
    %w[set_run_period ChangeBuildingLocation default_feature_reports openstudio_results generic_qaqc].each do |measure|
      assert_includes remaining_names, measure
    end
    assert_operator remaining_names.size, :<, original_count
  end

  def test_extract_feature_location_removes_argument_and_returns_value
    osw = JSON.parse(File.read(OSW_FIXTURE))

    location = OswTransform.extract_feature_location(osw)

    assert_equal FEATURE_LOCATION, location
    step = osw['steps'].find { |s| s['measure_dir_name'] == 'default_feature_reports' }
    refute_includes step['arguments'].keys, 'feature_location'
    # unrelated arguments on the same step are left alone
    assert_equal '1', step['arguments']['feature_id']
  end

  def test_transform_osw_file_writes_real_file_and_leaves_source_untouched
    Dir.mktmpdir do |dir|
      dest = File.join(dir, 'in.updated.osw')

      feature_location = OswTransform.transform_osw_file(OSW_FIXTURE, dest)

      assert_equal FEATURE_LOCATION, feature_location
      assert File.exist?(dest)

      updated = JSON.parse(File.read(dest))
      names = updated['steps'].map { |s| s['measure_dir_name'] }
      OswTransform::MEASURES_TO_REMOVE.each { |measure| refute_includes names, measure }

      step = updated['steps'].find { |s| s['measure_dir_name'] == 'default_feature_reports' }
      refute_includes step['arguments'].keys, 'feature_location'

      # the fixture on disk must be unmodified by the transform
      original = JSON.parse(File.read(OSW_FIXTURE))
      original_names = original['steps'].map { |s| s['measure_dir_name'] }
      assert_includes original_names, 'create_bar_from_building_type_ratios'
    end
  end

  def test_reinsert_feature_location_file_reproduces_real_production_output
    Dir.mktmpdir do |dir|
      analysis_path = File.join(dir, 'analysis.json')
      File.write(analysis_path, File.read(ANALYSIS_FIXTURE))

      OswTransform.reinsert_feature_location_file(analysis_path, FEATURE_LOCATION)

      actual = JSON.parse(File.read(analysis_path))
      expected = JSON.parse(File.read(ANALYSIS_EXPECTED_FIXTURE))

      actual_step = actual['analysis']['problem']['workflow'].find { |s| s['name'] == 'default_feature_reports' }
      expected_step = expected['analysis']['problem']['workflow'].find { |s| s['name'] == 'default_feature_reports' }

      # reinserting into the real "before" state must reproduce the real recorded
      # production output byte-for-byte (same argument list, order, and values)
      assert_equal expected_step['arguments'], actual_step['arguments']
    end
  end
end
