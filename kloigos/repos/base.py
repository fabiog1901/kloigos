from abc import ABC, abstractmethod

from ..models import (
    ComputeUnitInDB,
    ComputeUnitRequest,
    InitServerRequest,
    Playbook,
    Status,
)


class BaseRepo(ABC):

    @abstractmethod
    def get_playbook(self, playbook: Playbook) -> str:
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
    def update_playbook(
        self,
        playbook: Playbook,
        b64: str,
    ) -> None:
        pass

    @abstractmethod
    def insert_init_server(self, isr: InitServerRequest) -> None:
        pass

    @abstractmethod
    def delete_server(self, hostname: str) -> None:
        pass

    @abstractmethod
    def insert_new_cu(self, compute_id: str, cpu_count: int, x, isr: InitServerRequest):
        pass

    @abstractmethod
    def delete_cu(self, hostname: str) -> None:
        pass

    @abstractmethod
    def init_fail(self, hostname: str) -> None:
        pass

    @abstractmethod
    def mark_decommissioned(self, hostname: str, job_ok: bool) -> None:
        pass

    @abstractmethod
    def cu_mark_allocated(self, req: ComputeUnitRequest, cu: ComputeUnitInDB) -> None:
        pass

    @abstractmethod
    def cu_mark_deallocated(self, compute_id: str) -> None:
        pass

    @abstractmethod
    def update_cu_status_alloc(self, cu: ComputeUnitInDB) -> None:
        pass

    def update_cu_status_dealloc(self, compute_id: str, job_ok: bool) -> None:
        pass

    @abstractmethod
    def set_cu_status_alloc_fail(self, cu: ComputeUnitInDB) -> None:
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
    ) -> list[ComputeUnitInDB]:
        pass
