"""Fly Pilot AI gap scanner — hotel/flight booking AI assistant."""
from .base import Gap, health_check

PROJECT = "Fly Pilot AI"
# Service is ledgerlux-finova-engine based on Railway layout; Fly Pilot has social agent
SOCIAL_AGENT_URL = "https://fly-hotel-pilot-social-agent-production.up.railway.app"


def scan() -> list[Gap]:
    gaps: list[Gap] = []
    social_up = health_check(SOCIAL_AGENT_URL)

    if not social_up:
        gaps.append(Gap(PROJECT, "deployment", "Social agent service is down or unreachable", "high",
                        f"Health check failed: {SOCIAL_AGENT_URL}"))

    # Architecture gaps
    gaps.append(Gap(PROJECT, "feature",
                    "Core booking API service not deployed — only social agent exists in Railway",
                    "critical", "Fly Pilot has no backend service for flight/hotel search or booking"))

    gaps.append(Gap(PROJECT, "feature",
                    "No self-healing healer service — unlike CRAVYN/ProgramPilot, no cron health monitor",
                    "high", "Service failures will go undetected until a user reports them"))

    gaps.append(Gap(PROJECT, "integration",
                    "Amadeus or Skyscanner flight API not integrated",
                    "high", "No live flight data source — platform cannot search real flights"))

    gaps.append(Gap(PROJECT, "integration",
                    "Hotel booking API (Booking.com / Hotels.com partner API) not integrated",
                    "high", "No live hotel inventory — platform cannot search or book hotels"))

    gaps.append(Gap(PROJECT, "integration",
                    "Payment processing for bookings not implemented",
                    "critical", "Users cannot complete bookings without a payment flow"))

    gaps.append(Gap(PROJECT, "feature",
                    "User authentication and booking history not implemented",
                    "high", "No login system means bookings cannot be tracked per user"))

    gaps.append(Gap(PROJECT, "error_handling",
                    "No fallback when flight/hotel API is rate-limited or unavailable",
                    "medium", "AI agent will return empty results with no graceful degradation message"))

    gaps.append(Gap(PROJECT, "security",
                    "CORS policy not confirmed for booking API — potential cross-origin exposure",
                    "medium", "No production CORS allowlist documented for the booking backend"))

    gaps.append(Gap(PROJECT, "feature",
                    "Loyalty program / points integration absent",
                    "low", "Users cannot connect frequent flyer or hotel reward accounts"))

    return gaps
