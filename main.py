"""
Gap Detection Agent — Cosby AI Solutions
Weekly scan + auto-heal + Telegram command interface.
Schedule: Every Sunday at 9 PM Eastern.
"""
import os
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Header, Request
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from scanner import run_scan
from telegram_commands import handle_update

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

INTERNAL_KEY = os.environ.get("INTERNAL_KEY", "")
scheduler = AsyncIOScheduler(timezone="US/Eastern")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        _run_scan_job,
        CronTrigger(day_of_week=6, hour=21, minute=0, timezone="US/Eastern"),
        id="weekly_gap_scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("Gap detection scheduler started — fires Sunday 21:00 Eastern")

    # Register Telegram webhook
    from telegram_client import register_webhook, send
    public_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    if public_url:
        register_webhook(f"https://{public_url}/telegram/webhook")

    send("🔍 Gap Detection Agent online — auto-heal + Telegram commands active")

    yield
    scheduler.shutdown()
    logger.info("Scheduler stopped")


async def _run_scan_job():
    import asyncio
    loop = asyncio.get_event_loop()
    stats = await loop.run_in_executor(None, run_scan)
    logger.info("Scan complete: %s", stats)


app = FastAPI(
    title="Gap Detection Agent",
    description="Weekly Cosby AI gap scanner with auto-heal and rollback",
    version="2.0.0",
    lifespan=lifespan,
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    job = scheduler.get_job("weekly_gap_scan")
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "gap-detection-agent",
        "version": "2.0.0",
        "next_scan": job.next_run_time.isoformat() if job and job.next_run_time else None,
    }


# ── Telegram webhook ──────────────────────────────────────────────────────────

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram Update objects and dispatch commands."""
    try:
        update = await request.json()
        threading.Thread(target=handle_update, args=(update,), daemon=True).start()
    except Exception as e:
        logger.error("Webhook parse error: %s", e)
    return {"ok": True}


# ── Manual scan trigger ───────────────────────────────────────────────────────

@app.post("/scan/trigger")
def trigger_scan(x_internal_key: str = Header(default="")):
    """Manual scan trigger for testing. Requires X-Internal-Key header."""
    if INTERNAL_KEY and x_internal_key != INTERNAL_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal key")
    threading.Thread(target=run_scan, daemon=True).start()
    return {"status": "scan started", "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Gap queries ───────────────────────────────────────────────────────────────

@app.get("/gaps")
def list_gaps(
    status: str = "open",
    project: str | None = None,
    severity: str | None = None,
    x_internal_key: str = Header(default=""),
):
    if INTERNAL_KEY and x_internal_key != INTERNAL_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal key")

    from db import get_client
    client = get_client()
    query = (
        client.table("gap_detections")
        .select("*")
        .in_("status", status.split(","))
        .order("created_at", desc=True)
    )
    if project:
        query = query.eq("project_name", project)
    if severity:
        query = query.eq("severity", severity)

    result = query.execute()
    return {"gaps": result.data, "count": len(result.data or [])}


@app.patch("/gaps/{gap_id}")
def update_gap_status(
    gap_id: str,
    body: dict,
    x_internal_key: str = Header(default=""),
):
    if INTERNAL_KEY and x_internal_key != INTERNAL_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal key")

    allowed = {"status", "notes"}
    update = {k: v for k, v in body.items() if k in allowed}
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")

    from db import get_client
    client = get_client()
    result = client.table("gap_detections").update(update).eq("id", gap_id).execute()
    return {"updated": result.data}


# ── Fix queries ───────────────────────────────────────────────────────────────

@app.get("/fixes")
def list_fixes(
    status: str = "success,failed,rolled_back,executing",
    x_internal_key: str = Header(default=""),
):
    if INTERNAL_KEY and x_internal_key != INTERNAL_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal key")

    from db import get_client
    client = get_client()
    result = (
        client.table("gap_fixes")
        .select("*")
        .in_("status", status.split(","))
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    return {"fixes": result.data, "count": len(result.data or [])}
