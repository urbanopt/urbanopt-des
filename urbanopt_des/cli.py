from importlib.metadata import version
from pathlib import Path

from cyclopts import App

from .modelica_results import ModelicaResults

app = App(
    version=version("urbanopt-des"),
    version_flags=["--version", "-v"],
    help="Post-process and evaluate results from a Modelica simulation of an URBANopt district",
)


@app.command
def prepare_reopt_input(mat_filename: Path, output_path: Path | None = None) -> None:
    """Extract data from Modelica simulation results and prepare for REopt API input

    Parameters
    ----------
    mat_filename: Path
        Path to the file containing Modelica simulation results (.mat or zipped .mat)
    output_path: Path
        Custom path for saving files. Default is the same directory as the input file.
    """

    mr = ModelicaResults(mat_filename, output_path)
    mr.agg_for_reopt()


if __name__ == "__main__":
    app()
