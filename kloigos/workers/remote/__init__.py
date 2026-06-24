"""Remote job handlers that execute playbooks on Kloigos-managed servers."""

from .allocation import run_allocation_scale, run_compute_unit_allocate

__all__ = ["run_allocation_scale", "run_compute_unit_allocate"]
