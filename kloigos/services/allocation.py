import logging

from cpkit.audit import AuditLogRecord
from cpkit.jobs.types import JobID
from cpkit.logging import request_id_ctx
from cpkit.playbooks import run_playbook

from kloigos.models import (
    AllocationInDB,
    AllocationScaleCommand,
    AllocationScaleRequest,
    AllocationStatus,
    ComputeUnitNotFoundError,
    ComputeUnitOperationError,
    ComputeUnitOverview,
    ComputeUnitStatus,
    Event,
    IpAddressStatus,
    NoFreeComputeUnitError,
    Playbook,
    QueueCommand,
)

from ..repos import Repo
from .compute_unit import _ansible_host


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
        return self.repo.get_allocations(
            allocation_id=allocation_id,
            compute_id=compute_id,
            ip_address=ip_address,
            status=status,
        )

    def get_allocation(self, allocation_id: str) -> AllocationInDB:
        return self._get_allocation(allocation_id)

    def scale(
        self,
        actor_id: str,
        allocation_id: str,
        req: AllocationScaleRequest,
    ) -> JobID:
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
        self.log_event(
            actor_id,
            Event.ALLOCATION_SCALE_REQUEST,
            command.model_dump(),
            request_id=request_id_ctx.get(),
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

    def run_scale_job(
        self,
        job_id: int,
        command: AllocationScaleCommand,
        actor_id: str,
    ) -> None:
        request_id = request_id_ctx.get()
        allocation = self._get_allocation(command.allocation_id)
        source = self._get_active_compute_unit(allocation)
        try:
            target = self._lock_target_compute_unit(command)
        except Exception as exc:
            details = {
                "job_id": job_id,
                "allocation": allocation.model_dump(),
                "source_compute_unit": source.model_dump(),
                "request": command.model_dump(),
                "error": str(exc),
            }
            self.log_event(
                actor_id,
                Event.ALLOCATION_SCALE_FAILED,
                details,
                request_id=request_id,
            )
            raise

        details = {
            "job_id": job_id,
            "allocation": allocation.model_dump(),
            "source_compute_unit": source.model_dump(),
            "target_compute_unit": target.model_dump(),
            "request": command.model_dump(),
        }

        try:
            result = run_playbook(
                repo=self.repo,
                job_id=job_id,
                playbook_name=Playbook.ALLOCATION_SCALE.value,
                extra_vars=self._scale_extra_vars(allocation, source, target),
            )
            job_ok = result.status == "successful"
        except Exception as exc:
            job_ok = False
            details["error"] = f"Unhandled exception during scale playbook: {exc}"
            logging.exception(
                "Unhandled exception during allocation scale for %s",
                allocation.allocation_id,
            )

        if job_ok:
            self._finish_successful_scale(allocation, source, target)
            event = Event.ALLOCATION_SCALE_DONE
        else:
            self._finish_failed_scale(allocation, source, target)
            event = Event.ALLOCATION_SCALE_FAILED

        self.log_event(
            actor_id,
            event,
            details,
            request_id=request_id,
        )
        if not job_ok:
            raise ComputeUnitOperationError(
                f"Allocation scale job '{job_id}' failed."
            )

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

    def _lock_target_compute_unit(
        self,
        command: AllocationScaleCommand,
    ) -> ComputeUnitOverview:
        target = self.repo.lock_compute_unit(
            compute_id=command.compute_id,
            region=command.region,
            zone=command.zone,
            cpu_count=command.cpu_count,
            free_status=ComputeUnitStatus.FREE,
            allocated_status=ComputeUnitStatus.ALLOCATING,
        )
        if not target:
            self.repo.update_allocation(
                command.allocation_id,
                status=AllocationStatus.SCALE_FAIL,
            )
            raise NoFreeComputeUnitError(
                "No free target compute unit found for allocation scale request."
            )
        return target

    def _scale_extra_vars(
        self,
        allocation: AllocationInDB,
        source: ComputeUnitOverview,
        target: ComputeUnitOverview,
    ) -> dict:
        return {
            "allocation_id": allocation.allocation_id,
            "allocation_name": allocation.name,
            "allocation_ip_address": allocation.ip_address,
            "private_ip": allocation.ip_address,
            "source_compute_id": source.compute_id,
            "source_hostname": source.hostname,
            "source_ansible_host": _ansible_host(
                source.server_public_ip,
                source.server_private_ip,
            ),
            "source_server_private_ip": source.server_private_ip,
            "source_server_public_ip": source.server_public_ip,
            "source_compute_unit_private_ip": source.private_ip,
            "source_cu_user": source.cu_user,
            "source_cpu_range": source.cpu_range,
            "target_compute_id": target.compute_id,
            "target_hostname": target.hostname,
            "target_ansible_host": _ansible_host(
                target.server_public_ip,
                target.server_private_ip,
            ),
            "target_server_private_ip": target.server_private_ip,
            "target_server_public_ip": target.server_public_ip,
            "target_compute_unit_private_ip": target.private_ip,
            "target_cu_user": target.cu_user,
            "target_cpu_range": target.cpu_range,
            "target_cpu_count": target.cpu_count,
        }

    def _finish_successful_scale(
        self,
        allocation: AllocationInDB,
        source: ComputeUnitOverview,
        target: ComputeUnitOverview,
    ) -> None:
        tags = {
            **(allocation.tags or {}),
            "allocation_id": allocation.allocation_id,
            "allocation_name": allocation.name,
            "ip_address": allocation.ip_address,
        }
        self.repo.update_compute_unit(
            source.compute_id,
            status=ComputeUnitStatus.FREE,
            tags={},
        )
        self.repo.update_compute_unit(
            target.compute_id,
            status=ComputeUnitStatus.ALLOCATED,
            tags=tags,
        )
        self.repo.update_allocation(
            allocation.allocation_id,
            status=AllocationStatus.ALLOCATED,
            compute_id=target.compute_id,
            current_host=target.hostname,
        )
        self.repo.update_ip_pool_address(
            allocation.ip_address,
            status=IpAddressStatus.ALLOCATED,
            allocation_id=allocation.allocation_id,
            current_host=target.hostname,
        )

    def _finish_failed_scale(
        self,
        allocation: AllocationInDB,
        source: ComputeUnitOverview,
        target: ComputeUnitOverview,
    ) -> None:
        self.repo.update_compute_unit(
            target.compute_id,
            status=ComputeUnitStatus.ALLOCATION_FAIL,
            tags={},
        )
        self.repo.update_allocation(
            allocation.allocation_id,
            status=AllocationStatus.SCALE_FAIL,
            compute_id=source.compute_id,
            current_host=source.hostname,
        )
        self.repo.update_ip_pool_address(
            allocation.ip_address,
            status=IpAddressStatus.ALLOCATED,
            allocation_id=allocation.allocation_id,
            current_host=source.hostname,
        )

    def log_event(
        self,
        actor_id: str,
        action: Event,
        details: dict | None,
        request_id: str | None,
    ) -> None:
        self.repo.log_event(
            AuditLogRecord(
                user_id=actor_id,
                action=action,
                details=details,
                request_id=request_id,
            )
        )
