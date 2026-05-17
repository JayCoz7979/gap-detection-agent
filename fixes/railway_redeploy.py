"""Fix: trigger a Railway service redeploy via the GraphQL API."""
from __future__ import annotations
import os
import logging
import httpx

logger = logging.getLogger(__name__)

RAILWAY_TOKEN = os.environ.get("RAILWAY_TOKEN", "3432c16f-a92d-4bb2-b3e1-d4c464ed0c92")
RAILWAY_API = "https://backboard.railway.app/graphql/v2"

# Map project names to Railway service IDs
SERVICE_MAP: dict[str, str] = {
    "CoachLenz":       "78f5c761-f4c9-4aa8-8304-26ddcd01389e",  # coachlenz-backend
    "CRAVYN":          "6bfc2e07-aba9-4a0d-8d6a-a9e8a9b30ea7",  # cravyn-backend
    "ProgramPilot AI": "f3cc87c6-4eda-40dc-a82f-222b56eb1da6",  # pilotaihq
    "LedgerLux AI":    "e9550aac-ea7d-4f95-a9c7-2c6e69eafb3a",  # ledgerlux-finova-engine
    "Gap Detection":   "24d4b6ca-b06b-4cbd-a0a6-bd207261e802",  # self
}


def redeploy(project_name: str) -> tuple[bool, str]:
    """Trigger a Railway redeploy for the given project. Returns (success, message)."""
    service_id = SERVICE_MAP.get(project_name)
    if not service_id:
        return False, f"No Railway service ID mapped for project '{project_name}'"

    mutation = """
    mutation serviceInstanceRedeploy($serviceId: String!, $environmentId: String!) {
      serviceInstanceRedeploy(serviceId: $serviceId, environmentId: $environmentId)
    }
    """
    # courteous-analysis production environment
    env_id = "260f3931-851b-4579-b35e-ad28b5134c53"

    try:
        r = httpx.post(
            RAILWAY_API,
            headers={"Authorization": f"Bearer {RAILWAY_TOKEN}", "Content-Type": "application/json"},
            json={"query": mutation, "variables": {"serviceId": service_id, "environmentId": env_id}},
            timeout=15,
        )
        data = r.json()
        if data.get("errors"):
            return False, str(data["errors"][0].get("message", "unknown error"))
        return True, f"Redeploy triggered for {project_name} (service {service_id})"
    except Exception as e:
        return False, str(e)


def build_fix_and_rollback(project_name: str) -> tuple[str, str]:
    """Return (fix_code, rollback_script) strings for logging to gap_fixes."""
    service_id = SERVICE_MAP.get(project_name, "UNKNOWN")
    fix = (
        f"railway_redeploy(project='{project_name}', service_id='{service_id}')\n"
        f"# Triggers serviceInstanceRedeploy via Railway GraphQL API"
    )
    rollback = (
        f"# Rollback: no state change — redeploy is idempotent.\n"
        f"# If new deploy is worse, trigger another redeploy from the previous\n"
        f"# deployment in the Railway dashboard for service {service_id}."
    )
    return fix, rollback
