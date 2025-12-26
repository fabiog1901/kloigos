import datetime as dt
import json
import sqlite3

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status

from .. import CPU_PORTS_MAP, RANGE_SIZE, SQLITE_DB
from ..models import ComputeUnitInDB, ComputeUnitRequest, ComputeUnitResponse
from ..util import MyRunner, cpu_range_to_list

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
    bg_task.add_task(run_clean_up, compute_id)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)


@router.get("/")
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


def run_clean_up(compute_id: str) -> None:
    """
    Execute Ansible Playbook `clean_up.yaml`
    The goal is to return the compute unit to a clean state
    so that it can be available for being re-provisioned.
    """

    job_status = MyRunner().launch_runner("resources/clean_up.yaml", {})

    status = "free" if job_status == "successful" else "unavailable"

    with sqlite3.connect(SQLITE_DB) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE compute_units
            SET status = ?
            WHERE compute_id = ?
            """,
            (status, compute_id),
        )


def get_compute_units(
    compute_id: str = None,
    region: str = None,
    zone: str = None,
    cpu_count: int = None,
    deployment_id: str = None,
    status: str = None,
    limit: int = None,
) -> list[ComputeUnitInDB]:

    # Prepare the WHERE clause
    conditions = []
    params = []

    if compute_id is not None:
        conditions.append("compute_id = ?")
        params.append(compute_id)

    if region is not None:
        conditions.append("region = ?")
        params.append(region)

    if zone is not None:
        conditions.append("zone = ?")
        params.append(zone)

    if cpu_count is not None:
        conditions.append("cpu_count = ?")
        params.append(cpu_count)

    if deployment_id is not None:
        conditions.append("json_extract(tags, '$.deployment_id') = ?")
        params.append(status)

    if status is not None:
        conditions.append("status = ?")
        params.append(status)

    sql = "SELECT * FROM compute_units"

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    if limit:
        sql += f" LIMIT {limit}"

    with sqlite3.connect(SQLITE_DB) as conn:
        conn.row_factory = sqlite3.Row  # enables dict-like access

        cur = conn.cursor()

        rs = cur.execute(sql, params).fetchall()

        cu_list: list[ComputeUnitInDB] = []

        for row in rs:
            data = dict(row)

            # Parse tags JSON
            data["tags"] = json.loads(data["tags"]) if data.get("tags") else None

            # Parse started_at timestamp
            if data.get("started_at"):
                data["started_at"] = dt.datetime.fromisoformat(data["started_at"])
            else:
                data["started_at"] = None

            cu_list.append(ComputeUnitInDB(**data))

        return cu_list
