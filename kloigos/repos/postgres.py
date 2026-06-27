import json

from cpkit import CPKitRepo
from psycopg.rows import class_row
from psycopg_pool import ConnectionPool

from ..models import (
    AllocationInDB,
    AllocationStatus,
    ComputeUnitInDB,
    ComputeUnitOverview,
    ComputeUnitStatus,
    IpAddressStatus,
    IpPoolAddressInDB,
    ServerInDB,
    ServerInitRequest,
    ServerStatus,
)


class PostgresRepo(CPKitRepo):
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool: ConnectionPool = pool

    def server_init_new(
        self,
        sir: ServerInitRequest,
        status: ServerStatus,
    ) -> None:

        with self.pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO servers (
                    hostname, private_ip, public_ip, server_admin_user, region, zone, status,
                    cpu_count, mem_gb, disk_count, disk_size_gb, tags
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT DO NOTHING
                """,
                (
                    sir.hostname,
                    sir.private_ip,
                    sir.public_ip,
                    sir.server_admin_user,
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
    # ALLOCATION
    #
    def insert_allocation(self, allocation: AllocationInDB) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO allocations (
                    allocation_id, login_user, ip_address, compute_id,
                    current_host, status, tags
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    allocation.allocation_id,
                    allocation.login_user,
                    allocation.ip_address,
                    allocation.compute_id,
                    allocation.current_host,
                    allocation.status,
                    (
                        json.dumps(allocation.tags)
                        if allocation.tags is not None
                        else None
                    ),
                ),
            )

    def update_allocation(
        self,
        allocation_id: str,
        *,
        status: AllocationStatus | None = None,
        compute_id: str | None = None,
        current_host: str | None = None,
        tags: dict | None = None,
    ) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                """
                UPDATE allocations
                SET
                    status = coalesce(%s, status),
                    compute_id = coalesce(%s, compute_id),
                    current_host = coalesce(%s, current_host),
                    tags = coalesce(%s, tags),
                    updated_at = now()
                WHERE allocation_id = %s
                """,
                (
                    status,
                    compute_id,
                    current_host,
                    json.dumps(tags) if tags is not None else None,
                    allocation_id,
                ),
            )

    def clear_allocation_placement(
        self,
        allocation_id: str,
        status: AllocationStatus | None = None,
    ) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                """
                UPDATE allocations
                SET
                    status = coalesce(%s, status),
                    compute_id = NULL,
                    current_host = NULL,
                    updated_at = now()
                WHERE allocation_id = %s
                """,
                (
                    status,
                    allocation_id,
                ),
            )

    def get_allocations(
        self,
        allocation_id: str | None = None,
        login_user: str | None = None,
        compute_id: str | None = None,
        ip_address: str | None = None,
        status: str | None = None,
    ) -> list[AllocationInDB]:
        conditions = []
        params = []

        if allocation_id is not None:
            conditions.append("a.allocation_id = %s")
            params.append(allocation_id)

        if login_user is not None:
            conditions.append("a.login_user = %s")
            params.append(login_user)

        if compute_id is not None:
            conditions.append("a.compute_id = %s")
            params.append(compute_id)

        if ip_address is not None:
            conditions.append("a.ip_address = %s")
            params.append(ip_address)

        if status is not None:
            conditions.append("a.status = %s")
            params.append(status)

        sql = "SELECT a.* FROM allocations a"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY a.created_at DESC, a.allocation_id"

        with self.pool.connection() as conn:
            cur = conn.cursor(row_factory=class_row(AllocationInDB))
            return cur.execute(sql, params).fetchall()

    #
    # IP POOL
    #
    def insert_ip_pool_address(
        self,
        ip_address: str,
        status: IpAddressStatus = IpAddressStatus.FREE,
        allocation_id: str | None = None,
        current_host: str | None = None,
    ) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO ip_pool (
                    ip_address, status, allocation_id, current_host
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    ip_address,
                    status,
                    allocation_id,
                    current_host,
                ),
            )

    def delete_ip_pool_address(self, ip_address: str) -> bool:
        with self.pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE
                FROM ip_pool
                WHERE ip_address = %s
                """,
                (ip_address,),
            )
            return cur.rowcount > 0

    def update_ip_pool_address(
        self,
        ip_address: str,
        *,
        status: IpAddressStatus | None = None,
        allocation_id: str | None = None,
        current_host: str | None = None,
    ) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                """
                UPDATE ip_pool
                SET
                    status = coalesce(%s, status),
                    allocation_id = coalesce(%s, allocation_id),
                    current_host = coalesce(%s, current_host),
                    updated_at = now()
                WHERE ip_address = %s
                """,
                (
                    status,
                    allocation_id,
                    current_host,
                    ip_address,
                ),
            )

    def release_ip_pool_address(
        self,
        ip_address: str,
        status: IpAddressStatus = IpAddressStatus.FREE,
    ) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                """
                UPDATE ip_pool
                SET
                    status = %s,
                    allocation_id = NULL,
                    current_host = NULL,
                    updated_at = now()
                WHERE ip_address = %s
                """,
                (
                    status,
                    ip_address,
                ),
            )

    def clear_ip_pool_host(
        self,
        ip_address: str,
        status: IpAddressStatus | None = None,
    ) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                """
                UPDATE ip_pool
                SET
                    status = coalesce(%s, status),
                    current_host = NULL,
                    updated_at = now()
                WHERE ip_address = %s
                """,
                (
                    status,
                    ip_address,
                ),
            )

    def get_ip_pool_addresses(
        self,
        ip_address: str | None = None,
        status: str | None = None,
        allocation_id: str | None = None,
        current_host: str | None = None,
    ) -> list[IpPoolAddressInDB]:
        conditions = []
        params = []

        if ip_address is not None:
            conditions.append("ip_address = %s")
            params.append(ip_address)

        if status is not None:
            conditions.append("status = %s")
            params.append(status)

        if allocation_id is not None:
            conditions.append("allocation_id = %s")
            params.append(allocation_id)

        if current_host is not None:
            conditions.append("current_host = %s")
            params.append(current_host)

        sql = "SELECT * FROM ip_pool"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY ip_address"

        with self.pool.connection() as conn:
            cur = conn.cursor(row_factory=class_row(IpPoolAddressInDB))
            return cur.execute(sql, params).fetchall()

    def lock_ip_pool_address(
        self,
        free_status: IpAddressStatus,
        reserved_status: IpAddressStatus,
        ip_address: str | None = None,
    ) -> IpPoolAddressInDB | None:
        conditions = ["status = %s"]
        params = [free_status]

        if ip_address is not None:
            conditions.append("ip_address = %s")
            params.append(ip_address)

        params.append(reserved_status)
        params.append(free_status)

        sql = f"""
            WITH available_ip AS (
                SELECT ip_address
                FROM ip_pool
                WHERE {" AND ".join(conditions)}
                ORDER BY ip_address
                LIMIT 1
            )
            UPDATE ip_pool
            SET status = %s,
                updated_at = now()
            FROM available_ip
            WHERE ip_pool.ip_address = available_ip.ip_address
              AND ip_pool.status = %s
            RETURNING
                ip_pool.ip_address,
                ip_pool.status,
                ip_pool.allocation_id,
                ip_pool.current_host,
                ip_pool.created_at,
                ip_pool.updated_at
        """

        with self.pool.connection() as conn:
            cur = conn.cursor(row_factory=class_row(IpPoolAddressInDB))
            return cur.execute(sql, params).fetchone()

    #
    # COMPUTE UNIT
    #
    def insert_new_compute_unit(self, cudb: ComputeUnitInDB):
        with self.pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO compute_units (
                    hostname, ordinal, cpu_range, cpu_count, 
                    cpu_set, private_ip, public_ip,
                    status, started_at, tags
                ) 
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT DO NOTHING
                """,
                (
                    cudb.hostname,
                    cudb.ordinal,
                    cudb.cpu_range,
                    cudb.cpu_count,
                    cudb.cpu_set,
                    cudb.private_ip,
                    cudb.public_ip,
                    cudb.status,
                    cudb.started_at,
                    cudb.tags,
                ),
            )

    def update_compute_unit(
        self,
        compute_unit: str,
        status: ComputeUnitStatus | None = None,
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
                    json.dumps(tags) if tags is not None else None,
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

    def lock_compute_unit(
        self,
        free_status: ComputeUnitStatus,
        allocated_status: ComputeUnitStatus,
        compute_id: str | None = None,
        region: str | None = None,
        zone: str | None = None,
        cpu_count: int | None = None,
    ) -> ComputeUnitOverview:

        # Prepare the WHERE clause
        conditions = []
        params = []

        params.append(free_status)

        if compute_id is not None:
            conditions.append("c.compute_id = %s")
            params.append(compute_id)

        if region is not None:
            conditions.append("s.region = %s")
            params.append(region)

        if zone is not None:
            conditions.append("s.zone = %s")
            params.append(zone)

        if cpu_count is not None:
            conditions.append("c.cpu_count = %s")
            params.append(cpu_count)

        params.append(allocated_status)
        params.append(free_status)

        sql = """
            WITH 
            available_cu AS (
                SELECT 
                    c.compute_id,
                    c.hostname,
                    c.ordinal,
                    c.cpu_range,
                    s.private_ip AS server_private_ip,
                    s.public_ip AS server_public_ip,
                    s.region,
                    s.zone,
                    c.cpu_set,
                    c.private_ip,
                    c.public_ip,
                    c.cpu_count,
                    c.status,
                    c.started_at,
                    c.tags 
                FROM compute_units c JOIN servers s 
                    ON c.hostname = s.hostname 
                WHERE c.status = %s """

        if conditions:
            sql += " AND " + " AND ".join(conditions)

        sql += """ ORDER BY c.hostname, c.ordinal LIMIT 1)
        UPDATE compute_units
        SET status = %s
        FROM available_cu
        WHERE compute_units.compute_id = available_cu.compute_id
          AND compute_units.status = %s
        RETURNING 
            compute_units.compute_id,
            compute_units.hostname,
            compute_units.ordinal,
            compute_units.cpu_range,
            available_cu.server_private_ip,
            available_cu.server_public_ip,
            available_cu.region,
            available_cu.zone,
            compute_units.cpu_set,
            compute_units.private_ip,
            compute_units.public_ip,
            compute_units.cpu_count,
            compute_units.status,
            compute_units.started_at,
            compute_units.tags 
        """

        with self.pool.connection() as conn:

            with conn.cursor(
                row_factory=class_row(ComputeUnitOverview),
            ) as cur:

                rs = cur.execute(sql, params).fetchone()  # type: ignore

                return rs

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
                c.ordinal,
                c.cpu_range,
                s.private_ip AS server_private_ip,
                s.public_ip AS server_public_ip,
                s.region,
                s.zone,
                c.cpu_set,
                c.private_ip,
                c.public_ip,
                c.cpu_count,
                c.status,
                c.started_at,
                c.tags 
            FROM compute_units c JOIN servers s 
              ON c.hostname = s.hostname """

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY c.hostname, c.ordinal"

        if limit:
            sql += f" LIMIT {limit}"

        with self.pool.connection() as conn:

            with conn.cursor(
                row_factory=class_row(ComputeUnitOverview),
            ) as cur:

                rs = cur.execute(sql, params).fetchall()  # type: ignore

                return rs
