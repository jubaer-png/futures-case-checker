"""Background helper: watch ~/Downloads for chart-request files the dashboard's "Get chart" button drops,
run make_chart.py, and open the resulting PNG. Runs via a launchd agent (see com.fundednext.illiquidchart.plist).

Request file  : ~/Downloads/tradovate_chart_request_*.json  = {contract, fill, price, side}  (fill = CT "YYYY-MM-DD HH:MM:SS")
Output        : ~/Downloads/illiquid_chart_<contract>_<fillstamp>.png  (opened automatically)
Status (for the dashboard to poll): ~/Downloads/tradovate_chart_status.json = {state, message, png}
"""
import glob
import json
import os
import re
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
DL = os.path.expanduser("~/Downloads")
STATUS = os.path.join(DL, "tradovate_chart_status.json")


def set_status(**kw):
    try:
        json.dump(kw, open(STATUS, "w"))
    except Exception:
        pass


def handle(req_path):
    req = json.load(open(req_path))
    contract = re.sub(r"[^A-Z0-9]", "", req["contract"].upper())
    fill = req["fill"]
    stamp = re.sub(r"[^0-9]", "", fill)
    out = os.path.join(DL, f"illiquid_chart_{contract}_{stamp}.png")
    set_status(state="running", message=f"Building {contract} chart…", png=None)
    subprocess.run([sys.executable, os.path.join(HERE, "make_chart.py"),
                    contract, fill, str(req["price"]), req.get("side", "Buy"), out],
                   cwd=HERE, check=True, env={**os.environ, "PYTHONWARNINGS": "ignore"})
    subprocess.run(["open", out])
    set_status(state="done", message=f"{contract} chart saved to Downloads.", png=os.path.basename(out))
    print("done:", out)


def main():
    print("watching", DL)
    while True:
        for req in sorted(glob.glob(os.path.join(DL, "tradovate_chart_request_*.json"))):
            try:
                handle(req)
            except Exception as e:
                traceback.print_exc()
                set_status(state="error", message=str(e)[:200], png=None)
            finally:
                try:
                    os.remove(req)
                except Exception:
                    pass
        time.sleep(2)


if __name__ == "__main__":
    main()
