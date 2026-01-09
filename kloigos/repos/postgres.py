import datetime as dt
import gzip
import json

import psycopg
from psycopg.rows import class_row
from psycopg.types.json import Jsonb, JsonbDumper
from psycopg_pool import ConnectionPool

from ..models import (
    ComputeUnitInDB,
    ComputeUnitRequest,
    InitServerRequest,
    Playbook,
    Status,
)
from .base import BaseRepo


class Dict2JsonbDumper(JsonbDumper):
    def dump(self, obj):
        return super().dump(Jsonb(obj))


def create_postgres_pool(db_url: str):
    # Only import inside the function so it doesn't crash on module load

    psycopg.adapters.register_dumper(dict, Dict2JsonbDumper)

    return ConnectionPool(db_url, kwargs={"autocommit": True})


class PostgresRepo(BaseRepo):

    def __init__(self, pool: ConnectionPool) -> None:
        self.pool: ConnectionPool = pool

    #
    # ADMIN_SERVICE
    #
    def get_playbook(self, playbook: Playbook) -> str:

        with self.pool.connection() as conn:

            cur = conn.cursor()
            rs = cur.execute(
                """
                SELECT content
                FROM playbooks
                WHERE id = %s
                """,
                (playbook,),
            ).fetchone()

        return gzip.decompress(rs[0]).decode()  # type: ignore

    def update_playbook(
        self,
        playbook: Playbook,
        b64: str,
    ) -> None:

        with self.pool.connection() as conn:

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

    def insert_init_server(self, isr: InitServerRequest) -> None:

        with self.pool.connection() as conn:
            conn.execute(
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

    def delete_server(self, hostname: str) -> None:
        with self.pool.connection() as conn:
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

    def insert_new_cu(self, compute_id: str, cpu_count: int, x, isr: InitServerRequest):
        with self.pool.connection() as conn:
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

    def delete_cu(self, hostname: str) -> None:
        with self.pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                    DELETE 
                    FROM compute_units
                    WHERE compute_id = %s
                    """,
                (hostname,),
            )

    def init_fail(self, hostname: str) -> None:
        with self.pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                    UPDATE compute_units 
                    SET status = %s
                    WHERE compute_id = %s
                    """,
                (Status.INIT_FAIL, hostname),
            )

    def mark_decommissioned(self, hostname: str, job_ok: bool) -> None:
        with self.pool.connection() as conn:
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

    #
    # COMPUTE_UNIT_SERVICE
    #

    def cu_mark_allocated(
        self,
        req: ComputeUnitRequest,
        cu: ComputeUnitInDB,
    ) -> None:
        # mark the compute_unit to allocating
        with self.pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE compute_units
                SET status = %s,
                    tags = %s
                WHERE compute_id = %s
                """,
                (
                    Status.ALLOCATING,
                    json.dumps(req.tags),
                    cu.compute_id,
                ),
            )

    def cu_mark_deallocated(self, compute_id: str) -> None:

        with self.pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE compute_units
                SET status = %s,
                    tags = '{}'
                WHERE compute_id = %s
                """,
                (
                    Status.DEALLOCATING,
                    compute_id,
                ),
            )

    def update_cu_status_alloc(self, cu: ComputeUnitInDB) -> None:
        with self.pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE compute_units
                SET status = %s
                WHERE compute_id = %s
                """,
                (Status.ALLOCATED, cu.compute_id),
            )

    def update_cu_status_dealloc(self, compute_id: str, job_ok: bool) -> None:
        with self.pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE compute_units
                SET status = %s
                WHERE compute_id = %s
                """,
                (
                    Status.FREE if job_ok else Status.DEALLOCATION_FAIL,
                    compute_id,
                ),
            )

    def set_cu_status_alloc_fail(self, cu: ComputeUnitInDB) -> None:
        with self.pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE compute_units
                SET status = %s,
                    tags = '{}'
                WHERE compute_id = %s
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
            conditions.append("compute_id = %s")
            params.append(compute_id)

        if hostname is not None:
            conditions.append("hostname = %s")
            params.append(hostname)

        if region is not None:
            conditions.append("region = %s")
            params.append(region)

        if zone is not None:
            conditions.append("zone = %s")
            params.append(zone)

        if cpu_count is not None:
            conditions.append("cpu_count = %s")
            params.append(cpu_count)

        if deployment_id is not None:
            conditions.append("json_extract(tags, '$.deployment_id') = %s")
            params.append(status)

        if status is not None:
            conditions.append("status = %s")
            params.append(status)

        sql = "SELECT * FROM compute_units"

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        if limit:
            sql += f" LIMIT {limit}"

        with self.pool.connection() as conn:

            with conn.cursor(
                row_factory=class_row(ComputeUnitInDB),
            ) as cur:

                rs = cur.execute(sql, params).fetchall()  # type: ignore

                return rs
