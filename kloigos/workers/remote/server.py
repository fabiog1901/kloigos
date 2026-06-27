"""Remote server worker handlers."""

from cpkit import get_repo
from cpkit.audit import log_event
from cpkit.playbooks import run_playbook

from ...models import (
    Event,
    InitComputeUnit,
    Playbook,
    ServerDecommRequest,
    ServerInitRequest,
    ServerNotFoundError,
    ServerStateError,
    ServerStatus,
)
from ...util import parse_cpu_range, to_cpu_set


def _ansible_host(public_ip: str | None, private_ip: str) -> str:
    return public_ip or private_ip


def _init_compute_units(sir: ServerInitRequest) -> list[InitComputeUnit]:
    units: list[InitComputeUnit] = []
    compute_units = sorted(
        sir.compute_units,
        key=lambda item: (parse_cpu_range(item.cpu_range)[0], item.ordinal),
    )
    for cu in compute_units:
        cpu_set = to_cpu_set(cu.cpu_range)
        units.append(
            InitComputeUnit(
                ordinal=cu.ordinal,
                cpu_range=cu.cpu_range,
                cpu_set=cpu_set,
                cpu_count=len(cpu_set.split(",")),
                private_ip=cu.private_ip,
                public_ip=cu.public_ip,
            )
        )
    return units


def run_server_init(
    job_id: int,
    payload: ServerInitRequest,
    actor_id: str,
) -> None:
    """Run the remote playbook job that initializes a server."""
    repo = get_repo()
    compute_units = _init_compute_units(payload)

    result = run_playbook(
        repo=repo,
        job_id=job_id,
        playbook_name=Playbook.SERVER_INIT.value,
        extra_vars={
            "hostname": payload.hostname,
            "server_private_ip": payload.private_ip,
            "server_public_ip": payload.public_ip,
            "ansible_host": _ansible_host(payload.public_ip, payload.private_ip),
            "user_id": payload.user_id,
            "compute_units": [cu.as_playbook_vars() for cu in compute_units],
        },
    )
    job_ok = result.status == "successful"

    if job_ok:
        for cu in compute_units:
            repo.insert_new_compute_unit(cu.as_compute_unit(payload.hostname))
        repo.server_update_status(payload.hostname, ServerStatus.READY)
    else:
        repo.server_update_status(payload.hostname, ServerStatus.INIT_FAIL)

    log_event(
        repo,
        actor_id,
        Event.SERVER_INIT_DONE if job_ok else Event.SERVER_INIT_FAILED,
        payload.model_dump(),
    )
    if not job_ok:
        raise ServerStateError(f"Server initialization job '{job_id}' failed.")


def run_server_decommission(
    job_id: int,
    payload: ServerDecommRequest,
    actor_id: str,
) -> None:
    """Run the remote playbook job that decommissions a server."""
    repo = get_repo()
    matches = repo.get_servers(payload.hostname)
    if not matches:
        raise ServerNotFoundError(f"Server {payload.hostname} was not found.")
    srv = matches[0]

    result = run_playbook(
        repo=repo,
        job_id=job_id,
        playbook_name=Playbook.SERVER_DECOMM.value,
        extra_vars={
            "hostname": srv.hostname,
            "server_private_ip": srv.private_ip,
            "server_public_ip": srv.public_ip,
            "ansible_host": _ansible_host(srv.public_ip, srv.private_ip),
            "user_id": srv.user_id,
        },
    )
    job_ok = result.status == "successful"

    repo.server_update_status(
        srv.hostname,
        ServerStatus.DECOMMISSIONED if job_ok else ServerStatus.DECOMMISSION_FAIL,
    )

    log_event(
        repo,
        actor_id,
        Event.SERVER_DECOMM_DONE if job_ok else Event.SERVER_DECOMM_FAILED,
        srv.model_dump(),
    )
    if not job_ok:
        raise ServerStateError(f"Server decommission job '{job_id}' failed.")
