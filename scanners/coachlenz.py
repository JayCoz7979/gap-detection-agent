"""CoachLenz gap scanner — sports coaching admin platform."""
from .base import Gap, health_check

PROJECT = "CoachLenz"
BACKEND_URL = "https://coachlenz-backend-production.up.railway.app"
FRONTEND_URL = "https://coachlenz-frontend-production.up.railway.app"


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

    # Integration gaps
    gaps.append(Gap(PROJECT, "integration",
                    "Stripe payment integration not implemented — no billing or subscription flow",
                    "high", "CoachLenz has no payment model yet; coaches cannot monetize their teams"))

    gaps.append(Gap(PROJECT, "feature",
                    "Athlete onboarding flow missing — no invite/registration path for players",
                    "high", "Coaches can manage rosters but athletes have no self-service entry point"))

    gaps.append(Gap(PROJECT, "feature",
                    "Parent/guardian portal absent — no read-only access for non-coach stakeholders",
                    "medium", "Needed for youth sports orgs; parents want stats and schedule visibility"))

    gaps.append(Gap(PROJECT, "feature",
                    "Export/print functionality missing — no PDF for schedules or practice plans",
                    "medium", "Coaches need printable practice plans for offline use"))

    gaps.append(Gap(PROJECT, "security",
                    "JWT refresh rotation not implemented — refresh tokens are single-use but not rotated on use",
                    "medium", "Refresh token reuse window creates session hijack risk if token is intercepted"))

    gaps.append(Gap(PROJECT, "feature",
                    "Push notifications absent — no alerts for schedule changes or practice cancellations",
                    "low", "Would require FCM or similar; coaches manually notify teams today"))

    gaps.append(Gap(PROJECT, "feature",
                    "Video/media upload for practice plans not supported",
                    "low", "Coaches want to attach drill videos to practice plan entries"))

    gaps.append(Gap(PROJECT, "schema",
                    "No audit log table — roster/stat changes are not tracked for compliance",
                    "low", "Needed for league-regulated sports orgs; currently zero change history"))

    return gaps
