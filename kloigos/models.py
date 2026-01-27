import datetime as dt
from enum import StrEnum, auto
from typing import Any, Callable

from pydantic import BaseModel


class AutoNameStrEnum(StrEnum):
    def _generate_next_value_(name, start, count, last_values):
        return name


class NoFreeComputeUnitError(Exception):
    pass


class AllocatePlaybookError(Exception):
    pass


class EventActions(AutoNameStrEnum):
    UPDATE_PLAYBOOK = auto()
    SERVER_INIT = auto()
    SERVER_DECOMM = auto()
    SERVER_DELETE = auto()
    CU_ALLOCATE = auto()
    CU_DEALLOCATE = auto()


class Event(BaseModel):
    ts: dt.datetime = dt.datetime.now(dt.timezone.utc)
    user_id: str
    action: EventActions
    details: dict[str, Any] | None = None


class DeferredTask(BaseModel):
    fn: Callable[..., None]
    args: tuple | None
    kwargs: dict = {}


class Playbook(AutoNameStrEnum):
    # compute unit level statuses
    CU_ALLOCATE = auto()
    CU_DEALLOCATE = auto()
    SERVER_INIT = auto()
    SERVER_DECOMM = auto()


class ComputeUnitStatus(AutoNameStrEnum):
    # compute unit level statuses
    FREE = auto()
    ALLOCATING = auto()
    ALLOCATED = auto()
    ALLOCATION_FAIL = auto()
    DEALLOCATING = auto()
    DEALLOCATION_FAIL = auto()
    UNAVAILABLE = auto()


class ServerStatus(AutoNameStrEnum):
    # Server level statuses
    INITIALIZING = auto()
    INIT_FAIL = auto()
    READY = auto()
    DECOMMISSIONING = auto()
    DECOMMISSIONED = auto()
    DECOMMISSION_FAIL = auto()


class ComputeUnitInDB(BaseModel):
    compute_id: str
    hostname: str
    cpu_range: str
    cpu_count: int
    cpu_set: str
    port_range: str
    cu_user: str
    status: str
    started_at: dt.datetime | None = None
    tags: dict[str, Any] | None = None


class ComputeUnitOverview(ComputeUnitInDB):
    ip: str
    region: str
    zone: str


class ComputeUnitRequest(BaseModel):
    compute_id: str | None = None
    cpu_count: int | None = None
    region: str | None = None
    zone: str | None = None
    tags: dict[str, str | int | list[str]] | None
    ssh_public_key: str


class BaseServer(BaseModel):
    hostname: str
    ip: str
    user_id: str
    region: str
    zone: str | None = None
    cpu_count: int | None = None
    mem_gb: int | None = None
    disk_count: int | None = None
    disk_size_gb: int | None = None
    tags: dict[str, Any] | None = None


class ServerInDB(BaseServer):
    status: str


class ServerInitRequest(BaseServer):
    ssh_key: str
    cpu_ranges: list[str]


class ServerDecommRequest(BaseModel):
    ssh_key: str
    hostname: str
