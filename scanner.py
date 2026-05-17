"""Main scan orchestrator — runs all project scanners and persists findings."""
import logging
from dataclasses import asdict
from scanners import ALL_SCANNERS
from db import upsert_gaps, get_open_gaps_for_report
from telegram_client import build_report, send

logger = logging.getLogger(__name__)


def run_scan() -> dict:
    """
    Run all project scanners, persist findings, send Telegram report.
    Returns stats dict.
    """
    logger.info("Gap detection scan starting — %d scanners", len(ALL_SCANNERS))

    all_gaps: list[dict] = []
    projects_scanned = 0

    for scanner_fn in ALL_SCANNERS:
        try:
            gaps = scanner_fn()
            for g in gaps:
                all_gaps.append({
                    "project_name": g.project_name,
                    "gap_category": g.gap_category,
                    "gap_description": g.gap_description,
                    "severity": g.severity,
                    "notes": g.notes,
                    "status": "open",
                })
            projects_scanned += 1
            logger.info("  %s — %d gaps detected", gaps[0].project_name if gaps else "?", len(gaps))
        except Exception as e:
            logger.error("Scanner %s failed: %s", scanner_fn.__name__, e)

    # Persist — dedup against existing open records
    inserted, skipped = upsert_gaps(all_gaps)
    logger.info("DB: %d inserted, %d skipped (already tracked)", inserted, skipped)

    # Fetch full open gap list for report (includes pre-existing open gaps)
    open_gaps = get_open_gaps_for_report()

    stats = {
        "projects": projects_scanned,
        "total": len(all_gaps),
        "inserted": inserted,
        "skipped": skipped,
        "open_total": len(open_gaps),
    }

    report = build_report(open_gaps, stats)
    sent = send(report)
    logger.info("Telegram report sent: %s", sent)

    return stats
