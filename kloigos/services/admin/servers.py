from ...models import (
    ComputeUnitInDB,
    ComputeUnitStatus,
    DeferredTask,
    Event,
    LogMsg,
    Playbook,
    ServerDecommRequest,
    ServerInDB,
    ServerInitRequest,
    ServerStatus,
)
from ...util import MyRunner, ports_for_cpu_range, request_id_ctx, to_cpu_set
from .base import AdminServiceBase


class ServersAdminService(AdminServiceBase):
    def init_server(self, sir: ServerInitRequest) -> list[DeferredTask]:
        self.repo.log_event(
            LogMsg(
                user_id="fabio",
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
                args=(sir,),
            ),
        ]

    def list_servers(
        self,
        hostname: str | None = None,
    ) -> list[ServerInDB]:
        return self.repo.get_servers(hostname)

    def decommission_server(
        self,
        sdr: ServerDecommRequest,
    ) -> list[DeferredTask]:
        self.repo.log_event(
            LogMsg(
                user_id="fabio",
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
                args=(srv, sdr.ssh_key),
            ),
        ]

    def delete_server(self, hostname: str) -> None:
        self.repo.log_event(
            LogMsg(
                user_id="fabio",
                action=Event.SERVER_DELETE_REQUEST,
                details={"hostname": hostname},
                request_id=request_id_ctx.get(),
            )
        )

        self.repo.delete_server(hostname)

    def _run_init_server(self, sir: ServerInitRequest) -> None:
        cpu_sets = [to_cpu_set(x) for x in sir.cpu_ranges]
        cpu_ranges = [x.replace(":", "-") for x in sir.cpu_ranges]
        port_ranges = [ports_for_cpu_range(i) for i in cpu_ranges]

        job_ok = MyRunner(self.repo, sir.ssh_key).launch_runner(
            Playbook.SERVER_INIT,
            {
                "hostname": sir.hostname,
                "ip": sir.ip,
                "user_id": sir.user_id,
                "cpu_ranges": cpu_ranges,
                "cpu_sets": cpu_sets,
                "port_ranges": port_ranges,
            },
        )

        # add the created compute units if the job was successful
        if job_ok:
            for x in sir.cpu_ranges:
                self.repo.insert_new_compute_unit(
                    ComputeUnitInDB(
                        compute_id="",  # not used, computed
                        hostname=sir.hostname,
                        cpu_range=x,
                        cpu_count=len(to_cpu_set(x).split(",")),
                        cpu_set=to_cpu_set(x),
                        port_range=ports_for_cpu_range(x),
                        cu_user=f"c{x.replace(':', '-')}",
                        status=ComputeUnitStatus.FREE,
                    )
                )
            self.repo.server_update_status(sir.hostname, ServerStatus.READY)
        else:
            self.repo.server_update_status(sir.hostname, ServerStatus.INIT_FAIL)

        self.repo.log_event(
            LogMsg(
                user_id="fabio",
                action=Event.SERVER_INIT_DONE if job_ok else Event.SERVER_INIT_FAILED,
                details=sir.model_dump(),
                request_id=request_id_ctx.get(),
            )
        )

    def _run_decommission_server(self, srv: ServerInDB, ssh_key: str) -> None:
        """
        Execute Ansible Playbook `decommission.yaml`.
        The playbook decommissions the server with the requested hostname.
        """

        job_ok = MyRunner(self.repo, ssh_key).launch_runner(
            Playbook.SERVER_DECOMM,
            {
                "hostname": srv.hostname,
                "ip": srv.ip,
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
                user_id="fabio",
                action=(
                    Event.SERVER_DECOMM_DONE if job_ok else Event.SERVER_DECOMM_FAILED
                ),
                details=srv.model_dump(),
                request_id=request_id_ctx.get(),
            )
        )
