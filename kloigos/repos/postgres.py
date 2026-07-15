import json

from cpkit import CPKitRepo
from cpkit.db import execute_stmt, fetch_all, fetch_one, fetch_scalar
from psycopg_pool import ConnectionPool

from ..models import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    AllocationInDB,
    AllocationStatus,
    ComputeUnitInDB,
    ComputeUnitOverview,
    ComputeUnitStatus,
    IpAddressStatus,
    IpPoolAddressInDB,
    ServerHealthStatus,
    ServerInDB,
    ServerInitRequest,
    ServerStatus,
)


class PostgresRepo(CPKitRepo):
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool: ConnectionPool = pool

    def _server_init_tags(self, sir: ServerInitRequest) -> dict:
        tags = dict(sir.tags or {})
        tags["_kloigos_compute_units"] = [
            {
                "ordinal": unit.ordinal,
                "cpu_range": unit.cpu_range,
            }
            for unit in sir.compute_units
        ]
        return tags

    def server_init_new(
        self,
        sir: ServerInitRequest,
        status: ServerStatus,
    ) -> None:

        execute_stmt(
            """
            INSERT INTO servers (
                hostname, private_ip, public_ip, server_admin_user, region, zone, runtime_profile, status,
                cpu_count, mem_gb, disk_count, disk_size_gb, tags
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (hostname) DO UPDATE SET
                private_ip = EXCLUDED.private_ip,
                public_ip = EXCLUDED.public_ip,
                server_admin_user = EXCLUDED.server_admin_user,
                region = EXCLUDED.region,
                zone = EXCLUDED.zone,
                runtime_profile = EXCLUDED.runtime_profile,
                status = EXCLUDED.status,
                cpu_count = EXCLUDED.cpu_count,
                mem_gb = EXCLUDED.mem_gb,
                disk_count = EXCLUDED.disk_count,
                disk_size_gb = EXCLUDED.disk_size_gb,
                health_status = 'UNKNOWN',
                last_health_check_at = NULL,
                last_health_error = NULL,
                last_healthy_at = NULL,
                tags = EXCLUDED.tags
            """,
            (
                sir.hostname,
                sir.private_ip,
                sir.public_ip,
                sir.server_admin_user,
                sir.region,
                sir.zone,
                sir.runtime_profile,
                status,
                sir.cpu_count,
                sir.mem_gb,
                sir.disk_count,
                sir.disk_size_gb,
                self._server_init_tags(sir),
            ),
        )

    def server_update_status(self, hostname: str, status: ServerStatus) -> None:
        execute_stmt(
            """
            UPDATE servers
            SET
                status = %s,
                health_status = CASE
                    WHEN %s = 'READY' THEN 'HEALTHY'
                    WHEN %s IN ('DECOMMISSIONED', 'DECOMMISSION_FAIL') THEN 'UNKNOWN'
                    ELSE health_status
                END,
                last_health_check_at = CASE
                    WHEN %s = 'READY' THEN now()
                    ELSE last_health_check_at
                END,
                last_health_error = CASE
                    WHEN %s = 'READY' THEN NULL
                    ELSE last_health_error
                END,
                last_healthy_at = CASE
                    WHEN %s = 'READY' THEN now()
                    ELSE last_healthy_at
                END
            WHERE hostname = %s
            """,
            (
                status,
                status,
                status,
                status,
                status,
                status,
                hostname,
            ),
        )

    def update_server_health(
        self,
        hostname: str,
        health_status: ServerHealthStatus,
        error: str | None = None,
    ) -> None:
        execute_stmt(
            """
            UPDATE servers
            SET
                health_status = %s,
                last_health_check_at = now(),
                last_health_error = %s,
                last_healthy_at = CASE
                    WHEN %s = 'HEALTHY' THEN now()
                    ELSE last_healthy_at
                END
            WHERE hostname = %s
            """,
            (
                health_status,
                error,
                health_status,
                hostname,
            ),
        )

    def open_or_touch_alert(
        self,
        *,
        alert_type: AlertType,
        severity: AlertSeverity,
        resource_type: str,
        resource_id: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        execute_stmt(
            """
            INSERT INTO alerts (
                alert_type, severity, status, resource_type, resource_id,
                message, details
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (alert_type, resource_type, resource_id)
            WHERE status = 'OPEN'
            DO UPDATE SET
                severity = EXCLUDED.severity,
                last_seen_at = now(),
                message = EXCLUDED.message,
                details = EXCLUDED.details
            """,
            (
                alert_type,
                severity,
                AlertStatus.OPEN,
                resource_type,
                resource_id,
                message,
                json.dumps(details) if details is not None else None,
            ),
        )

    def resolve_alert(
        self,
        *,
        alert_type: AlertType,
        resource_type: str,
        resource_id: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        execute_stmt(
            """
            UPDATE alerts
            SET
                status = %s,
                resolved_at = now(),
                last_seen_at = now(),
                message = %s,
                details = coalesce(%s, details)
            WHERE alert_type = %s
              AND resource_type = %s
              AND resource_id = %s
              AND status = %s
            """,
            (
                AlertStatus.RESOLVED,
                message,
                json.dumps(details) if details is not None else None,
                alert_type,
                resource_type,
                resource_id,
                AlertStatus.OPEN,
            ),
        )

    def schedule_server_health_check(self, start_after_seconds: int) -> None:
        execute_stmt(
            """
            INSERT INTO cpkit.mq (msg_type, start_after)
            VALUES (
                'SERVER_HEALTH_CHECK',
                now() + (%s * INTERVAL '1s') + (random() * INTERVAL '10s')
            )
            """,
            (start_after_seconds,),
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

        return fetch_all(sql, tuple(params), ServerInDB)

    def delete_server(self, hostname: str) -> None:
        execute_stmt(
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
        execute_stmt(
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
                json.dumps(allocation.tags) if allocation.tags is not None else None,
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
        execute_stmt(
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
        execute_stmt(
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
        current_host: str | None = None,
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

        if current_host is not None:
            conditions.append("a.current_host = %s")
            params.append(current_host)

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

        return fetch_all(sql, tuple(params), AllocationInDB)

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
        execute_stmt(
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
        deleted = fetch_scalar(
            """
            DELETE
            FROM ip_pool
            WHERE ip_address = %s
            RETURNING 1
            """,
            (ip_address,),
        )
        return bool(deleted)

    def update_ip_pool_address(
        self,
        ip_address: str,
        *,
        status: IpAddressStatus | None = None,
        allocation_id: str | None = None,
        current_host: str | None = None,
    ) -> None:
        execute_stmt(
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
        execute_stmt(
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
        execute_stmt(
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

        return fetch_all(sql, tuple(params), IpPoolAddressInDB)

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

        return fetch_one(sql, tuple(params), IpPoolAddressInDB)

    #
    # COMPUTE UNIT
    #
    def insert_new_compute_unit(self, cudb: ComputeUnitInDB):
        execute_stmt(
            """
            INSERT INTO compute_units (
                hostname, ordinal, cpu_range, cpu_count,
                cpu_set,
                status, allocation_id, started_at, tags
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT DO NOTHING
            """,
            (
                cudb.hostname,
                cudb.ordinal,
                cudb.cpu_range,
                cudb.cpu_count,
                cudb.cpu_set,
                cudb.status,
                cudb.allocation_id,
                cudb.started_at,
                cudb.tags,
            ),
        )

    def update_compute_unit(
        self,
        compute_unit: str,
        status: ComputeUnitStatus | None = None,
        allocation_id: str | None = None,
        clear_allocation_id: bool = False,
        tags: dict | None = None,
    ) -> None:
        execute_stmt(
            """
            UPDATE compute_units
            SET
                status = coalesce(%s, status),
                allocation_id = CASE
                    WHEN %s THEN NULL
                    ELSE coalesce(%s, allocation_id)
                END,
                tags = coalesce(%s, tags)
            WHERE compute_id = %s
            """,
            (
                status,
                clear_allocation_id,
                allocation_id,
                json.dumps(tags) if tags is not None else None,
                compute_unit,
            ),
        )

    def delete_compute_units(self, hostname: str) -> None:
        execute_stmt(
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
                    s.server_admin_user,
                    s.region,
                    s.zone,
                    c.cpu_set,
                    c.cpu_count,
                    c.status,
                    c.allocation_id,
                    c.started_at,
                    c.tags 
                FROM compute_units c JOIN servers s 
                    ON c.hostname = s.hostname 
                WHERE c.status = %s
                  AND s.status = 'READY'
                  AND s.health_status = 'HEALTHY' """

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
            available_cu.server_admin_user,
            available_cu.region,
            available_cu.zone,
            compute_units.cpu_set,
            compute_units.cpu_count,
            compute_units.status,
            compute_units.allocation_id AS allocation_id,
            compute_units.started_at,
            compute_units.tags 
        """

        return fetch_one(sql, tuple(params), ComputeUnitOverview)

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
                s.server_admin_user,
                s.region,
                s.zone,
                c.cpu_set,
                c.cpu_count,
                c.status,
                c.allocation_id AS allocation_id,
                c.started_at,
                c.tags 
            FROM compute_units c JOIN servers s 
              ON c.hostname = s.hostname """

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY c.hostname, c.ordinal"

        if limit:
            sql += f" LIMIT {limit}"

        return fetch_all(sql, tuple(params), ComputeUnitOverview)
