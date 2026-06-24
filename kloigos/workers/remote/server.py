"""Remote server worker handlers."""

from cpkit import get_repo

from ...models import ServerDecommRequest, ServerInitRequest
from ...services.admin import AdminService


def run_server_init(
    job_id: int,
    payload: ServerInitRequest,
    actor_id: str,
) -> None:
    """Run the remote playbook job that initializes a server."""
    AdminService(get_repo()).run_init_server_job(job_id, payload, actor_id)


def run_server_decommission(
    job_id: int,
    payload: ServerDecommRequest,
    actor_id: str,
) -> None:
    """Run the remote playbook job that decommissions a server."""
    AdminService(get_repo()).run_decommission_server_job(job_id, payload, actor_id)
