import logging

from kloigos.models import (
    ComputeUnitNotFoundError,
    ComputeUnitOperationError,
    ComputeUnitOverview,
    ComputeUnitRequest,
    ComputeUnitStateError,
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
    """Coordinate compute-unit allocation, deallocation, and audit logging."""

    def __init__(self, repo: BaseRepo):
        self.repo = repo

    def allocate(
        self,
        actor_id: str,
        req: ComputeUnitRequest,
    ) -> tuple[str, list[DeferredTask]]:
        """
        Reserve a free compute unit and queue the playbook that finishes allocation.

        The method performs the synchronous part of the workflow:
        1. log that the caller requested an allocation
        2. atomically lock one free compute unit into the ALLOCATING state
        3. attach request metadata such as tags
        4. return the background task that will run the playbook

        Raises:
            NoFreeComputeUnitError: if no matching compute unit is available.
            ComputeUnitOperationError: if the unit was locked but setup could not finish.
        """
        request_id = request_id_ctx.get()
        self.log_event(
            actor_id,
            Event.CU_ALLOCATION_REQUEST,
            req.model_dump(),
            request_id=request_id,
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

        try:
            # Once the unit is locked, attach request metadata before we hand work to
            # the background task. If this step fails, we mark the unit as failed so
            # it does not remain stuck in ALLOCATING forever.
            self.repo.update_compute_unit(
                cu.compute_id,
                tags=req.tags,
            )
        except Exception as exc:
            try:
                self.repo.update_compute_unit(
                    cu.compute_id,
                    status=ComputeUnitStatus.ALLOCATION_FAIL,
                )
            except Exception:
                logging.exception(
                    "Failed to move compute unit %s to failure status %s",
                    cu.compute_id,
                    ComputeUnitStatus.ALLOCATION_FAIL,
                )

            self.log_event(
                actor_id,
                Event.CU_ALLOCATION_FAILED,
                {
                    **cu.model_dump(),
                    "request": req.model_dump(),
                    "error": "Failed to persist allocation metadata before scheduling the background task.",
                },
                request_id=request_id,
            )
            raise ComputeUnitOperationError(
                "Unable to prepare compute unit allocation."
            ) from exc

        # The background task does the slow playbook execution and final status update.
        tasks = [
            DeferredTask(
                fn=self._run_allocate,
                args=(
                    cu,
                    req.ssh_public_key,
                    actor_id,
                    request_id,
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
        """
        Mark a compute unit as DEALLOCATING and queue the cleanup playbook.

        Raises:
            ComputeUnitNotFoundError: if the compute unit does not exist.
            ComputeUnitStateError: if the compute unit is not in a state we can deallocate.
            ComputeUnitOperationError: if the state transition could not be persisted.
        """
        request_id = request_id_ctx.get()

        self.log_event(
            actor_id,
            Event.CU_DEALLOCATION_REQUEST,
            {"compute_id": compute_id},
            request_id=request_id,
        )

        matches = self.repo.get_compute_units(compute_id=compute_id)
        if not matches:
            raise ComputeUnitNotFoundError(
                f"Compute unit '{compute_id}' does not exist."
            )
        cu = matches[0]

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
        except Exception as exc:
            raise ComputeUnitOperationError(
                "Unable to prepare compute unit deallocation."
            ) from exc

        tasks = [
            DeferredTask(
                fn=self._run_deallocate,
                args=(cu, actor_id, request_id),
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

    def _run_allocate(
        self,
        cu: ComputeUnitOverview,
        ssh_public_key: str,
        actor_id: str,
        request_id: str | None,
    ) -> None:
        """
        Execute the allocation playbook and always record the final outcome.

        Any unexpected exception is treated as a failed allocation so the compute unit
        cannot remain stuck in ALLOCATING.
        """
        details = cu.model_dump()
        job_ok = False

        try:
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

        try:
            self.repo.update_compute_unit(
                cu.compute_id,
                status=final_status,
            )
        except Exception:
            logging.exception(
                "Failed to update compute unit %s to final status %s",
                cu.compute_id,
                final_status,
            )

        self.log_event(
            actor_id,
            final_event,
            details,
            request_id=request_id,
        )

    def _run_deallocate(
        self,
        cu: ComputeUnitOverview,
        actor_id: str,
        request_id: str | None,
    ) -> None:
        """
        Execute the deallocation playbook and always record the final outcome.

        Any unexpected exception is treated as a failed deallocation so the compute
        unit cannot remain stuck in DEALLOCATING.
        """
        details = cu.model_dump()
        job_ok = False

        try:
            job_ok = MyRunner(self.repo).launch_runner(
                Playbook.CU_DEALLOCATE,
                {
                    "compute_id": cu.compute_id,
                    "hostname": cu.hostname,
                    "ip": cu.ip,
                    "cu_user": cu.cu_user,
                },
            )
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
        except Exception:
            logging.exception(
                "Failed to update compute unit %s to final status %s",
                cu.compute_id,
                final_status,
            )

        self.log_event(
            actor_id,
            final_event,
            details,
            request_id=request_id,
        )

    def log_event(
        self,
        actor_id: str,
        action: Event,
        details: dict | None,
        request_id: str | None,
    ) -> None:
        """Attempt to write an audit event without letting secondary logging failures crash the flow."""
        try:
            self.repo.log_event(
                LogMsg(
                    user_id=actor_id,
                    action=action,
                    details=details,
                    request_id=request_id,
                )
            )
        except Exception:
            logging.exception("Failed to write compute unit event %s", action)
