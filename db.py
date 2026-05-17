"""Supabase persistence layer — gap_detections + gap_fixes."""
import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    return _client


# ── gap_detections ────────────────────────────────────────────────────────────

def upsert_gaps(gaps: list[dict]) -> tuple[int, int]:
    """
    Insert new gaps, skip already-open duplicates (same project + description).
    Returns (inserted, skipped).
    """
    if not gaps:
        return 0, 0

    client = get_client()
    inserted = skipped = 0

    for gap in gaps:
        try:
            existing = (
                client.table("gap_detections")
                .select("id, status")
                .eq("project_name", gap["project_name"])
                .eq("gap_description", gap["gap_description"])
                .in_("status", ["open", "acknowledged", "in_progress"])
                .execute()
            )
            if existing.data:
                skipped += 1
                continue
            client.table("gap_detections").insert(gap).execute()
            inserted += 1
        except Exception as e:
            logger.error("DB insert failed for '%s': %s", gap.get("gap_description", "?")[:60], e)

    return inserted, skipped


def get_open_gaps_for_report() -> list[dict]:
    """All open/acknowledged gaps ordered by severity for the weekly Telegram report."""
    client = get_client()
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    rows = (
        client.table("gap_detections")
        .select("project_name, gap_category, gap_description, severity, status, created_at")
        .in_("status", ["open", "acknowledged", "in_progress"])
        .execute()
    ).data or []
    rows.sort(key=lambda r: (sev_order.get(r["severity"], 9), r["project_name"]))
    return rows


def get_new_critical_gaps(since_id_set: set[str] | None = None) -> list[dict]:
    """
    Return critical gaps that are open and not yet auto_executed.
    Used by the healer after each scan to find gaps to act on.
    """
    client = get_client()
    rows = (
        client.table("gap_detections")
        .select("*")
        .eq("severity", "critical")
        .eq("status", "open")
        .eq("auto_executed", False)
        .execute()
    ).data or []

    if since_id_set:
        rows = [r for r in rows if r["id"] not in since_id_set]
    return rows


def mark_gap_auto_executed(gap_id: str) -> None:
    client = get_client()
    try:
        client.table("gap_detections").update({"auto_executed": True}).eq("id", gap_id).execute()
    except Exception as e:
        logger.error("mark_gap_auto_executed failed for %s: %s", gap_id, e)


# ── gap_fixes ─────────────────────────────────────────────────────────────────

def create_gap_fix(data: dict) -> dict | None:
    """Insert a new gap_fix row. Returns the created row or None on error."""
    client = get_client()
    try:
        result = client.table("gap_fixes").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("create_gap_fix failed: %s", e)
        return None


def update_gap_fix(fix_id: str, data: dict) -> None:
    client = get_client()
    try:
        client.table("gap_fixes").update(data).eq("id", fix_id).execute()
    except Exception as e:
        logger.error("update_gap_fix %s failed: %s", fix_id, e)


def get_gap_fix(fix_id: str) -> dict | None:
    client = get_client()
    try:
        result = client.table("gap_fixes").select("*").eq("id", fix_id).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("get_gap_fix %s failed: %s", fix_id, e)
        return None
