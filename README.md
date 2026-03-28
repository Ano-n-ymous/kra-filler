# KRA Nil Returns Filer

Automate filing of nil returns on the Kenya Revenue Authority (KRA) iTax portal. Supports **single**, **bulk** (CSV), and **web‑based** filing with real‑time logs, automatic captcha solving, and receipt download.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-green)
![Playwright](https://img.shields.io/badge/Playwright-1.48.0-orange)

---

## Features

- ✅ **Automated Login** – Handles PIN, password, and OTP prompts.
- ✅ **Captcha Solving** – OCR‑based math captcha solver (with manual fallback).
- ✅ **Nil Return Filing** – Navigates iTax and submits the nil return.
- ✅ **Receipt Download** – Saves PDF receipt locally.
- ✅ **Bulk Processing** – Reads `clients.csv` and processes multiple accounts.
- ✅ **Web Interface** – Live job tracking via WebSocket, receipts downloadable.
- ✅ **Headless / Headed** – Run silently or watch the browser.

---

## Tech Stack

- **Backend:** Python 3.8+, FastAPI, Playwright (async)
- **Frontend:** HTML/CSS/JS (static), WebSocket for live logs
- **OCR:** pytesseract, Pillow
- **Automation:** Playwright with Chromium

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/kra-nil-filer.git
cd kra-nil-filer
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Playwright browsers

```bash
playwright install chromium
```

### 4. Install Tesseract OCR

- **Ubuntu/Debian:** `sudo apt install tesseract-ocr`
- **macOS:** `brew install tesseract`
- **Windows:** Download from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki) and add to PATH

### 5. Configure environment variables

Create a `.env` file in the project root (see `.env.example`):

```env
# Optional for CLI single mode – if not set, you'll be prompted
KRA_PIN=A000000000X
KRA_PASSWORD=your_password

# Browser mode: true = headless (no UI), false = visible
HEADLESS=true
```

### 6. (Optional) Bulk filing CSV

Create `clients.csv` with columns: `PIN`, `Password`

```csv
PIN,Password
A000000000X,pass123
B000000000Y,pass456
```

---

## Usage

### 1. Command‑line interface (CLI)

Run the main script and choose from the menu:

```bash
python main.py
```

- **Option 1:** File a single return (prompts for PIN/password)
- **Option 2:** Bulk filing using `clients.csv`
- **Option 3:** Exit

Use `--no-headless` to see the browser:

```bash
python main.py --no-headless
```

### 2. Web application

Start the FastAPI server:

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Access the web UI at `http://localhost:8000` (or your IP).

- Enter PIN and password, click “File Return”.
- Watch live logs as the process runs.
- When done, download the receipt PDF.

#### Make it public (share with anyone)

- **ngrok:** `ngrok http 8000`
- **cloudflared:** `cloudflared tunnel --url http://localhost:8000`

---

## Project Structure

```
kra-nil-filer/
├── main.py                # CLI entry point (single/bulk)
├── server.py              # FastAPI web server
├── auth.py                # Login logic (PIN, password, captcha)
├── filer.py               # Nil return filing routine
├── utils.py               # Logger, animator, helpers
├── bulk.py                # Bulk processing logic
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create from .env.example)
├── clients.csv            # Bulk input file (create if needed)
├── receipts/              # Downloaded receipts (auto‑created)
├── logs/                  # Debug logs and screenshots
└── static/
    └── index.html         # Web UI frontend
```

---

## Troubleshooting

### Debug scripts

The repository includes several debug scripts to help you inspect the iTax pages:

- `debug.py` – Dumps all buttons and inputs after PIN entry.
- `debug2.py` – Locates the exact captcha element.
- `debug3.py` – Saves screenshots before and after login.
- `debug4.py` – Finds text nodes containing math expressions.

Run them as:

```bash
python debug.py
```

### Common issues

- **Captcha always wrong** – The OCR might misread the math. The fallback will open the image for manual entry.
- **Login fails** – Check PIN/password, or see `logs/login_fail_<PIN>.png` for the error page.
- **Already filed** – The script detects this and stops with status `ALREADY_FILED`.

---

## Disclaimer

This tool is intended **only for authorized use** on your own KRA iTax accounts. Use responsibly and comply with KRA’s terms of service. The authors are not liable for any misuse or violation of KRA policies.

---

## License

MIT License – see [LICENSE](LICENSE) file.

---

## Contributing

Pull requests are welcome! Please open an issue first to discuss major changes.
