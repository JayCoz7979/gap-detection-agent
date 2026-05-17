"""Fix: apply a SQL migration via psycopg2."""
from __future__ import annotations
import os
import logging
import psycopg2

logger = logging.getLogger(__name__)


def run_sql(sql: str, db_url: str | None = None) -> tuple[bool, str]:
    """Execute SQL against the configured database. Returns (success, message)."""
    url = db_url or os.environ.get("DATABASE_URL", "")
    if not url:
        return False, "DATABASE_URL not set — cannot apply SQL migration"
    try:
        conn = psycopg2.connect(url, sslmode="require")
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.close()
        return True, "SQL migration applied successfully"
    except Exception as e:
        return False, str(e)


def build_fix_and_rollback(sql: str, rollback_sql: str) -> tuple[str, str]:
    """Return (fix_code, rollback_script) for logging."""
    fix = f"-- Auto-applied migration\n{sql}"
    rollback = f"-- Rollback SQL\n{rollback_sql}"
    return fix, rollback
