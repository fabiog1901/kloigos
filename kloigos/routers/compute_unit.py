import json
import sqlite3

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status

from .. import CPU_PORTS_MAP, RANGE_SIZE, SQLITE_DB
from ..models import ComputeUnitInDB, ComputeUnitRequest, ComputeUnitResponse
from ..services.compute_unit import (
    clean_up_compute_unit,
    cpu_range_to_list,
    get_compute_units,
)

router = APIRouter(
    prefix="/compute_units",
    tags=["compute_units"],
)


@router.post(
    "/provision",
)
async def provision_resources(
    req: ComputeUnitRequest,
) -> ComputeUnitResponse:

    # find and return a free instance that matches the provision request
    cu_list: list[ComputeUnitInDB] = get_compute_units(
        region=req.region,
        zone=req.zone,
        cpu_count=req.cpu_count,
        status="free",
        limit=1,
    )

    # if the list is empty, raise an HTTPException
    if cu_list:
        cu = cu_list[0]
    else:
        raise HTTPException(
            status_code=460, detail="No free Compute Unit found to match your request"
        )

    cpu_list = cpu_range_to_list(cu.cpu_range)

    s = CPU_PORTS_MAP[cpu_list[-1]]
    ports_range = f"{s}-{s + RANGE_SIZE}"

    # mark the compute_unit to allocated
    with sqlite3.connect(SQLITE_DB) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE compute_units
            SET status='allocated',
                tags = ?
            WHERE compute_id = ?
            """,
            (json.dumps(req.tags), cu.compute_id),
        )

    # return the details of the compute_unit
    return ComputeUnitResponse(
        cpu_list=cpu_list,
        ports_range=ports_range,
        tags=req.tags,
        **cu.model_dump(exclude="tags"),
    )


@router.delete(
    "/deprovision/{compute_id}",
)
async def deprovision_resources(
    compute_id: str,
    bg_task: BackgroundTasks,
) -> None:

    # mark the compute_id as terminating
    with sqlite3.connect(SQLITE_DB) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE compute_units
            SET status='terminating',
                tags = '{}'
            WHERE compute_id = ?
            """,
            (compute_id,),
        )

    # async, run the cleanup task
    bg_task.add_task(clean_up_compute_unit, compute_id)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)


@router.get("/servers")
async def list_servers(
    compute_id: str | None = None,
    region: str | None = None,
    zone: str | None = None,
    cpu_count: int | None = None,
    deployment_id: str | None = None,
    status: str | None = None,
) -> list[ComputeUnitResponse]:
    """
    Returns a list of all servers.
    Optionally filter the results by 'deployment_id' or 'status' query parameters.

    Example:
    - /servers
    - /servers?deployment_id=web_app_v1
    - /servers?status=free
    """

    cu_list: list[ComputeUnitInDB] = get_compute_units(
        compute_id,
        region,
        zone,
        cpu_count,
        deployment_id,
        status,
    )

    inventory: list[ComputeUnitResponse] = []

    for x in cu_list:
        cpu_list = cpu_range_to_list(x.cpu_range)

        s = CPU_PORTS_MAP[cpu_list[-1]]
        ports_range = f"{s}-{s + RANGE_SIZE}"

        inventory.append(
            ComputeUnitResponse(
                cpu_list=cpu_list,
                ports_range=ports_range,
                **x.model_dump(),
            )
        )

    return inventory
