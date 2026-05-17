"""
Gap Detection Agent — Cosby AI Solutions
Weekly scan of all 8 Cosby AI projects for gaps, security issues, and missing integrations.
Schedule: Every Sunday at 9 PM Eastern (UTC-5 standard / UTC-4 daylight).
"""
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Header
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from scanner import run_scan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

INTERNAL_KEY = os.environ.get("INTERNAL_KEY", "")

scheduler = AsyncIOScheduler(timezone="US/Eastern")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sunday 9 PM Eastern
    scheduler.add_job(
        _run_scan_job,
        CronTrigger(day_of_week=6, hour=21, minute=0, timezone="US/Eastern"),
        id="weekly_gap_scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("Gap detection scheduler started — fires Sunday 21:00 Eastern")

    from telegram_client import send
    send("🔍 Gap Detection Agent online — Sunday 9 PM Eastern scans active")

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
    description="Weekly Cosby AI project gap scanner",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    next_run = None
    job = scheduler.get_job("weekly_gap_scan")
    if job and job.next_run_time:
        next_run = job.next_run_time.isoformat()

    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "gap-detection-agent",
        "next_scan": next_run,
    }


@app.post("/scan/trigger")
def trigger_scan(x_internal_key: str = Header(default="")):
    """Manual trigger for testing. Requires INTERNAL_KEY header."""
    if INTERNAL_KEY and x_internal_key != INTERNAL_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal key")

    import threading
    threading.Thread(target=run_scan, daemon=True).start()
    return {"status": "scan started", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/gaps")
def list_gaps(
    status: str = "open",
    project: str | None = None,
    severity: str | None = None,
    x_internal_key: str = Header(default=""),
):
    """Query stored gaps. Requires INTERNAL_KEY header."""
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
    """Update a gap's status or notes. Requires INTERNAL_KEY header."""
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
