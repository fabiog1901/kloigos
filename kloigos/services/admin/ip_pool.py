from cpkit.audit import log_event

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

        log_event(
            self.repo,
            actor_id,
            Event.IP_POOL_UPSERT,
            req.model_dump(),
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

        log_event(
            self.repo,
            actor_id,
            Event.IP_POOL_UPDATE,
            {
                "ip_address": ip_address,
                **req.model_dump(),
            },
        )

        matches = self.repo.get_ip_pool_addresses(ip_address=ip_address)
        return matches[0] if matches else None

    def release_ip_pool_address(
        self,
        actor_id: str,
        allocation_id: str,
    ) -> IpPoolAddressInDB | None:
        matches = self.repo.get_ip_pool_addresses(allocation_id=allocation_id)
        if not matches:
            return None

        ip_address = matches[0].ip_address
        self.repo.release_ip_pool_address(
            ip_address=ip_address,
            status=IpAddressStatus.FREE,
        )

        log_event(
            self.repo,
            actor_id,
            Event.IP_POOL_RELEASE,
            {
                "allocation_id": allocation_id,
                "ip_address": ip_address,
            },
        )

        matches = self.repo.get_ip_pool_addresses(ip_address=ip_address)
        return matches[0] if matches else None
