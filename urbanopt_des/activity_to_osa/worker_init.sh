#!/bin/bash -e

# This script will enable a user to change a single gem in the list of accessible gems. The script will create the
# NEW_GEMFILE_DIR if it does not already exist.

# This script only works with OpenStudio 1.8.0 or newer.
echo "Calling $0 with arguments: $@"

# Find the location of the existing Gemfile based on the contents of the RUBYLIB env variable
echo $(which openstudio)
# You can't call openstudio here since it will load the Server's Gemfile
# echo $(openstudio openstudio_version)
for x in $(printenv RUBYLIB | tr ":" "\n")
do
  if [[ $x =~ .*[Oo]pen[Ss]tudio-[0-9]*\.[0-9]*\.[0-9]*/Ruby ]]; then
    GEMFILE_DIR=$x
    continue
  fi
done

echo "GEMFILE_DIR is set to $GEMFILE_DIR"
NEW_GEMFILE_DIR=/var/oscli
EXISTING_GEM=$1
NEW_GEM_REPO=$2
NEW_GEM_BRANCH=$3
GEMFILEUPDATE=$NEW_GEMFILE_DIR/analysis_$SCRIPT_ANALYSIS_ID.lock

# Determine the version of Bundler and make sure it is installed
if [ -e ${GEMFILE_DIR}/Gemfile.lock ]; then
  LOCAL_BUNDLER_VERSION=$(tail -n 1 ${GEMFILE_DIR}/Gemfile.lock | tr -dc '[0-9.]')
  echo "Installing Bundler version $LOCAL_BUNDLER_VERSION"
  if [ -z $LOCAL_BUNDLER_VERSION ]; then
    echo "Could not determine version of Bundler to use from Gemfile.lock"
  fi
  gem install bundler -v $LOCAL_BUNDLER_VERSION
else
  echo "Could not find Gemfile.lock file in $GEMFILE_DIR"
  exit 1
fi

# Verify the path of the required files
if [ ! -d "$GEMFILE_DIR" ]; then
  echo "Directory for Gemfile does not exist: ${GEMFILE_DIR}"
  exit 1
fi

if [ ! -f "$GEMFILE_DIR/Gemfile" ]; then
  echo "Gemfile does not exist in: ${GEMFILE_DIR}"
  exit 1
fi

if [ ! -f "$GEMFILE_DIR/openstudio-gems.gemspec" ]; then
  echo "openstudio-gems.gemspec does not exist in: ${GEMFILE_DIR}"
  echo "!!! This script only works with OpenStudio 2.8.0 and newer !!!"
  exit 1
fi

# First check if there is a file that indicates the gem has already been updated.
# We only need to update the bundle once / worker, not every time a data point is initialized.
echo "Checking if Gemfile has been updated in ${GEMFILEUPDATE}"
if [ -e $GEMFILEUPDATE ]; then
    echo "***The gem bundle has already been updated"
    exit 0
fi

# Modify the reference Gemfile and gemspec in place
mkdir -p $NEW_GEMFILE_DIR
cp $GEMFILE_DIR/Gemfile $NEW_GEMFILE_DIR
cp $GEMFILE_DIR/openstudio-gems.gemspec $NEW_GEMFILE_DIR

# add in the new gem to the Gemfile if the gem is not already there
# check if string exists in file
function string_exists_in_file {
  grep -q "$1" $2
}

if ! string_exists_in_file 'urbanopt-reporting' $NEW_GEMFILE_DIR/Gemfile; then
  echo "gem 'urbanopt-reporting', '0.9.1'" >> $NEW_GEMFILE_DIR/Gemfile
fi

# Pull the workflow gem from develop otherwise `require 'openstudio-workflow'` fails, supposedly
# replace_gem_in_files $NEW_GEMFILE_DIR 'openstudio-workflow' 'NREL/openstudio-workflow-gem' '2.9.X-LTS'

# Show the modified Gemfile contents in the log
cd $NEW_GEMFILE_DIR
dos2unix $NEW_GEMFILE_DIR/Gemfile
dos2unix $NEW_GEMFILE_DIR/openstudio-gems.gemspec
echo "***Here are the modified Gemfile and openstudio-gems.gemspec files:"
cat $NEW_GEMFILE_DIR/Gemfile
cat $NEW_GEMFILE_DIR/openstudio-gems.gemspec

# Unset all BUNDLE, GEM, and RUBY environment variables before calling bundle install. These
# are required before re-bundling!
for evar in $(env | cut -d '=' -f 1 | grep ^BUNDLE); do unset $evar; done
for evar in $(env | cut -d '=' -f 1 | grep ^GEM); do unset $evar; done
for evar in $(env | cut -d '=' -f 1 | grep ^RUBY); do unset $evar; done
export RUBYLIB=$GEMFILE_DIR:/usr/Ruby:$RUBYLIB

# Update the specified gem in the bundle
echo "***Running bundle install with version $LOCAL_BUNDLER_VERSION in $(which bundle)"
if [ -f Gemfile.lock ]; then
  rm Gemfile.lock
fi
bundle '_'$LOCAL_BUNDLER_VERSION'_' install --path gems

# Note that the bundle has been updated
echo >> $GEMFILEUPDATE
