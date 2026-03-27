# KRA Nil Returns Filer 🇰🇪

Automates KRA iTax nil return filing using Python + Playwright.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## Configure
Edit `.env` with your KRA PIN and password.

## Run
```bash
python main.py
```

## Phases
- ✅ Phase 1 — Single PIN filing
- 🔲 Phase 2 — Error handling & OTP
- 🔲 Phase 3 — Bulk/batch filing
- 🔲 Phase 4 — Scheduling & notifications
