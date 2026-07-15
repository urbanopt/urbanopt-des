# Changelog

<!-- Release notes generated using configuration in .github/release.yml at develop -->

## Version 0.3.0

## What's Changed

### Exciting New Features 🎉

- Add helper methods for CLI methods and analyses by @nllong in https://github.com/urbanopt/urbanopt-des/pull/83

### Improvements & Bug Fixes 🐛

- Add methods to fix base workflow OSWs by @nllong in https://github.com/urbanopt/urbanopt-des/pull/74
- Remove hard codes warmup skip and allow empty results, updated to UO CLI 1.2.0 by @nllong in https://github.com/urbanopt/urbanopt-des/pull/78
- Add uo update cli method to wrapper by @nllong in https://github.com/urbanopt/urbanopt-des/pull/80
- Improve aggregate method to create single large load by @nllong in https://github.com/urbanopt/urbanopt-des/pull/81
- Add more building statistics to export CSV by @nllong in https://github.com/urbanopt/urbanopt-des/pull/89

### Bug Fixes 🐞

- Fix building and DES end uses by adding in pump and fans to DES post processing by @nllong in https://github.com/urbanopt/urbanopt-des/pull/79
- Update location on where dataframes are saved by @nllong in https://github.com/urbanopt/urbanopt-des/pull/82
- Copy weather files after copying the project by @nllong in https://github.com/urbanopt/urbanopt-des/pull/87

### Dependency Updates 📦

- deps: bump the dev-deps group across 1 directory with 3 updates by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/73
- deps: bump cyclopts from 4.5.1 to 4.5.2 in the prod-deps group by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/68
- deps: bump the dev-deps group with 2 updates by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/75
- deps: bump mypy from 1.20.2 to 2.1.0 in the dev-deps group across 1 directory by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/77
- deps: bump cyclopts from 4.10.2 to 4.11.0 in the prod-deps group across 1 directory by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/76
- deps: bump cyclopts from 4.13.0 to 4.15.0 in the prod-deps group by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/84
- deps: bump the prod-deps group with 2 updates by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/90
- deps: bump the dev-deps group across 1 directory with 2 updates by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/95
- deps: bump cyclopts from 4.16.1 to 4.21.0 in the prod-deps group across 1 directory by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/91

### Maintenance 🧹

- ci: bump the actions-deps group across 1 directory with 3 updates by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/72
- ci: bump actions/checkout from 6 to 7 in the actions-deps group by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/93
- Add test for running uo and uo-des with project from scratch by @nllong in https://github.com/urbanopt/urbanopt-des/pull/92

**Full Changelog**: https://github.com/urbanopt/urbanopt-des/compare/v0.2.0...v0.3.0

## Version 0.2.0

## What's Changed

### Improvements & Bug Fixes 🐛

- Breakout heating plant natural gas and electricity by @nllong in https://github.com/urbanopt/urbanopt-des/pull/53
- Mock modelica reader and implement aggregation test by @nllong in https://github.com/urbanopt/urbanopt-des/pull/54
- Refactor for constants and type checking by @nllong in https://github.com/urbanopt/urbanopt-des/pull/55
- Add in natural gas grid metrics by @nllong in https://github.com/urbanopt/urbanopt-des/pull/59

### Bug Fixes 🐞

- Fix aggregation by @nllong in https://github.com/urbanopt/urbanopt-des/pull/58

### Dependency Updates 📦

- deps: bump the dev-deps group with 2 updates by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/44
- ci: bump the actions-deps group with 2 updates by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/43
- ci: bump actions/checkout from 5 to 6 in the actions-deps group by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/47
- deps: bump the dev-deps group across 1 directory with 2 updates by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/48
- deps: bump mypy from 1.18.2 to 1.19.0 in the dev-deps group by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/49
- ci: bump the actions-deps group with 2 updates by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/56
- deps: bump cyclopts from 3.24.0 to 4.5.1 in the prod-deps group across 1 directory by @dependabot[bot] in https://github.com/urbanopt/urbanopt-des/pull/65
- Bump version, update GMT dependency, and run pre-commit by @nllong in https://github.com/urbanopt/urbanopt-des/pull/67

### Maintenance 🧹

- Update CI to checkout the GMT repo if developing by @nllong in https://github.com/urbanopt/urbanopt-des/pull/52
- Update copyright name by @nllong in https://github.com/urbanopt/urbanopt-des/pull/61
- Update dependabot by @nllong in https://github.com/urbanopt/urbanopt-des/pull/63
- Lock pandas to version <1.0 by @nllong in https://github.com/urbanopt/urbanopt-des/pull/64
- update names and copyright dates by @kflemin in https://github.com/urbanopt/urbanopt-des/pull/66

## New Contributors

- @kflemin made their first contribution in https://github.com/urbanopt/urbanopt-des/pull/66

## Version 0.1.3

- Downgrade Geopandas to <1.0 by @vtnate in <https://github.com/urbanopt/urbanopt-des/pull/40>

## Version 0.1.2

- Bump GMT to version 0.12.0 by @vtnate in <https://github.com/urbanopt/urbanopt-des/pull/39>

## Version 0.1.1

- Bump GMT to version 0.11.0 by @vtnate in <https://github.com/urbanopt/urbanopt-des/pull/26>

## Version 0.1.0

- Add build test by @nllong in https://github.com/urbanopt/urbanopt-des/pull/2
- Use ruff, cleanup formatting by @nllong in https://github.com/urbanopt/urbanopt-des/pull/1
- Fix typo in ruff config filename by @vtnate in https://github.com/urbanopt/urbanopt-des/pull/3
- Add simple unit test and support processing UO results only by @nllong in https://github.com/urbanopt/urbanopt-des/pull/4
- Add more building mappings by @nllong in https://github.com/urbanopt/urbanopt-des/pull/5
- When aggregating buildings, treat strings better by @nllong in https://github.com/urbanopt/urbanopt-des/pull/6
- Support 4G result data by @nllong in https://github.com/urbanopt/urbanopt-des/pull/7
- Inherit much of geojson parser from GMT by @vtnate in https://github.com/urbanopt/urbanopt-des/pull/8
- Explicitly name chillers & boilers when there is only one by @vtnate in https://github.com/urbanopt/urbanopt-des/pull/10
- Update readme by @nllong in https://github.com/urbanopt/urbanopt-des/pull/12
- Automate releasing to PyPI by @vtnate in https://github.com/urbanopt/urbanopt-des/pull/11
- Allow skip validation at a higher level by @nllong in https://github.com/urbanopt/urbanopt-des/pull/15
- Fix links in README by @nllong in https://github.com/urbanopt/urbanopt-des/pull/13
- Add uo_des call to CLI wrapper by @nllong in https://github.com/urbanopt/urbanopt-des/pull/17
- Add building level result tests by @nllong in https://github.com/urbanopt/urbanopt-des/pull/18
- Infrastructure improvements by @vtnate in https://github.com/urbanopt/urbanopt-des/pull/19
- Improve & expand Modelica output processing by @vtnate in https://github.com/urbanopt/urbanopt-des/pull/16
