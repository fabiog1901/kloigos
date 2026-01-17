from kloigos.models import (
    ComputeUnitInDB,
    ComputeUnitOverview,
    ComputeUnitRequest,
    ComputeUnitStatus,
    DeferredTask,
    NoFreeComputeUnitError,
    Playbook,
)

from ..repos.base import BaseRepo
from ..util import MyRunner, audit_logger


class ComputeUnitService:
    def __init__(self, repo: BaseRepo):
        self.repo = repo

    @audit_logger()
    def allocate(self, req: ComputeUnitRequest) -> tuple[str, str, list[DeferredTask]]:
        """
        Allocate a compute unit.

        Returns hostname, cpu_range and list of background tasks

        Raises:
            NoFreeComputeUnitError: if no matching compute unit is available
        """
        # find and return a free instance that matches the allocate request
        cu_list: list[ComputeUnitInDB] = self.repo.get_compute_units(
            compute_id=req.compute_id,
            region=req.region,
            zone=req.zone,
            cpu_count=req.cpu_count,
            status=ComputeUnitStatus.FREE,
            limit=1,
        )

        # if the list is empty, raise an HTTPException
        if cu_list:
            cu = cu_list[0]
        else:
            raise NoFreeComputeUnitError()

        # mark the compute_unit to allocating
        self.repo.update_compute_unit(
            cu.hostname, cu.cpu_range, ComputeUnitStatus.ALLOCATING
        )

        # async, run the cleanup task
        tasks = [
            DeferredTask(
                fn=self._run_allocate,
                args=(
                    cu,
                    req.ssh_public_key,
                ),
                kwargs={},
            )
        ]

        return cu.hostname, cu.cpu_range, tasks

    @audit_logger()
    def deallocate(
        self,
        compute_id: str,
    ) -> list[DeferredTask]:

        # get details for the compute_unit

        cu = self.repo.get_compute_units(compute_id=compute_id)[0]

        self.repo.update_compute_unit(
            cu.hostname, cu.cpu_range, ComputeUnitStatus.DEALLOCATING
        )

        # async, run the cleanup task
        tasks = [DeferredTask(fn=self._run_deallocate, args=(cu,), kwargs={})]

        return tasks

    def list_server(
        self,
        compute_id: str | None = None,
        hostname: str | None = None,
        region: str | None = None,
        zone: str | None = None,
        cpu_count: int | None = None,
        deployment_id: str | None = None,
        status: str | None = None,
    ) -> list[ComputeUnitOverview]:

        return self.repo.get_compute_units(
            compute_id,
            hostname,
            region,
            zone,
            cpu_count,
            deployment_id,
            status,
        )

    def _run_allocate(self, cu: ComputeUnitOverview, ssh_public_key: str) -> bool:

        job_ok = MyRunner(self.repo).launch_runner(
            Playbook.CU_ALLOCATE,
            {
                "compute_id": f"{cu.hostname}_{cu.cpu_range}",
                "hostname": cu.hostname,
                "ip": cu.ip,
                "cpu_range": cu.cpu_range,
                "cpu_count": cu.cpu_count,
                "port_range": cu.port_range,
                "ssh_public_key": ssh_public_key,
            },
        )

        self.repo.update_compute_unit(
            cu.hostname,
            cu.cpu_range,
            (
                ComputeUnitStatus.ALLOCATED
                if job_ok
                else ComputeUnitStatus.ALLOCATION_FAIL
            ),
        )

    def _run_deallocate(self, cu: ComputeUnitOverview) -> None:

        job_ok = MyRunner(self.repo).launch_runner(
            Playbook.CU_DEALLOCATE,
            {
                "compute_id": f"{cu.hostname}_{cu.cpu_range}",
                "hostname": cu.hostname,
                "ip": cu.ip,
                "cu_user": cu.cu_user,
            },
        )

        self.repo.update_compute_unit(
            cu.hostname,
            cu.cpu_range,
            ComputeUnitStatus.FREE if job_ok else ComputeUnitStatus.DEALLOCATION_FAIL,
        )
