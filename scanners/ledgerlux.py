"""LedgerLux AI gap scanner — AI-powered accounting and bookkeeping platform."""
from .base import Gap, health_check

PROJECT = "LedgerLux AI"
ENGINE_URL = "https://ledgerlux-finova-engine-production.up.railway.app"


def scan() -> list[Gap]:
    gaps: list[Gap] = []
    engine_up = health_check(f"{ENGINE_URL}/health")

    if not engine_up:
        gaps.append(Gap(PROJECT, "deployment", "Finova engine service is down or unreachable", "critical",
                        f"Health check failed: {ENGINE_URL}/health"))

    gaps.append(Gap(PROJECT, "integration",
                    "QuickBooks Online / Xero sync integration not implemented",
                    "high", "Users expect two-way sync with their existing accounting software"))

    gaps.append(Gap(PROJECT, "integration",
                    "Bank feed aggregation (Plaid or Finicity) not integrated",
                    "high", "Without bank feeds, transaction import is manual — core value prop is broken"))

    gaps.append(Gap(PROJECT, "feature",
                    "AI categorization model for transactions not trained or deployed",
                    "critical", "The 'AI-powered' claim requires an actual categorization model; none exists"))

    gaps.append(Gap(PROJECT, "integration",
                    "Stripe billing integration absent — no subscription or per-seat pricing flow",
                    "high", "LedgerLux has no way to charge customers"))

    gaps.append(Gap(PROJECT, "feature",
                    "Chart of accounts customization not implemented",
                    "high", "Different industries need different account structures; hardcoded COA won't work"))

    gaps.append(Gap(PROJECT, "feature",
                    "Accounts payable module absent — only receivable side exists",
                    "high", "Full bookkeeping requires both AP and AR"))

    gaps.append(Gap(PROJECT, "feature",
                    "Tax preparation export (CSV/TXF for CPA handoff) not implemented",
                    "medium", "Year-end handoff to CPA is a core workflow; no export capability"))

    gaps.append(Gap(PROJECT, "security",
                    "Financial data encryption at rest not confirmed — PII and account numbers unprotected",
                    "high", "Banking data requires field-level encryption beyond Supabase row security"))

    gaps.append(Gap(PROJECT, "feature",
                    "Multi-entity / multi-company bookkeeping not supported",
                    "medium", "Small businesses with multiple entities cannot consolidate books"))

    gaps.append(Gap(PROJECT, "error_handling",
                    "No reconciliation conflict resolution UI — duplicate transactions silently overwrite",
                    "medium", "Bank feed duplicates need a review queue, not silent deduplication"))

    return gaps
