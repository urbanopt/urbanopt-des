# Changelog

## Version 0.2.0

<!-- Release notes generated using configuration in .github/release.yml at develop -->

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
