import datetime as dt
import json
import sqlite3
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from util import MyRunner

app = FastAPI(title="Κλοηγός")

RANGE_SIZE = 200
CPU_PORTS_MAP = {f"{k}": 2000 + i * RANGE_SIZE for i, k in enumerate(range(256))}

SQLITE = "kloigos.sqlite"


class ComputeUnit(BaseModel):
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


class ComputeUnitResponse(ComputeUnit):
    cpu_list: str
    ports_range: str | None


class ComputeUnitRequest(BaseModel):
    cpu_count: int | None = 4
    region: str | None = None
    zone: str | None = None
    tags: dict[str, str | int] | None


@app.post(
    "/provision",
)
async def provision_resources(
    req: ComputeUnitRequest,
) -> ComputeUnitResponse:

    cu_list = get_compute_units(
        region=req.region,
        zone=req.zone,
        status="free",
        cpu_count=req.cpu_count,
        limit=1,
    )

    if cu_list:
        cu = cu_list[0]
    else:
        raise HTTPException(status.HTTP_416_RANGE_NOT_SATISFIABLE)

    cpu_list = cpu_range_to_list(cu.cpu_range)

    s = CPU_PORTS_MAP[cpu_list[-1]]
    ports_range = f"{s}-{s + RANGE_SIZE}"

    with sqlite3.connect(SQLITE) as conn:
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

    return ComputeUnitResponse(
        cpu_list=cpu_list,
        ports_range=ports_range,
        **cu.model_dump(),
    )


@app.delete(
    "/deprovision/{compute_id}",
)
async def deprovision_resources(
    compute_id: str,
    bg_task: BackgroundTasks,
) -> None:

    with sqlite3.connect(SQLITE) as conn:
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

    bg_task.add_task(clean_up_compute_unit, compute_id)

    return Response(status_code=status.HTTP_200_OK)


def clean_up_compute_unit(compute_id: str) -> None:
    job_status = MyRunner().launch_runner("examples/clean_up.yaml", {})

    status = "free" if job_status == "successful" else "unavailable"

    with sqlite3.connect(SQLITE) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE compute_units
            SET status = ?
            WHERE compute_id = ?
            """,
            (status, compute_id),
        )


@app.get("/servers")
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

    cu = get_compute_units(
        compute_id,
        region,
        zone,
        cpu_count,
        deployment_id,
        status,
    )

    inventory: list[ComputeUnitResponse] = []

    for x in cu:
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


def cpu_range_to_list(s: str):
    """
    Convert from cpu_short syntax to a comma separated list

    Examples:

    "0-7:2" -> "0,2,4,6"

    "1-7:2" -> "1,3,5,7"

    "0-7"   -> "0,1,2,3,4,5,6,7"
    """

    # check whether the string is already a comma separated list
    if s.find(",") > 0:
        return s

    # check to see if the step syntax is used:
    if s.find(":") < 0:
        step = 1
        rng = s
    else:
        rng, step = s.split(":")
        step = int(step)

    start, end = rng.split("-")
    start = int(start)
    end = int(end)

    return ",".join([str(x) for x in list(range(start, end + 1, step))])


def get_compute_units(
    compute_id: str = None,
    region: str = None,
    zone: str = None,
    cpu_count: int = None,
    deployment_id: str = None,
    status: str = None,
    limit: int = None,
) -> list[ComputeUnit]:

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

    with sqlite3.connect(SQLITE) as conn:
        conn.row_factory = sqlite3.Row  # enables dict-like access

        cur = conn.cursor()

        rs = cur.execute(sql, params).fetchall()

        response = []

        for row in rs:
            data = dict(row)

            # Parse tags JSON
            data["tags"] = json.loads(data["tags"]) if data.get("tags") else None

            # Parse started_at timestamp
            if data.get("started_at"):
                data["started_at"] = dt.datetime.fromisoformat(data["started_at"])
            else:
                data["started_at"] = None

            response.append(ComputeUnit(**data))

        return response


# Configure the templates
templates = Jinja2Templates(directory="kloigos/templates")


@app.get("/", response_class=HTMLResponse)
async def inventory_dashboard(request: Request):

    inventory = {x.compute_id: x.model_dump() for x in get_compute_units()}

    for _, v in inventory.items():
        cpu_list = cpu_range_to_list(v.get("cpu_range"))
        start_port = CPU_PORTS_MAP.get(cpu_list.split(",")[-1])

        v["cpu_list"] = cpu_list
        v["ports_range"] = f"{start_port}-{start_port+RANGE_SIZE}"

    # 2. Prepare the context dictionary to pass data to the HTML template
    context = {
        "request": request,  # Required by Jinja2Templates
        "title": "κλοηγός: Data Center Inventory Dashboard",
        "hosts": inventory,
    }

    return templates.TemplateResponse("dashboard.html", context)
