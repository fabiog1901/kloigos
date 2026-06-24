from cpkit.audit import log_event
from cpkit.jobs.types import JobID
from cpkit.playbooks import run_playbook

from ...models import (
    Event,
    InitComputeUnit,
    Playbook,
    QueueCommand,
    ServerDecommRequest,
    ServerInDB,
    ServerInitRequest,
    ServerNotFoundError,
    ServerStateError,
    ServerStatus,
)
from ...util import to_cpu_set
from .base import AdminServiceBase


def _cu_user(ordinal: int) -> str:
    return f"c{ordinal:02d}"


def _ansible_host(public_ip: str | None, private_ip: str) -> str:
    return public_ip or private_ip


DELETABLE_SERVER_STATUSES = {
    ServerStatus.DECOMMISSIONED.value,
    ServerStatus.INIT_FAIL.value,
    ServerStatus.DECOMMISSION_FAIL.value,
}


def _init_compute_units(sir: ServerInitRequest) -> list[InitComputeUnit]:
    units: list[InitComputeUnit] = []
    for cu in sorted(sir.compute_units, key=lambda item: item.ordinal):
        cpu_set = to_cpu_set(cu.cpu_range)
        units.append(
            InitComputeUnit(
                ordinal=cu.ordinal,
                cu_user=_cu_user(cu.ordinal),
                cpu_range=cu.cpu_range,
                cpu_set=cpu_set,
                cpu_count=len(cpu_set.split(",")),
                private_ip=cu.private_ip,
                public_ip=cu.public_ip,
            )
        )
    return units


class ServersAdminService(AdminServiceBase):
    def init_server(self, actor_id: str, sir: ServerInitRequest) -> JobID:
        log_event(
            self.repo,
            actor_id,
            Event.SERVER_INIT_REQUEST,
            sir.model_dump(),
        )

        self.repo.server_init_new(sir, ServerStatus.INITIALIZING)
        return self.repo.enqueue_command(QueueCommand.SERVER_INIT, sir, actor_id)

    def list_servers(
        self,
        hostname: str | None = None,
    ) -> list[ServerInDB]:
        return self.repo.get_servers(hostname)

    def decommission_server(
        self,
        actor_id: str,
        sdr: ServerDecommRequest,
    ) -> JobID:
        log_event(
            self.repo,
            actor_id,
            Event.SERVER_DECOMM_REQUEST,
            sdr.model_dump(),
        )

        self.repo.server_update_status(sdr.hostname, ServerStatus.DECOMMISSIONING)
        self.repo.delete_compute_units(sdr.hostname)
        return self.repo.enqueue_command(QueueCommand.SERVER_DECOMM, sdr, actor_id)

    def delete_server(self, actor_id: str, hostname: str) -> None:
        matches = self.repo.get_servers(hostname)
        if not matches:
            raise ServerNotFoundError(f"Server {hostname} was not found.")

        server = matches[0]
        if server.status not in DELETABLE_SERVER_STATUSES:
            allowed = ", ".join(sorted(DELETABLE_SERVER_STATUSES))
            raise ServerStateError(
                f"Server {hostname} is {server.status}; "
                f"delete is only allowed for {allowed}."
            )

        log_event(
            self.repo,
            actor_id,
            Event.SERVER_DELETE_REQUEST,
            {"hostname": hostname},
        )

        self.repo.delete_server(hostname)

    def run_init_server_job(
        self,
        job_id: int,
        sir: ServerInitRequest,
        actor_id: str,
    ) -> None:
        """Run the queued server initialization playbook and persist compute units."""
        compute_units = _init_compute_units(sir)

        result = run_playbook(
            repo=self.repo,
            job_id=job_id,
            playbook_name=Playbook.SERVER_INIT.value,
            extra_vars={
                "hostname": sir.hostname,
                "server_private_ip": sir.private_ip,
                "server_public_ip": sir.public_ip,
                "ansible_host": _ansible_host(sir.public_ip, sir.private_ip),
                "user_id": sir.user_id,
                "compute_units": [cu.as_playbook_vars() for cu in compute_units],
            },
        )
        job_ok = result.status == "successful"

        # add the created compute units if the job was successful
        if job_ok:
            for cu in compute_units:
                self.repo.insert_new_compute_unit(cu.as_compute_unit(sir.hostname))
            self.repo.server_update_status(sir.hostname, ServerStatus.READY)
        else:
            self.repo.server_update_status(sir.hostname, ServerStatus.INIT_FAIL)

        log_event(
            self.repo,
            actor_id,
            Event.SERVER_INIT_DONE if job_ok else Event.SERVER_INIT_FAILED,
            sir.model_dump(),
        )
        if not job_ok:
            raise ServerStateError(f"Server initialization job '{job_id}' failed.")

    def run_decommission_server_job(
        self,
        job_id: int,
        sdr: ServerDecommRequest,
        actor_id: str,
    ) -> None:
        """
        Execute the queued Ansible decommission playbook.

        The playbook decommissions the server with the requested hostname.
        """
        matches = self.repo.get_servers(sdr.hostname)
        if not matches:
            raise ServerNotFoundError(f"Server {sdr.hostname} was not found.")
        srv = matches[0]

        result = run_playbook(
            repo=self.repo,
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

        # don't delete any metadata, instead mark the compute units as DECOMMISSIONED
        self.repo.server_update_status(
            srv.hostname,
            ServerStatus.DECOMMISSIONED if job_ok else ServerStatus.DECOMMISSION_FAIL,
        )

        log_event(
            self.repo,
            actor_id,
            Event.SERVER_DECOMM_DONE if job_ok else Event.SERVER_DECOMM_FAILED,
            srv.model_dump(),
        )
        if not job_ok:
            raise ServerStateError(f"Server decommission job '{job_id}' failed.")
