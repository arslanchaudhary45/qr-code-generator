#!/usr/bin/env python3
"""QR Code Generator — web UI (Flask).

Thin routes only: each handler parses and validates its HTTP input,
calls one service function from :mod:`main`, then renders a page or
redirects. All rules (content kinds, vCard building, QR generation)
live in ``main.py``; nothing about QR codes is decided here.

Run it with:

    pip install -r requirements.txt
    python app.py

Then open http://127.0.0.1:5000 in your browser.
Set the PORT environment variable to use a different port.
The command-line app still works exactly as before:
python3 main.py --url https://example.com --output site.png
"""

from __future__ import annotations

import base64
import io
import os
import secrets
import sys
from typing import Any

from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import main as cli

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-key")

APP_NAME = "QR Code Generator"
APP_TAGLINE = "Turn text, URLs and contacts into scannable QR codes"

DEFAULT_BOX_SIZE = cli.DEFAULT_BOX_SIZE
DEFAULT_BORDER = cli.DEFAULT_BORDER
MAX_BOX_SIZE = 50
MAX_BORDER = 20

# token -> {"png": bytes, "data": str, "kind": str,
#            "box_size": int, "border": int, "width": int, "height": int}
QR_STORE: dict[str, dict[str, Any]] = {}

KINDS = cli.KINDS


def _parse_int(value: object, default: int) -> int | None:
    """Parse a whole number from a form/JSON value; ``None`` if invalid."""
    if value is None or value == "":
        return default
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def resolve(values: dict) -> tuple[str, str, int, int]:
    """Resolve the encoded payload from form/JSON values.

    Returns ``(kind, data, box_size, border)``. Raises
    :class:`cli.QrError` on any bad input (unknown kind, blank text,
    missing contact name, bad box size or border).
    """
    kind = (str(values.get("kind") or "text")).strip().lower()
    if kind not in KINDS:
        raise cli.QrError(f"Invalid QR kind {kind!r}: "
                          f"expected one of {', '.join(KINDS)}.")
    box_size = _parse_int(values.get("box_size"), DEFAULT_BOX_SIZE)
    border = _parse_int(values.get("border"), DEFAULT_BORDER)
    if box_size is None or border is None:
        raise cli.QrError("Box size and border must be whole numbers.")
    if box_size < 1 or box_size > MAX_BOX_SIZE:
        raise cli.QrError(
            f"Box size must be between 1 and {MAX_BOX_SIZE}.")
    if border < 0 or border > MAX_BORDER:
        raise cli.QrError(f"Border must be between 0 and {MAX_BORDER}.")

    if kind == "text":
        data = (str(values.get("text") or "")).strip()
        if not data:
            raise cli.QrError("Enter some text to encode.")
    elif kind == "url":
        data = (str(values.get("url") or "")).strip()
        if not data:
            raise cli.QrError("Enter a URL to encode.")
    else:
        data = cli.build_vcard(
            str(values.get("name") or ""),
            str(values.get("phone") or ""),
            str(values.get("email") or ""))
    return kind, data, box_size, border


def store_qr(kind: str, data: str, box_size: int, border: int) -> str:
    """Generate a QR PNG via the service and store it under a token.

    Returns the token used to fetch or download the image.
    """
    png = cli.generate_qr_bytes(kind, data, box_size, border)
    width, height = cli.qr_dimensions(png)
    token = secrets.token_urlsafe(12)
    QR_STORE[token] = {"png": png, "data": data, "kind": kind,
                       "box_size": box_size, "border": border,
                       "width": width, "height": height}
    return token


def qr_payload(kind: str, data: str, box_size: int,
               border: int) -> dict[str, Any]:
    """Build the JSON payload for a QR code via the service layer."""
    png = cli.generate_qr_bytes(kind, data, box_size, border)
    width, height = cli.qr_dimensions(png)
    data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    return {"data_url": data_url, "data": data,
            "width": width, "height": height,
            "box_size": box_size, "border": border}


@app.context_processor
def inject_globals() -> dict:
    """Make the app name and tagline available to every template."""
    return {"app_name": APP_NAME, "app_tagline": APP_TAGLINE}


@app.route("/")
def index() -> str:
    """Dashboard: the generate form and the latest QR code, if any."""
    token = request.args.get("qr")
    qr = QR_STORE.get(token) if token else None
    if token and qr is None:
        flash("That QR code is no longer available; generate a new one.",
              "error")
    return render_template("index.html", qr=qr, token=token,
                           box_size=DEFAULT_BOX_SIZE,
                           border=DEFAULT_BORDER)


@app.route("/generate", methods=["POST"])
def generate() -> str:
    """Generate a QR code from the dashboard form, then show it."""
    try:
        kind, data, box_size, border = resolve(request.form)
        token = store_qr(kind, data, box_size, border)
    except cli.QrError as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))
    flash("QR code generated.", "success")
    return redirect(url_for("index", qr=token))


@app.route("/qr/<token>.png")
def qr_image(token: str) -> Response:
    """Serve a stored QR code as a PNG image."""
    qr = QR_STORE.get(token)
    if qr is None:
        return Response("QR code not found.", status=404)
    return send_file(io.BytesIO(qr["png"]), mimetype="image/png")


@app.route("/download/<token>")
def download(token: str) -> Response:
    """Download a stored QR code as a PNG file."""
    qr = QR_STORE.get(token)
    if qr is None:
        return Response("QR code not found.", status=404)
    return send_file(io.BytesIO(qr["png"]), mimetype="image/png",
                     as_attachment=True, download_name="qr-code.png")


def _api_response(values: dict) -> tuple[Response, int]:
    """Resolve the request values and return the QR JSON payload."""
    try:
        kind, data, box_size, border = resolve(values)
        payload = qr_payload(kind, data, box_size, border)
    except cli.QrError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(payload), 200


@app.route("/api/qr")
def api_qr() -> tuple[Response, int]:
    """Generate a QR preview from query parameters (live preview)."""
    return _api_response(request.args.to_dict())


@app.route("/api/qr", methods=["POST"])
def api_qr_post() -> tuple[Response, int]:
    """Generate a QR preview from a JSON body (live preview)."""
    return _api_response(request.get_json(silent=True) or {})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port)
