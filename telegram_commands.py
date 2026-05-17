"""
Telegram bot command handler.
Receives webhook updates from Telegram and dispatches:
  /status              — list all open gaps and auto-execute eligibility
  /approve_fix <gap_id> — manually trigger a fix for a non-critical gap
  /rollback <fix_id>   — manually rollback a deployed fix
"""
from __future__ import annotations
import logging
import os

logger = logging.getLogger(__name__)

ALLOWED_CHAT_ID = int(os.environ.get("TELEGRAM_GROUP_ID", "-5271660549"))


def handle_update(update: dict) -> None:
    """Entry point: parse a Telegram Update object and dispatch to the right handler."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id = message.get("chat", {}).get("id")
    text: str = (message.get("text") or "").strip()

    # Only respond to the authorised chat
    if chat_id != ALLOWED_CHAT_ID:
        logger.warning("Ignored update from unauthorised chat_id %s", chat_id)
        return

    if not text.startswith("/"):
        return

    parts = text.split()
    command = parts[0].lower().split("@")[0]  # strip @botname suffix

    if command == "/status":
        _handle_status(chat_id)
    elif command == "/approve_fix" and len(parts) >= 2:
        _handle_approve_fix(chat_id, parts[1])
    elif command == "/rollback" and len(parts) >= 2:
        _handle_rollback(chat_id, parts[1])
    elif command in ("/approve_fix", "/rollback"):
        from telegram_client import send
        send(f"Usage: {command} &lt;id&gt;", chat_id=str(chat_id))
    elif command == "/help":
        _handle_help(chat_id)


def _handle_status(chat_id: int) -> None:
    from db import get_client
    from telegram_client import send

    client = get_client()
    rows = (
        client.table("gap_detections")
        .select("id, project_name, gap_description, severity, status, auto_executed, created_at")
        .in_("status", ["open", "acknowledged", "in_progress"])
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    ).data or []

    if not rows:
        send("✅ No open gaps.", chat_id=str(chat_id))
        return

    import fixes as fix_registry
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    rows.sort(key=lambda r: sev_order.get(r["severity"], 9))

    sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}
    lines = [f"<b>Open Gaps ({len(rows)})</b>\n"]

    for r in rows:
        fix = fix_registry.lookup(r["project_name"], r["gap_description"])
        if fix is None:
            eligibility = "⬛ no fix registered"
        elif not fix.auto_executable:
            if fix.requires_credentials:
                eligibility = "🔑 needs credentials"
            else:
                eligibility = "👤 manual only"
        else:
            eligibility = "⚡ auto-executable"

        auto_tag = " [auto-executed]" if r.get("auto_executed") else ""
        icon = sev_icon.get(r["severity"], "⚪")
        gap_id_short = str(r["id"])[:8]
        lines.append(
            f"{icon} <b>{r['project_name']}</b>{auto_tag}\n"
            f"   {r['gap_description'][:80]}\n"
            f"   {eligibility} · ID: <code>{gap_id_short}</code>"
        )

    send("\n".join(lines), chat_id=str(chat_id))


def _handle_approve_fix(chat_id: int, gap_id_prefix: str) -> None:
    from db import get_client, create_gap_fix
    from healer import execute_approved_fix
    from telegram_client import send
    import fixes as fix_registry

    client = get_client()

    # Resolve short ID prefix to full UUID
    rows = (
        client.table("gap_detections")
        .select("*")
        .ilike("id", f"{gap_id_prefix}%")
        .in_("status", ["open", "acknowledged", "in_progress"])
        .limit(2)
        .execute()
    ).data or []

    if not rows:
        send(f"Gap <code>{gap_id_prefix}</code> not found or already resolved.", chat_id=str(chat_id))
        return
    if len(rows) > 1:
        send(f"Ambiguous ID prefix <code>{gap_id_prefix}</code> — use more characters.", chat_id=str(chat_id))
        return

    gap_row = rows[0]
    fix = fix_registry.lookup(gap_row["project_name"], gap_row["gap_description"])

    if fix is None or fix.fix_type == "manual_only":
        send(
            f"No automated fix for:\n<b>{gap_row['project_name']}</b> — {gap_row['gap_description']}\n"
            f"This gap requires manual implementation.",
            chat_id=str(chat_id)
        )
        return

    if fix.requires_credentials:
        send(
            f"🔑 Fix requires external credentials.\n"
            f"<b>Action needed:</b> {fix.manual_reason}",
            chat_id=str(chat_id)
        )
        return

    send(
        f"⚙️ Executing approved fix for <b>{gap_row['project_name']}</b>…\n"
        f"{gap_row['gap_description'][:80]}",
        chat_id=str(chat_id)
    )

    # Create the gap_fix row so execute_approved_fix can update it
    from datetime import datetime, timezone
    fix_row = create_gap_fix({
        "gap_detection_id": gap_row["id"],
        "fix_type": fix.fix_type,
        "fix_code": fix.fix_code,
        "rollback_script": fix.rollback_script,
        "validation_log": {},
        "status": "pending",
        "executed_at": datetime.now(timezone.utc).isoformat(),
    })
    if not fix_row:
        send("Failed to create fix record in DB.", chat_id=str(chat_id))
        return

    import threading
    threading.Thread(
        target=execute_approved_fix,
        args=(gap_row, fix_row["id"]),
        daemon=True,
    ).start()


def _handle_rollback(chat_id: int, fix_id_prefix: str) -> None:
    from db import get_client
    from healer import manual_rollback
    from telegram_client import send

    client = get_client()

    rows = (
        client.table("gap_fixes")
        .select("*, gap_detections(project_name)")
        .ilike("id", f"{fix_id_prefix}%")
        .limit(2)
        .execute()
    ).data or []

    if not rows:
        send(f"Fix <code>{fix_id_prefix}</code> not found.", chat_id=str(chat_id))
        return
    if len(rows) > 1:
        send(f"Ambiguous ID prefix <code>{fix_id_prefix}</code> — use more characters.", chat_id=str(chat_id))
        return

    fix_row = rows[0]
    # Flatten joined project_name
    if isinstance(fix_row.get("gap_detections"), dict):
        fix_row["project_name"] = fix_row["gap_detections"].get("project_name", "Unknown")

    if fix_row.get("status") == "rolled_back":
        send(f"Fix <code>{fix_id_prefix}</code> already rolled back.", chat_id=str(chat_id))
        return

    send(f"⏪ Running rollback for fix <code>{fix_id_prefix}</code>…", chat_id=str(chat_id))

    import threading
    threading.Thread(target=manual_rollback, args=(fix_row,), daemon=True).start()


def _handle_help(chat_id: int) -> None:
    from telegram_client import send
    send(
        "<b>Gap Detection Agent — Commands</b>\n\n"
        "/status — list all open gaps with auto-execute eligibility\n"
        "/approve_fix &lt;gap_id&gt; — trigger an approved fix (use first 8 chars of gap ID)\n"
        "/rollback &lt;fix_id&gt; — rollback a deployed fix\n"
        "/help — show this message\n\n"
        "<i>Critical gaps are auto-executed immediately after Sunday scan.\n"
        "High/medium/low gaps require /approve_fix.</i>",
        chat_id=str(chat_id)
    )
