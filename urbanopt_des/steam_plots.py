# :copyright (c) URBANopt, Alliance for Energy Innovation, LLC, and other contributors.
# See also https://github.com/urbanopt/urbanopt-des/blob/develop/LICENSE.md

"""Plots for 1st-generation (steam) district results. Requires matplotlib (imported when called)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .steam_results import COL_BOILER, COL_DELIVERED, COL_FUEL, SteamResults

COLORS = {
    "fuel": "#E05A33",
    "boiler": "#F0A030",
    "delivered": "#2E86AB",
    "loss": "#B0BEC5",
    "pump": "#7E5BA6",
    "efficiency": "#2E9E5B",
    "title": "#0F3554",
    "muted": "#455A64",
}


def _pyplot():
    try:
        import matplotlib.pyplot as plt  # noqa: PLC0415 (optional dependency)
    except ImportError as err:  # pragma: no cover - depends on the environment
        raise ImportError("steam_dashboard requires matplotlib; install it in the analysis environment") from err
    return plt


def steam_dashboard(
    results: SteamResults,
    title: str = "STEAM DISTRICT — ANNUAL SYSTEM RESPONSE",
    subtitle: str = "",
    save_path: Path | str | None = None,
) -> Any:
    """Annual system response dashboard: KPI tiles, hourly power, energy balance, monthly bars, fuel split.

    :param results: SteamResults of a GMT 1G steam district
    :param title: figure title
    :param subtitle: one-line description under the title
    :param save_path: write a PNG here when given
    :return: matplotlib Figure
    """
    plt = _pyplot()
    s = results.annual_summary()
    h = results.hourly() / 1e3  # kW
    monthly = results.monthly()
    c = COLORS
    gas_key = next(k for k in s if k.startswith("Natural gas [m3"))

    fig = plt.figure(figsize=(14, 17))
    gs = fig.add_gridspec(5, 4, height_ratios=[0.5, 1.1, 2.0, 2.2, 0.5], hspace=0.55, wspace=0.3)
    ax = fig.add_subplot(gs[0, :])
    ax.axis("off")
    ax.text(0, 0.7, title, fontsize=22, fontweight="bold", color=c["title"])
    ax.text(0, 0.1, subtitle, fontsize=11, color=c["muted"])

    tiles = [
        ("TOTAL ENERGY IN", s["Total energy in (fuel, LHV) [GJ]"], "GJ", c["fuel"]),
        ("USEFUL HEAT (BOILER)", s["Boiler useful heat [GJ]"], "GJ", c["boiler"]),
        ("DELIVERED TO BUILDINGS", s["Delivered to buildings [GJ]"], "GJ", c["delivered"]),
        ("NATURAL GAS USED", s[gas_key], "m³", c["fuel"]),
        ("BOILER EFFICIENCY", s["Boiler efficiency [%]"], "%", c["efficiency"]),
        ("SYSTEM EFFICIENCY", s["System efficiency [%]"], "%", c["efficiency"]),
        ("PUMP ELECTRICITY", s["Feedwater pump electricity [kWh]"], "kWh", c["pump"]),
        ("PEAK FUEL RATE", s["Peak fuel rate [kW]"], "kW", c["fuel"]),
    ]
    if results.has_losses:
        tiles[6] = ("MAKE-UP WATER", s["Make-up water [m3]"], "m³", c["delivered"])
    tile_gs = gs[1, :].subgridspec(2, 4, hspace=0.4)
    for i, (label, value, unit, color) in enumerate(tiles):
        a = fig.add_subplot(tile_gs[i // 4, i % 4])
        a.set_xticks([])
        a.set_yticks([])
        for spine in a.spines.values():
            spine.set_color("#CFD8DC")
        a.axvline(0, color=color, lw=6)
        a.text(0.08, 0.75, label, fontsize=9, fontweight="bold", color=c["muted"], transform=a.transAxes)
        text = f"{value:,.1f}" if unit == "%" else f"{value:,.0f}"
        a.text(0.08, 0.3, text, fontsize=20, fontweight="bold", transform=a.transAxes)
        a.text(0.92, 0.3, unit, fontsize=10, ha="right", color="#607D8B", transform=a.transAxes)

    a = fig.add_subplot(gs[2, :])
    a.plot(h.index, h[COL_FUEL], color=c["fuel"], lw=0.6, label="Fuel input rate")
    if COL_BOILER in h:
        a.plot(h.index, h[COL_BOILER], color=c["boiler"], lw=0.6, label="Boiler useful heat")
    a.plot(h.index, h[COL_DELIVERED], color=c["delivered"], lw=0.6, label="Building load served")
    a.set_title("System response — instantaneous power over the year (hourly)", loc="left", fontweight="bold")
    a.set_ylabel("Power (kW)")
    a.legend(loc="upper right", ncol=3, frameon=False)

    a = fig.add_subplot(gs[3, :2])
    steps = [
        ("Fuel\nin", s["Total energy in (fuel, LHV) [GJ]"], 0, c["fuel"]),
        ("Combustion\nloss", s["Combustion loss [GJ]"], s["Boiler useful heat [GJ]"], c["loss"]),
        ("Boiler\nheat", s["Boiler useful heat [GJ]"], 0, c["boiler"]),
        ("Dist. +\nstorage loss", s["Dist. + storage loss [GJ]"], s["Delivered to buildings [GJ]"], c["loss"]),
        ("Delivered\nto bldgs", s["Delivered to buildings [GJ]"], 0, c["delivered"]),
    ]
    for i, (_label, value, bottom, color) in enumerate(steps):
        a.bar(i, value, bottom=bottom, color=color, width=0.6)
        a.text(i, bottom + value, f"{value:,.0f}", ha="center", va="bottom", fontweight="bold", fontsize=9)
    a.set_xticks(range(len(steps)), [x[0] for x in steps], fontsize=9)
    a.set_ylabel("Energy (GJ)")
    a.set_title("Energy balance (annual totals)", loc="left", fontweight="bold")

    a = fig.add_subplot(gs[3, 2:])
    x = np.arange(len(monthly))
    a.bar(x - 0.2, monthly[COL_FUEL], 0.4, color=c["fuel"], label="Fuel in")
    a.bar(x + 0.2, monthly[COL_DELIVERED], 0.4, color=c["delivered"], label="Delivered")
    a.set_xticks(x, monthly.index.strftime("%b"))
    a.set_ylabel("Energy (GJ / month)")
    a.legend(frameon=False)
    a.set_title("Monthly energy in vs. delivered", loc="left", fontweight="bold")

    a = fig.add_subplot(gs[4, :])
    fuel_in = s["Total energy in (fuel, LHV) [GJ]"]
    parts = [
        ("Delivered", s["Delivered to buildings [GJ]"], c["delivered"]),
        ("Dist.+storage loss", s["Dist. + storage loss [GJ]"], c["boiler"]),
        ("Combustion loss", s["Combustion loss [GJ]"], c["loss"]),
    ]
    left = 0.0
    for label, value, color in parts:
        share = value / fuel_in if fuel_in else 0.0
        a.barh(0, share, left=left, color=color, label=label)
        if share > 0.05:
            a.text(left + share / 2, 0, f"{100 * share:.0f}%", ha="center", va="center", color="white", fontweight="bold")
        left += share
    a.set_xlim(0, 1)
    a.axis("off")
    a.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, frameon=False)
    a.set_title("WHERE THE FUEL ENERGY GOES", loc="left", fontsize=10, fontweight="bold", color=c["muted"])

    if save_path is not None:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    return fig
