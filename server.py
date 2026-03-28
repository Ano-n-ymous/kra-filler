import asyncio
import uuid
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Add parent directory to path so we can import our bot modules ──
sys.path.insert(0, str(Path(__file__).parent.parent))
from auth import login
from filer import file_nil_return

from playwright.async_api import async_playwright

# ─────────────────────────────────────────────
#  App Setup
# ─────────────────────────────────────────────

app = FastAPI(title="KRA Nil Returns Filer", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (frontend)
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Serve receipts for download
receipts_path = Path(__file__).parent.parent / "receipts"
receipts_path.mkdir(exist_ok=True)
app.mount("/receipts", StaticFiles(directory=str(receipts_path)), name="receipts")

# In-memory job store: job_id → {"status", "logs", "receipt", "pin"}
jobs: Dict[str, dict] = {}

# WebSocket connections: job_id → [WebSocket]
connections: Dict[str, list] = {}


# ─────────────────────────────────────────────
#  WebSocket Log Handler
# ─────────────────────────────────────────────

class WSLogHandler(logging.Handler):
    """Sends log records to all WebSocket clients watching a job."""

    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id
        self.loop = None

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        level = record.levelname
        asyncio.run_coroutine_threadsafe(
            broadcast(self.job_id, {"type": "log", "level": level, "message": msg}),
            self.loop or asyncio.get_event_loop()
        )


async def broadcast(job_id: str, data: dict):
    """Send a message to all WebSocket clients watching a job."""
    dead = []
    for ws in connections.get(job_id, []):
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            dead.append(ws)
    for ws in dead:
        connections.get(job_id, []).remove(ws)


# ─────────────────────────────────────────────
#  Models
# ─────────────────────────────────────────────

class FileRequest(BaseModel):
    pin: str
    password: str


# ─────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(str(static_path / "index.html"))


@app.post("/api/file")
async def start_filing(req: FileRequest, background_tasks: BackgroundTasks):
    """Start a nil return filing job. Returns a job_id immediately."""
    if not req.pin.strip() or not req.password.strip():
        return JSONResponse({"error": "PIN and password are required."}, status_code=400)

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "queued",
        "pin": req.pin.strip().upper(),
        "logs": [],
        "receipt": None,
        "started_at": datetime.now().isoformat(),
    }
    connections[job_id] = []

    background_tasks.add_task(run_filing_job, job_id, req.pin.strip().upper(), req.password.strip())

    return {"job_id": job_id}


@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    """Get current job status."""
    job = jobs.get(job_id)
    if not job:
        return JSONResponse({"error": "Job not found."}, status_code=404)
    return job


@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket for live log streaming."""
    await websocket.accept()

    if job_id not in connections:
        connections[job_id] = []
    connections[job_id].append(websocket)

    # Replay existing logs to newly connected client
    job = jobs.get(job_id, {})
    for log in job.get("logs", []):
        try:
            await websocket.send_text(json.dumps(log))
        except Exception:
            break

    # Keep alive until disconnect
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if job_id in connections and websocket in connections[job_id]:
            connections[job_id].remove(websocket)


# ─────────────────────────────────────────────
#  Filing Job Runner
# ─────────────────────────────────────────────

async def run_filing_job(job_id: str, pin: str, password: str):
    """Runs the full filing process and streams logs via WebSocket."""

    async def log(level: str, message: str):
        entry = {"type": "log", "level": level, "message": message, "time": datetime.now().strftime("%H:%M:%S")}
        jobs[job_id]["logs"].append(entry)
        await broadcast(job_id, entry)

    async def update_status(status: str):
        jobs[job_id]["status"] = status
        await broadcast(job_id, {"type": "status", "status": status})

    await update_status("running")
    await log("INFO", f"🚀 Starting nil return filing for PIN: {pin}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                accept_downloads=True
            )
            page = await context.new_page()

            # ── Intercept console logs from auth/filer ──
            # Patch logger to stream via WebSocket
            import auth as auth_module
            import filer as filer_module

            for mod in [auth_module, filer_module]:
                mod_logger = mod.logger
                mod_logger.handlers.clear()

                class AsyncBridgeHandler(logging.Handler):
                    def __init__(self, jid, loop):
                        super().__init__()
                        self.jid = jid
                        self.loop = loop

                    def emit(self, record):
                        msg = self.format(record)
                        lvl = record.levelname
                        entry = {"type": "log", "level": lvl, "message": msg, "time": datetime.now().strftime("%H:%M:%S")}
                        jobs[self.jid]["logs"].append(entry)
                        asyncio.run_coroutine_threadsafe(
                            broadcast(self.jid, entry),
                            self.loop
                        )

                handler = AsyncBridgeHandler(job_id, asyncio.get_event_loop())
                handler.setFormatter(logging.Formatter("%(message)s"))
                mod_logger.addHandler(handler)

            # ── Login ──────────────────────────────────
            await log("INFO", "🔑 Logging in to iTax portal...")
            logged_in = await login(page, pin, password)

            if not logged_in:
                await log("ERROR", "❌ Login failed. Check your PIN and password.")
                await update_status("failed")
                await browser.close()
                return

            await log("INFO", "✅ Login successful!")

            # ── File Nil Return ────────────────────────
            await log("INFO", "📋 Filing nil return...")
            result = await file_nil_return(page, pin)

            if result == "SUCCESS":
                await log("INFO", "🎉 Nil return filed successfully!")
                # Find receipt
                receipt_file = receipts_path / f"{pin}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
                if receipt_file.exists():
                    jobs[job_id]["receipt"] = f"/receipts/{receipt_file.name}"
                    await broadcast(job_id, {"type": "receipt", "url": jobs[job_id]["receipt"]})
                    await log("INFO", f"📄 Receipt saved: {receipt_file.name}")
                await update_status("success")

            elif result == "ALREADY_FILED":
                await log("INFO", "⏭️  Return already filed for this period.")
                await update_status("already_filed")

            else:
                await log("ERROR", "❌ Filing failed. Check logs for details.")
                await update_status("failed")

            await browser.close()

    except Exception as e:
        await log("ERROR", f"💥 Unexpected error: {str(e)}")
        await update_status("failed")
