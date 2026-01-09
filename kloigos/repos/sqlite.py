import datetime as dt
import json
import sqlite3

from ..models import (
    ComputeUnitInDB,
    ComputeUnitRequest,
    InitServerRequest,
    Playbook,
    Status,
)
from .base import BaseRepo


class SQLiteRepo(BaseRepo):

    def __init__(self, db_url: str) -> None:
        self.db_url = db_url

    def get_playbook(self, playbook: Playbook) -> str:

        with sqlite3.connect(self.db_url) as conn:

            cur = conn.cursor()
            rs = cur.execute(
                """
                SELECT content
                FROM playbooks
                WHERE id = ?
                """,
                (playbook,),
            ).fetchone()

        return rs[0]

    def update_playbook(
        self,
        playbook: Playbook,
        b64: str,
    ) -> None:

        with sqlite3.connect(self.db_url) as conn:

            cur = conn.cursor()
            cur.execute(
                """
                UPDATE playbooks
                SET content = ?
                WHERE id = ?
                """,
                (
                    b64,
                    playbook,
                ),
            )

    def insert_init_server(self, isr: InitServerRequest) -> None:

        with sqlite3.connect(self.db_url) as conn:
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

    def delete_server(self, hostname: str) -> None:
        with sqlite3.connect(self.db_url) as conn:
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

    def insert_new_cu(self, compute_id: str, cpu_count: int, x, isr: InitServerRequest):
        with sqlite3.connect(self.db_url) as conn:
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

    def delete_cu(self, hostname: str) -> None:
        with sqlite3.connect(self.db_url) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE 
                FROM compute_units
                WHERE compute_id = ?
                """,
                (hostname,),
            )

    def init_fail(self, hostname: str) -> None:
        with sqlite3.connect(self.db_url) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE compute_units 
                SET status = ?
                WHERE compute_id = ?
                """,
                (Status.INIT_FAIL, hostname),
            )

    def mark_decommissioned(self, hostname: str, job_ok: bool) -> None:
        with sqlite3.connect(self.db_url) as conn:
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

    def cu_mark_allocated(self, req: ComputeUnitRequest, cu: ComputeUnitInDB) -> None:
        # mark the compute_unit to allocating
        with sqlite3.connect(self.db_url) as conn:
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

    def update_cu_status_alloc(self, cu: ComputeUnitInDB) -> None:
        with sqlite3.connect(self.db_url) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                    UPDATE compute_units
                    SET status = ?
                    WHERE compute_id = ?
                    """,
                (Status.ALLOCATED, cu.compute_id),
            )

    def set_cu_status_alloc_fail(self, cu: ComputeUnitInDB) -> None:
        with sqlite3.connect(self.db_url) as conn:
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

    def get_compute_units(
        self,
        compute_id: str | None = None,
        hostname: str | None = None,
        region: str | None = None,
        zone: str | None = None,
        cpu_count: int | None = None,
        deployment_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
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

        with sqlite3.connect(self.db_url) as conn:
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
