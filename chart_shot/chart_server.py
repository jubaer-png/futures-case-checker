"""Flask server: POST /chart {contract, fill, price, side} → PNG bytes.
Run: python chart_server.py
Expose publicly: ngrok http --domain=YOUR_DOMAIN 5001
"""
import os
import sys
import tempfile
from datetime import datetime
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from make_chart import make

app = Flask(__name__)
CORS(app)


@app.route("/chart", methods=["POST"])
def chart():
    try:
        data = request.get_json(force=True)
        contract = data["contract"]
        fill_ct = datetime.strptime(data["fill"], "%Y-%m-%d %H:%M:%S")
        price = float(data["price"])
        side = data.get("side", "Buy")
    except (KeyError, ValueError) as e:
        return jsonify(error=str(e)), 400

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        out = f.name
    try:
        make(contract, fill_ct, price, side, out)
        fname = f"illiquid_chart_{contract}_{fill_ct.strftime('%Y%m%d_%H%M%S')}.png"
        return send_file(out, mimetype="image/png",
                         as_attachment=True, download_name=fname)
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        try:
            os.unlink(out)
        except Exception:
            pass


@app.route("/ping")
def ping():
    return "ok"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"Chart server running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port)
