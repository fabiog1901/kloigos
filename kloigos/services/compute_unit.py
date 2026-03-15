from kloigos.models import (
    ComputeUnitOverview,
    ComputeUnitRequest,
    ComputeUnitStatus,
    DeferredTask,
    Event,
    LogMsg,
    NoFreeComputeUnitError,
    Playbook,
)

from ..repos.base import BaseRepo
from ..util import MyRunner, request_id_ctx


class ComputeUnitService:
    def __init__(self, repo: BaseRepo):
        self.repo = repo

    def allocate(
        self,
        actor_id: str,
        req: ComputeUnitRequest,
    ) -> tuple[str, list[DeferredTask]]:
        """
        Allocate a compute unit.

        Returns hostname, cpu_range and list of background tasks

        Raises:
            NoFreeComputeUnitError: if no matching compute unit is available
        """

        self.repo.log_event(
            LogMsg(
                user_id=actor_id,
                action=Event.CU_ALLOCATION_REQUEST,
                details=req.model_dump(),
                request_id=request_id_ctx.get(),
            )
        )

        # find and return a free instance that matches the allocate request
        cu: ComputeUnitOverview = self.repo.lock_compute_unit(
            compute_id=req.compute_id,
            region=req.region,
            zone=req.zone,
            cpu_count=req.cpu_count,
            free_status=ComputeUnitStatus.FREE,
            allocated_status=ComputeUnitStatus.ALLOCATING,
        )

        # if the list is empty, raise an HTTPException
        if not cu:
            raise NoFreeComputeUnitError()

        # once locked, add tags and other metadata
        self.repo.update_compute_unit(
            cu.compute_id,
            tags=req.tags,
        )

        # async, run the cleanup task
        tasks = [
            DeferredTask(
                fn=self._run_allocate,
                args=(
                    cu,
                    req.ssh_public_key,
                    actor_id,
                ),
                kwargs={},
            ),
        ]

        return cu.compute_id, tasks

    def deallocate(
        self,
        actor_id: str,
        compute_id: str,
    ) -> list[DeferredTask]:

        self.repo.log_event(
            LogMsg(
                user_id=actor_id,
                action=Event.CU_DEALLOCATION_REQUEST,
                details={"compute_id": compute_id},
                request_id=request_id_ctx.get(),
            )
        )

        # get details for the compute_unit

        cu = self.repo.get_compute_units(compute_id=compute_id)[0]

        self.repo.update_compute_unit(
            cu.compute_id,
            ComputeUnitStatus.DEALLOCATING,
            {},
        )

        # async, run the cleanup task
        tasks = [
            DeferredTask(
                fn=self._run_deallocate,
                args=(cu, actor_id),
                kwargs={},
            )
        ]

        return tasks

    def list_compute_units(
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

    def _run_allocate(
        self,
        cu: ComputeUnitOverview,
        ssh_public_key: str,
        actor_id: str,
    ) -> None:

        job_ok = MyRunner(self.repo).launch_runner(
            Playbook.CU_ALLOCATE,
            {
                "compute_id": cu.compute_id,
                "hostname": cu.hostname,
                "ip": cu.ip,
                "cpu_range": cu.cpu_range,
                "cpu_count": cu.cpu_count,
                "port_range": cu.port_range,
                "ssh_public_key": ssh_public_key,
            },
        )

        self.repo.update_compute_unit(
            cu.compute_id,
            (
                ComputeUnitStatus.ALLOCATED
                if job_ok
                else ComputeUnitStatus.ALLOCATION_FAIL
            ),
        )

        self.repo.log_event(
            LogMsg(
                user_id=actor_id,
                action=(
                    Event.CU_ALLOCATION_DONE if job_ok else Event.CU_ALLOCATION_FAILED
                ),
                details=cu.model_dump(),
                request_id=request_id_ctx.get(),
            ),
        )

    def _run_deallocate(self, cu: ComputeUnitOverview, actor_id: str) -> None:

        job_ok = MyRunner(self.repo).launch_runner(
            Playbook.CU_DEALLOCATE,
            {
                "compute_id": cu.compute_id,
                "hostname": cu.hostname,
                "ip": cu.ip,
                "cu_user": cu.cu_user,
            },
        )

        self.repo.update_compute_unit(
            cu.compute_id,
            ComputeUnitStatus.FREE if job_ok else ComputeUnitStatus.DEALLOCATION_FAIL,
        )

        self.repo.log_event(
            LogMsg(
                user_id=actor_id,
                action=(
                    Event.CU_DEALLOCATION_DONE
                    if job_ok
                    else Event.CU_DEALLOCATION_FAILED
                ),
                details=cu.model_dump(),
                request_id=request_id_ctx.get(),
            ),
        )
