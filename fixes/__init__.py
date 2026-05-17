"""
Fix registry: maps (project_name, gap_description_substring) → Fix descriptor.

Only CRITICAL severity gaps with auto_executable=True will be auto-healed.
All others appear in the Sunday report for manual review.
"""
from __future__ import annotations
from .base import Fix
from .railway_redeploy import build_fix_and_rollback as redeploy_fix
from .apply_migration import build_fix_and_rollback as sql_fix


def _redeploy(project: str, notes: str = "") -> Fix:
    fix_code, rollback = redeploy_fix(project)
    return Fix(
        fix_type="railway_redeploy",
        fix_code=fix_code,
        rollback_script=rollback,
        auto_executable=True,
        meta={"project_name": project},
    )


def _manual(reason: str) -> Fix:
    return Fix(
        fix_type="manual_only",
        fix_code=f"# Manual action required: {reason}",
        rollback_script="# N/A — no automated change was made",
        auto_executable=False,
        manual_reason=reason,
    )


def _needs_creds(label: str) -> Fix:
    return Fix(
        fix_type="env_update",
        fix_code=f"# Requires external credential: {label}",
        rollback_script="# N/A — no automated change was made",
        auto_executable=False,
        requires_credentials=True,
        manual_reason=f"Set {label} in Railway dashboard → service → Variables",
    )


# Registry: list of (project_name_substr, gap_description_substr, Fix)
# Matched in order — first match wins. Case-insensitive on both keys.
REGISTRY: list[tuple[str, str, Fix]] = [

    # ── Service-down gaps: auto-redeploy ─────────────────────────────────────
    ("CoachLenz",       "backend service is down",   _redeploy("CoachLenz")),
    ("CoachLenz",       "frontend service is down",  _redeploy("CoachLenz")),
    ("CRAVYN",          "backend service is down",   _redeploy("CRAVYN")),
    ("CRAVYN",          "frontend service is down",  _redeploy("CRAVYN")),
    ("ProgramPilot AI", "api service is down",       _redeploy("ProgramPilot AI")),
    ("ProgramPilot AI", "frontend is down",          _redeploy("ProgramPilot AI")),
    ("LedgerLux AI",    "finova engine service is down", _redeploy("LedgerLux AI")),

    # ── Credential gaps: needs human ─────────────────────────────────────────
    ("CRAVYN", "stripe secret key",          _needs_creds("STRIPE_SECRET_KEY")),
    ("CRAVYN", "stripe webhook secret",      _needs_creds("STRIPE_WEBHOOK_SECRET")),
    ("CRAVYN", "twilio",                     _needs_creds("TWILIO_ACCOUNT_SID / AUTH_TOKEN / FROM_NUMBER")),
    ("CRAVYN", "taxjar",                     _needs_creds("TAXJAR_API_KEY")),
    ("CRAVYN", "supabase anon key",          _needs_creds("NEXT_PUBLIC_SUPABASE_ANON_KEY")),
    ("CRAVYN", "stripe premium price",       _needs_creds("STRIPE_PREMIUM_PRICE_ID")),
    ("ProgramPilot AI", "stripe_secret_key", _needs_creds("PP_STRIPE_SECRET_KEY")),

    # ── Schema gaps: apply migration SQL ─────────────────────────────────────
    ("CRAVYN", "migration 001_cravyn_schema.sql not confirmed", Fix(
        fix_type="sql_migration",
        fix_code="-- See migrations/001_cravyn_schema.sql\n-- Run manually in Supabase SQL editor",
        rollback_script="DROP SCHEMA IF EXISTS cravyn CASCADE;",
        auto_executable=False,  # too destructive to auto-apply; requires manual review
        manual_reason="Run migrations/001_cravyn_schema.sql in Supabase SQL editor for project mbkstodswexxvdgyunio",
    )),
    ("ProgramPilot AI", "migration file not in repo", _manual(
        "Add pp_budget_variance migration to repo and apply via CI"
    )),

    # ── Security gaps: manual action required ─────────────────────────────────
    ("ProgramPilot AI", "webhook endpoint lacks idempotency", _manual(
        "Add processed_webhook_ids table; check event ID before processing in billing/webhook handler"
    )),
    ("ProgramPilot AI", "csrf protection", _manual(
        "Implement double-submit CSRF token on all state-changing POST routes"
    )),
    ("CoachLenz",       "jwt refresh rotation", _manual(
        "Store used refresh token hashes in DB; reject replayed tokens"
    )),

    # ── Feature gaps: all manual ──────────────────────────────────────────────
    ("CoachLenz",       "stripe payment integration", _manual("Build Stripe billing integration")),
    ("CoachLenz",       "onboarding flow",            _manual("Build athlete invite/registration flow")),
    ("ProgramPilot AI", "password reset",             _manual("Add /api/auth/forgot-password and /api/auth/reset-password")),
    ("ProgramPilot AI", "email notifications",        _manual("Wire Resend to invoice reminder routes")),
    ("Fly Pilot AI",    "core booking api",           _manual("Build and deploy Fly Pilot AI booking backend")),
    ("Fly Pilot AI",    "payment processing",         _needs_creds("Stripe or payment processor API key")),
    ("PreClose IQ",     "core preclose iq platform",  _manual("Build and deploy PreClose IQ backend")),
    ("EquityForge AI",  "core equityforge platform",  _manual("Build and deploy EquityForge AI backend")),
    ("EquityForge AI",  "database schema",            _manual("Design and deploy equity instruments schema")),
    ("LedgerLux AI",    "ai categorization model",    _manual("Train/integrate transaction categorization model")),
    ("LedgerLux AI",    "plaid",                      _needs_creds("PLAID_CLIENT_ID / PLAID_SECRET")),
    ("Cosby Capital",   "core deal flow platform",    _manual("Build and deploy Cosby Capital backend")),
    ("Cosby Capital",   "accredited investor",        _needs_creds("Veriff or KYC provider API key")),
    ("Cosby Capital",   "finra/sec compliance",       _manual("Engage securities attorney before building capital platform")),
]


def lookup(project_name: str, gap_description: str) -> Fix | None:
    """Return the first matching Fix for this gap, or None if unregistered."""
    p = project_name.lower()
    d = gap_description.lower()
    for proj_key, desc_key, fix in REGISTRY:
        if proj_key.lower() in p and desc_key.lower() in d:
            return fix
    return None
