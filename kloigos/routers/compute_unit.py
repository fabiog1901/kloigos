import datetime as dt
import json
import sqlite3

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status

from .. import SQLITE_DB
from ..models import (
    ComputeUnitInDB,
    ComputeUnitRequest,
    ComputeUnitResponse,
    Playbook,
    Status,
)
from ..util import MyRunner, cpu_range_to_list_str, ports_for_cpu_range

router = APIRouter(
    prefix="/compute_units",
    tags=["compute_units"],
)


@router.post(
    "/allocate",
)
async def allocate(
    req: ComputeUnitRequest,
) -> ComputeUnitResponse:

    # find and return a free instance that matches the allocate request
    cu_list: list[ComputeUnitInDB] = get_compute_units(
        region=req.region,
        zone=req.zone,
        cpu_count=req.cpu_count,
        status=Status.FREE,
        limit=1,
    )

    # if the list is empty, raise an HTTPException
    if cu_list:
        cu = cu_list[0]
    else:
        raise HTTPException(
            status_code=460, detail="No free Compute Unit found to match your request"
        )

    cpu_list = cpu_range_to_list_str(cu.cpu_range)

    pr = ports_for_cpu_range(cu.cpu_range)
    ports_range = f"{pr.start}-{pr.end}"

    # mark the compute_unit to allocating
    with sqlite3.connect(SQLITE_DB) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE compute_units
            SET status = ?,
                tags = ?
            WHERE compute_id = ?
            """,
            (Status.ALLOCATING, json.dumps(req.tags), cu.compute_id),
        )

    # blocking task - this is not async
    job_ok = run_allocate(cu.compute_id, req.ssh_public_key)

    if job_ok:
        with sqlite3.connect(SQLITE_DB) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE compute_units
                SET status = ?
                WHERE compute_id = ?
                """,
                (Status.ALLOCATED, cu.compute_id),
            )

        # return the details of the compute_unit
        return ComputeUnitResponse(
            cpu_list=cpu_list,
            ports_range=ports_range,
            tags=req.tags,
            **cu.model_dump(exclude="tags"),
        )
    else:
        with sqlite3.connect(SQLITE_DB) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE compute_units
                SET status = ?,
                    tags = '{}'
                WHERE compute_id = ?
                """,
                (Status.ALLOCATION_FAIL, cu.compute_id),
            )
        raise HTTPException(status_code=470, detail="Error running allocating playbook")


@router.delete(
    "/deallocate/{compute_id}",
)
async def deallocate(
    compute_id: str,
    bg_task: BackgroundTasks,
) -> None:

    # mark the compute_id as terminating
    with sqlite3.connect(SQLITE_DB) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE compute_units
            SET status = ?,
                tags = '{}'
            WHERE compute_id = ?
            """,
            (
                Status.DEALLOCATING,
                compute_id,
            ),
        )

    # async, run the cleanup task
    bg_task.add_task(run_deallocate, compute_id)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)


@router.get("/")
async def list_servers(
    compute_id: str | None = None,
    hostname: str | None = None,
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
        hostname,
        region,
        zone,
        cpu_count,
        deployment_id,
        status,
    )

    inventory: list[ComputeUnitResponse] = []

    for x in cu_list:
        cpu_list = cpu_range_to_list_str(x.cpu_range)

        pr = ports_for_cpu_range(x.cpu_range)
        ports_range = f"{pr.start}-{pr.end}"

        inventory.append(
            ComputeUnitResponse(
                cpu_list=cpu_list,
                ports_range=ports_range,
                **x.model_dump(),
            )
        )

    return inventory


def run_allocate(compute_id: str, ssh_public_key: str) -> bool:
    """
    Execute Ansible Playbook `allocate.yaml`
    """

    return MyRunner().launch_runner(
        Playbook.cu_allocate,
        {
            "compute_id": compute_id,
            "ssh_public_key": ssh_public_key,
        },
    )


def run_deallocate(compute_id: str) -> None:
    """
    Execute Ansible Playbook `deallocate.yaml`
    The goal is to return the compute unit to a clean state
    so that it can be available for being re-allocateed.
    """

    job_ok = MyRunner().launch_runner(
        Playbook.cu_deallocate,
        {
            "compute_id": compute_id,
        },
    )

    with sqlite3.connect(SQLITE_DB) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE compute_units
            SET status = ?
            WHERE compute_id = ?
            """,
            (
                Status.FREE if job_ok else Status.DEALLOCATION_FAIL,
                compute_id,
            ),
        )


def get_compute_units(
    compute_id: str = None,
    hostname: str = None,
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

    if hostname is not None:
        conditions.append("hostname = ?")
        params.append(hostname)

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
