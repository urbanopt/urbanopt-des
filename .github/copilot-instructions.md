# Copilot instructions for urbanopt-des

## Updating URBANopt CLI / OpenStudio dependencies

Trigger phrases: "new UO released", "update urbanopt cli", "bump openstudio version",
"update dependencies and test" (in the context of URBANopt/OpenStudio).

This repo shells out to the **URBANopt CLI** (a Ruby program bundling an **OpenStudio SDK**
release) rather than depending on it via a package manager, so bumping versions is a manual,
multi-file process. Follow these steps in order. Do not skip the "verify on rubygems.org" step —
pinning an unpublished gem version will break `bundle install`.

### 1. Identify what actually changed

1. Find the latest **published** (non-draft) release tag on
   `https://github.com/urbanopt/urbanopt-cli` (check `/releases`, not just `/tags` — tags without
   a release have no downloadable `.deb`/`.gem` assets and CI can't use them).
2. On that tag, fetch two files to learn what it bundles:
   - `FindOpenStudioSDK.cmake` → `OPENSTUDIO_VERSION_MAJOR/MINOR/PATCH` gives the exact
     OpenStudio SDK version (e.g. `3.10.0`).
   - `uo_cli.gemspec` → `required_ruby_version` and the pinned `urbanopt-geojson`,
     `urbanopt-reopt`, `urbanopt-reporting`, `urbanopt-rnm-us`, `urbanopt-scenario` versions.
3. If the OpenStudio SDK version didn't change from what's already pinned in this repo, only
   step 2 (the CLI version bump) is needed — skip step 3.

### 2. Update the URBANopt CLI version pin

File: `urbanopt_des/uo_cli_wrapper.py`

- Bump `DEFAULT_UO_VERSION = "X.Y.Z"` (no leading `v`) to the new release tag.
- Nothing else needs to change here: `.github/workflows/ci.yml` resolves the GitHub release,
  asset URL, and cache keys dynamically from `UOCliWrapper.DEFAULT_UO_VERSION` at run time.
- Do NOT hand-edit `ci.yml` version strings — there aren't any; it reads the constant above.

### 3. Update the bundled Ruby gems (`activity_to_osa/`)

File: `urbanopt_des/activity_to_osa/Gemfile` (single file — there is intentionally **no**
accompanying `.gemspec`; we don't publish an "openstudio-gems" package, so don't reintroduce a
gemspec/`gemspec` directive split just because upstream has one — see "Note" below).

Versions here track NREL/NatLabRockies' `openstudio-gems` repo, which is versioned to match the
OpenStudio SDK release (not the URBANopt CLI release).

1. On `https://github.com/NatLabRockies/openstudio-gems`, find the tag `vX.Y.Z` matching the
   OpenStudio SDK version from step 1.2 exactly. If no exact tag exists, use the closest earlier
   version and note the mismatch in the PR description.
2. Fetch that tag's `Gemfile` (and, for reference only, its `openstudio-gems.gemspec` — see
   "Note" below for why we don't copy the gemspec itself). In the `Gemfile`, use the **`elsif
   !FINAL_PACKAGE` branch** values (plain rubygems-published versions), not the `LOCAL_DEV`
   (path-based) or `FINAL_PACKAGE` (github-pinned rubocop fork) branches — ours is a flat
   consumer Gemfile, not the openstudio-gems build repo itself.
3. Update in our `Gemfile`: `ruby` version, `addressable`, `regexp_parser`, `oslg`, `tbd`,
   `osut`, `bcl`, `openstudio-extension`, `openstudio-workflow`, `openstudio-standards`,
   `openstudio_measure_tester`, `parallel`, and the `:native_ext` group (`jaro_winkler`,
   `sqlite3`, `oga`, `msgpack`). Prefer plain `gem 'name', 'version'` (rubygems) over `:github`
   refs whenever the version is published on rubygems.org (check step 4) — GitHub-pinned forks
   are a maintenance liability and most of these gems have since been published to rubygems
   directly.
4. Update `gem 'urbanopt-reporting', '~> X.Y.0'` to match the `urbanopt-reporting` version pinned
   in `uo_cli.gemspec` (step 1.2) — this is the CLI's own reporting gem version, not the
   openstudio-gems repo's (which doesn't include it).
5. Do not reintroduce `pycall` or `json_schemer` unless something in this repo starts requiring
   them again (both were dropped upstream and are unused here as of this writing — verify with
   `grep -rn "pycall\|PyCall\|json_schemer\|JSONSchemer" --include="*.rb" .`).

**Note on why there's no gemspec:** upstream's `openstudio-gems.gemspec` exists because that repo
*publishes* an `openstudio-gems` RubyGem — the gemspec is that gem's dependency contract, and
their Gemfile re-pins the same deps to exact versions purely for their own build/lockfile
determinism. We never publish or install "openstudio-gems" as a package; our Gemfile is only ever
`bundle install`'d directly on the OSA worker (registered via `a.gem_files.add(...)` in
`uo_building_to_osa.rb`). A gemspec here would just duplicate entries with no benefit, and a
plain `gemspec` directive also silently pulls in upstream's gemspec *development* dependencies
(`rubocop`, `simplecov`, etc.) that we don't need to run measures. Keep it a single flat Gemfile.

### 4. Verify every pinned gem version is actually published

For each gem/version pin you changed, confirm it exists on rubygems before committing:

```bash
curl -s "https://rubygems.org/api/v1/versions/<gem_name>.json" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('<version>' in [x['number'] for x in d])"
```

Should print `True`. If `False`, the gem is only available via a `:github` ref — keep the
`:github`/`:ref` form for that one gem instead of switching it to a plain version.

### 5. Validate Ruby syntax (no bundler required)

```bash
cd urbanopt_des/activity_to_osa
ruby -c Gemfile
ruby -c openstudio-gems.gemspec
```

Both must print `Syntax OK`.

### 6. Check the GMT/uv override workaround in CI

`.github/workflows/ci.yml`, step "Run pytest", carries a temporary workaround
(`UV_OVERRIDE` forcing `geojson-modelica-translator>=0.15.0,<0.16.0`) because the URBANopt CLI's
isolated `uv tool run --from urbanopt-des==<pinned>` previously resolved an older GMT that lacked
`ets_pump_flow_rate`. Tracking: `urbanopt/urbanopt-des#99`.

- Check what `urbanopt-des` version the new CLI release's isolated tool env pins (search the CLI
  release's `lib/` or its own `uv`/`pyproject` references for `urbanopt-des==`).
- If that pinned `urbanopt-des` version now requires `geojson-modelica-translator>=0.15.0`
  natively, remove the `UV_OVERRIDE` workaround block and this comment from `ci.yml`, and close
  issue #99.

### 7. Test

```bash
poetry install --no-root
poetry run pytest -v --cov-report term-missing --cov
```

- Unit tests don't require the real URBANopt CLI to be installed (they mock subprocess calls) —
  run these first as a fast check.
- To exercise the real CLI end-to-end (matches what CI does), install the resolved `.deb`/release
  asset for the new `DEFAULT_UO_VERSION`, set `PATH`/`GEM_HOME`/`GEM_PATH`/`RUBYLIB` as shown in
  `ci.yml`'s "Install URBANopt CLI" step, then run:
  ```bash
  RUN_INTENSIVE_FROM_SCRATCH_TESTS=true poetry run pytest -v tests/test_uo_cli_from_scratch_integration_test.py
  ```
- Push a branch / open a PR to let the real `ci.yml` workflow run on GitHub Actions — this is the
  most reliable full validation since it installs the actual CLI `.deb` in a clean Ubuntu runner.

### 8. What NOT to touch

- `urbanopt_des/activity_to_osa/uo_building_to_osa.rb` and `worker_init.sh` are standalone,
  disconnected scripts (not invoked anywhere in the Python package) for an OpenStudio-Server-based
  calibration workflow. `worker_init.sh` hardcodes `urbanopt-reporting 0.9.1` against a *different*
  Gemfile (the OpenStudio Server's own, found via `RUBYLIB` at runtime) — leave it alone unless
  explicitly asked, since its target server's OpenStudio version is unknown/independent of this
  repo's pinned CLI version.
- `CHANGELOG.md` is auto-generated from merged PR labels via `.github/release.yml` — don't
  hand-edit it; just label the PR appropriately (e.g. `dependencies`).
