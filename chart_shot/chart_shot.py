"""Tradovate chart screenshot for illiquid-contract cases.

Logs in to the test account (credentials in ~/.tradovate/test_account.json), opens a 1-minute chart of the contract,
hovers the last bar at or before the fill time so the price box (OPEN/HIGH/LOW/CLOSE/VOLUME) shows, and saves a PNG.

    python3 chart_shot.py MGCV6 "2026-09-30 03:03:57" out.png      # fill time in CT
"""
import json
import os
import sys
import warnings
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

warnings.filterwarnings("ignore")
from playwright.sync_api import sync_playwright

CRED = os.path.expanduser("~/.tradovate/test_account.json")
CT = ZoneInfo("America/Chicago")
VIEW = {"width": 1600, "height": 950}


def login(pg):
    cred = json.load(open(CRED))
    pg.goto("https://trader.tradovate.com/welcome", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_selector("input[type=password]", timeout=30000)
    try:
        pg.get_by_role("button", name="Accept Cookies").click(timeout=3000)
    except Exception:
        pass
    pg.locator("input[type=text]").first.fill(cred["username"])
    pg.locator("input[type=password]").fill(cred["password"])
    pg.get_by_role("button", name="Login", exact=True).click()
    pg.get_by_role("button", name="Start Simulated Trading").click(timeout=30000)
    pg.wait_for_selector(".contract-symbol", timeout=60000)
    pg.wait_for_timeout(4000)


def capture_bars(pg, store):
    """Keep every chart bar the page receives (timestamps in UTC), keyed by chart id."""
    def rec(d):
        if isinstance(d, str) and '"bars"' in d:
            try:
                for msg in json.loads(d[1:]):
                    for ch in (msg.get("d") or {}).get("charts", []) if isinstance(msg, dict) else []:
                        store.setdefault(ch["id"], []).extend(ch.get("bars", []))
            except Exception:
                pass
    pg.on("websocket", lambda ws: ws.on("framereceived", rec))


def shot(contract, fill_ct, out):
    fill_utc = fill_ct.replace(tzinfo=CT).astimezone(timezone.utc)
    bars = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport=VIEW, timezone_id="America/Chicago")
        pg = ctx.new_page()
        capture_bars(pg, bars)
        login(pg)
        tabs_before = pg.locator("li", has_text="1m").count()

        # New chart tab for the contract
        before = set(bars)
        pg.mouse.click(335, 64)
        search = pg.locator("input[placeholder=Search]").last
        search.wait_for(timeout=15000)
        search.fill(contract)
        pg.wait_for_timeout(2500)
        pg.locator("a:visible", has_text=contract).last.click()
        try:                                                  # "Use previous chart settings?" → yes (same look as usual)
            pg.get_by_role("button", name="Yes use previous settings").click(timeout=5000)
        except Exception:
            pass
        for _ in range(30):                                   # wait for this chart's bars
            pg.wait_for_timeout(500)
            if set(bars) - before:
                break
        pg.wait_for_timeout(2500)
        new = [bars[k] for k in bars if k not in before]
        if not new:
            raise RuntimeError(f"No chart data arrived for {contract}")
        series = sorted(new[0], key=lambda x: x["timestamp"])
        ts = [datetime.fromisoformat(x["timestamp"].replace("Z", "+00:00")) for x in series]
        print(f"{contract}: {len(series)} bars {ts[0]:%m/%d %H:%M}Z → {ts[-1]:%m/%d %H:%M}Z")
        prior = [i for i, t in enumerate(ts) if t <= fill_utc]
        if not prior:
            raise RuntimeError("The fill time is older than the bars the chart loaded")
        target = ts[prior[-1]].astimezone(CT).strftime("%m/%d/%Y %H:%M")
        print("target bar (last bar at or before the fill):", target, series[prior[-1]])

        # Price box on, then find the target bar by reading the box while moving the mouse
        pg.mouse.move(700, 300)
        pg.mouse.click(29, 271)
        pg.wait_for_timeout(800)

        def box_time(x):
            pg.mouse.move(x, 320)
            pg.wait_for_timeout(250)
            txt = pg.evaluate("""() => { const e = [...document.querySelectorAll('ul.entries')].find(u => u.offsetParent);
                                         return e ? e.parentElement.parentElement.innerText : '' }""")
            for line in txt.splitlines():
                line = line.strip()
                try:
                    return datetime.strptime(line, "%m/%d/%Y %H:%M"), txt
                except ValueError:
                    continue
            return None, txt
        want = datetime.strptime(target, "%m/%d/%Y %H:%M")
        lo, hi, best = 10, 1475, None
        for _ in range(16):
            mid = (lo + hi) // 2
            t, _txt = box_time(mid)
            if t is None:
                lo = mid + 1
                continue
            if t == want:
                best = mid
                break
            if t < want:
                lo = mid + 1
            else:
                hi = mid - 1
        if best is None:
            raise RuntimeError(f"Couldn't place the cursor on the {target} bar")
        box_time(best)
        pg.screenshot(path=out)
        print("saved", out, "cursor x", best)

        # Close the tab we added so the workspace stays as it was
        try:
            pg.locator("li", has_text=f"{contract} 1m").locator("text=×").first.click(timeout=3000)
        except Exception:
            pass
        b.close()


if __name__ == "__main__":
    contract, fill, out = sys.argv[1], sys.argv[2], sys.argv[3]
    shot(contract, datetime.strptime(fill, "%Y-%m-%d %H:%M:%S"), out)
