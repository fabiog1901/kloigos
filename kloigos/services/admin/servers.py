from ...models import (
    DeferredTask,
    Event,
    InitComputeUnit,
    LogMsg,
    Playbook,
    ServerDecommRequest,
    ServerInDB,
    ServerInitRequest,
    ServerStatus,
)
from ...util import MyRunner, request_id_ctx, to_cpu_set
from .base import AdminServiceBase


def _cu_user(ordinal: int) -> str:
    return f"c{ordinal:02d}"


def _ansible_host(public_ip: str | None, private_ip: str) -> str:
    return public_ip or private_ip


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
    def init_server(self, actor_id: str, sir: ServerInitRequest) -> list[DeferredTask]:
        self.repo.log_event(
            LogMsg(
                user_id=actor_id,
                action=Event.SERVER_INIT_REQUEST,
                details=sir.model_dump(),
                request_id=request_id_ctx.get(),
            )
        )

        self.repo.server_init_new(sir, ServerStatus.INITIALIZING)

        # async, run the init task
        return [
            DeferredTask(
                fn=self._run_init_server,
                args=(sir, actor_id),
            ),
        ]

    def list_servers(
        self,
        hostname: str | None = None,
    ) -> list[ServerInDB]:
        return self.repo.get_servers(hostname)

    def decommission_server(
        self,
        actor_id: str,
        sdr: ServerDecommRequest,
    ) -> list[DeferredTask]:
        self.repo.log_event(
            LogMsg(
                user_id=actor_id,
                action=Event.SERVER_DECOMM_REQUEST,
                details=sdr.model_dump(),
                request_id=request_id_ctx.get(),
            )
        )

        self.repo.server_update_status(sdr.hostname, ServerStatus.DECOMMISSIONING)
        self.repo.delete_compute_units(sdr.hostname)
        srv = self.repo.get_servers(sdr.hostname)[0]

        # async, run the decomm task
        return [
            DeferredTask(
                fn=self._run_decommission_server,
                args=(srv, actor_id),
            ),
        ]

    def delete_server(self, actor_id: str, hostname: str) -> None:
        self.repo.log_event(
            LogMsg(
                user_id=actor_id,
                action=Event.SERVER_DELETE_REQUEST,
                details={"hostname": hostname},
                request_id=request_id_ctx.get(),
            )
        )

        self.repo.delete_server(hostname)

    def _run_init_server(self, sir: ServerInitRequest, actor_id: str) -> None:
        compute_units = _init_compute_units(sir)

        job_ok = MyRunner(self.repo).launch_runner(
            Playbook.SERVER_INIT,
            {
                "hostname": sir.hostname,
                "server_private_ip": sir.private_ip,
                "server_public_ip": sir.public_ip,
                "ansible_host": _ansible_host(sir.public_ip, sir.private_ip),
                "user_id": sir.user_id,
                "compute_units": [cu.as_playbook_vars() for cu in compute_units],
            },
        )

        # add the created compute units if the job was successful
        if job_ok:
            for cu in compute_units:
                self.repo.insert_new_compute_unit(cu.as_compute_unit(sir.hostname))
            self.repo.server_update_status(sir.hostname, ServerStatus.READY)
        else:
            self.repo.server_update_status(sir.hostname, ServerStatus.INIT_FAIL)

        self.repo.log_event(
            LogMsg(
                user_id=actor_id,
                action=Event.SERVER_INIT_DONE if job_ok else Event.SERVER_INIT_FAILED,
                details=sir.model_dump(),
                request_id=request_id_ctx.get(),
            )
        )

    def _run_decommission_server(self, srv: ServerInDB, actor_id: str) -> None:
        """
        Execute Ansible Playbook `decommission.yaml`.
        The playbook decommissions the server with the requested hostname.
        """

        job_ok = MyRunner(self.repo).launch_runner(
            Playbook.SERVER_DECOMM,
            {
                "hostname": srv.hostname,
                "server_private_ip": srv.private_ip,
                "server_public_ip": srv.public_ip,
                "ansible_host": _ansible_host(srv.public_ip, srv.private_ip),
                "user_id": srv.user_id,
            },
        )

        # don't delete any metadata, instead mark the compute units as DECOMMISSIONED
        self.repo.server_update_status(
            srv.hostname,
            ServerStatus.DECOMMISSIONED if job_ok else ServerStatus.DECOMMISSION_FAIL,
        )

        self.repo.log_event(
            LogMsg(
                user_id=actor_id,
                action=(
                    Event.SERVER_DECOMM_DONE if job_ok else Event.SERVER_DECOMM_FAILED
                ),
                details=srv.model_dump(),
                request_id=request_id_ctx.get(),
            )
        )
