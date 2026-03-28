# KRA Nil Returns Filer — Web App

## Setup

```bash
# 1. Copy server.py and static/ into your kra-nil-filer project
cp server.py ../kra-nil-filer/
cp -r static/ ../kra-nil-filer/static/

# 2. Install new dependencies
cd ../kra-nil-filer
pip install fastapi uvicorn[standard]

# 3. Run the server
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

## Access

- Local:   http://localhost:8000
- Network: http://YOUR_IP:8000

## Make it public (share with anyone)

```bash
# Option A: ngrok (free)
ngrok http 8000

# Option B: cloudflared (free)
cloudflared tunnel --url http://localhost:8000
```

## Structure

```
kra-nil-filer/
├── server.py        ← FastAPI backend
├── static/
│   └── index.html   ← Web UI
├── auth.py          ← Login logic
├── filer.py         ← Filing logic
├── utils.py         ← Helpers
└── receipts/        ← PDFs served here
```
