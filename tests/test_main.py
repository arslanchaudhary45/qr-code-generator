"""Unit tests for the QR Code Generator service layer (main.py).

Run from the project folder with:

    pip install -r requirements-dev.txt
    pytest

Tests target the service layer only — no routes, no CLI printing.
Generated PNGs are checked by their magic bytes and dimensions.
"""

from __future__ import annotations

import pytest

import main

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_generate_qr_bytes_text_is_png():
    """A text QR is a valid PNG with the expected dimensions."""
    png = main.generate_qr_bytes("text", "Hello, world!")
    assert png[:8] == PNG_MAGIC
    width, height = main.qr_dimensions(png)
    assert width == height
    assert width > 0


def test_generate_qr_bytes_url():
    """A URL QR is a valid PNG."""
    png = main.generate_qr_bytes("url", "https://example.com")
    assert png[:8] == PNG_MAGIC


def test_generate_qr_bytes_vcard():
    """A vCard payload encodes to a valid PNG."""
    vcard = main.build_vcard("Arslan Nasir", "+923497988829",
                             "arslannasir045@gmail.com")
    png = main.generate_qr_bytes("vcard", vcard)
    assert png[:8] == PNG_MAGIC


def test_generate_qr_bytes_box_size_changes_image():
    """A larger box size makes a larger image."""
    small = main.generate_qr_bytes("text", "Hi", box_size=5)
    large = main.generate_qr_bytes("text", "Hi", box_size=20)
    assert main.qr_dimensions(large)[0] > main.qr_dimensions(small)[0]


def test_generate_qr_bytes_border_changes_image():
    """A larger border makes a larger image."""
    thin = main.generate_qr_bytes("text", "Hi", border=0)
    thick = main.generate_qr_bytes("text", "Hi", border=8)
    assert main.qr_dimensions(thick)[0] > main.qr_dimensions(thin)[0]


def test_generate_qr_bytes_rejects_bad_kind():
    """Anything outside text/url/vcard is refused."""
    with pytest.raises(main.QrError, match="Invalid QR kind"):
        main.generate_qr_bytes("email", "hello@example.com")


def test_generate_qr_bytes_rejects_blank_data():
    """Blank data is refused with a clear error."""
    with pytest.raises(main.QrError, match="Enter some text"):
        main.generate_qr_bytes("text", "   ")
    with pytest.raises(main.QrError, match="Enter a URL"):
        main.generate_qr_bytes("url", "")
    with pytest.raises(main.QrError, match="Data to encode"):
        main.generate_qr_bytes("vcard", "")


def test_generate_qr_bytes_rejects_bad_box_size():
    """Box sizes below 1 are refused."""
    with pytest.raises(main.QrError, match="Box size must be at least 1"):
        main.generate_qr_bytes("text", "Hi", box_size=0)
    with pytest.raises(main.QrError, match="Box size must be at least 1"):
        main.generate_qr_bytes("text", "Hi", box_size=-3)


def test_generate_qr_bytes_rejects_bad_border():
    """Borders below 0 are refused."""
    with pytest.raises(main.QrError, match="Border must be at least 0"):
        main.generate_qr_bytes("text", "Hi", border=-1)


def test_build_vcard_full():
    """A full vCard has the 3.0 header, name, phone and email."""
    vcard = main.build_vcard("Arslan Nasir", "+923497988829",
                             "arslannasir045@gmail.com")
    assert vcard == (
        "BEGIN:VCARD\nVERSION:3.0\nFN:Arslan Nasir\n"
        "TEL:+923497988829\nEMAIL:arslannasir045@gmail.com\nEND:VCARD")


def test_build_vcard_name_only():
    """A vCard with just a name omits the phone and email lines."""
    vcard = main.build_vcard("Arslan Nasir")
    assert vcard == "BEGIN:VCARD\nVERSION:3.0\nFN:Arslan Nasir\nEND:VCARD"


def test_build_vcard_rejects_blank_name():
    """A vCard without a name is refused."""
    with pytest.raises(main.QrError, match="at least a name"):
        main.build_vcard("   ")
    with pytest.raises(main.QrError, match="at least a name"):
        main.build_vcard("")


def test_qr_dimensions_matches_content():
    """qr_dimensions reads the real PNG size."""
    png = main.generate_qr_bytes("text", "Hello", box_size=10, border=4)
    width, height = main.qr_dimensions(png)
    # 21 modules for version 1 + 2*4 border, at 10 px per module.
    assert (width, height) == (290, 290)


def test_cmd_generate_writes_png(tmp_path, capsys):
    """The CLI wrapper writes a PNG and prints its size line."""
    out = tmp_path / "hello.png"
    args = main.build_parser().parse_args(
        ["--text", "Hello, world!", "--output", str(out)])
    assert main.cmd_generate(args) == 0
    assert out.read_bytes()[:8] == PNG_MAGIC
    printed = capsys.readouterr().out
    assert f"Saved {out}" in printed
    assert "bytes" in printed and "px" in printed


def test_cmd_generate_vcard_without_name_returns_1(capsys):
    """The CLI wrapper prints the error to stderr and returns 1."""
    args = main.build_parser().parse_args(
        ["--vcard", "--output", "contact.png"])
    assert main.cmd_generate(args) == 1
    captured = capsys.readouterr()
    assert "at least a name" in captured.err
    assert captured.out == ""


def test_cmd_generate_bad_box_size_returns_1(capsys):
    """The CLI wrapper refuses a bad box size with exit code 1."""
    args = main.build_parser().parse_args(
        ["--text", "Hi", "--box-size", "0", "--output", "x.png"])
    assert main.cmd_generate(args) == 1
    assert "Box size must be at least 1" in capsys.readouterr().err
