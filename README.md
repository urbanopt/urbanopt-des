# URBANopt District Energy Systems (DES)

## Overview

The **URBANopt District Energy Systems (DES) Package** is an extension of the [URBANopt SDK](https://github.com/urbanopt/urbanopt) designed to analyze the results of URBANopt simulated **district energy systems**. This package combines the results from **OpenStudio/EnergyPlus** with the results from **Modelica/Buildings Library** to provide detailed thermal and energy performance analysis at a district scale.

This project will pull in the GeoJSON to Modelica Translator (and required dependencies).

## Example Projects

Example projects leveraging this library will be shared shortly.

## Release Instructions

1. Create a branch named `Release 0.x.`
1. Update version in pyproject.toml
1. Update CHANGELOG using GitHub's "Autogenerate Change Log" feature, using `develop` as the target
1. After tests pass, squash merge branch into develop
1. In GitHub, tag the release against main. Copy and paste the changelog entry into the notes. Verify the release is posted to PyPI.

## License

This package is released under the **BSD-3-Clause License**. See the [LICENSE](LICENSE) file for details.

## Contact

For questions or issues, please open a GitHub Issue or reach out to the **URBANopt team** at [URBANopt Support](https://github.com/urbanopt/urbanopt/issues).
