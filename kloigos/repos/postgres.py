import gzip
import json

from psycopg.rows import class_row
from psycopg.types.json import Jsonb, JsonbDumper
from psycopg_pool import ConnectionPool

from ..models import (
    ComputeUnitInDB,
    ComputeUnitOverview,
    ComputeUnitStatus,
    Event,
    Playbook,
    ServerInDB,
    ServerInitRequest,
    ServerStatus,
)
from .base import BaseRepo


class Dict2JsonbDumper(JsonbDumper):
    def dump(self, obj):
        return super().dump(Jsonb(obj))


class PostgresRepo(BaseRepo):
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool: ConnectionPool = pool

    #
    # ADMIN_SERVICE
    #
    def playbook_get_content(self, playbook: Playbook) -> str:

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

    def playbook_update_content(
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

    def server_init_new(
        self,
        sir: ServerInitRequest,
        status: ServerStatus,
    ) -> None:

        with self.pool.connection() as conn:
            conn.execute(
                """
                UPSERT INTO servers (
                    hostname, ip, user_id, region, zone, status, 
                    cpu_count, mem_gb, disk_count, disk_size_gb, tags
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    sir.hostname,
                    sir.ip,
                    sir.user_id,
                    sir.region,
                    sir.zone,
                    status,
                    sir.cpu_count,
                    sir.mem_gb,
                    sir.disk_count,
                    sir.disk_size_gb,
                    sir.tags,
                ),
            )

    def server_update_status(self, hostname: str, status: ServerStatus) -> None:
        with self.pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE servers
                SET status = %s
                WHERE hostname = %s
                """,
                (
                    status,
                    hostname,
                ),
            )

    def get_servers(
        self,
        hostname: str | None = None,
    ) -> list[ServerInDB]:

        # Prepare the WHERE clause
        conditions = []
        params = []

        if hostname is not None:
            conditions.append("hostname = %s")
            params.append(hostname)

        sql = "SELECT * FROM servers "

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        with self.pool.connection() as conn:
            cur = conn.cursor(row_factory=class_row(ServerInDB))
            return cur.execute(sql, params).fetchall()

    def delete_server(self, hostname: str) -> None:
        with self.pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE
                FROM servers
                WHERE hostname = %s
                """,
                (hostname,),
            )

    #
    # COMPUTE UNIT
    #
    def insert_new_compute_unit(self, cudb: ComputeUnitInDB):
        with self.pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPSERT INTO compute_units (
                    hostname, cpu_range, cpu_count, 
                    cpu_set, port_range, cu_user,
                    status, started_at, tags
                ) 
                VALUES (
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s
                )
                """,
                (
                    cudb.hostname,
                    cudb.cpu_range,
                    cudb.cpu_count,
                    cudb.cpu_set,
                    cudb.port_range,
                    cudb.cu_user,
                    cudb.status,
                    cudb.started_at,
                    cudb.tags,
                ),
            )

    def update_compute_unit(
        self,
        compute_unit: str,
        status: ComputeUnitStatus | None,
        tags: dict | None = None,
    ) -> None:
        # mark the compute_unit to allocating
        with self.pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE compute_units
                SET 
                    status = coalesce(%s, status),
                    tags = coalesce(%s, tags)
                WHERE compute_id = %s
                """,
                (
                    status,
                    json.dumps(tags),
                    compute_unit,
                ),
            )

    def delete_compute_units(self, hostname: str) -> None:
        with self.pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE
                FROM compute_units
                WHERE hostname = %s
                """,
                (hostname,),
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
    ) -> list[ComputeUnitOverview]:

        # Prepare the WHERE clause
        conditions = []
        params = []

        if compute_id is not None:
            conditions.append("c.compute_id = %s")
            params.append(compute_id)

        if hostname is not None:
            conditions.append("s.hostname = %s")
            params.append(hostname)

        if region is not None:
            conditions.append("s.region = %s")
            params.append(region)

        if zone is not None:
            conditions.append("s.zone = %s")
            params.append(zone)

        if cpu_count is not None:
            conditions.append("c.cpu_count = %s")
            params.append(cpu_count)

        if deployment_id is not None:
            conditions.append("c.tags ->> 'deployment_id' = %s")
            params.append(deployment_id)

        if status is not None:
            conditions.append("c.status = %s")
            params.append(status)

        sql = """
            SELECT c.compute_id,
                c.hostname,
                c.cpu_range,
                s.ip,
                s.region,
                s.zone,
                c.cpu_set,
                c.port_range,
                c.cu_user,
                c.cpu_count,
                c.status,
                c.started_at,
                c.tags 
            FROM compute_units c JOIN servers s 
              ON c.hostname = s.hostname """

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        if limit:
            sql += f" LIMIT {limit}"

        with self.pool.connection() as conn:

            with conn.cursor(
                row_factory=class_row(ComputeUnitOverview),
            ) as cur:

                rs = cur.execute(sql, params).fetchall()  # type: ignore

                return rs

    # AUDIT
    def log_event(self, event: Event):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO event_log (ts, user_id, action, details)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        event.ts,
                        event.user_id,
                        event.action,
                        event.details,
                    ),
                )
