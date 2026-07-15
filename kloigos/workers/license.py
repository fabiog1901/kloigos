"""License compliance queue handler."""

from typing import Any

from cpkit.repository import get_repo

from ..services.admin.license import LicenseService

CHECK_INTERVAL_SECONDS = 300


def run_license_compliance_check(
    _job_id: int,
    _command: Any,
    actor_id: str,
) -> None:
    """Run one license compliance check cycle and enqueue the next cycle."""
    repo = get_repo()
    try:
        LicenseService(repo).check_compliance(actor_id or "system")
    finally:
        repo.schedule_license_compliance_check(CHECK_INTERVAL_SECONDS)
