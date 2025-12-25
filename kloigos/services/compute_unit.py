import datetime as dt
import json
import sqlite3

from .. import SQLITE_DB
from ..models import ComputeUnitInDB, NewServerInit
from ..util import MyRunner


def clean_up_compute_unit(compute_id: str) -> None:
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


def init_new_server(nsi: NewServerInit) -> None:
    """
    Execute Ansible Playbook `init.yaml`
    The playbook setups the server with the requested
    compute_units.
    """

    cpu_ranges_list = [cpu_range_to_list(x) for x in nsi.cpu_ranges]
    cpu_ranges = [x.replace(":", "-") for x in nsi.cpu_ranges]

    job_status = MyRunner().launch_runner(
        "examples/init.yaml",
        {
            "compute_id": nsi.hostname,
            "cpu_ranges": cpu_ranges,
            "cpu_ranges_list": cpu_ranges_list,
        },
    )

    # add the created compute units if the job was successfull
    if job_status == "successful":
        for x in nsi.cpu_ranges:

            cpu_count = len(cpu_range_to_list(x).split(","))
            compute_id = f"{nsi.hostname}_c{x.replace(':', '-')}"

            with sqlite3.connect(SQLITE_DB) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO compute_units (
                        compute_id, cpu_count, cpu_range, hostname, ip, 
                        region, zone, status, started_at, tags
                    ) 
                    VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    ) 
                    ON CONFLICT DO UPDATE SET 
                        compute_id = excluded.compute_id, 
                        cpu_count = excluded.cpu_count,
                        cpu_range = excluded.cpu_range,
                        hostname = excluded.hostname,
                        ip = excluded.ip,
                        region = excluded.region,
                        zone = excluded.zone,
                        status = excluded.status,
                        started_at = excluded.started_at,
                        tags = excluded.tags
                    """,
                    (
                        compute_id,
                        cpu_count,
                        x,
                        nsi.hostname,
                        nsi.ip,
                        nsi.region,
                        nsi.zone,
                        "free",
                        None,
                        "{}",
                    ),
                )

        # remove the row with the details of the server in init status
        with sqlite3.connect(SQLITE_DB) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE 
                FROM compute_units
                WHERE compute_id = ?
                """,
                (nsi.hostname,),
            )

    else:
        with sqlite3.connect(SQLITE_DB) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE compute_units 
                SET status = 'init-failed'
                WHERE compute_id = ?
                """,
                (nsi.hostname,),
            )


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
