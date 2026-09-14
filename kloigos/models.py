import base64
import binascii
import datetime as dt
import ipaddress
from enum import StrEnum, auto
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AutoNameStrEnum(StrEnum):
    def _generate_next_value_(name, start, count, last_values):
        return name


class NoFreeComputeUnitError(Exception):
    pass


class NoFreeIpAddressError(Exception):
    pass


class ComputeUnitNotFoundError(Exception):
    pass


class ComputeUnitStateError(Exception):
    pass


class ComputeUnitOperationError(Exception):
    pass


class SecurityGroupNotFoundError(Exception):
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
    SERVER_INIT_REQUEST = auto()
    SERVER_INIT_DONE = auto()
    SERVER_INIT_FAILED = auto()
    SERVER_DECOMM_REQUEST = auto()
    SERVER_DECOMM_DONE = auto()
    SERVER_DECOMM_FAILED = auto()
    SERVER_DELETE_REQUEST = auto()
    SERVER_DELETE_DONE = auto()
    SERVER_DELETE_FAILED = auto()
    ALLOCATION_CREATE_REQUEST = auto()
    ALLOCATION_CREATE_DONE = auto()
    ALLOCATION_CREATE_FAILED = auto()
    DEALLOCATION_REQUEST = auto()
    DEALLOCATION_DONE = auto()
    DEALLOCATION_FAILED = auto()
    ALLOCATION_SCALE_REQUEST = auto()
    ALLOCATION_SCALE_DONE = auto()
    ALLOCATION_SCALE_FAILED = auto()
    IP_POOL_INSERT = auto()
    IP_POOL_DELETE = auto()
    SECURITY_GROUP_CREATED = auto()
    SECURITY_GROUP_UPDATED = auto()
    SECURITY_GROUP_DELETED = auto()
    SECURITY_GROUP_RULE_ADDED = auto()
    SECURITY_GROUP_RULE_DELETED = auto()
    SECURITY_GROUP_ATTACHED = auto()
    SECURITY_GROUP_DETACHED = auto()
    NETWORK_POLICY_APPLY_DONE = auto()
    NETWORK_POLICY_APPLY_FAILED = auto()


class Playbook(AutoNameStrEnum):
    ALLOCATION_CREATE = auto()
    ALLOCATION_DELETE = auto()
    ALLOCATION_SCALE = auto()
    SERVER_INIT = auto()
    SERVER_DECOMM = auto()
    SSH_CREDENTIAL_PREPARE = auto()
    SSH_CREDENTIAL_CLEANUP = auto()
    NETWORK_POLICY_APPLY = auto()


class QueueCommand(AutoNameStrEnum):
    ALLOCATION_CREATE = auto()
    ALLOCATION_DELETE = auto()
    ALLOCATION_SCALE = auto()
    SERVER_INIT = auto()
    SERVER_DECOMM = auto()
    SERVER_HEALTH_CHECK = auto()
    NETWORK_POLICY_APPLY = auto()


class ComputeUnitStatus(AutoNameStrEnum):
    # compute unit level statuses
    FREE = auto()
    ALLOCATING = auto()
    ALLOCATED = auto()
    ALLOCATION_FAIL = auto()
    DEALLOCATING = auto()
    DEALLOCATION_FAIL = auto()
    UNAVAILABLE = auto()


class AllocationStatus(AutoNameStrEnum):
    REQUESTED = auto()
    ALLOCATING = auto()
    ALLOCATED = auto()
    SCALING = auto()
    SCALE_FAIL = auto()
    DEALLOCATING = auto()
    DEALLOCATED = auto()
    ALLOCATION_FAIL = auto()
    DEALLOCATION_FAIL = auto()


class IpAddressStatus(AutoNameStrEnum):
    FREE = auto()
    RESERVED = auto()
    ALLOCATED = auto()
    RELEASING = auto()
    UNAVAILABLE = auto()


class ServerStatus(AutoNameStrEnum):
    # Server level statuses
    INITIALIZING = auto()
    INIT_FAIL = auto()
    READY = auto()
    DECOMMISSIONING = auto()
    DECOMMISSIONED = auto()
    DECOMMISSION_FAIL = auto()


class ServerHealthStatus(AutoNameStrEnum):
    UNKNOWN = auto()
    HEALTHY = auto()
    DEGRADED = auto()
    UNREACHABLE = auto()


class AlertType(AutoNameStrEnum):
    SERVER_UNHEALTHY = auto()


class AlertSeverity(AutoNameStrEnum):
    WARNING = auto()
    CRITICAL = auto()


class AlertStatus(AutoNameStrEnum):
    OPEN = auto()
    RESOLVED = auto()


class SecurityGroupDirection(AutoNameStrEnum):
    INGRESS = "ingress"
    EGRESS = "egress"


class SecurityGroupProtocol(AutoNameStrEnum):
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    ICMPV6 = "icmpv6"
    ALL = "all"


class SecurityGroupIpVersion(AutoNameStrEnum):
    IPV4 = "ipv4"
    IPV6 = "ipv6"


RUNTIME_PROFILES = {"minimal", "standard", "build"}
SSH_PUBLIC_KEY_TYPES = {
    "ssh-ed25519",
    "ssh-rsa",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
}


def _validate_ssh_public_key(value: str) -> str:
    text = str(value or "").strip()
    parts = text.split()
    if len(parts) < 2:
        raise ValueError("ssh_public_key must be an OpenSSH public key.")

    key_type, encoded_key = parts[0], parts[1]
    if key_type not in SSH_PUBLIC_KEY_TYPES:
        allowed = ", ".join(sorted(SSH_PUBLIC_KEY_TYPES))
        raise ValueError(f"ssh_public_key type must be one of: {allowed}.")

    try:
        decoded = base64.b64decode(encoded_key.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise ValueError("ssh_public_key key material is not valid base64.") from exc

    if len(decoded) < 32:
        raise ValueError("ssh_public_key key material is too short.")

    type_length = int.from_bytes(decoded[:4], "big")
    encoded_type = decoded[4 : 4 + type_length].decode("ascii", errors="ignore")
    if encoded_type != key_type:
        raise ValueError("ssh_public_key key material does not match its key type.")

    return text


class ComputeUnitInDB(BaseModel):
    compute_id: str
    hostname: str
    ordinal: int
    cpu_range: str
    cpu_count: int
    cpu_set: str
    status: str
    allocation_id: str | None = None
    started_at: dt.datetime | None = None
    tags: dict[str, Any] | None = None


class InitComputeUnit(BaseModel):
    ordinal: int
    cpu_range: str
    cpu_set: str
    cpu_count: int

    def as_playbook_vars(self) -> dict:
        return {
            "ordinal": self.ordinal,
            "cpu_range": self.cpu_range,
            "cpu_set": self.cpu_set,
            "cpu_count": self.cpu_count,
        }

    def as_compute_unit(self, hostname: str) -> ComputeUnitInDB:
        return ComputeUnitInDB(
            compute_id="",  # generated by the database
            hostname=hostname,
            ordinal=self.ordinal,
            cpu_range=self.cpu_range,
            cpu_count=self.cpu_count,
            cpu_set=self.cpu_set,
            status=ComputeUnitStatus.FREE,
        )


class ComputeUnitOverview(ComputeUnitInDB):
    server_private_ip: str
    server_public_ip: str | None = None
    server_admin_user: str
    region: str
    zone: str


class AllocationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allocation_id: str | None = None
    login_user: str | None = None
    cpu_count: int | None = None
    region: str | None = None
    zone: str | None = None
    tags: dict[str, Any] | None = None
    ssh_public_key: str

    @field_validator("ssh_public_key")
    @classmethod
    def validate_ssh_public_key(cls, value: str) -> str:
        return _validate_ssh_public_key(value)


class AllocationCreateCommand(BaseModel):
    allocation_id: str
    compute_id: str
    ssh_public_key: str


class AllocationCreateResponse(BaseModel):
    allocation_id: str
    job_id: int


class ServerHealthCheckCommand(BaseModel):
    pass


class NetworkPolicyApplyCommand(BaseModel):
    hostname: str


class AllocationDeallocateCommand(BaseModel):
    allocation_id: str
    compute_id: str


class AllocationScaleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu_count: int = Field(gt=0)
    region: str | None = None
    zone: str | None = None


class AllocationScaleCommand(AllocationScaleRequest):
    allocation_id: str


class AllocationInDB(BaseModel):
    allocation_id: str
    login_user: str
    ip_address: str
    compute_id: str | None = None
    current_host: str | None = None
    status: str
    tags: dict[str, Any] | None = None
    cpu_count: int | None = None
    cpu_range: str | None = None
    cpu_set: str | None = None
    memory_gb: float | None = None
    disk_size_gb: int | None = None
    region: str | None = None
    zone: str | None = None
    runtime_profile: str | None = None
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None


class IpPoolAddressInDB(BaseModel):
    ip_address: str
    status: str
    allocation_id: str | None = None
    current_host: str | None = None
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None


class IpPoolInsertRequest(BaseModel):
    ip_addresses: list[str] = Field(min_length=1)


class SecurityGroupCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("security group name cannot be empty.")
        return name


class SecurityGroupUpdateRequest(SecurityGroupCreateRequest):
    pass


class SecurityGroupInDB(BaseModel):
    security_group_id: str
    name: str
    description: str | None = None
    created_at: dt.datetime
    updated_at: dt.datetime


class SecurityGroupRuleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: SecurityGroupDirection
    protocol: SecurityGroupProtocol
    port_from: int | None = Field(default=None, ge=1, le=65535)
    port_to: int | None = Field(default=None, ge=1, le=65535)
    cidr: str
    ip_version: SecurityGroupIpVersion
    description: str | None = None

    @field_validator("cidr")
    @classmethod
    def normalize_cidr(cls, value: str) -> str:
        try:
            return str(ipaddress.ip_network(value.strip(), strict=False))
        except ValueError as exc:
            raise ValueError("cidr must be a valid IPv4 or IPv6 CIDR range.") from exc

    @model_validator(mode="after")
    def validate_rule(self):
        network = ipaddress.ip_network(self.cidr, strict=False)
        if self.ip_version is SecurityGroupIpVersion.IPV4 and network.version != 4:
            raise ValueError("ip_version is ipv4 but cidr is not an IPv4 range.")
        if self.ip_version is SecurityGroupIpVersion.IPV6 and network.version != 6:
            raise ValueError("ip_version is ipv6 but cidr is not an IPv6 range.")

        if (
            self.protocol is SecurityGroupProtocol.ICMPV6
            and self.ip_version is not SecurityGroupIpVersion.IPV6
        ):
            raise ValueError("icmpv6 rules must use ip_version ipv6.")
        if (
            self.protocol is SecurityGroupProtocol.ICMP
            and self.ip_version is not SecurityGroupIpVersion.IPV4
        ):
            raise ValueError("icmp rules must use ip_version ipv4.")

        has_port = self.port_from is not None or self.port_to is not None
        if (
            self.protocol
            in {
                SecurityGroupProtocol.ICMP,
                SecurityGroupProtocol.ICMPV6,
                SecurityGroupProtocol.ALL,
            }
            and has_port
        ):
            raise ValueError(f"{self.protocol.value} rules must not include ports.")

        if self.protocol in {SecurityGroupProtocol.TCP, SecurityGroupProtocol.UDP}:
            if self.port_from is None and self.port_to is not None:
                raise ValueError("port_from is required when port_to is set.")
            if self.port_from is not None and self.port_to is None:
                self.port_to = self.port_from
            if (
                self.port_from is not None
                and self.port_to is not None
                and self.port_from > self.port_to
            ):
                raise ValueError("port_from must be less than or equal to port_to.")

        return self


class SecurityGroupRuleInDB(SecurityGroupRuleCreateRequest):
    rule_id: str
    security_group_id: str
    created_at: dt.datetime


class SecurityGroupAttachmentInDB(BaseModel):
    allocation_id: str
    security_group_id: str
    attached_at: dt.datetime


class SecurityGroupDetail(SecurityGroupInDB):
    ingress_rules: list[SecurityGroupRuleInDB] = Field(default_factory=list)
    egress_rules: list[SecurityGroupRuleInDB] = Field(default_factory=list)
    attached_allocations: list[str] = Field(default_factory=list)


class EffectiveNetworkRule(BaseModel):
    direction: SecurityGroupDirection
    protocol: SecurityGroupProtocol
    port_from: int | None = None
    port_to: int | None = None
    cidr: str
    ip_version: SecurityGroupIpVersion
    source_rule_ids: list[str] = Field(default_factory=list)
    source_security_group_ids: list[str] = Field(default_factory=list)
    description: str | None = None

    def key(self) -> tuple:
        return (
            self.direction,
            self.protocol,
            self.port_from,
            self.port_to,
            self.cidr,
            self.ip_version,
        )


class AllocationNetworkPolicy(BaseModel):
    allocation_id: str
    login_user: str
    hostname: str
    ip_address: str
    ip_version: SecurityGroupIpVersion
    ingress_rules: list[EffectiveNetworkRule] = Field(default_factory=list)
    egress_rules: list[EffectiveNetworkRule] = Field(default_factory=list)


class HostNetworkPolicy(BaseModel):
    hostname: str
    allocations: list[AllocationNetworkPolicy] = Field(default_factory=list)


class BaseServer(BaseModel):
    hostname: str
    private_ip: str
    public_ip: str | None = None
    server_admin_user: str
    region: str
    zone: str | None = None
    runtime_profile: str = "standard"
    cpu_count: int | None = None
    mem_gb: int | None = None
    disk_count: int | None = None
    disk_size_gb: int | None = None
    tags: dict[str, Any] | None = None

    @field_validator("runtime_profile")
    @classmethod
    def validate_runtime_profile(cls, value: str) -> str:
        profile = (value or "standard").strip().lower()
        if profile not in RUNTIME_PROFILES:
            allowed = ", ".join(sorted(RUNTIME_PROFILES))
            raise ValueError(f"runtime_profile must be one of: {allowed}.")
        return profile


class ServerInDB(BaseServer):
    status: str
    health_status: str = ServerHealthStatus.UNKNOWN
    last_health_check_at: dt.datetime | None = None
    last_health_error: str | None = None
    last_healthy_at: dt.datetime | None = None


class AlertInDB(BaseModel):
    alert_id: int
    alert_type: str
    severity: str
    status: str
    resource_type: str
    resource_id: str
    first_seen_at: dt.datetime
    last_seen_at: dt.datetime
    resolved_at: dt.datetime | None = None
    message: str
    details: dict[str, Any] | None = None


class ServerComputeUnitInitSpec(BaseModel):
    ordinal: int = Field(gt=0)
    cpu_range: str


class ServerInitRequest(BaseServer):
    compute_units: list[ServerComputeUnitInitSpec]

    @model_validator(mode="after")
    def validate_compute_units(self):
        if not self.compute_units:
            raise ValueError("compute_units must contain at least one compute unit.")

        ordinals = [cu.ordinal for cu in self.compute_units]
        if len(set(ordinals)) != len(ordinals):
            raise ValueError("compute_units ordinals must be unique.")

        seen_cpus: set[int] = set()
        for cu in self.compute_units:
            cpu_ids = _cpu_ids_for_range(cu.cpu_range)
            if seen_cpus.intersection(cpu_ids):
                raise ValueError("compute_units cpu_range values must not overlap.")
            seen_cpus.update(cpu_ids)

        return self


class ServerDecommRequest(BaseModel):
    hostname: str
