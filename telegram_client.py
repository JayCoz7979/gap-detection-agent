"""Telegram notification sender."""
import os
import logging
import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def send(message: str, chat_id: str | None = None) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping Telegram send")
        return False

    target = chat_id or os.environ.get("TELEGRAM_GROUP_ID", "-5271660549")

    # Telegram max message length is 4096 chars; split if needed
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]

    success = True
    for chunk in chunks:
        try:
            r = httpx.post(
                f"{TELEGRAM_API}/bot{token}/sendMessage",
                json={"chat_id": target, "text": chunk, "parse_mode": "HTML"},
                timeout=12,
            )
            if not r.is_success:
                logger.error("Telegram error %s: %s", r.status_code, r.text[:200])
                success = False
        except Exception as e:
            logger.error("Telegram send failed: %s", e)
            success = False

    return success


def build_report(gaps: list[dict], scan_stats: dict) -> str:
    """Format the weekly gap detection report for Telegram."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%A, %B %-d, %Y")

    severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}
    severity_label = {"critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM", "low": "LOW"}

    lines = [
        f"📋 <b>Gap Detection Report — {now}</b>",
        f"Scanned {scan_stats['projects']} projects · "
        f"{scan_stats['total']} gaps found · "
        f"{scan_stats['inserted']} new · "
        f"{scan_stats['skipped']} already tracked",
        "",
    ]

    if not gaps:
        lines.append("✅ No open gaps detected across all projects.")
        return "\n".join(lines)

    # Group by severity
    by_severity: dict[str, list[dict]] = {"critical": [], "high": [], "medium": [], "low": []}
    for gap in gaps:
        sev = gap.get("severity", "low")
        by_severity.setdefault(sev, []).append(gap)

    for sev in ("critical", "high", "medium", "low"):
        items = by_severity.get(sev, [])
        if not items:
            continue

        emoji = severity_emoji[sev]
        label = severity_label[sev]
        lines.append(f"{emoji} <b>{label} ({len(items)})</b>")

        # Group items by project within this severity
        by_project: dict[str, list[dict]] = {}
        for item in items:
            by_project.setdefault(item["project_name"], []).append(item)

        for project, project_gaps in by_project.items():
            for g in project_gaps:
                desc = g["gap_description"]
                lines.append(f"  • <b>{project}</b> — {desc}")

        lines.append("")

    lines.append("🐝 <i>Review Monday morning. Auto-fix disabled — Jay decides priority.</i>")
    return "\n".join(lines)
