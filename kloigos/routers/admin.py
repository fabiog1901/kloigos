import sqlite3

from fastapi import APIRouter, BackgroundTasks, Response, status

from .. import SQLITE_DB
from ..models import InitServerRequest, Status
from ..util import MyRunner, cpu_range_to_list

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.post(
    "/init_server",
)
async def init_server(
    isr: InitServerRequest,
    bg_task: BackgroundTasks,
) -> None:

    # add the server to the compute_units table with
    # status='init'
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
            ON CONFLICT DO NOTHING
            """,
            (
                isr.hostname,
                0,
                "0-0",
                isr.hostname,
                isr.ip,
                isr.region,
                isr.zone,
                Status.INITIALIZING,
                None,
                "{}",
            ),
        )

    # async, run the cleanup task
    bg_task.add_task(run_init_server, isr)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)


@router.delete(
    "/decommission_server/{hostname}",
)
async def decommission_server(
    hostname: str,
    bg_task: BackgroundTasks,
) -> None:

    with sqlite3.connect(SQLITE_DB) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE compute_units
            SET status = ?
            WHERE hostname = ?
            """,
            (
                Status.DECOMMISSIONING,
                hostname,
            ),
        )

    # async, run the decomm task
    bg_task.add_task(run_decommission_server, hostname)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)


def run_init_server(isr: InitServerRequest) -> None:
    """
    Execute Ansible Playbook `init.yaml`
    The playbook setups the server with the requested
    compute_units.
    """

    cpu_ranges_list = [cpu_range_to_list(x) for x in isr.cpu_ranges]
    cpu_ranges = [x.replace(":", "-") for x in isr.cpu_ranges]

    job_ok = MyRunner().launch_runner(
        "resources/init.yaml",
        {
            "compute_id": isr.hostname,
            "cpu_ranges": cpu_ranges,
            "cpu_ranges_list": cpu_ranges_list,
        },
    )

    # add the created compute units if the job was successfull
    if job_ok:
        for x in isr.cpu_ranges:

            cpu_count = len(cpu_range_to_list(x).split(","))
            compute_id = f"{isr.hostname}_c{x.replace(':', '-')}"

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
                        isr.hostname,
                        isr.ip,
                        isr.region,
                        isr.zone,
                        Status.FREE,
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
                (isr.hostname,),
            )

    else:
        with sqlite3.connect(SQLITE_DB) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE compute_units 
                SET status = ?
                WHERE compute_id = ?
                """,
                (Status.INIT_FAIL, isr.hostname),
            )


def run_decommission_server(hostname: str) -> None:
    """
    Execute Ansible Playbook `decommission.yaml`
    The playbook decomm the server with the requested
    hostname.
    """

    job_ok = MyRunner().launch_runner(
        "resources/decommission.yaml",
        {
            "decomm_hostname": hostname,
        },
    )

    # don't delete any metadata, instead mark the compute units as
    # status = 'DECOMMISSIONED'
    with sqlite3.connect(SQLITE_DB) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE compute_units 
            SET status = ?
            WHERE hostname = ?
            """,
            (
                Status.DECOMMISSIONED if job_ok else Status.DECOMMISSION_FAIL,
                hostname,
            ),
        )
