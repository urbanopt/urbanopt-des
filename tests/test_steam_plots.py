# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

import pytest

mpl = pytest.importorskip("matplotlib")
mpl.use("Agg")

from tests.mock_modelica_reader import MockModelicaReader  # noqa: E402
from urbanopt_des.steam_plots import steam_dashboard  # noqa: E402
from urbanopt_des.steam_results import SteamResults  # noqa: E402


def test_steam_dashboard_writes_png(tmp_path):
    n = 49
    data = {
        "pla.QFue_flow": [1e6] * n,
        "pla.boi.QWat_flow": [0.7e6] * n,
        "pla.PPum": [1e3] * n,
        "bld1.Q_flow": [0.69e6] * n,
        "losMak.QLos_flow": [1e4] * n,
        "losMak.mLea_flow": [0.001] * n,
        "losMak.mMak_flow": [0.002] * n,
        "losMak.mDum_flow": [0.001] * n,
    }
    png = tmp_path / "plots" / "dashboard.png"
    fig = steam_dashboard(SteamResults(reader=MockModelicaReader(data)), "TEST", "subtitle", png)
    assert png.exists()
    assert len(fig.axes) > 5
