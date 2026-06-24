"""Remote allocation worker handlers."""

from cpkit import get_repo

from ...models import AllocationScaleCommand
from ...services.allocation import AllocationService


def run_allocation_scale(
    job_id: int,
    payload: AllocationScaleCommand,
    actor_id: str,
) -> None:
    """Run the remote playbook job that scales an allocation placement."""
    AllocationService(get_repo()).run_scale_job(job_id, payload, actor_id)
