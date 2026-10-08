"""Render a chart that matches Tradovate's native 1-minute chart screenshot, for an illiquid-contract case.

Minimalist to match the manual screenshots: pure black, sparse candles plotted by bar index, a dashed crosshair
on the last traded bar before the fill, that bar's OHLC box top-left, and the time pill on the x-axis.
"""
import json
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.transforms as mtransforms
from matplotlib.patches import Rectangle, FancyBboxPatch

CT = ZoneInfo("America/Chicago")
BG = "#000000"
GRID = "#141414"
AXFG = "#8e8e94"
UP, DOWN = "#2eae6a", "#e2574c"
CROSS = "#9a9a9a"
BOX_BG = "#111317"
BOX_BORDER = "#3a3d44"
HILITE = "#e2574c"


def _ampm(dt):
    h = dt.hour % 12 or 12
    return f"{dt.month:02d}/{dt.day:02d}/{dt.year} {h}:{dt.minute:02d}:{dt.second:02d} {'am' if dt.hour < 12 else 'pm'}"


def render(contract, fill_ct, entry_price, side, bars, out, pre=22, post=58):
    for x in bars:
        x["t"] = datetime.fromisoformat(x["timestamp"].replace("Z", "+00:00")).astimezone(CT)
    bars.sort(key=lambda x: x["t"])
    li = max(i for i, x in enumerate(bars) if x["t"] <= fill_ct)      # last traded bar at/before the fill
    a = max(0, li - pre)
    b = min(len(bars), li + post + 1)
    view = bars[a:b]
    li_v = li - a
    right_edge = li_v + post + 1        # always extend this far right, even past the data — empty = illiquid

    fig, ax = plt.subplots(figsize=(13, 10), dpi=150)
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    for s in ax.spines.values(): s.set_color(GRID)
    ax.tick_params(colors=AXFG, labelsize=8.5, length=0)
    ax.grid(True, color=GRID, lw=0.5)

    for i, x in enumerate(view):
        o, h, l, c = x["open"], x["high"], x["low"], x["close"]
        col = UP if c >= o else DOWN
        ax.plot([i, i], [l, h], color=col, lw=0.8, zorder=2, solid_capstyle="round")
        ax.add_patch(Rectangle((i - 0.32, min(o, c)), 0.64, max(abs(c - o), 0.04),
                               facecolor=col, edgecolor=col, lw=0.4, zorder=3))

    stale = view[li_v]
    vol = stale.get("upVolume", 0) + stale.get("downVolume", 0)
    dp = 1 if stale["close"] >= 100 else 2

    # dashed crosshair on the stale bar
    ax.axvline(li_v, color=CROSS, ls=(0, (4, 3)), lw=0.8, zorder=4)
    ax.axhline(stale["close"], color=CROSS, ls=(0, (4, 3)), lw=0.8, zorder=4)
    # thin highlight box around the stale bar
    pad = (max(x["high"] for x in view) - min(x["low"] for x in view)) * 0.012
    ax.add_patch(Rectangle((li_v - 0.5, stale["low"] - pad), 1, stale["high"] - stale["low"] + 2 * pad,
                           fill=False, edgecolor=HILITE, lw=1.3, zorder=5))

    # OHLC box, top-left, Tradovate-style — contract name added, red border
    lines = [contract, f"{stale['t']:%m/%d/%Y %H:%M}", "",
             f"OPEN    {stale['open']:.{dp}f}", f"HIGH    {stale['high']:.{dp}f}",
             f"LOW     {stale['low']:.{dp}f}", f"CLOSE   {stale['close']:.{dp}f}", f"VOLUME  {vol}"]
    ax.text(0.011, 0.978, "\n".join(lines), transform=ax.transAxes, color="#e8e8ea", fontsize=10,
            family="monospace", va="top", ha="left", zorder=6,
            bbox=dict(boxstyle="round,pad=0.55", facecolor=BOX_BG, edgecolor=HILITE, lw=1.8))

    # x axis: a few date/time labels, price axis on the right
    # a few evenly-spaced, compact, non-overlapping time labels across the data region
    n = 5
    ticks = sorted(set(round(i * (len(view) - 1) / (n - 1)) for i in range(n))) if len(view) > 1 else [0]
    ax.set_xticks(ticks)
    ax.set_xticklabels([view[i]["t"].strftime("%-m/%-d %-I:%M%p").lower() for i in ticks])
    ax.set_xlim(-1, right_edge); ax.yaxis.tick_right(); ax.yaxis.set_label_position("right")
    ax.margins(y=0.04)

    # time pill under the crosshair on the x axis
    trans = mtransforms.blended_transform_factory(ax.transData, ax.transAxes)
    ax.text(li_v, -0.085, _ampm(stale["t"]), transform=trans, color="#f0f0f0", fontsize=9, ha="center", va="top",
            zorder=7, bbox=dict(boxstyle="round,pad=0.35", facecolor="#2a2d33", edgecolor=HILITE, lw=1.5))

    fig.tight_layout(rect=[0, 0.02, 1, 1])
    fig.savefig(out, facecolor=BG); plt.close(fig)
    print("saved", out)


if __name__ == "__main__":
    contract, fill, price, side, bars_json, out = sys.argv[1:7]
    render(contract, datetime.strptime(fill, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CT),
           float(price), side, json.load(open(bars_json)), out)
