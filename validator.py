"""
Pre- and post-fix validation: health checks, schema probes, API smoke tests.
All results are logged to gap_fixes.validation_log (JSONB).
"""
from __future__ import annotations
import os
import logging
import psycopg2
import httpx
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Project → health endpoint URL
HEALTH_ENDPOINTS: dict[str, str] = {
    "CoachLenz":       "https://coachlenz-backend-production.up.railway.app/health",
    "CRAVYN":          "https://cravyn-backend-production.up.railway.app/health",
    "ProgramPilot AI": "https://pilotaihq-production.up.railway.app/health",
    "LedgerLux AI":    "https://ledgerlux-finova-engine-production.up.railway.app/health",
    "Gap Detection":   "https://gap-detection-agent-production.up.railway.app/health",
}

# Tables expected to exist per project (spot-checks)
SCHEMA_CHECKS: dict[str, list[str]] = {
    "CRAVYN":          ["cravyn.restaurants", "cravyn.orders", "cravyn.menus"],
    "CoachLenz":       ["coachlenz.teams", "coachlenz.players", "coachlenz.games"],
    "ProgramPilot AI": ["pp_companies", "pp_users", "pp_programs", "pp_invoices"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _http_check(url: str, label: str) -> dict:
    try:
        r = httpx.get(url, timeout=8, follow_redirects=True, verify=False)
        ok = r.status_code < 400
        return {"check": label, "url": url, "status_code": r.status_code, "passed": ok, "ts": _now()}
    except Exception as e:
        return {"check": label, "url": url, "error": str(e), "passed": False, "ts": _now()}


def _schema_check(project_name: str) -> list[dict]:
    tables = SCHEMA_CHECKS.get(project_name, [])
    if not tables:
        return []

    db_url = os.environ.get("DATABASE_URL", "")
    results = []
    if not db_url:
        for t in tables:
            results.append({"check": f"schema:{t}", "passed": False, "error": "DATABASE_URL not set", "ts": _now()})
        return results

    try:
        conn = psycopg2.connect(db_url, sslmode="require")
        conn.autocommit = True
        with conn.cursor() as cur:
            for table in tables:
                schema, _, tname = table.partition(".")
                if tname:
                    cur.execute(
                        "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema=%s AND table_name=%s)",
                        (schema, tname)
                    )
                else:
                    cur.execute(
                        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=%s)",
                        (table,)
                    )
                exists = cur.fetchone()[0]
                results.append({"check": f"schema:{table}", "passed": exists, "ts": _now()})
        conn.close()
    except Exception as e:
        for t in tables:
            results.append({"check": f"schema:{t}", "passed": False, "error": str(e), "ts": _now()})

    return results


def pre_validate(project_name: str, fix_type: str) -> tuple[bool, list[dict]]:
    """
    Run pre-fix smoke tests. Returns (all_passed, results_list).
    For redeploy fixes: service must be contactable (or unreachable — we're fixing that).
    For sql fixes: DB must be reachable.
    """
    results: list[dict] = []

    if fix_type == "railway_redeploy":
        url = HEALTH_ENDPOINTS.get(project_name)
        if url:
            # We expect it to be DOWN — that's why we're redeploying.
            # Pre-check: verify Railway API is reachable (our mechanism must work).
            results.append(_http_check(
                "https://backboard.railway.app/graphql/v2",
                "railway_api_reachable"
            ))
        results.append({"check": "pre_redeploy", "passed": True,
                        "note": "Redeploy safe — idempotent operation", "ts": _now()})

    elif fix_type == "sql_migration":
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url:
            try:
                conn = psycopg2.connect(db_url, sslmode="require")
                conn.close()
                results.append({"check": "db_reachable", "passed": True, "ts": _now()})
            except Exception as e:
                results.append({"check": "db_reachable", "passed": False, "error": str(e), "ts": _now()})
        else:
            results.append({"check": "db_reachable", "passed": False,
                            "error": "DATABASE_URL not set", "ts": _now()})

    all_passed = all(r.get("passed", False) for r in results) if results else True
    return all_passed, results


def post_validate(project_name: str, fix_type: str) -> tuple[bool, list[dict]]:
    """
    Run post-fix smoke tests. Returns (all_passed, results_list).
    For redeploy: health endpoint must respond 2xx within ~30s of redeploy trigger.
    For sql: expected tables must exist.
    """
    results: list[dict] = []

    if fix_type == "railway_redeploy":
        import time
        url = HEALTH_ENDPOINTS.get(project_name)
        if url:
            # Give Railway up to 60s to spin up
            for attempt in range(4):
                result = _http_check(url, f"post_health_attempt_{attempt + 1}")
                results.append(result)
                if result["passed"]:
                    break
                if attempt < 3:
                    time.sleep(15)

    elif fix_type == "sql_migration":
        schema_results = _schema_check(project_name)
        results.extend(schema_results)

    all_passed = all(r.get("passed", False) for r in results) if results else True
    return all_passed, results
