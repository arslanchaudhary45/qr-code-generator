# QR Code Generator

Convert text, URLs, and contact information into downloadable QR codes
(PNG files).

## Setup

```bash
cd qr-code-generator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Web app

```bash
cd qr-code-generator
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 in your browser. The web app covers the
same three content types as the command line (text, URL, contact/vCard)
with box-size and border options, a live QR preview, an inline result
image and a PNG download. Set the `PORT` environment variable to run on
a different port.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests in `tests/` cover the service layer in `main.py`: vCard
building, QR PNG generation for all three kinds, box-size and border
validation, the unknown-kind and blank-data errors, and the CLI
wrapper's exit codes.

## Architecture

- `main.py` — the service layer: vCard building and QR PNG generation
  (typed functions, `QrError` on bad input). The `cmd_generate`
  function at the bottom is a thin command-line wrapper around it.
- `app.py` — the Flask web UI: thin routes that validate HTTP input
  and call the service. No QR rules live in the routes.
- `templates/` + `static/` — the web pages and the shared design
  system (same layout, colors and components as the other projects).

## Requirements

- Python 3.12+
- `qrcode` and `Pillow` packages

Install the dependencies (a venv is recommended):

```bash
pip install -r requirements.txt
```

## How to run

```bash
python main.py --text "Hello, world!" --output hello.png
```

## Options

| Option | Description |
| --- | --- |
| `--text TEXT` | Plain text to encode |
| `--url URL` | URL to encode |
| `--vcard` | Encode a vCard built from `--name` / `--phone` / `--email` |
| `--name NAME` | Contact name (with `--vcard`) |
| `--phone PHONE` | Contact phone number (with `--vcard`) |
| `--email EMAIL` | Contact email address (with `--vcard`) |
| `--output FILE`, `-o FILE` | Output PNG file path (required) |
| `--box-size N` | Pixels per QR module (default: 10) |
| `--border N` | Border width in modules (default: 4) |

Exactly one of `--text`, `--url`, or `--vcard` must be given.

## Examples

```bash
# QR code for plain text
python main.py --text "Hello, world!" --output hello.png

# QR code for a URL
python main.py --url https://example.com --output site.png

# QR code for a contact (scans into the phone's address book)
python main.py --vcard --name "Arslan Nasir" --phone "+923497988829" \
    --email arslannasir045@gmail.com --output contact.png

# Larger modules, thicker border
python main.py --url https://example.com --output big.png \
    --box-size 20 --border 8
```
