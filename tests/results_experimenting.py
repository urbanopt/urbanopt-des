import marimo

__generated_with = "0.11.23"
app = marimo.App(width="medium")


@app.cell
def _():
    from pathlib import Path

    from urbanopt_des.modelica_results import ModelicaResults

    return ModelicaResults, Path


@app.cell
def _(Path, __file__):
    mat_filepath = (
        Path.home()
        / "github"
        / "three_building_test_des_agg"
        / "five_g_controlled_flow"
        / "five_g_controlled_flow.Districts.DistrictEnergySystem_results"
        / "five_g_controlled_flow.Districts.DistrictEnergySystem_res.mat"
    )
    here = Path(__file__).parent
    return here, mat_filepath


@app.cell
def _(ModelicaResults, mat_filepath):
    five_g_controlled_results = ModelicaResults(mat_filename=mat_filepath)
    return (five_g_controlled_results,)


@app.cell
def _(five_g_controlled_results):
    five_g_controlled_results.resample_and_convert_to_df()


@app.cell
def _(five_g_controlled_results):
    five_g_controlled_results.save_dataframes()


@app.cell
def _(five_g_controlled_results):
    five_g_controlled_results.agg_for_reopt()


@app.cell
def _(Path):
    tanushree_test_filepath = (
        Path.home()
        / "github"
        / "geojson-modelica-translator"
        / "tests"
        / "geojson_modelica_translator"
        / "data"
        / "modelica_multiple"
        / "modelica_multiple.Districts.DistrictEnergySystem_results"
        / "modelica_multiple.Districts.DistrictEnergySystem_res.mat"
    )
    return (tanushree_test_filepath,)


@app.cell
def _(ModelicaResults, tanushree_test_filepath):
    tanushree_results = ModelicaResults(mat_filename=tanushree_test_filepath)
    return (tanushree_results,)


@app.cell
def _(tanushree_results):
    tanushree_results.agg_for_reopt()


if __name__ == "__main__":
    app.run()
