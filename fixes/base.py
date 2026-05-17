"""Fix descriptor — returned by every fix function in the registry."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Fix:
    # What kind of operation this is
    fix_type: str           # railway_redeploy | sql_migration | env_update | manual_only

    # The actual remediation code (SQL, bash, or descriptive string for manual)
    fix_code: str

    # How to undo the fix if post-validation fails
    rollback_script: str

    # True = safe to auto-run immediately on critical gaps
    auto_executable: bool = False

    # True = missing external credential; cannot auto-run
    requires_credentials: bool = False

    # Human-readable reason this fix cannot auto-execute (shown in Telegram)
    manual_reason: str = ""

    # Optional metadata passed to the executor
    meta: dict = field(default_factory=dict)
