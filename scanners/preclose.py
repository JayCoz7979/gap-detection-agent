"""PreClose IQ gap scanner — real estate pre-close intelligence platform."""
from .base import Gap, health_check

PROJECT = "PreClose IQ"
SOCIAL_AGENT_URL = "https://preclose-iq-social-agent-production.up.railway.app"


def scan() -> list[Gap]:
    gaps: list[Gap] = []
    social_up = health_check(SOCIAL_AGENT_URL)

    if not social_up:
        gaps.append(Gap(PROJECT, "deployment", "Social agent service is down or unreachable", "high",
                        f"Health check failed: {SOCIAL_AGENT_URL}"))

    gaps.append(Gap(PROJECT, "feature",
                    "Core PreClose IQ platform service not deployed — only social agent in Railway",
                    "critical", "No backend or frontend deployed; product is social-only"))

    gaps.append(Gap(PROJECT, "integration",
                    "MLS data feed integration absent — no live property data source",
                    "high", "Platform cannot pull real listing data without an MLS or RETS feed"))

    gaps.append(Gap(PROJECT, "integration",
                    "Title company workflow integration not implemented",
                    "high", "Pre-close checklist cannot sync with title company status"))

    gaps.append(Gap(PROJECT, "feature",
                    "Buyer/seller document collection portal not built",
                    "high", "Users have no way to upload or track required closing documents"))

    gaps.append(Gap(PROJECT, "integration",
                    "E-signature integration for closing documents absent",
                    "high", "Closing documents require DocuSign or similar; not implemented"))

    gaps.append(Gap(PROJECT, "feature",
                    "Transaction timeline tracker not implemented",
                    "medium", "No visual timeline showing days-to-close, contingency deadlines, etc."))

    gaps.append(Gap(PROJECT, "integration",
                    "Lender portal / loan status integration not implemented",
                    "medium", "Buyers cannot see their loan status or lender communication in-app"))

    gaps.append(Gap(PROJECT, "security",
                    "No data residency or PII handling policy for sensitive financial/identity documents",
                    "high", "Real estate closing involves SSNs, bank statements, tax returns — no PII controls defined"))

    gaps.append(Gap(PROJECT, "feature",
                    "Agent commission calculator and split tracker not implemented",
                    "low", "Agents want to see their net commission at various price points"))

    return gaps
