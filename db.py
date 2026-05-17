"""Supabase persistence layer for gap detections."""
import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client


def upsert_gaps(gaps: list[dict]) -> tuple[int, int]:
    """
    Insert new gaps, skip already-open duplicates (same project + description).
    Returns (inserted, skipped).
    """
    if not gaps:
        return 0, 0

    client = get_client()
    inserted = 0
    skipped = 0

    for gap in gaps:
        try:
            # Check if this gap is already open/acknowledged/in_progress
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
            logger.error("DB insert failed for %s: %s", gap.get("gap_description", "?")[:60], e)

    return inserted, skipped


def get_open_gaps_for_report() -> list[dict]:
    """Fetch all open/acknowledged gaps ordered by severity for the weekly report."""
    client = get_client()
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    result = (
        client.table("gap_detections")
        .select("project_name, gap_category, gap_description, severity, status, created_at")
        .in_("status", ["open", "acknowledged", "in_progress"])
        .execute()
    )

    rows = result.data or []
    rows.sort(key=lambda r: (severity_order.get(r["severity"], 9), r["project_name"]))
    return rows
