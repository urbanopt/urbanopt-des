# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

import os

import pytest

from urbanopt_des.results_guard import (
    ExistingResultsError,
    check_manifest,
    guard_scenario_dir,
    manifest_changes,
    mark_scenario_dir,
    take_manifest,
)


def test_manifest_allows_new_files_and_flags_changes(tmp_path):
    root = tmp_path / "results"
    (root / "fourg_system").mkdir(parents=True)
    existing = root / "fourg_system" / "power.csv"
    existing.write_text("a")
    before = take_manifest([root])
    assert check_manifest(before, take_manifest([root])) == 1

    (root / "new_scenario").mkdir()
    (root / "new_scenario" / "out.csv").write_text("new")
    assert check_manifest(before, take_manifest([root])) == 1  # new files are fine

    existing.write_text("changed content")
    os.utime(existing, ns=(1, 1))
    changes = manifest_changes(before, take_manifest([root]))
    assert changes["changed"] == [str(existing.resolve())]
    with pytest.raises(ExistingResultsError, match="1 changed"):
        check_manifest(before, take_manifest([root]))


def test_manifest_exclude_and_missing(tmp_path):
    root = tmp_path / "results"
    (root / "ours").mkdir(parents=True)
    (root / "ours" / "x.txt").write_text("x")
    (root / "keep.txt").write_text("k")
    before = take_manifest([root, tmp_path / "does_not_exist"], exclude=[root / "ours"])
    assert list(before) == [str((root / "keep.txt").resolve())]
    (root / "keep.txt").unlink()
    with pytest.raises(ExistingResultsError, match="1 missing"):
        check_manifest(before, take_manifest([root], exclude=[root / "ours"]))


def test_guard_scenario_dir(tmp_path):
    scenario = tmp_path / "oneg_steam"
    assert guard_scenario_dir(scenario, ".mine") == "new"
    scenario.mkdir()
    with pytest.raises(ExistingResultsError, match="not created by this workflow"):
        guard_scenario_dir(scenario, ".mine")
    mark_scenario_dir(scenario, ".mine")
    assert guard_scenario_dir(scenario, ".mine") == "ours"
