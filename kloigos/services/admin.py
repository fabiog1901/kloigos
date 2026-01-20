from kloigos.models import Playbook, ServerInitRequest

from ..models import (
    ComputeUnitInDB,
    ComputeUnitStatus,
    DeferredTask,
    ServerInDB,
    ServerStatus,
)
from ..repos.base import BaseRepo
from ..util import MyRunner, audit_logger, ports_for_cpu_range, to_cpu_set


class AdminService:
    def __init__(self, repo: BaseRepo):
        self.repo = repo

    @audit_logger()
    def update_playbooks(self, playbook: Playbook, b64: str):
        return self.repo.playbook_update_content(playbook, b64)

    def get_playbook(self, playbook: Playbook):
        return self.repo.playbook_get_content(playbook)

    @audit_logger()
    def init_server(self, sir: ServerInitRequest) -> list[DeferredTask]:

        self.repo.server_init_new(sir, ServerStatus.INITIALIZING)

        # async, run the init task
        return [DeferredTask(fn=self._run_init_server, args=(sir,))]

    def list_servers(
        self,
        hostname: str | None = None,
    ) -> list[ServerInDB]:

        return self.repo.get_servers(hostname)

    @audit_logger()
    def decommission_server(
        self,
        hostname: str,
    ) -> list[DeferredTask]:

        self.repo.server_update_status(hostname, ServerStatus.DECOMMISSIONING)

        self.repo.delete_compute_units(hostname)

        srv = self.repo.get_servers(hostname)[0]

        # async, run the decomm task
        return [DeferredTask(fn=self._run_decommission_server, args=(srv,))]

    @audit_logger()
    def delete_server(self, hostname: str) -> None:
        self.repo.delete_server(hostname)

    def _run_init_server(self, sir: ServerInitRequest) -> None:

        cpu_sets = [to_cpu_set(x) for x in sir.cpu_ranges]
        cpu_ranges = [x.replace(":", "-") for x in sir.cpu_ranges]
        port_ranges = [ports_for_cpu_range(i) for i in cpu_ranges]

        job_ok = MyRunner(self.repo).launch_runner(
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

        # add the created compute units if the job was successfull
        if job_ok:
            for x in sir.cpu_ranges:
                self.repo.insert_new_compute_unit(
                    ComputeUnitInDB(
                        compute_id="",  # not used
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

    def _run_decommission_server(self, srv: ServerInDB) -> None:
        """
        Execute Ansible Playbook `decommission.yaml`
        The playbook decomm the server with the requested
        hostname.
        """

        job_ok = MyRunner(self.repo).launch_runner(
            Playbook.SERVER_DECOMM,
            {
                "hostname": srv.hostname,
                "ip": srv.ip,
                "user_id": srv.user_id,
            },
        )

        # don't delete any metadata, instead mark the compute units as
        # status = 'DECOMMISSIONED'

        self.repo.server_update_status(
            srv.hostname,
            ServerStatus.DECOMMISSIONED if job_ok else ServerStatus.DECOMMISSION_FAIL,
        )
