# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

"""Guardrails that keep existing analysis results from being deleted, overwritten, or re-run.

Typical use in an analysis notebook::

    before = take_manifest([des_analysis_agg_dir, results_summary_dir], exclude=[new_scenario_dir])
    ...  # build and run new scenarios only in new folders
    check_manifest(before, take_manifest([des_analysis_agg_dir, results_summary_dir], exclude=[new_scenario_dir]))

and, for every scenario folder a workflow creates::

    state = guard_scenario_dir(scenario_dir, marker="created_by_steam_analysis")  # "new" or "ours", or raises
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterable
from pathlib import Path

DEFAULT_MARKER = ".created_by_urbanopt_des"

Manifest = dict[str, tuple[int, int]]


class ExistingResultsError(RuntimeError):
    """Raised when a workflow would touch results it did not create."""


def take_manifest(roots: Iterable[Path | str], exclude: Iterable[Path | str] = ()) -> Manifest:
    """Record path -> (size in bytes, mtime in ns) for every file under ``roots``.

    :param roots: folders to record; missing folders are skipped
    :param exclude: folders (and their subfolders) to leave out, e.g. folders the workflow itself creates
    :return: the manifest
    """
    excluded = [Path(e).resolve() for e in exclude]
    manifest: Manifest = {}
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        for dirpath, _dirnames, filenames in os.walk(root_path):
            current = Path(dirpath).resolve()
            if any(current == e or e in current.parents for e in excluded):
                continue
            for filename in filenames:
                path = current / filename
                try:
                    stat = path.stat()
                except FileNotFoundError:
                    continue
                manifest[str(path)] = (stat.st_size, stat.st_mtime_ns)
    return manifest


def manifest_changes(before: Manifest, after: Manifest) -> dict[str, list[str]]:
    """Pre-existing files that were removed or modified between two manifests. New files are allowed."""
    return {
        "missing": [p for p in before if p not in after],
        "changed": [p for p in before if p in after and before[p] != after[p]],
    }


def check_manifest(before: Manifest, after: Manifest) -> int:
    """Raise ExistingResultsError if any pre-existing file was removed or modified.

    :return: number of pre-existing files checked
    """
    changes = manifest_changes(before, after)
    if changes["missing"] or changes["changed"]:
        sample = "\n  ".join((changes["missing"] + changes["changed"])[:20])
        raise ExistingResultsError(
            f"Existing results were modified or removed: {len(changes['missing'])} missing, {len(changes['changed'])} changed.\n  {sample}"
        )
    return len(before)


def guard_scenario_dir(scenario_dir: Path | str, marker: str = DEFAULT_MARKER) -> str:
    """Check a scenario folder before a workflow writes to it.

    :return: "new" if the folder does not exist, "ours" if it carries ``marker`` (created by this workflow)
    :raises ExistingResultsError: if the folder exists and was not created by this workflow
    """
    scenario_dir = Path(scenario_dir)
    if not scenario_dir.exists():
        return "new"
    if (scenario_dir / marker).exists():
        return "ours"
    raise ExistingResultsError(
        f"{scenario_dir} exists and was not created by this workflow (no {marker} file). "
        "It will not be touched; choose a different scenario name."
    )


def mark_scenario_dir(scenario_dir: Path | str, marker: str = DEFAULT_MARKER) -> Path:
    """Write the marker file that identifies a folder as created by this workflow."""
    path = Path(scenario_dir) / marker
    path.write_text(f"created {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    return path
