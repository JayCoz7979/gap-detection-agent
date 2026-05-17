"""Main scan orchestrator — runs all project scanners, persists, heals, reports."""
import logging
from scanners import ALL_SCANNERS
from db import upsert_gaps, get_open_gaps_for_report, get_new_critical_gaps
from telegram_client import build_report, send

logger = logging.getLogger(__name__)


def run_scan() -> dict:
    """
    1. Run all 8 project scanners
    2. Persist new gaps to Supabase (dedup open ones)
    3. Auto-heal critical gaps that have registered fixes
    4. Send Telegram report grouped by severity
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
                    "auto_executed": False,
                })
            projects_scanned += 1
            name = gaps[0].project_name if gaps else "unknown"
            logger.info("  %s — %d gaps", name, len(gaps))
        except Exception as e:
            logger.error("Scanner %s failed: %s", scanner_fn.__name__, e)

    # Persist
    inserted, skipped = upsert_gaps(all_gaps)
    logger.info("DB: %d inserted, %d skipped", inserted, skipped)

    # Auto-heal critical gaps
    healed = 0
    if inserted > 0:
        critical_gaps = get_new_critical_gaps()
        if critical_gaps:
            logger.info("Auto-healing %d critical gap(s)…", len(critical_gaps))
            from healer import heal_gap
            for gap_row in critical_gaps:
                try:
                    fix_row = heal_gap(gap_row)
                    if fix_row:
                        healed += 1
                except Exception as e:
                    logger.error("heal_gap failed for %s: %s", gap_row.get("id"), e)

    # Report
    open_gaps = get_open_gaps_for_report()
    stats = {
        "projects": projects_scanned,
        "total": len(all_gaps),
        "inserted": inserted,
        "skipped": skipped,
        "open_total": len(open_gaps),
        "auto_healed": healed,
    }

    report = build_report(open_gaps, stats)
    send(report)
    logger.info("Report sent. Stats: %s", stats)

    return stats
