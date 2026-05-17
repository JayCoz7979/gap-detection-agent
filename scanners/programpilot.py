"""ProgramPilot AI gap scanner — GovCon program management platform."""
from .base import Gap, health_check

PROJECT = "ProgramPilot AI"
API_URL = "https://pilotaihq-production.up.railway.app"
FRONTEND_URL = "https://programpilotaihq.com"


def scan() -> list[Gap]:
    gaps: list[Gap] = []
    api_up = health_check(f"{API_URL}/health")
    frontend_up = health_check(FRONTEND_URL)

    if not api_up:
        gaps.append(Gap(PROJECT, "deployment", "API service is down or unreachable", "critical",
                        f"Health check failed: {API_URL}/health"))

    if not frontend_up:
        gaps.append(Gap(PROJECT, "deployment", "Frontend is down or unreachable", "critical",
                        f"Health check failed: {FRONTEND_URL}"))

    # Security
    gaps.append(Gap(PROJECT, "security",
                    "Stripe webhook endpoint lacks idempotency key tracking — replay attacks possible",
                    "high", "billing/webhook handler processes events but does not store processed event IDs"))

    gaps.append(Gap(PROJECT, "security",
                    "No CSRF protection on cookie-auth endpoints — sameSite=strict helps but explicit token missing",
                    "medium", "State-changing POST routes rely only on sameSite cookie; double-submit CSRF token not implemented"))

    gaps.append(Gap(PROJECT, "security",
                    "PP_STRIPE_SECRET_KEY not confirmed set in production environment",
                    "high", "Billing routes will error at runtime if Stripe key is absent"))

    # Features
    gaps.append(Gap(PROJECT, "feature",
                    "Email notifications not wired — invoice reminders send Telegram only, not email to clients",
                    "high", "Government contractors expect formal email reminders; Resend key is set but email routes unused"))

    gaps.append(Gap(PROJECT, "feature",
                    "Password reset flow absent — users cannot recover accounts without admin intervention",
                    "high", "No /api/auth/forgot-password or /api/auth/reset-password route exists"))

    gaps.append(Gap(PROJECT, "feature",
                    "Multi-company user support missing — a user cannot belong to more than one company",
                    "medium", "Subcontractors working across prime contracts need cross-company access"))

    gaps.append(Gap(PROJECT, "feature",
                    "Audit trail for approval actions not persisted — approve/reject events logged to console only",
                    "medium", "DCAA compliance requires immutable audit log of approval decisions"))

    gaps.append(Gap(PROJECT, "integration",
                    "DocuSign / e-signature integration absent for RFA approvals",
                    "medium", "RFAs approved in-app have no legal enforceability without e-signature"))

    gaps.append(Gap(PROJECT, "schema",
                    "pp_budget_variance company_id column added via manual migration — migration file not in repo",
                    "low", "Column was added ad-hoc; not tracked in a versioned migration script"))

    gaps.append(Gap(PROJECT, "feature",
                    "Demo mode accessible but no rate limit or time-box on demo dashboard endpoint",
                    "low", "/api/demo/dashboard is unauthenticated and unthrottled"))

    return gaps
