from cpkit.audit import AuditLogRecord
from cpkit.logging import request_id_ctx

from ...models import (
    Event,
    IpAddressStatus,
    IpPoolAddressInDB,
    IpPoolUpdateRequest,
    IpPoolUpsertRequest,
)
from .base import AdminServiceBase


class IpPoolAdminService(AdminServiceBase):
    def list_ip_pool_addresses(
        self,
        ip_address: str | None = None,
        status: str | None = None,
        allocation_id: str | None = None,
        current_host: str | None = None,
    ) -> list[IpPoolAddressInDB]:
        return self.repo.get_ip_pool_addresses(
            ip_address=ip_address,
            status=status,
            allocation_id=allocation_id,
            current_host=current_host,
        )

    def upsert_ip_pool_addresses(
        self,
        actor_id: str,
        req: IpPoolUpsertRequest,
    ) -> list[IpPoolAddressInDB]:
        # Floating IPs are durable allocation resources, so admins manage them
        # independently from server/CU initialization.
        for ip_address in req.ip_addresses:
            self.repo.upsert_ip_pool_address(
                ip_address=ip_address,
                status=req.status,
                current_host=req.current_host,
            )

        self.repo.log_event(
            AuditLogRecord(
                user_id=actor_id,
                action=Event.IP_POOL_UPSERT,
                details=req.model_dump(),
                request_id=request_id_ctx.get(),
            )
        )

        return self.repo.get_ip_pool_addresses()

    def update_ip_pool_address(
        self,
        actor_id: str,
        ip_address: str,
        req: IpPoolUpdateRequest,
    ) -> IpPoolAddressInDB | None:
        self.repo.update_ip_pool_address(
            ip_address=ip_address,
            status=req.status,
            allocation_id=req.allocation_id,
            current_host=req.current_host,
        )

        self.repo.log_event(
            AuditLogRecord(
                user_id=actor_id,
                action=Event.IP_POOL_UPDATE,
                details={
                    "ip_address": ip_address,
                    **req.model_dump(),
                },
                request_id=request_id_ctx.get(),
            )
        )

        matches = self.repo.get_ip_pool_addresses(ip_address=ip_address)
        return matches[0] if matches else None

    def release_ip_pool_address(
        self,
        actor_id: str,
        ip_address: str,
    ) -> IpPoolAddressInDB | None:
        self.repo.release_ip_pool_address(
            ip_address=ip_address,
            status=IpAddressStatus.FREE,
        )

        self.repo.log_event(
            AuditLogRecord(
                user_id=actor_id,
                action=Event.IP_POOL_RELEASE,
                details={"ip_address": ip_address},
                request_id=request_id_ctx.get(),
            )
        )

        matches = self.repo.get_ip_pool_addresses(ip_address=ip_address)
        return matches[0] if matches else None
