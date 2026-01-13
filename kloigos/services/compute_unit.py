from kloigos.models import (
    AllocatePlaybookError,
    ComputeUnitInDB,
    ComputeUnitRequest,
    ComputeUnitResponse,
    DeferredTask,
    NoFreeComputeUnitError,
    Playbook,
    Status,
)

from ..repos.base import BaseRepo
from ..util import MyRunner, audit_logger, cpu_range_to_list_str, ports_for_cpu_range


class ComputeUnitService:
    def __init__(self, repo: BaseRepo):
        self.repo = repo

    @audit_logger()
    def allocate(self, req: ComputeUnitRequest) -> ComputeUnitResponse:
        """
        Allocate a compute unit.

        Raises:
            NoFreeComputeUnitError: if no matching compute unit is available
            AllocatePlaybookError: if the allocation playbook fails
        """
        # find and return a free instance that matches the allocate request
        cu_list: list[ComputeUnitInDB] = self.repo.get_compute_units(
            compute_id=req.compute_id,
            region=req.region,
            zone=req.zone,
            cpu_count=req.cpu_count,
            status=Status.FREE,
            limit=1,
        )

        # if the list is empty, raise an HTTPException
        if cu_list:
            cu = cu_list[0]
        else:
            raise NoFreeComputeUnitError()

        cpu_list = cpu_range_to_list_str(cu.cpu_range)

        pr = ports_for_cpu_range(cu.cpu_range)
        ports_range = f"{pr.start}-{pr.end}"

        # mark the compute_unit to allocating
        self.repo.cu_mark_allocated(req, cu)

        # blocking task - this is not async
        job_ok = self.run_allocate(cu.compute_id, req.ssh_public_key)

        if job_ok:
            self.repo.update_cu_status_alloc(cu)

            # return the details of the compute_unit
            return ComputeUnitResponse(
                cpu_list=cpu_list,
                ports_range=ports_range,
                user=f"c{ports_range}",
                tags=req.tags,
                **cu.model_dump(exclude="tags"),  # type: ignore
            )
        else:
            self.repo.set_cu_status_alloc_fail(cu)
            raise AllocatePlaybookError()

    @audit_logger()
    def deallocate(
        self,
        compute_id: str,
    ) -> list[DeferredTask]:

        # mark the compute_id as terminating
        self.repo.cu_mark_deallocated(compute_id)

        # async, run the cleanup task
        tasks = [DeferredTask(fn=self.run_deallocate, args=(compute_id,), kwargs={})]

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
    ) -> list[ComputeUnitResponse]:

        cu_list: list[ComputeUnitInDB] = self.repo.get_compute_units(
            compute_id,
            hostname,
            region,
            zone,
            cpu_count,
            deployment_id,
            status,
        )

        inventory: list[ComputeUnitResponse] = []

        for x in cu_list:
            cpu_list = cpu_range_to_list_str(x.cpu_range)

            pr = ports_for_cpu_range(x.cpu_range)
            ports_range = f"{pr.start}-{pr.end}"

            inventory.append(
                ComputeUnitResponse(
                    cpu_list=cpu_list,
                    ports_range=ports_range,
                    user=f"c{x.cpu_range}",
                    **x.model_dump(),
                )
            )

        return inventory

    def run_allocate(self, compute_id: str, ssh_public_key: str) -> bool:

        cu = self.list_server(compute_id=compute_id)[0]

        return MyRunner(self.repo).launch_runner(
            Playbook.cu_allocate,
            {
                "compute_id": compute_id,
                "hostname": cu.hostname,
                "ip": cu.ip,
                "cpu_range": cu.cpu_range,
                "cpu_count": cu.cpu_count,
                "port_ranges": cu.ports_range,
                "ssh_public_key": ssh_public_key,
            },
        )

    def run_deallocate(self, compute_id: str) -> None:

        job_ok = MyRunner(self.repo).launch_runner(
            Playbook.cu_deallocate,
            {
                "compute_id": compute_id,
            },
        )

        self.repo.update_cu_status_dealloc(compute_id, job_ok)
