import datetime as dt
from typing import Any

from pydantic import BaseModel


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
