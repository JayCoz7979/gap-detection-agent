"""Telegram notification sender + webhook registration."""
import os
import logging
import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def _token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def send(message: str, chat_id: str | None = None) -> bool:
    token = _token()
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping send")
        return False

    target = chat_id or os.environ.get("TELEGRAM_GROUP_ID", "-5271660549")
    chunks = [message[i:i + 4000] for i in range(0, len(message), 4000)]
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


def register_webhook(url: str) -> bool:
    """Tell Telegram to push updates to our /telegram/webhook endpoint."""
    token = _token()
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping webhook registration")
        return False
    try:
        r = httpx.post(
            f"{TELEGRAM_API}/bot{token}/setWebhook",
            json={"url": url, "allowed_updates": ["message", "edited_message"]},
            timeout=10,
        )
        data = r.json()
        if data.get("ok"):
            logger.info("Telegram webhook registered: %s", url)
            return True
        logger.error("Webhook registration failed: %s", data)
        return False
    except Exception as e:
        logger.error("Webhook registration error: %s", e)
        return False


def build_report(gaps: list[dict], scan_stats: dict) -> str:
    """Format the weekly gap detection report for Telegram."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%A, %B %-d, %Y")

    severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}

    lines = [
        f"📋 <b>Gap Detection Report — {now}</b>",
        f"Scanned {scan_stats['projects']} projects · "
        f"{scan_stats['total']} gaps found · "
        f"{scan_stats['inserted']} new · "
        f"{scan_stats['skipped']} already tracked",
        "",
    ]

    if not gaps:
        lines.append("✅ No open gaps detected.")
        return "\n".join(lines)

    by_severity: dict[str, list[dict]] = {"critical": [], "high": [], "medium": [], "low": []}
    for gap in gaps:
        by_severity.setdefault(gap.get("severity", "low"), []).append(gap)

    for sev in ("critical", "high", "medium", "low"):
        items = by_severity.get(sev, [])
        if not items:
            continue

        lines.append(f"{severity_emoji[sev]} <b>{sev.upper()} ({len(items)})</b>")
        by_project: dict[str, list[dict]] = {}
        for item in items:
            by_project.setdefault(item["project_name"], []).append(item)

        for project, pgaps in by_project.items():
            for g in pgaps:
                lines.append(f"  • <b>{project}</b> — {g['gap_description']}")
        lines.append("")

    lines.append(
        "Commands: /status · /approve_fix &lt;id&gt; · /rollback &lt;id&gt;\n"
        "🐝 <i>Critical gaps auto-executed. High/med/low await your approval.</i>"
    )
    return "\n".join(lines)
