# URBANopt DES

Project-wide context is in `../AGENTS.md`; shared preferences are in `~/.codex/AGENTS.md`.

- Python source lives in `urbanopt_des/`; tests live in `tests/`. This package combines OpenStudio/EnergyPlus and Modelica/Buildings results for district energy analysis.
- Use `poetry run pytest` for tests. The README identifies `tests/test_output/` as test output.
- Formatting and lint configuration live in `ruff.toml` and `.pre-commit-config.yaml`; the documented full check is `poetry run pre-commit run --all-files`.
- `pyproject.toml` selects the GMT dependency. A commented sibling path dependency is available for development; do not assume the sibling checkout is active.
- The sibling `esbe/` project consumes this checkout through an editable path dependency, so library changes can affect its notebooks directly.
