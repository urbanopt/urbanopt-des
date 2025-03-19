# URBANopt District Energy Systems (DES)

## Overview

The **URBANopt District Energy Systems (DES) Package** is an extension of the [URBANopt SDK](https://github.com/urbanopt) designed to analyze the results of URBANopt simulated **district energy systems**. This package combines results from **[OpenStudio](https://openstudio.net/)/[EnergyPlus](https://energyplus.net/)** with results from **[Modelica](https://modelica.org/)/[Buildings Library](https://simulationresearch.lbl.gov/modelica/)** to provide detailed thermal and energy performance analysis at a district scale.

This project pulls in the [GeoJSON to Modelica Translator](https://github.com/urbanopt/geojson-modelica-translator) (and required dependencies).

## Installation

`pip install urbanopt-des`

## Developer installation

- Clone the repository: `git clone https://github.com/urbanopt/urbanopt-des.git`
- Change directories into the repository: `cd urbanopt-des`
- We recommend using virtual environments on principle to avoid dependencies colliding between your Python projects. [venv](https://docs.python.org/3/library/venv.html) is the Python native solution that will work everywhere, though other options may be more user-friendly.
  - Some popular alternatives are:
    - [pyenv](https://github.com/pyenv/pyenv) and [the virtualenv plugin](https://github.com/pyenv/pyenv-virtualenv) work together nicely for Linux/Mac machines
    - [virtualenv](https://virtualenv.pypa.io/en/latest/)
    - [miniconda](https://docs.conda.io/projects/miniconda/en/latest/)
    - [uv](https://docs.astral.sh/uv/)

Once you have set up your environment:

1. `pip install -U pip setuptools poetry`
   - This will update pip & setuptools, and install Poetry to manage the project
1. `poetry install`
   - This installs the project and all dependencies
1. Activate pre-commit (only once, after making a new venv): `poetry run pre-commit install`
   - Runs automatically on your staged changes before every commit
   - Includes linting and formatting via [ruff](https://docs.astral.sh/ruff/)
   - To check the whole repo, run `poetry run pre-commit run --all-files`
     - Settings and documentation links for pre-commit and ruff are in .pre-commit-config.yaml and ruff.toml
     - Pre-commit will run automatically during CI, linting and formatting the entire repository.

## Testing

Tests are run with `poetry run pytest`

Test output will be in tests/test_output/

## Example Projects

Example projects leveraging this library will be shared shortly.

## Release Instructions

1. Create a branch named `Release 0.x.`
1. Update version in pyproject.toml
1. Update CHANGELOG using GitHub's "Autogenerate Change Log" feature, using `develop` as the target
1. After tests pass, squash merge branch into develop
1. From local command line, merge develop into main with: `git checkout main; git pull; git merge --ff-only origin develop; git push`
1. In GitHub, tag the release against main. Copy and paste the changelog entry into the notes. Verify the release is posted to PyPI.

## License

This package is released under the **BSD-3-Clause License**. See the [LICENSE](LICENSE.md) file for details.

## Contact

For questions or issues on the URBANopt DES project, please open a GitHub Issue or reach out to the **URBANopt DES team** at [URBANopt DES Support](https://github.com/urbanopt/urbanopt-des/issues). General URBANopt documentation can be found at https://docs.urbanopt.net.
