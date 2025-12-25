import sqlite3

from fastapi import APIRouter, BackgroundTasks, Response, status

from .. import SQLITE_DB
from ..models import NewServerInit
from ..services.admin import init_new_server

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.post(
    "/new_server_init",
)
async def new_server_init(
    nsi: NewServerInit,
    bg_task: BackgroundTasks,
) -> None:

    # add the server to the compute_units with
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
                nsi.hostname,
                0,
                "0-0",
                nsi.hostname,
                nsi.ip,
                nsi.region,
                nsi.zone,
                "init",
                None,
                "{}",
            ),
        )

    # async, run the cleanup task
    bg_task.add_task(init_new_server, nsi)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)
