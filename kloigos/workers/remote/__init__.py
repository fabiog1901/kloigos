"""Remote job handlers that execute playbooks on Kloigos-managed servers."""

from .allocation import (
    run_allocation_scale,
    run_compute_unit_allocate,
    run_compute_unit_deallocate,
)
from .server import run_server_decommission, run_server_init

__all__ = [
    "run_allocation_scale",
    "run_compute_unit_allocate",
    "run_compute_unit_deallocate",
    "run_server_decommission",
    "run_server_init",
]
