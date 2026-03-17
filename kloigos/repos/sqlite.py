import datetime as dt
import json
import sqlite3

from ..models import (
    ApiKeyCreateRequest,
    ApiKeyRecord,
    ApiKeySummary,
    ComputeUnitInDB,
    ComputeUnitRequest,
    ComputeUnitStatus,
    LogMsg,
    Playbook,
    ServerInitRequest,
)
from .base import BaseRepo


class SQLiteRepo(BaseRepo):

    def __init__(self, db_url: str) -> None:
        self.db_url = db_url

    def get_api_key(self, access_key: str) -> ApiKeyRecord | None:
        with sqlite3.connect(self.db_url) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            rs = cur.execute(
                """
                SELECT access_key, encrypted_secret_access_key, owner, valid_until, roles
                FROM api_keys
                WHERE access_key = ?
                """,
                (access_key,),
            ).fetchone()

        if rs is None:
            return None

        valid_until = dt.datetime.fromisoformat(rs["valid_until"])
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=dt.timezone.utc)

        roles = json.loads(rs["roles"]) if rs["roles"] else None

        return ApiKeyRecord(
            access_key=rs["access_key"],
            encrypted_secret_access_key=rs["encrypted_secret_access_key"],
            owner=rs["owner"],
            valid_until=valid_until,
            roles=roles,
        )

    def list_api_keys(self, access_key: str | None = None) -> list[ApiKeySummary]:
        conditions = []
        params = []

        if access_key is not None:
            conditions.append("access_key = ?")
            params.append(access_key)

        sql = """
            SELECT access_key, owner, valid_until, roles
            FROM api_keys
        """
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY access_key"

        with sqlite3.connect(self.db_url) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()

        summaries: list[ApiKeySummary] = []
        for row in rows:
            valid_until = dt.datetime.fromisoformat(row["valid_until"])
            if valid_until.tzinfo is None:
                valid_until = valid_until.replace(tzinfo=dt.timezone.utc)
            roles = json.loads(row["roles"]) if row["roles"] else None
            summaries.append(
                ApiKeySummary(
                    access_key=row["access_key"],
                    owner=row["owner"],
                    valid_until=valid_until,
                    roles=roles,
                )
            )
        return summaries

    def create_api_key(
        self,
        api_key: ApiKeyCreateRequest,
        *,
        owner: str,
        encrypted_secret_access_key: bytes,
    ) -> ApiKeySummary:
        valid_until = api_key.valid_until
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=dt.timezone.utc)

        with sqlite3.connect(self.db_url) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO api_keys (
                    access_key,
                    encrypted_secret_access_key,
                    owner,
                    valid_until,
                    roles
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    api_key.access_key,
                    encrypted_secret_access_key,
                    owner,
                    valid_until.isoformat(),
                    json.dumps(api_key.roles) if api_key.roles is not None else None,
                ),
            )

        return ApiKeySummary(
            access_key=api_key.access_key,
            owner=owner,
            valid_until=valid_until,
            roles=api_key.roles,
        )

    def delete_api_key(self, access_key: str) -> None:
        with sqlite3.connect(self.db_url) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE
                FROM api_keys
                WHERE access_key = ?
                """,
                (access_key,),
            )

    def playbook_get_content(self, playbook: Playbook) -> str:

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

    def playbook_update_content(
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

    def server_init_new(self, isr: ServerInitRequest) -> None:

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
                    ComputeUnitStatus.INITIALIZING,
                    None,
                    "{}",
                ),
            )

    def server_update_status(self, hostname: str) -> None:
        with sqlite3.connect(self.db_url) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE compute_units
                SET status = ?
                WHERE hostname = ?
                """,
                (
                    ComputeUnitStatus.DECOMMISSIONING,
                    hostname,
                ),
            )

    def insert_new_compute_unit(
        self, compute_id: str, cpu_count: int, x, isr: ServerInitRequest
    ):
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
                    ComputeUnitStatus.FREE,
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
                (ComputeUnitStatus.INIT_FAIL, hostname),
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
                    (
                        ComputeUnitStatus.DECOMMISSIONED
                        if job_ok
                        else ComputeUnitStatus.DECOMMISSION_FAIL
                    ),
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
                (ComputeUnitStatus.ALLOCATING, json.dumps(req.tags), cu.compute_id),
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
                (ComputeUnitStatus.ALLOCATED, cu.compute_id),
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
                (ComputeUnitStatus.ALLOCATION_FAIL, cu.compute_id),
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

    def get_events(self) -> list[LogMsg]:
        return []

    def log_event(self, event: LogMsg):
        return None
