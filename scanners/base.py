"""Shared types and health-check helper used by all project scanners."""
from __future__ import annotations
import httpx
from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["critical", "high", "medium", "low"]
Category = Literal["integration", "security", "feature", "schema", "deployment", "error_handling"]


@dataclass
class Gap:
    project_name: str
    gap_category: Category
    gap_description: str
    severity: Severity
    notes: str = ""


def health_check(url: str, timeout: int = 8) -> bool:
    """Returns True if the URL responds with 2xx."""
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True, verify=False)
        return r.status_code < 400
    except Exception:
        return False
