"""One-shot: log in to the Tradovate test account, pull the contract's 1-minute bars, render the illiquid chart PNG.

    python3 make_chart.py MGCV6 "2026-09-30 03:03:57" 4198.3 Buy /path/out.png
The fill time is CT. Used by the dashboard's "Get chart" button via watch_charts.py.
"""
import json
import sys
from datetime import datetime

import warnings
warnings.filterwarnings("ignore")
from playwright.sync_api import sync_playwright

from chart_shot import login, capture_bars, VIEW, CT
from render_chart import render


def make(contract, fill_ct, price, side, out):
    bars = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport=VIEW, timezone_id="America/Chicago")
        pg = ctx.new_page()
        capture_bars(pg, bars)
        login(pg)
        before = {k: len(v) for k, v in bars.items()}
        pg.mouse.click(225, 24)                         # open the top search box
        pg.wait_for_timeout(1000)
        pg.locator("input.search-box--input").first.fill(contract)
        pg.wait_for_timeout(2500)
        pg.locator("ul.dropdown-menu a", has_text=contract).first.click()
        try:
            pg.get_by_role("button", name="Yes use previous settings").click(timeout=4000)
        except Exception:
            pass
        for _ in range(30):
            pg.wait_for_timeout(500)
            if any(len(bars[k]) > before.get(k, 0) for k in bars):
                break
        pg.wait_for_timeout(4000)
        b.close()
    if not bars:
        raise RuntimeError(f"No chart data for {contract}")
    cid = max(bars, key=lambda k: len(bars[k]) - before.get(k, 0))
    render(contract, fill_ct.replace(tzinfo=CT), price, side, bars[cid], out)


if __name__ == "__main__":
    contract, fill, price, side, out = sys.argv[1:6]
    make(contract, datetime.strptime(fill, "%Y-%m-%d %H:%M:%S"), float(price), side, out)
