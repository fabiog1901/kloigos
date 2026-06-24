from kloigos.models import ComputeUnitOverview

from ..repos import Repo


class ComputeUnitService:
    """Serve compute-unit inventory queries."""

    def __init__(self, repo: Repo):
        self.repo = repo

    def list_compute_units(
        self,
        compute_id: str | None = None,
        hostname: str | None = None,
        region: str | None = None,
        zone: str | None = None,
        cpu_count: int | None = None,
        deployment_id: str | None = None,
        status: str | None = None,
    ) -> list[ComputeUnitOverview]:
        """Return compute units filtered by the provided query parameters."""
        return self.repo.get_compute_units(
            compute_id,
            hostname,
            region,
            zone,
            cpu_count,
            deployment_id,
            status,
        )
