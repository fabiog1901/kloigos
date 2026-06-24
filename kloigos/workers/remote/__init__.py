"""Remote job handlers that execute playbooks on Kloigos-managed servers."""

from .allocation import run_allocation_scale

__all__ = ["run_allocation_scale"]
