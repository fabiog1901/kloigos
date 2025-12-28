import datetime as dt
from enum import StrEnum, auto
from typing import Any

from pydantic import BaseModel


class AutoNameStrEnum(StrEnum):
    def _generate_next_value_(name, start, count, last_values):
        return name


class Status(AutoNameStrEnum):
    # compute unit level statuses
    FREE = auto()
    ALLOCATING = auto()
    ALLOCATED = auto()
    ALLOCATION_FAIL = auto()
    DEALLOCATING = auto()
    DEALLOCATION_FAIL = auto()
    UNAVAILABLE = auto()
    # Server level statuses
    INITIALIZING = auto()
    INIT_FAIL = auto()
    DECOMMISSIONING = auto()
    DECOMMISSIONED = auto()
    DECOMMISSION_FAIL = auto()


class ComputeUnitInDB(BaseModel):
    compute_id: str
    hostname: str
    ip: str
    cpu_count: int
    cpu_range: str
    region: str
    zone: str
    status: str
    started_at: dt.datetime | None
    tags: dict[str, Any] | None


class ComputeUnitResponse(ComputeUnitInDB):
    cpu_list: str
    ports_range: str | None


class ComputeUnitRequest(BaseModel):
    cpu_count: int | None = 4
    region: str | None = None
    zone: str | None = None
    tags: dict[str, str | int | list[str]] | None


class InitServerRequest(BaseModel):
    ip: str
    region: str
    zone: str
    hostname: str
    cpu_ranges: list[str]
