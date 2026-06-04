import datetime as dt
from enum import StrEnum, auto
from typing import Any, Callable

from pydantic import BaseModel, Field, model_validator


class AutoNameStrEnum(StrEnum):
    def _generate_next_value_(name, start, count, last_values):
        return name


class NoFreeComputeUnitError(Exception):
    pass


class ComputeUnitNotFoundError(Exception):
    pass


class ComputeUnitStateError(Exception):
    pass


class ComputeUnitOperationError(Exception):
    pass


class AllocatePlaybookError(Exception):
    pass


class ApiKeyNotFoundError(Exception):
    pass


class InvalidApiKeyValidityError(Exception):
    pass


class SettingNotFoundError(Exception):
    pass


class ServerNotFoundError(Exception):
    pass


class ServerStateError(Exception):
    pass


def _cpu_ids_for_range(cpu_range: str) -> set[int]:
    raw_range = cpu_range.strip()
    if not raw_range:
        raise ValueError("cpu_range is empty.")

    step = 1
    if ":" in raw_range:
        raw_range, raw_step = raw_range.split(":", 1)
        step = int(raw_step)
        if step <= 0:
            raise ValueError("cpu_range step must be positive.")

    if "-" in raw_range:
        raw_start, raw_end = raw_range.split("-", 1)
        start = int(raw_start)
        end = int(raw_end)
    else:
        start = end = int(raw_range)

    if start < 0 or end < start:
        raise ValueError("cpu_range must be a non-negative start-end range.")

    return set(range(start, end + 1, step))


class Event(AutoNameStrEnum):
    LOGIN = auto()
    LOGOUT = auto()
    UPDATE_PLAYBOOK = auto()
    API_KEY_CREATE = auto()
    API_KEY_DELETE = auto()
    SETTING_UPDATE = auto()
    SETTING_RESET = auto()
    SERVER_INIT_REQUEST = auto()
    SERVER_INIT_DONE = auto()
    SERVER_INIT_FAILED = auto()
    SERVER_DECOMM_REQUEST = auto()
    SERVER_DECOMM_DONE = auto()
    SERVER_DECOMM_FAILED = auto()
    SERVER_DELETE_REQUEST = auto()
    SERVER_DELETE_DONE = auto()
    SERVER_DELETE_FAILED = auto()
    CU_ALLOCATION_REQUEST = auto()
    CU_ALLOCATION_DONE = auto()
    CU_ALLOCATION_FAILED = auto()
    CU_DEALLOCATION_REQUEST = auto()
    CU_DEALLOCATION_DONE = auto()
    CU_DEALLOCATION_FAILED = auto()


class KloigosRole(AutoNameStrEnum):
    KLOIGOS_READONLY = auto()
    KLOIGOS_USER = auto()
    KLOIGOS_ADMIN = auto()


class SettingKey(AutoNameStrEnum):
    KLOIGOS_ENTERPRISE_LICENSE_KEY = auto()
    OIDC_ENABLED = auto()
    OIDC_ISSUER_URL = auto()
    OIDC_CLIENT_ID = auto()
    OIDC_CLIENT_SECRET = auto()
    OIDC_SCOPES = auto()
    OIDC_AUDIENCE = auto()
    OIDC_EXTRA_AUTH_PARAMS = auto()
    OIDC_REDIRECT_URI = auto()
    OIDC_LOGIN_PATH = auto()
    OIDC_SESSION_COOKIE_NAME = auto()
    OIDC_STATE_COOKIE_NAME = auto()
    OIDC_NONCE_COOKIE_NAME = auto()
    OIDC_NEXT_COOKIE_NAME = auto()
    OIDC_COOKIE_SECURE = auto()
    OIDC_COOKIE_SAMESITE = auto()
    OIDC_COOKIE_DOMAIN = auto()
    OIDC_VERIFY_AUDIENCE = auto()
    OIDC_UI_USERNAME_CLAIM = auto()
    OIDC_AUTHZ_READONLY_GROUPS = auto()
    OIDC_AUTHZ_USER_GROUPS = auto()
    OIDC_AUTHZ_ADMIN_GROUPS = auto()
    OIDC_AUTHZ_GROUPS_CLAIM = auto()


class SettingRecord(BaseModel):
    key: SettingKey
    value: str | None = None
    default_value: str
    effective_value: str
    value_type: str
    category: str
    is_secret: bool = False
    description: str = ""
    updated_at: dt.datetime
    updated_by: str | None = None


class SettingUpdateRequest(BaseModel):
    value: str


class LogMsg(BaseModel):
    ts: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    user_id: str
    action: Event
    details: dict[str, Any] | None = None
    request_id: str | None = None


class ApiKeyRecord(BaseModel):
    access_key: str
    encrypted_secret_access_key: bytes
    owner: str
    valid_until: dt.datetime
    roles: list[KloigosRole] | None = None


class ApiKeySummary(BaseModel):
    access_key: str
    owner: str
    valid_until: dt.datetime
    roles: list[KloigosRole] | None = None


class ApiKeyCreateRequest(BaseModel):
    valid_until: dt.datetime
    roles: list[KloigosRole] | None = None


class ApiKeyCreateRequestInDB(ApiKeyCreateRequest):
    access_key: str


class ApiKeyCreateResponse(ApiKeySummary):
    secret_access_key: str


class DeferredTask(BaseModel):
    fn: Callable[..., None]
    args: tuple | None
    kwargs: dict = {}


class Playbook(AutoNameStrEnum):
    # compute unit level statuses
    CU_ALLOCATE = auto()
    CU_DEALLOCATE = auto()
    SERVER_INIT = auto()
    SERVER_DECOMM = auto()


class ComputeUnitStatus(AutoNameStrEnum):
    # compute unit level statuses
    FREE = auto()
    ALLOCATING = auto()
    ALLOCATED = auto()
    ALLOCATION_FAIL = auto()
    DEALLOCATING = auto()
    DEALLOCATION_FAIL = auto()
    UNAVAILABLE = auto()


class ServerStatus(AutoNameStrEnum):
    # Server level statuses
    INITIALIZING = auto()
    INIT_FAIL = auto()
    READY = auto()
    DECOMMISSIONING = auto()
    DECOMMISSIONED = auto()
    DECOMMISSION_FAIL = auto()


class ComputeUnitInDB(BaseModel):
    compute_id: str
    hostname: str
    ordinal: int
    cpu_range: str
    cpu_count: int
    cpu_set: str
    private_ip: str
    public_ip: str | None = None
    cu_user: str
    status: str
    started_at: dt.datetime | None = None
    tags: dict[str, Any] | None = None


class InitComputeUnit(BaseModel):
    ordinal: int
    cu_user: str
    cpu_range: str
    cpu_set: str
    cpu_count: int
    private_ip: str
    public_ip: str | None = None

    def as_playbook_vars(self) -> dict:
        return {
            "ordinal": self.ordinal,
            "cu_user": self.cu_user,
            "cpu_range": self.cpu_range,
            "cpu_set": self.cpu_set,
            "cpu_count": self.cpu_count,
            "private_ip": self.private_ip,
            "public_ip": self.public_ip,
        }

    def as_compute_unit(self, hostname: str) -> ComputeUnitInDB:
        return ComputeUnitInDB(
            compute_id="",  # generated by the database
            hostname=hostname,
            ordinal=self.ordinal,
            cpu_range=self.cpu_range,
            cpu_count=self.cpu_count,
            cpu_set=self.cpu_set,
            private_ip=self.private_ip,
            public_ip=self.public_ip,
            cu_user=self.cu_user,
            status=ComputeUnitStatus.FREE,
        )


class ComputeUnitOverview(ComputeUnitInDB):
    server_private_ip: str
    server_public_ip: str | None = None
    region: str
    zone: str


class ComputeUnitRequest(BaseModel):
    compute_id: str | None = None
    cpu_count: int | None = None
    region: str | None = None
    zone: str | None = None
    tags: dict[str, str | int | list[str]] | None
    ssh_public_key: str


class BaseServer(BaseModel):
    hostname: str
    private_ip: str
    public_ip: str | None = None
    user_id: str
    region: str
    zone: str | None = None
    cpu_count: int | None = None
    mem_gb: int | None = None
    disk_count: int | None = None
    disk_size_gb: int | None = None
    tags: dict[str, Any] | None = None


class ServerInDB(BaseServer):
    status: str


class ServerComputeUnitInitSpec(BaseModel):
    ordinal: int = Field(gt=0)
    cpu_range: str
    private_ip: str
    public_ip: str | None = None


class ServerInitRequest(BaseServer):
    compute_units: list[ServerComputeUnitInitSpec]

    @model_validator(mode="after")
    def validate_compute_units(self):
        if not self.compute_units:
            raise ValueError("compute_units must contain at least one compute unit.")

        ordinals = [cu.ordinal for cu in self.compute_units]
        if len(set(ordinals)) != len(ordinals):
            raise ValueError("compute_units ordinals must be unique.")

        private_ips = [cu.private_ip for cu in self.compute_units]
        if len(set(private_ips)) != len(private_ips):
            raise ValueError("compute_units private_ip values must be unique.")

        public_ips = [
            cu.public_ip for cu in self.compute_units if cu.public_ip is not None
        ]
        if len(set(public_ips)) != len(public_ips):
            raise ValueError("compute_units public_ip values must be unique.")

        seen_cpus: set[int] = set()
        for cu in self.compute_units:
            cpu_ids = _cpu_ids_for_range(cu.cpu_range)
            if seen_cpus.intersection(cpu_ids):
                raise ValueError("compute_units cpu_range values must not overlap.")
            seen_cpus.update(cpu_ids)

        return self


class ServerDecommRequest(BaseModel):
    hostname: str
