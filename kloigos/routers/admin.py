import gzip
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Response, status

from ..models import InitServerRequest, Playbook, Status
from ..util import MyRunner, cpu_range_to_list_str, pool

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.patch("/playbooks/{playbook}")
async def update_playbooks(
    playbook: Playbook,
    # Annotated tells FastAPI this MUST come from the Body
    b64: Annotated[str, Body(description="The base64 encoded string")],
):

    with pool.connection() as conn:

        cur = conn.cursor()
        cur.execute(
            """
            UPDATE playbooks
            SET content = %s
            WHERE id = %s
            """,
            (
                gzip.compress(b64.encode()),
                playbook,
            ),
        )

    return Response(status_code=status.HTTP_200_OK)


@router.get("/playbooks/{playbook}")
async def fetch_playbook(
    playbook: Playbook,
) -> str:

    with pool.connection() as conn:

        cur = conn.cursor()
        rs = cur.execute(
            """
            SELECT content
            FROM playbooks
            WHERE id = %s
            """,
            (playbook,),
        ).fetchone()

    return gzip.decompress(rs[0]).decode()


@router.post(
    "/init_server",
)
async def init_server(
    isr: InitServerRequest,
    bg_task: BackgroundTasks,
) -> None:

    # add the server to the compute_units table with
    # status='init'
    with pool.connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO compute_units (
                compute_id, cpu_count, cpu_range, hostname, ip,
                region, zone, status, started_at, tags
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
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

    with pool.connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE compute_units
            SET status = %s
            WHERE hostname = %s
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

    cpu_ranges_list = [cpu_range_to_list_str(x) for x in isr.cpu_ranges]
    cpu_ranges = [x.replace(":", "-") for x in isr.cpu_ranges]

    job_ok = MyRunner().launch_runner(
        Playbook.server_init,
        {
            "compute_id": isr.hostname,
            "cpu_ranges": cpu_ranges,
            "cpu_ranges_list": cpu_ranges_list,
        },
    )

    # add the created compute units if the job was successfull
    if job_ok:
        for x in isr.cpu_ranges:

            cpu_count = len(cpu_range_to_list_str(x).split(","))
            compute_id = f"{isr.hostname}_c{x.replace(':', '-')}"

            with pool.connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPSERT INTO compute_units (
                        compute_id, cpu_count, cpu_range, hostname, ip, 
                        region, zone, status, started_at, tags
                    ) 
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
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
        with pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE 
                FROM compute_units
                WHERE compute_id = %s
                """,
                (isr.hostname,),
            )

    else:
        with pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE compute_units 
                SET status = %s
                WHERE compute_id = %s
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
        Playbook.server_decomm,
        {
            "decomm_hostname": hostname,
        },
    )

    # don't delete any metadata, instead mark the compute units as
    # status = 'DECOMMISSIONED'
    with pool.connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE compute_units 
            SET status = %s
            WHERE hostname = %s
            """,
            (
                Status.DECOMMISSIONED if job_ok else Status.DECOMMISSION_FAIL,
                hostname,
            ),
        )
