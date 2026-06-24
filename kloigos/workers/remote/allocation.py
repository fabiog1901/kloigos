"""Remote allocation worker handlers."""

from cpkit import get_repo

from ...models import (
    AllocationCreateCommand,
    AllocationDeallocateCommand,
    AllocationScaleCommand,
)
from ...services.allocation import AllocationService
from ...services.compute_unit import ComputeUnitService


def run_compute_unit_allocate(
    job_id: int,
    payload: AllocationCreateCommand,
    actor_id: str,
) -> None:
    """Run the remote playbook job that prepares a compute unit allocation."""
    ComputeUnitService(get_repo()).run_allocate_job(job_id, payload, actor_id)


def run_compute_unit_deallocate(
    job_id: int,
    payload: AllocationDeallocateCommand,
    actor_id: str,
) -> None:
    """Run the remote playbook job that deallocates a compute unit."""
    ComputeUnitService(get_repo()).run_deallocate_job(job_id, payload, actor_id)


def run_allocation_scale(
    job_id: int,
    payload: AllocationScaleCommand,
    actor_id: str,
) -> None:
    """Run the remote playbook job that scales an allocation placement."""
    AllocationService(get_repo()).run_scale_job(job_id, payload, actor_id)
