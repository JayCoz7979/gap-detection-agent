"""EquityForge AI gap scanner — equity/cap table management platform."""
from .base import Gap, health_check

PROJECT = "EquityForge AI"
SOCIAL_AGENT_URL = "https://equity-forge-ai-social-agent-production.up.railway.app"


def scan() -> list[Gap]:
    gaps: list[Gap] = []
    social_up = health_check(SOCIAL_AGENT_URL)

    if not social_up:
        gaps.append(Gap(PROJECT, "deployment", "Social agent service is down or unreachable", "high",
                        f"Health check failed: {SOCIAL_AGENT_URL}"))

    gaps.append(Gap(PROJECT, "feature",
                    "Core EquityForge platform not deployed — cap table engine absent",
                    "critical", "No backend for equity issuance, vesting schedules, or 409A valuations"))

    gaps.append(Gap(PROJECT, "integration",
                    "409A valuation provider integration not implemented",
                    "high", "Platform cannot generate compliant fair market value determinations"))

    gaps.append(Gap(PROJECT, "integration",
                    "SEC compliance reporting (Form D) filing integration absent",
                    "high", "Equity raises require Form D; no automated filing or reminder workflow"))

    gaps.append(Gap(PROJECT, "feature",
                    "Vesting schedule calculator and cliff/acceleration logic not built",
                    "high", "Core feature of any cap table tool; entirely absent"))

    gaps.append(Gap(PROJECT, "feature",
                    "Waterfall analysis (liquidation preferences) not implemented",
                    "high", "Investors need to model payout scenarios across funding rounds"))

    gaps.append(Gap(PROJECT, "security",
                    "No SOC 2 readiness posture — financial data requires audit-grade security controls",
                    "high", "Enterprise investors will not use a cap table tool without SOC 2 or equivalent"))

    gaps.append(Gap(PROJECT, "integration",
                    "DocuSign integration for stock option agreements not implemented",
                    "medium", "Option grants require countersignature; no e-signature flow exists"))

    gaps.append(Gap(PROJECT, "feature",
                    "Scenario modeling (round simulation) not implemented",
                    "medium", "Founders want to model dilution impact of new rounds before signing term sheets"))

    gaps.append(Gap(PROJECT, "schema",
                    "Database schema for equity instruments not designed or deployed",
                    "critical", "No tables for shares, options, warrants, or convertible notes"))

    return gaps
