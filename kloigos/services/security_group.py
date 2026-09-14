from uuid import uuid4

from cpkit.audit import log_event

from kloigos.models import (
    AllocationInDB,
    ComputeUnitNotFoundError,
    ComputeUnitOperationError,
    Event,
    NetworkPolicyApplyCommand,
    QueueCommand,
    SecurityGroupAttachmentInDB,
    SecurityGroupCreateRequest,
    SecurityGroupDetail,
    SecurityGroupDirection,
    SecurityGroupInDB,
    SecurityGroupNotFoundError,
    SecurityGroupRuleCreateRequest,
    SecurityGroupRuleInDB,
    SecurityGroupUpdateRequest,
)

from ..repos import Repo


def _model_details(model) -> dict:
    return model.model_dump(mode="json")


class SecurityGroupService:
    """Manage reusable allocation network security groups."""

    def __init__(self, repo: Repo):
        self.repo = repo

    def list_security_groups(self) -> list[SecurityGroupInDB]:
        """Return all network security groups."""
        return self.repo.get_security_groups()

    def get_security_group(self, security_group_id: str) -> SecurityGroupDetail:
        """Return one network security group with rules and allocation attachments."""
        security_group = self._get_security_group(security_group_id)
        rules = self.repo.get_security_group_rules(security_group_id=security_group_id)
        attachments = self.repo.get_security_group_attachments(
            security_group_id=security_group_id
        )
        return self._security_group_detail(security_group, rules, attachments)

    def create_security_group(
        self,
        actor_id: str,
        req: SecurityGroupCreateRequest,
    ) -> SecurityGroupDetail:
        """Create a reusable network security group."""
        self._ensure_unique_name(req.name)
        security_group = self.repo.create_security_group(
            f"sg-{uuid4().hex[:12]}",
            req,
        )
        log_event(
            self.repo,
            actor_id,
            Event.SECURITY_GROUP_CREATED,
            _model_details(security_group),
        )
        return self._security_group_detail(security_group, [], [])

    def update_security_group(
        self,
        actor_id: str,
        security_group_id: str,
        req: SecurityGroupUpdateRequest,
    ) -> SecurityGroupDetail:
        """Update a network security group's name or description."""
        before = self.get_security_group(security_group_id)
        self._ensure_unique_name(req.name, exclude_security_group_id=security_group_id)
        updated = self.repo.update_security_group(security_group_id, req)
        if updated is None:
            raise SecurityGroupNotFoundError(
                f"Security group '{security_group_id}' was not found."
            )
        after = self.get_security_group(security_group_id)
        log_event(
            self.repo,
            actor_id,
            Event.SECURITY_GROUP_UPDATED,
            {
                "security_group_id": security_group_id,
                "old_state": _model_details(before),
                "new_state": _model_details(after),
            },
        )
        return after

    def delete_security_group(self, actor_id: str, security_group_id: str) -> bool:
        """Delete an unattached network security group."""
        before = self.get_security_group(security_group_id)
        if before.attached_allocations:
            raise ComputeUnitOperationError(
                f"Security group '{security_group_id}' is attached to allocations and cannot be deleted."
            )
        deleted = self.repo.delete_security_group(security_group_id)
        if deleted:
            log_event(
                self.repo,
                actor_id,
                Event.SECURITY_GROUP_DELETED,
                _model_details(before),
            )
        return deleted

    def add_rule(
        self,
        actor_id: str,
        security_group_id: str,
        req: SecurityGroupRuleCreateRequest,
    ) -> SecurityGroupRuleInDB:
        """Add one allow rule to a network security group."""
        self._get_security_group(security_group_id)
        self._ensure_unique_rule(security_group_id, req)
        rule = self.repo.create_security_group_rule(
            f"sgr-{uuid4().hex[:12]}",
            security_group_id,
            req,
        )
        log_event(
            self.repo,
            actor_id,
            Event.SECURITY_GROUP_RULE_ADDED,
            _model_details(rule),
        )
        self._enqueue_attached_host_reconciliations(security_group_id, actor_id)
        return rule

    def delete_rule(
        self,
        actor_id: str,
        security_group_id: str,
        rule_id: str,
    ) -> bool:
        """Delete one rule from a network security group."""
        self._get_security_group(security_group_id)
        rules = self.repo.get_security_group_rules(
            security_group_id=security_group_id,
            rule_id=rule_id,
        )
        if not rules:
            return False
        deleted = self.repo.delete_security_group_rule(security_group_id, rule_id)
        if deleted:
            log_event(
                self.repo,
                actor_id,
                Event.SECURITY_GROUP_RULE_DELETED,
                _model_details(rules[0]),
            )
            self._enqueue_attached_host_reconciliations(security_group_id, actor_id)
        return deleted

    def list_allocation_security_groups(
        self,
        allocation_id: str,
    ) -> list[SecurityGroupDetail]:
        """Return network security groups attached to one allocation."""
        self._get_allocation(allocation_id)
        attachments = self.repo.get_security_group_attachments(
            allocation_id=allocation_id
        )
        return [
            self.get_security_group(attachment.security_group_id)
            for attachment in attachments
        ]

    def attach_to_allocation(
        self,
        actor_id: str,
        allocation_id: str,
        security_group_id: str,
    ) -> SecurityGroupAttachmentInDB:
        """Attach a network security group to an allocation."""
        allocation = self._get_allocation(allocation_id)
        security_group = self._get_security_group(security_group_id)
        attachment = self.repo.attach_security_group(
            allocation.allocation_id,
            security_group.security_group_id,
        )
        log_event(
            self.repo,
            actor_id,
            Event.SECURITY_GROUP_ATTACHED,
            {
                **_model_details(attachment),
                "security_group_name": security_group.name,
            },
        )
        self._enqueue_host_reconciliation(allocation.current_host, actor_id)
        return attachment

    def detach_from_allocation(
        self,
        actor_id: str,
        allocation_id: str,
        security_group_id: str,
    ) -> bool:
        """Detach a network security group from an allocation."""
        self._get_allocation(allocation_id)
        self._get_security_group(security_group_id)
        deleted = self.repo.detach_security_group(allocation_id, security_group_id)
        if deleted:
            log_event(
                self.repo,
                actor_id,
                Event.SECURITY_GROUP_DETACHED,
                {
                    "allocation_id": allocation_id,
                    "security_group_id": security_group_id,
                },
            )
            allocation = self._get_allocation(allocation_id)
            self._enqueue_host_reconciliation(allocation.current_host, actor_id)
        return deleted

    def _get_security_group(self, security_group_id: str) -> SecurityGroupInDB:
        matches = self.repo.get_security_groups(security_group_id=security_group_id)
        if not matches:
            raise SecurityGroupNotFoundError(
                f"Security group '{security_group_id}' was not found."
            )
        return matches[0]

    def _get_allocation(self, allocation_id: str) -> AllocationInDB:
        matches = self.repo.get_allocations(allocation_id=allocation_id)
        if not matches:
            raise ComputeUnitNotFoundError(
                f"Allocation '{allocation_id}' was not found."
            )
        return matches[0]

    def _ensure_unique_name(
        self,
        name: str,
        exclude_security_group_id: str | None = None,
    ) -> None:
        matches = self.repo.get_security_groups(name=name)
        for match in matches:
            if match.security_group_id != exclude_security_group_id:
                raise ComputeUnitOperationError(
                    f"Security group name '{name}' already exists."
                )

    def _ensure_unique_rule(
        self,
        security_group_id: str,
        req: SecurityGroupRuleCreateRequest,
    ) -> None:
        for rule in self.repo.get_security_group_rules(
            security_group_id=security_group_id
        ):
            if (
                rule.direction == req.direction
                and rule.protocol == req.protocol
                and rule.port_from == req.port_from
                and rule.port_to == req.port_to
                and rule.cidr == req.cidr
                and rule.ip_version == req.ip_version
            ):
                raise ComputeUnitOperationError(
                    "An identical security group rule already exists."
                )

    def _enqueue_attached_host_reconciliations(
        self,
        security_group_id: str,
        actor_id: str,
    ) -> None:
        hostnames = {
            allocation.current_host
            for attachment in self.repo.get_security_group_attachments(
                security_group_id=security_group_id
            )
            for allocation in self.repo.get_allocations(
                allocation_id=attachment.allocation_id
            )
            if allocation.current_host
        }
        for hostname in sorted(hostnames):
            self._enqueue_host_reconciliation(hostname, actor_id)

    def _enqueue_host_reconciliation(
        self,
        hostname: str | None,
        actor_id: str,
    ) -> None:
        if hostname:
            self.repo.enqueue_command(
                QueueCommand.NETWORK_POLICY_APPLY,
                NetworkPolicyApplyCommand(hostname=hostname),
                actor_id,
            )

    def _security_group_detail(
        self,
        security_group: SecurityGroupInDB,
        rules: list[SecurityGroupRuleInDB],
        attachments: list[SecurityGroupAttachmentInDB],
    ) -> SecurityGroupDetail:
        return SecurityGroupDetail(
            **_model_details(security_group),
            ingress_rules=[
                rule
                for rule in rules
                if rule.direction == SecurityGroupDirection.INGRESS
            ],
            egress_rules=[
                rule
                for rule in rules
                if rule.direction == SecurityGroupDirection.EGRESS
            ],
            attached_allocations=[
                attachment.allocation_id for attachment in attachments
            ],
        )
