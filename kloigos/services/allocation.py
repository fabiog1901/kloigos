import logging

from cpkit.audit import log_event
from cpkit.jobs.types import JobID

from kloigos.models import (
    AllocationCreateCommand,
    AllocationCreateResponse,
    AllocationDeallocateCommand,
    AllocationInDB,
    AllocationScaleCommand,
    AllocationScaleRequest,
    AllocationStatus,
    ComputeUnitNotFoundError,
    ComputeUnitOperationError,
    ComputeUnitOverview,
    ComputeUnitRequest,
    ComputeUnitStateError,
    ComputeUnitStatus,
    Event,
    IpAddressStatus,
    IpPoolAddressInDB,
    NoFreeComputeUnitError,
    NoFreeIpAddressError,
    QueueCommand,
)

from ..repos import Repo


def _request_allocation_identity(
    req: ComputeUnitRequest,
    cu: ComputeUnitOverview,
) -> tuple[str, str]:
    tags = req.tags if isinstance(req.tags, dict) else {}
    tagged_name = (
        tags.get("allocation_id") or tags.get("deployment_id") or tags.get("name")
    )
    allocation_id = str(req.allocation_id or tagged_name or cu.compute_id).strip()
    name = str(req.name or tagged_name or allocation_id).strip()
    return allocation_id, name


class AllocationService:
    """Coordinate durable allocation operations and cpkit job scheduling."""

    def __init__(self, repo: Repo):
        self.repo = repo

    def list_allocations(
        self,
        *,
        allocation_id: str | None = None,
        compute_id: str | None = None,
        ip_address: str | None = None,
        status: str | None = None,
    ) -> list[AllocationInDB]:
        """Return allocations filtered by durable identity, placement, IP, or status."""
        return self.repo.get_allocations(
            allocation_id=allocation_id,
            compute_id=compute_id,
            ip_address=ip_address,
            status=status,
        )

    def get_allocation(self, allocation_id: str) -> AllocationInDB:
        """Return one allocation by durable allocation id."""
        return self._get_allocation(allocation_id)

    def allocate(
        self,
        actor_id: str,
        req: ComputeUnitRequest,
    ) -> AllocationCreateResponse:
        """Reserve capacity, create allocation metadata, and queue preparation."""
        log_event(
            self.repo,
            actor_id,
            Event.CU_ALLOCATION_REQUEST,
            req.model_dump(),
        )

        cu: ComputeUnitOverview = self.repo.lock_compute_unit(
            compute_id=req.compute_id,
            region=req.region,
            zone=req.zone,
            cpu_count=req.cpu_count,
            free_status=ComputeUnitStatus.FREE,
            allocated_status=ComputeUnitStatus.ALLOCATING,
        )
        if not cu:
            raise NoFreeComputeUnitError()

        allocation: AllocationInDB | None = None
        ip_address: IpPoolAddressInDB | None = None
        try:
            ip_address = self.repo.lock_ip_pool_address(
                free_status=IpAddressStatus.FREE,
                reserved_status=IpAddressStatus.RESERVED,
                ip_address=req.ip_address,
            )
            if not ip_address:
                self.repo.update_compute_unit(
                    cu.compute_id,
                    status=ComputeUnitStatus.FREE,
                    tags={},
                )
                raise NoFreeIpAddressError()

            allocation_id, allocation_name = _request_allocation_identity(req, cu)
            allocation = AllocationInDB(
                allocation_id=allocation_id,
                name=allocation_name,
                ip_address=ip_address.ip_address,
                compute_id=cu.compute_id,
                current_host=cu.hostname,
                status=AllocationStatus.ALLOCATING,
                tags=req.tags,
            )
            log_event(
                self.repo,
                actor_id,
                Event.ALLOCATION_CREATE_REQUEST,
                allocation.model_dump(),
            )
            self.repo.insert_allocation(allocation)
            self.repo.update_ip_pool_address(
                ip_address.ip_address,
                status=IpAddressStatus.RESERVED,
                allocation_id=allocation.allocation_id,
                current_host=cu.hostname,
            )
            self.repo.update_compute_unit(
                cu.compute_id,
                tags={
                    **(req.tags or {}),
                    "allocation_id": allocation.allocation_id,
                    "allocation_name": allocation.name,
                    "ip_address": allocation.ip_address,
                },
            )
            job: JobID = self.repo.enqueue_command(
                QueueCommand.CU_ALLOCATE,
                AllocationCreateCommand(
                    allocation_id=allocation.allocation_id,
                    compute_id=cu.compute_id,
                    ssh_public_key=req.ssh_public_key,
                ),
                actor_id,
            )
        except NoFreeIpAddressError:
            raise
        except Exception as exc:
            try:
                if allocation:
                    self.repo.clear_allocation_placement(
                        allocation.allocation_id,
                        status=AllocationStatus.ALLOCATION_FAIL,
                    )
                    self.repo.clear_ip_pool_host(
                        allocation.ip_address,
                        status=IpAddressStatus.RESERVED,
                    )
                elif ip_address:
                    self.repo.release_ip_pool_address(ip_address.ip_address)
                self.repo.update_compute_unit(
                    cu.compute_id,
                    status=ComputeUnitStatus.FREE,
                    tags={},
                )
            except Exception:
                logging.exception(
                    "Failed to release compute unit %s after allocation preparation failed",
                    cu.compute_id,
                )

            log_event(
                self.repo,
                actor_id,
                Event.ALLOCATION_CREATE_FAILED,
                {
                    **cu.model_dump(),
                    "request": req.model_dump(),
                    "ip_address": ip_address.model_dump() if ip_address else None,
                    "error": "Failed to persist allocation metadata before scheduling the allocation job.",
                },
            )
            raise ComputeUnitOperationError(
                "Unable to prepare compute unit allocation."
            ) from exc

        return AllocationCreateResponse(
            allocation_id=allocation.allocation_id,
            job_id=job.job_id,
        )

    def deallocate(
        self,
        actor_id: str,
        allocation_id: str,
    ) -> JobID:
        """Mark an allocation as deallocating and queue compute-unit cleanup."""
        allocation = self._get_allocation(allocation_id)
        if allocation.compute_id is None:
            raise ComputeUnitOperationError(
                f"Allocation '{allocation_id}' has no active compute unit."
            )
        cu = self._get_active_compute_unit(allocation)

        log_event(
            self.repo,
            actor_id,
            Event.CU_DEALLOCATION_REQUEST,
            {"compute_id": cu.compute_id, "allocation_id": allocation_id},
        )

        allowed_statuses = {
            ComputeUnitStatus.ALLOCATED,
            ComputeUnitStatus.ALLOCATION_FAIL,
            ComputeUnitStatus.DEALLOCATION_FAIL,
        }
        current_status = ComputeUnitStatus(cu.status)
        if current_status not in allowed_statuses:
            allowed = ", ".join(sorted(status.value for status in allowed_statuses))
            raise ComputeUnitStateError(
                f"Compute unit '{cu.compute_id}' cannot be deallocated from status '{current_status.value}'. Allowed statuses: {allowed}."
            )

        try:
            self.repo.update_compute_unit(
                cu.compute_id,
                status=ComputeUnitStatus.DEALLOCATING,
                tags={},
            )
            self.repo.update_allocation(
                allocation.allocation_id,
                status=AllocationStatus.DEALLOCATING,
            )
            self.repo.update_ip_pool_address(
                allocation.ip_address,
                status=IpAddressStatus.RELEASING,
            )
        except Exception as exc:
            raise ComputeUnitOperationError(
                "Unable to prepare allocation deallocation."
            ) from exc

        return self.repo.enqueue_command(
            QueueCommand.CU_DEALLOCATE,
            AllocationDeallocateCommand(
                allocation_id=allocation.allocation_id,
                compute_id=cu.compute_id,
            ),
            actor_id,
        )

    def scale(
        self,
        actor_id: str,
        allocation_id: str,
        req: AllocationScaleRequest,
    ) -> JobID:
        """Queue a cpkit job that migrates an allocation to another compute unit."""
        allocation = self._get_allocation(allocation_id)
        if allocation.compute_id is None:
            raise ComputeUnitOperationError(
                f"Allocation '{allocation_id}' has no active compute unit."
            )

        current_status = AllocationStatus(allocation.status)
        if current_status is not AllocationStatus.ALLOCATED:
            raise ComputeUnitOperationError(
                f"Allocation '{allocation_id}' cannot scale from status '{current_status.value}'."
            )

        command = AllocationScaleCommand(
            allocation_id=allocation_id,
            **req.model_dump(),
        )
        self.repo.update_allocation(
            allocation_id,
            status=AllocationStatus.SCALING,
        )
        log_event(
            self.repo,
            actor_id,
            Event.ALLOCATION_SCALE_REQUEST,
            command.model_dump(),
        )
        try:
            return self.repo.enqueue_command(
                QueueCommand.ALLOCATION_SCALE,
                command,
                actor_id,
            )
        except Exception as exc:
            self.repo.update_allocation(
                allocation_id,
                status=AllocationStatus.ALLOCATED,
            )
            raise ComputeUnitOperationError(
                "Unable to enqueue allocation scale job."
            ) from exc

    def _get_allocation(self, allocation_id: str) -> AllocationInDB:
        matches = self.repo.get_allocations(allocation_id=allocation_id)
        if not matches:
            raise ComputeUnitNotFoundError(
                f"Allocation '{allocation_id}' does not exist."
            )
        return matches[0]

    def _get_active_compute_unit(
        self,
        allocation: AllocationInDB,
    ) -> ComputeUnitOverview:
        if allocation.compute_id is None:
            raise ComputeUnitNotFoundError(
                f"Allocation '{allocation.allocation_id}' has no active compute unit."
            )
        matches = self.repo.get_compute_units(compute_id=allocation.compute_id)
        if not matches:
            raise ComputeUnitNotFoundError(
                f"Compute unit '{allocation.compute_id}' does not exist."
            )
        return matches[0]
