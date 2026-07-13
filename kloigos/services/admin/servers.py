from cpkit.audit import log_event
from cpkit.jobs.types import JobID

from ...models import (
    AllocationStatus,
    Event,
    QueueCommand,
    ServerDecommRequest,
    ServerInDB,
    ServerInitRequest,
    ServerNotFoundError,
    ServerStateError,
    ServerStatus,
)
from .base import AdminServiceBase


def _model_details(model) -> dict:
    return model.model_dump(mode="json")


DELETABLE_SERVER_STATUSES = {
    ServerStatus.DECOMMISSIONED.value,
    ServerStatus.INIT_FAIL.value,
    ServerStatus.DECOMMISSION_FAIL.value,
}


class ServersAdminService(AdminServiceBase):
    def init_server(self, actor_id: str, sir: ServerInitRequest) -> JobID:
        log_event(
            self.repo,
            actor_id,
            Event.SERVER_INIT_REQUEST,
            _model_details(sir),
        )

        self.repo.server_init_new(sir, ServerStatus.INITIALIZING)
        return self.repo.enqueue_command(QueueCommand.SERVER_INIT, sir, actor_id)

    def list_servers(
        self,
        hostname: str | None = None,
    ) -> list[ServerInDB]:
        return self.repo.get_servers(hostname)

    def decommission_server(
        self,
        actor_id: str,
        sdr: ServerDecommRequest,
    ) -> JobID:
        matches = self.repo.get_servers(sdr.hostname)
        if not matches:
            raise ServerNotFoundError(f"Server {sdr.hostname} was not found.")

        active_allocations = [
            allocation
            for allocation in self.repo.get_allocations(current_host=sdr.hostname)
            if allocation.status != AllocationStatus.DEALLOCATED.value
        ]
        if active_allocations:
            allocation_ids = ", ".join(
                sorted(allocation.allocation_id for allocation in active_allocations)
            )
            raise ServerStateError(
                f"Server {sdr.hostname} cannot be decommissioned while allocations "
                f"are still placed on it: {allocation_ids}."
            )

        log_event(
            self.repo,
            actor_id,
            Event.SERVER_DECOMM_REQUEST,
            _model_details(sdr),
        )

        self.repo.server_update_status(sdr.hostname, ServerStatus.DECOMMISSIONING)
        return self.repo.enqueue_command(QueueCommand.SERVER_DECOMM, sdr, actor_id)

    def delete_server(self, actor_id: str, hostname: str) -> None:
        matches = self.repo.get_servers(hostname)
        if not matches:
            raise ServerNotFoundError(f"Server {hostname} was not found.")

        server = matches[0]
        if server.status not in DELETABLE_SERVER_STATUSES:
            allowed = ", ".join(sorted(DELETABLE_SERVER_STATUSES))
            raise ServerStateError(
                f"Server {hostname} is {server.status}; "
                f"delete is only allowed for {allowed}."
            )

        log_event(
            self.repo,
            actor_id,
            Event.SERVER_DELETE_REQUEST,
            {"hostname": hostname},
        )

        self.repo.delete_server(hostname)
