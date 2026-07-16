# Notes

The measures in this directory are copied from the openstudio calibration gem. Only certain measures are copied to
save space.

This directory (including `uo_building_to_osa.rb`) is standalone Ruby tooling, not wired into the
`urbanopt_des` Python package or its CI. Ruby is **not** required to install or use `urbanopt-des`;
it's only needed if you're working on the script here.

## Testing

The JSON/OSW manipulation logic used by `uo_building_to_osa.rb` lives in `lib/osw_transform.rb`,
kept free of any OpenStudio gem dependency so it can be tested with plain Ruby (no `bundle
install` required -- `json` and `minitest` both ship with Ruby's standard library):

```bash
ruby test/test_osw_transform.rb
```

Tests read real fixture files from `test/fixtures/` and write real temporary files (no mocking).
