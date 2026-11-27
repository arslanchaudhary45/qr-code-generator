#!/usr/bin/env python3
"""Convert text, URLs, and contact information into QR code PNG files.

Architecture
------------
This module is the **service layer**: pure functions that own the QR
rules and validation (``build_vcard`` and ``generate_qr_bytes``).
They raise :class:`QrError` on bad input instead of printing or
exiting, so the command-line app and the Flask web app (``app.py``)
can both use them.

The ``cmd_generate`` function at the bottom is the thin command-line
wrapper: it turns parsed arguments into a service call, writes the
PNG file and prints the result. ``app.py`` does the same for HTTP
requests.

Usage:
    python main.py --text "Hello, world!" --output hello.png
    python main.py --url https://example.com --output site.png
    python main.py --vcard --name "Arslan Nasir" --phone "+923497988829" \\
                   --email arslannasir045@gmail.com --output contact.png
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import qrcode
from PIL import Image

KINDS = ("text", "url", "vcard")
DEFAULT_BOX_SIZE = 10
DEFAULT_BORDER = 4


class QrError(ValueError):
    """Raised when a QR code request is invalid (bad kind, bad size)."""


# ---------------------------------------------------------------------------
# Service layer (pure functions; no printing, no exiting, no file writes)
# ---------------------------------------------------------------------------

def build_vcard(name: str, phone: str = "", email: str = "") -> str:
    """Build a vCard 3.0 payload from contact details.

    Raises :class:`QrError` when the name is blank — a vCard needs
    at least a name.
    """
    name = name.strip()
    if not name:
        raise QrError("A contact needs at least a name.")
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{name}"]
    if phone.strip():
        lines.append(f"TEL:{phone.strip()}")
    if email.strip():
        lines.append(f"EMAIL:{email.strip()}")
    lines.append("END:VCARD")
    return "\n".join(lines)


def _make_qr_image(kind: str, data: str, box_size: int,
                   border: int) -> Image.Image:
    """Build the QR image for ``data`` with the CLI's qrcode settings."""
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


def generate_qr_bytes(kind: str, data: str, box_size: int = DEFAULT_BOX_SIZE,
                      border: int = DEFAULT_BORDER) -> bytes:
    """Generate a QR code PNG for ``data`` and return its bytes.

    ``kind`` must be ``"text"``, ``"url"`` or ``"vcard"``. Raises
    :class:`QrError` when the kind is unknown, the data is blank,
    ``box_size`` is below 1 or ``border`` is below 0.
    """
    if kind not in KINDS:
        raise QrError(f"Invalid QR kind {kind!r}: "
                      f"expected one of {', '.join(KINDS)}.")
    if not data or not data.strip():
        if kind == "text":
            raise QrError("Enter some text to encode.")
        if kind == "url":
            raise QrError("Enter a URL to encode.")
        raise QrError("Data to encode is required.")
    if box_size < 1:
        raise QrError("Box size must be at least 1.")
    if border < 0:
        raise QrError("Border must be at least 0.")
    image = _make_qr_image(kind, data, box_size, border)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def qr_dimensions(png: bytes) -> tuple[int, int]:
    """Return the ``(width, height)`` of a PNG's image in pixels."""
    with Image.open(io.BytesIO(png)) as image:
        return image.size


# ---------------------------------------------------------------------------
# Command-line wrapper (thin: arguments -> service -> file -> print)
# ---------------------------------------------------------------------------

def cmd_generate(args: argparse.Namespace) -> int:
    """Generate a QR code PNG from parsed CLI arguments."""
    try:
        if args.vcard:
            data = build_vcard(args.name or "", args.phone or "",
                               args.email or "")
            kind = "vcard"
        else:
            kind = "text" if args.text is not None else "url"
            data = args.text if args.text is not None else args.url
        png = generate_qr_bytes(kind, data, args.box_size, args.border)
    except QrError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    out_path = Path(args.output)
    try:
        out_path.write_bytes(png)
    except OSError as exc:
        print(f"Error: cannot write {out_path}: {exc}", file=sys.stderr)
        return 1
    width, height = qr_dimensions(png)
    print(f"Saved {out_path} ({len(png)} bytes, {width}x{height} px)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate QR codes as PNG files."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Plain text to encode")
    source.add_argument("--url", help="URL to encode")
    source.add_argument(
        "--vcard", action="store_true",
        help="Encode a vCard built from --name/--phone/--email",
    )
    parser.add_argument("--name", help="Contact name (with --vcard)")
    parser.add_argument("--phone", help="Contact phone number (with --vcard)")
    parser.add_argument("--email", help="Contact email address (with --vcard)")
    parser.add_argument(
        "--output", "-o", required=True,
        help="Output PNG file path, e.g. qr.png",
    )
    parser.add_argument(
        "--box-size", type=int, default=DEFAULT_BOX_SIZE,
        help="Pixels per QR module (default: 10)",
    )
    parser.add_argument(
        "--border", type=int, default=DEFAULT_BORDER,
        help="Border width in modules (default: 4)",
    )
    parser.set_defaults(func=cmd_generate)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the command-line app."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
