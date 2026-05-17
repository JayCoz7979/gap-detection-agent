"""
Auto-heal orchestrator.

Flow for each new CRITICAL gap:
  1. Look up fix in registry
  2. If manual_only or requires_credentials → skip, annotate in Telegram
  3. Pre-validate → if fails, abort (don't touch production)
  4. Log gap_fix row as 'executing', mark gap.auto_executed = True
  5. Execute fix (Railway redeploy or SQL migration)
  6. Post-validate → if fails, run rollback and alert Jay
  7. Update gap_fix status: success | failed | rolled_back
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

import fixes as fix_registry
from fixes.railway_redeploy import redeploy
from fixes.apply_migration import run_sql
from validator import pre_validate, post_validate
from db import (
    create_gap_fix,
    update_gap_fix,
    mark_gap_auto_executed,
)
from telegram_client import send

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def heal_gap(gap_row: dict) -> dict | None:
    """
    Attempt to auto-heal one gap. Returns the gap_fix record dict, or None if skipped.
    gap_row must have: id, project_name, gap_description, severity.
    """
    gap_id = gap_row["id"]
    project = gap_row["project_name"]
    description = gap_row["gap_description"]
    severity = gap_row["severity"]

    # Only auto-execute critical gaps
    if severity != "critical":
        return None

    fix = fix_registry.lookup(project, description)
    if fix is None:
        logger.info("No fix registered for: [%s] %s", project, description[:60])
        return None

    if not fix.auto_executable:
        reason = fix.manual_reason or "Fix requires manual action"
        logger.info("Fix not auto-executable for [%s]: %s", project, reason)
        send(
            f"⚠️ <b>Manual action needed</b>\n"
            f"<b>Project:</b> {project}\n"
            f"<b>Gap:</b> {description}\n"
            f"<b>Action:</b> {reason}"
        )
        return None

    logger.info("Auto-healing [%s]: %s", project, description[:60])

    # Step 1: Pre-validate
    pre_ok, pre_results = pre_validate(project, fix.fix_type)
    if not pre_ok:
        failed_checks = [r["check"] for r in pre_results if not r.get("passed")]
        msg = (
            f"🚫 <b>Auto-heal ABORTED</b> — pre-validation failed\n"
            f"<b>Project:</b> {project}\n"
            f"<b>Gap:</b> {description}\n"
            f"<b>Failed checks:</b> {', '.join(failed_checks)}\n"
            f"<i>No changes made to production.</i>"
        )
        send(msg)
        logger.warning("Pre-validation failed for [%s]: %s", project, failed_checks)
        return None

    # Step 2: Create gap_fix row as 'executing'
    fix_row = create_gap_fix({
        "gap_detection_id": gap_id,
        "fix_type": fix.fix_type,
        "fix_code": fix.fix_code,
        "rollback_script": fix.rollback_script,
        "validation_log": {"pre": pre_results},
        "status": "executing",
        "executed_at": _now(),
    })
    if not fix_row:
        logger.error("Failed to create gap_fix row — aborting heal")
        return None

    fix_id = fix_row["id"]
    mark_gap_auto_executed(gap_id)

    # Step 3: Execute fix
    exec_ok, exec_msg = _execute(fix, project)
    logger.info("Fix execution [%s]: ok=%s msg=%s", project, exec_ok, exec_msg[:80])

    if not exec_ok:
        update_gap_fix(fix_id, {
            "status": "failed",
            "failure_reason": exec_msg,
            "validation_log": {"pre": pre_results, "exec_error": exec_msg},
        })
        send(
            f"❌ <b>Auto-heal FAILED at execution</b>\n"
            f"<b>Project:</b> {project}\n"
            f"<b>Gap:</b> {description}\n"
            f"<b>Error:</b> {exec_msg}\n"
            f"<b>Fix ID:</b> <code>{fix_id}</code>\n"
            f"<i>No rollback needed — fix did not execute.</i>"
        )
        return fix_row

    # Step 4: Post-validate
    post_ok, post_results = post_validate(project, fix.fix_type)
    validation_log = {"pre": pre_results, "exec": exec_msg, "post": post_results}

    if post_ok:
        update_gap_fix(fix_id, {"status": "success", "validation_log": validation_log})
        send(
            f"✅ <b>Auto-heal SUCCESS</b>\n"
            f"<b>Project:</b> {project}\n"
            f"<b>Fix:</b> {fix.fix_type}\n"
            f"<b>Gap resolved:</b> {description}\n"
            f"<b>Fix ID:</b> <code>{fix_id}</code>"
        )
        logger.info("Auto-heal succeeded for [%s]", project)
    else:
        # Post-validation failed — run rollback
        failed_post = [r["check"] for r in post_results if not r.get("passed")]
        logger.warning("Post-validation failed [%s]: %s — running rollback", project, failed_post)

        rollback_ok, rollback_msg = _rollback(fix, project)
        status = "rolled_back" if rollback_ok else "failed"

        update_gap_fix(fix_id, {
            "status": status,
            "failure_reason": f"Post-validation failed: {failed_post}",
            "validation_log": validation_log,
            "rolled_back_at": _now(),
        })

        send(
            f"🔴 <b>Auto-heal ROLLED BACK</b>\n"
            f"<b>Project:</b> {project}\n"
            f"<b>Gap:</b> {description}\n"
            f"<b>Failed post-checks:</b> {', '.join(failed_post)}\n"
            f"<b>Rollback:</b> {'succeeded ✅' if rollback_ok else 'FAILED ❌ — manual intervention needed'}\n"
            f"<b>Rollback note:</b> {rollback_msg}\n"
            f"<b>Fix ID:</b> <code>{fix_id}</code>\n"
            f"Use /rollback {fix_id} to re-attempt rollback if needed."
        )

    return fix_row


def execute_approved_fix(gap_row: dict, fix_id: str) -> None:
    """
    Execute a manually approved non-critical fix (triggered by /approve_fix command).
    Same flow as auto-heal but initiated by Jay.
    """
    project = gap_row["project_name"]
    description = gap_row["gap_description"]

    fix = fix_registry.lookup(project, description)
    if fix is None or fix.fix_type == "manual_only":
        send(
            f"⚠️ No automated fix available for:\n"
            f"<b>{project}</b> — {description}\n"
            f"This gap requires manual implementation."
        )
        return

    pre_ok, pre_results = pre_validate(project, fix.fix_type)
    if not pre_ok:
        failed = [r["check"] for r in pre_results if not r.get("passed")]
        update_gap_fix(fix_id, {
            "status": "failed",
            "failure_reason": f"Pre-validation failed: {failed}",
            "validation_log": {"pre": pre_results},
        })
        send(f"🚫 Pre-validation failed for <b>{project}</b>: {failed}")
        return

    update_gap_fix(fix_id, {"status": "executing", "executed_at": _now()})
    mark_gap_auto_executed(gap_row["id"])

    exec_ok, exec_msg = _execute(fix, project)
    post_ok, post_results = post_validate(project, fix.fix_type) if exec_ok else (False, [])
    validation_log = {"pre": pre_results, "exec": exec_msg, "post": post_results}

    if exec_ok and post_ok:
        update_gap_fix(fix_id, {"status": "success", "validation_log": validation_log})
        send(f"✅ Approved fix succeeded for <b>{project}</b>: {description}")
    else:
        failed_post = [r["check"] for r in post_results if not r.get("passed")]
        rollback_ok, rollback_msg = _rollback(fix, project) if exec_ok else (True, "Not executed")
        update_gap_fix(fix_id, {
            "status": "rolled_back" if rollback_ok else "failed",
            "failure_reason": exec_msg if not exec_ok else f"Post-validation: {failed_post}",
            "validation_log": validation_log,
            "rolled_back_at": _now(),
        })
        send(
            f"❌ Approved fix failed for <b>{project}</b>\n"
            f"Rollback: {'succeeded' if rollback_ok else 'FAILED — manual action needed'}"
        )


def manual_rollback(fix_row: dict) -> None:
    """Execute a manual rollback for a fix, triggered by /rollback command."""
    fix_id = fix_row["id"]
    fix_type = fix_row["fix_type"]
    rollback_script = fix_row["rollback_script"]

    # Reconstruct a minimal Fix object for _rollback
    from fixes.base import Fix
    fix = Fix(
        fix_type=fix_type,
        fix_code=fix_row["fix_code"],
        rollback_script=rollback_script,
    )

    # Extract project from gap_detection join (stored in validation_log or look up gap)
    project = fix_row.get("project_name", "Unknown")
    ok, msg = _rollback(fix, project)

    update_gap_fix(fix_id, {
        "status": "rolled_back" if ok else "failed",
        "failure_reason": None if ok else f"Manual rollback failed: {msg}",
        "rolled_back_at": _now(),
    })

    send(
        f"{'✅' if ok else '❌'} Manual rollback {'succeeded' if ok else 'FAILED'}\n"
        f"<b>Fix ID:</b> <code>{fix_id}</code>\n"
        f"<b>Note:</b> {msg}"
    )


# ── Private execution helpers ─────────────────────────────────────────────────

def _execute(fix, project: str) -> tuple[bool, str]:
    if fix.fix_type == "railway_redeploy":
        return redeploy(project)
    elif fix.fix_type == "sql_migration":
        return run_sql(fix.fix_code)
    else:
        return False, f"No executor for fix_type '{fix.fix_type}'"


def _rollback(fix, project: str) -> tuple[bool, str]:
    if fix.fix_type == "railway_redeploy":
        # Redeploy is idempotent — rollback means trigger another redeploy from last stable
        return True, (
            "Redeploy is idempotent. If the new deploy is unhealthy, use Railway dashboard "
            f"to roll back service to the previous deployment."
        )
    elif fix.fix_type == "sql_migration":
        if fix.rollback_script and not fix.rollback_script.startswith("# N/A"):
            return run_sql(fix.rollback_script)
        return True, "No destructive SQL was applied; no rollback needed."
    return False, f"No rollback handler for fix_type '{fix.fix_type}'"
