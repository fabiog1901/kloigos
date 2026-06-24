import logging

from cpkit.audit import log_event
from cpkit.jobs.types import JobID
from cpkit.playbooks import run_playbook

from kloigos.models import (
    AllocationCreateCommand,
    AllocationCreateResponse,
    AllocationDeallocateCommand,
    AllocationInDB,
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
    Playbook,
    QueueCommand,
)

from ..repos import Repo


def _ansible_host(public_ip: str | None, private_ip: str) -> str:
    return public_ip or private_ip


def _request_allocation_identity(
    req: ComputeUnitRequest,
    cu: ComputeUnitOverview,
) -> tuple[str, str]:
    tags = req.tags if isinstance(req.tags, dict) else {}
    tagged_name = tags.get("allocation_id") or tags.get("deployment_id") or tags.get("name")
    allocation_id = str(req.allocation_id or tagged_name or cu.compute_id).strip()
    name = str(req.name or tagged_name or allocation_id).strip()
    return allocation_id, name


class ComputeUnitService:
    """Coordinate compute-unit allocation, deallocation, and audit logging."""

    def __init__(self, repo: Repo):
        self.repo = repo

    def allocate(
        self,
        actor_id: str,
        req: ComputeUnitRequest,
    ) -> AllocationCreateResponse:
        """
        Reserve a free compute unit and queue the cpkit job that finishes allocation.

        The method performs the synchronous part of the workflow:
        1. log that the caller requested an allocation
        2. atomically lock one free compute unit into the ALLOCATING state
        3. attach request metadata such as tags
        4. enqueue the cpkit job that will run the playbook

        Raises:
            NoFreeComputeUnitError: if no matching compute unit is available.
            ComputeUnitOperationError: if the unit was locked but setup could not finish.
        """
        log_event(
            self.repo,
            actor_id,
            Event.CU_ALLOCATION_REQUEST,
            req.model_dump(),
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

            allocation_tags = {
                **(req.tags or {}),
                "allocation_id": allocation.allocation_id,
                "allocation_name": allocation.name,
                "ip_address": allocation.ip_address,
            }
            # Once the unit is locked, attach request metadata before we hand work to
            # the background task. If this step fails, we mark the unit as failed so
            # it does not remain stuck in ALLOCATING forever.
            self.repo.update_compute_unit(
                cu.compute_id,
                tags=allocation_tags,
            )
            command = AllocationCreateCommand(
                allocation_id=allocation.allocation_id,
                compute_id=cu.compute_id,
                ssh_public_key=req.ssh_public_key,
            )
            job: JobID = self.repo.enqueue_command(
                QueueCommand.CU_ALLOCATE,
                command,
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
                    "error": "Failed to persist allocation metadata before scheduling the background task.",
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
        compute_id: str,
    ) -> JobID:
        """
        Mark a compute unit as DEALLOCATING and queue the cleanup playbook.

        Raises:
            ComputeUnitNotFoundError: if the compute unit does not exist.
            ComputeUnitStateError: if the compute unit is not in a state we can deallocate.
            ComputeUnitOperationError: if the state transition could not be persisted.
        """
        log_event(
            self.repo,
            actor_id,
            Event.CU_DEALLOCATION_REQUEST,
            {"compute_id": compute_id},
        )

        matches = self.repo.get_compute_units(compute_id=compute_id)
        if not matches:
            raise ComputeUnitNotFoundError(
                f"Compute unit '{compute_id}' does not exist."
            )
        cu = matches[0]
        allocations = self.repo.get_allocations(compute_id=compute_id)
        allocation = allocations[0] if allocations else None

        # Deallocation only makes sense once a unit has been allocated before, or if
        # we are retrying cleanup after a previous background failure.
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
            # Clear tags as soon as deallocation starts so the unit no longer looks
            # assigned to the previous workload while cleanup is in progress.
            self.repo.update_compute_unit(
                cu.compute_id,
                status=ComputeUnitStatus.DEALLOCATING,
                tags={},
            )
            if allocation:
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
                "Unable to prepare compute unit deallocation."
            ) from exc

        if allocation is None:
            raise ComputeUnitOperationError(
                f"Compute unit '{compute_id}' has no allocation metadata."
            )

        return self.repo.enqueue_command(
            QueueCommand.CU_DEALLOCATE,
            AllocationDeallocateCommand(
                allocation_id=allocation.allocation_id,
                compute_id=cu.compute_id,
            ),
            actor_id,
        )

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
        """Return compute units filtered by the provided query parameters."""
        return self.repo.get_compute_units(
            compute_id,
            hostname,
            region,
            zone,
            cpu_count,
            deployment_id,
            status,
        )

    def run_allocate_job(
        self,
        job_id: int,
        command: AllocationCreateCommand,
        actor_id: str,
    ) -> None:
        """
        Execute the queued allocation playbook and record final placement state.

        Any unexpected exception is treated as a failed allocation so the compute unit
        cannot remain stuck in ALLOCATING.
        """
        cu = self._get_compute_unit(command.compute_id)
        allocation = self._get_allocation(command.allocation_id)
        details = {
            **cu.model_dump(),
            "allocation": allocation.model_dump(),
        }
        job_ok = False

        try:
            result = run_playbook(
                repo=self.repo,
                job_id=job_id,
                playbook_name=Playbook.CU_ALLOCATE.value,
                extra_vars={
                    "compute_id": cu.compute_id,
                    "hostname": cu.hostname,
                    "ansible_host": _ansible_host(
                        cu.server_public_ip, cu.server_private_ip
                    ),
                    "server_private_ip": cu.server_private_ip,
                    "server_public_ip": cu.server_public_ip,
                    "private_ip": allocation.ip_address,
                    "allocation_id": allocation.allocation_id,
                    "allocation_name": allocation.name,
                    "allocation_ip_address": allocation.ip_address,
                    "compute_unit_private_ip": cu.private_ip,
                    "public_ip": cu.public_ip,
                    "cu_user": cu.cu_user,
                    "cpu_range": cu.cpu_range,
                    "cpu_count": cu.cpu_count,
                    "ssh_public_key": command.ssh_public_key,
                },
            )
            job_ok = result.status == "successful"
        except Exception as exc:
            details["error"] = f"Unhandled exception during allocation playbook: {exc}"
            logging.exception(
                "Unhandled exception during compute unit allocation for %s",
                cu.compute_id,
            )

        final_status = (
            ComputeUnitStatus.ALLOCATED if job_ok else ComputeUnitStatus.ALLOCATION_FAIL
        )
        final_event = Event.CU_ALLOCATION_DONE if job_ok else Event.CU_ALLOCATION_FAILED
        final_allocation_status = (
            AllocationStatus.ALLOCATED if job_ok else AllocationStatus.ALLOCATION_FAIL
        )
        final_ip_status = IpAddressStatus.ALLOCATED if job_ok else IpAddressStatus.RESERVED

        try:
            self.repo.update_compute_unit(
                cu.compute_id,
                status=final_status,
            )
            self.repo.update_allocation(
                allocation.allocation_id,
                status=final_allocation_status,
            )
            self.repo.update_ip_pool_address(
                allocation.ip_address,
                status=final_ip_status,
                allocation_id=allocation.allocation_id,
                current_host=cu.hostname,
            )
        except Exception:
            logging.exception(
                "Failed to update allocation state for compute unit %s to final status %s",
                cu.compute_id,
                final_status,
            )

        log_event(
            self.repo,
            actor_id,
            final_event,
            details,
        )
        log_event(
            self.repo,
            actor_id,
            Event.ALLOCATION_CREATE_DONE if job_ok else Event.ALLOCATION_CREATE_FAILED,
            details,
        )
        if not job_ok:
            raise ComputeUnitOperationError(
                f"Compute unit allocation job '{job_id}' failed."
            )

    def run_deallocate_job(
        self,
        job_id: int,
        command: AllocationDeallocateCommand,
        actor_id: str,
    ) -> None:
        """
        Execute the queued deallocation playbook and record final placement state.

        Any unexpected exception is treated as a failed deallocation so the compute
        unit cannot remain stuck in DEALLOCATING.
        """
        cu = self._get_compute_unit(command.compute_id)
        allocation = self._get_allocation(command.allocation_id)
        details = {
            **cu.model_dump(),
            "allocation": allocation.model_dump(),
        }
        job_ok = False

        try:
            result = run_playbook(
                repo=self.repo,
                job_id=job_id,
                playbook_name=Playbook.CU_DEALLOCATE.value,
                extra_vars={
                    "compute_id": cu.compute_id,
                    "hostname": cu.hostname,
                    "ansible_host": _ansible_host(
                        cu.server_public_ip, cu.server_private_ip
                    ),
                    "server_private_ip": cu.server_private_ip,
                    "server_public_ip": cu.server_public_ip,
                    "private_ip": allocation.ip_address,
                    "allocation_id": allocation.allocation_id,
                    "allocation_ip_address": allocation.ip_address,
                    "compute_unit_private_ip": cu.private_ip,
                    "cu_user": cu.cu_user,
                },
            )
            job_ok = result.status == "successful"
        except Exception as exc:
            details["error"] = (
                f"Unhandled exception during deallocation playbook: {exc}"
            )
            logging.exception(
                "Unhandled exception during compute unit deallocation for %s",
                cu.compute_id,
            )

        final_status = (
            ComputeUnitStatus.FREE if job_ok else ComputeUnitStatus.DEALLOCATION_FAIL
        )
        final_event = (
            Event.CU_DEALLOCATION_DONE if job_ok else Event.CU_DEALLOCATION_FAILED
        )

        try:
            self.repo.update_compute_unit(
                cu.compute_id,
                status=final_status,
            )
            if job_ok:
                self.repo.clear_allocation_placement(
                    allocation.allocation_id,
                    status=AllocationStatus.DEALLOCATED,
                )
                self.repo.clear_ip_pool_host(
                    allocation.ip_address,
                    status=IpAddressStatus.ALLOCATED,
                )
            else:
                self.repo.update_allocation(
                    allocation.allocation_id,
                    status=AllocationStatus.DEALLOCATION_FAIL,
                )
                self.repo.update_ip_pool_address(
                    allocation.ip_address,
                    status=IpAddressStatus.ALLOCATED,
                    allocation_id=allocation.allocation_id,
                    current_host=cu.hostname,
                )
        except Exception:
            logging.exception(
                "Failed to update deallocation state for compute unit %s to final status %s",
                cu.compute_id,
                final_status,
            )

        log_event(
            self.repo,
            actor_id,
            final_event,
            details,
        )
        if not job_ok:
            raise ComputeUnitOperationError(
                f"Compute unit deallocation job '{job_id}' failed."
            )

    def _get_compute_unit(self, compute_id: str) -> ComputeUnitOverview:
        matches = self.repo.get_compute_units(compute_id=compute_id)
        if not matches:
            raise ComputeUnitNotFoundError(
                f"Compute unit '{compute_id}' does not exist."
            )
        return matches[0]

    def _get_allocation(self, allocation_id: str) -> AllocationInDB:
        matches = self.repo.get_allocations(allocation_id=allocation_id)
        if not matches:
            raise ComputeUnitNotFoundError(
                f"Allocation '{allocation_id}' does not exist."
            )
        return matches[0]
