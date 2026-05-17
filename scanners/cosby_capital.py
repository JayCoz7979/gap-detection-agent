"""Cosby Capital gap scanner — capital advisory and deal flow platform."""
from .base import Gap, health_check

PROJECT = "Cosby Capital"
SOCIAL_AGENT_URL = "https://cosby-capital-social-agent-production.up.railway.app"


def scan() -> list[Gap]:
    gaps: list[Gap] = []
    social_up = health_check(SOCIAL_AGENT_URL)

    if not social_up:
        gaps.append(Gap(PROJECT, "deployment", "Social agent service is down or unreachable", "high",
                        f"Health check failed: {SOCIAL_AGENT_URL}"))

    gaps.append(Gap(PROJECT, "feature",
                    "Core deal flow platform not deployed — only social agent in Railway",
                    "critical", "No investor CRM, deal pipeline, or capital tracking backend exists"))

    gaps.append(Gap(PROJECT, "integration",
                    "Accredited investor verification (Veriff or similar KYC) not integrated",
                    "critical", "SEC Reg D requires verification of accredited investor status before fundraising"))

    gaps.append(Gap(PROJECT, "integration",
                    "Wire transfer / ACH capital call processing not implemented",
                    "critical", "Capital calls cannot be collected without a payment mechanism"))

    gaps.append(Gap(PROJECT, "feature",
                    "LP portal with distribution statements and K-1 documents not built",
                    "high", "Limited partners need document access for tax reporting"))

    gaps.append(Gap(PROJECT, "integration",
                    "Compliance reporting (Form D, blue sky filings) workflow absent",
                    "high", "Securities offerings require ongoing regulatory filings not tracked anywhere"))

    gaps.append(Gap(PROJECT, "feature",
                    "Deal pipeline CRM with stage tracking not implemented",
                    "high", "No way to track deals from sourcing through close"))

    gaps.append(Gap(PROJECT, "security",
                    "No FINRA/SEC compliance framework for digital investment platform",
                    "critical", "Operating a capital platform without broker-dealer registration or RIA compliance is a legal risk"))

    gaps.append(Gap(PROJECT, "feature",
                    "Portfolio performance reporting (IRR, MOIC, TVPI) not implemented",
                    "medium", "Investors expect standardized return metrics across their portfolio"))

    gaps.append(Gap(PROJECT, "schema",
                    "No database schema for investment instruments, LP agreements, or capital accounts",
                    "critical", "Zero data model exists for the core financial objects of the platform"))

    return gaps
