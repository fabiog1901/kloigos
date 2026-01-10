from kloigos.models import InitServerRequest, Playbook

from ..models import DeferredTask
from ..repos.base import BaseRepo
from ..util import MyRunner, cpu_range_to_list_str


class AdminService:
    def __init__(self, repo: BaseRepo):
        self.repo = repo

    def update_playbooks(self, playbook: Playbook, b64: str):
        return self.repo.update_playbook(playbook, b64)

    def get_playbook(self, playbook: Playbook):
        return self.repo.get_playbook(playbook)

    def init_server(self, isr: InitServerRequest) -> list[DeferredTask]:

        # add the server to the compute_units table with
        # status='init'
        self.repo.insert_init_server(isr)

        # async, run the cleanup task
        return [DeferredTask(fn=self.run_init_server, args=(isr,), kwargs={})]

    def decommission_server(
        self,
        hostname: str,
    ) -> list[DeferredTask]:

        self.repo.delete_server(hostname)

        # async, run the decomm task
        return [
            DeferredTask(fn=self.run_decommission_server, args=(hostname,), kwargs={})
        ]

    def run_init_server(self, isr: InitServerRequest) -> None:
        """
        Execute Ansible Playbook `init.yaml`
        The playbook setups the server with the requested
        compute_units.
        """

        cpu_ranges_list = [cpu_range_to_list_str(x) for x in isr.cpu_ranges]
        cpu_ranges = [x.replace(":", "-") for x in isr.cpu_ranges]

        job_ok = MyRunner(self.repo).launch_runner(
            Playbook.server_init,
            {
                "compute_id": isr.hostname,
                "cpu_ranges": cpu_ranges,
                "cpu_ranges_list": cpu_ranges_list,
            },
        )

        # add the created compute units if the job was successfull
        if job_ok:
            for x in isr.cpu_ranges:

                cpu_count = len(cpu_range_to_list_str(x).split(","))
                compute_id = f"{isr.hostname}_c{x.replace(':', '-')}"

                self.repo.insert_new_cu(compute_id, cpu_count, x, isr)

            # remove the row with the details of the server in init status
            self.repo.delete_cu(isr.hostname)

        else:
            self.repo.init_fail(isr.hostname)

    def run_decommission_server(self, hostname: str) -> None:
        """
        Execute Ansible Playbook `decommission.yaml`
        The playbook decomm the server with the requested
        hostname.
        """

        job_ok = MyRunner(self.repo).launch_runner(
            Playbook.server_decomm,
            {
                "decomm_hostname": hostname,
            },
        )

        # don't delete any metadata, instead mark the compute units as
        # status = 'DECOMMISSIONED'
        self.repo.mark_decommissioned(hostname, job_ok)
