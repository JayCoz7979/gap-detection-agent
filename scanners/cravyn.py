"""CRAVYN gap scanner — pickup-only food ordering platform."""
from .base import Gap, health_check

PROJECT = "CRAVYN"
BACKEND_URL = "https://cravyn-backend-production.up.railway.app"
FRONTEND_URL = "https://cravyn-frontend-production.up.railway.app"


def scan() -> list[Gap]:
    gaps: list[Gap] = []
    backend_up = health_check(f"{BACKEND_URL}/health")
    frontend_up = health_check(FRONTEND_URL)

    if not backend_up:
        gaps.append(Gap(PROJECT, "deployment", "Backend service is down or unreachable", "critical",
                        f"Health check failed: {BACKEND_URL}/health"))

    if not frontend_up:
        gaps.append(Gap(PROJECT, "deployment", "Frontend service is down or unreachable", "critical",
                        f"Health check failed: {FRONTEND_URL}"))

    # Integration gaps — known from deploy (REPLACE_ME values set in Railway)
    gaps.append(Gap(PROJECT, "integration",
                    "Stripe secret key not configured — STRIPE_SECRET_KEY is REPLACE_ME in Railway",
                    "critical", "Payments are completely blocked; no orders can be processed"))

    gaps.append(Gap(PROJECT, "integration",
                    "Stripe webhook secret not configured — STRIPE_WEBHOOK_SECRET is REPLACE_ME",
                    "critical", "Payment confirmations will not be received; order status won't update"))

    gaps.append(Gap(PROJECT, "integration",
                    "Twilio SMS credentials not configured — TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER are REPLACE_ME",
                    "high", "Order pickup SMS notifications to customers and restaurants are disabled"))

    gaps.append(Gap(PROJECT, "integration",
                    "TaxJar API key not configured — TAXJAR_API_KEY is REPLACE_ME",
                    "high", "Alabama sales tax cannot be calculated; orders will fail tax validation"))

    gaps.append(Gap(PROJECT, "integration",
                    "Supabase anon key not set in frontend — NEXT_PUBLIC_SUPABASE_ANON_KEY is REPLACE_ME",
                    "critical", "Frontend cannot connect to Supabase; real-time order tracking is broken"))

    gaps.append(Gap(PROJECT, "integration",
                    "Stripe Connect onboarding flow not tested end-to-end with live restaurant account",
                    "high", "Restaurant payout setup is untested; no restaurant can complete onboarding"))

    gaps.append(Gap(PROJECT, "feature",
                    "Stripe Premium price ID not configured — STRIPE_PREMIUM_PRICE_ID is REPLACE_ME",
                    "high", "Restaurant premium subscription upgrades will fail at checkout"))

    gaps.append(Gap(PROJECT, "schema",
                    "Supabase migration 001_cravyn_schema.sql not confirmed applied to production",
                    "high", "cravyn schema tables may not exist in production Supabase project"))

    gaps.append(Gap(PROJECT, "feature",
                    "Admin dashboard has no revenue reporting — platform commission tracking absent",
                    "medium", "Cosby AI cannot see platform earnings without a revenue report view"))

    gaps.append(Gap(PROJECT, "error_handling",
                    "No retry logic on failed order SMS — if Twilio fails, customer receives no notification",
                    "medium", "Single-attempt SMS with no fallback or retry queue"))

    return gaps
