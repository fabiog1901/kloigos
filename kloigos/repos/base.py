from abc import ABC, abstractmethod

from ..models import (
    ComputeUnitInDB,
    ComputeUnitOverview,
    ComputeUnitStatus,
    Event,
    Playbook,
    ServerInDB,
    ServerInitRequest,
    ServerStatus,
)


class BaseRepo(ABC):

    # PLAYBOOK
    @abstractmethod
    def playbook_get_content(self, playbook: Playbook) -> str:
        """
        Returns the content of the given playbook as
        a b64 encoded string

        :param playbook: the playbook name
        :type playbook: Playbook
        :return: b64 encoded playbook
        :rtype: str
        """
        pass

    @abstractmethod
    def playbook_update_content(
        self,
        playbook: Playbook,
        b64: str,
    ) -> None:
        pass

    # SERVER
    @abstractmethod
    def server_init_new(self, sir: ServerInitRequest, status: ServerStatus) -> None:
        pass

    @abstractmethod
    def server_update_status(self, hostname: str, status: ServerStatus) -> None:
        pass

    @abstractmethod
    def get_servers(self, hostname: str | None) -> list[ServerInDB]:
        pass

    @abstractmethod
    def delete_server(self, hostname: str) -> None:
        pass

    # COMPUTE UNIT
    @abstractmethod
    def insert_new_compute_unit(self, cudb: ComputeUnitInDB):
        pass

    @abstractmethod
    def update_compute_unit(
        self,
        compute_id: str,
        status: ComputeUnitStatus,
        tags: dict | None = None,
    ) -> None:
        pass

    @abstractmethod
    def delete_compute_units(self, hostname: str) -> None:
        pass

    @abstractmethod
    def get_compute_units(
        self,
        compute_id: str | None = None,
        hostname: str | None = None,
        region: str | None = None,
        zone: str | None = None,
        cpu_count: int | None = None,
        deployment_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[ComputeUnitOverview]:
        pass

    @abstractmethod
    def log_event(event: Event):
        pass
