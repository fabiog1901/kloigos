import datetime as dt
import unittest
from unittest.mock import MagicMock, patch

from cpkit.jobs.types import JobID

from kloigos.models import (
    AllocationInDB,
    SecurityGroupAttachmentInDB,
    SecurityGroupDirection,
    SecurityGroupInDB,
    SecurityGroupIpVersion,
    SecurityGroupProtocol,
    SecurityGroupRuleCreateRequest,
    SecurityGroupRuleInDB,
)
from kloigos.services.security_group import SecurityGroupService


NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


def _allocation(allocation_id: str, hostname: str | None) -> AllocationInDB:
    return AllocationInDB(
        allocation_id=allocation_id,
        login_user=allocation_id,
        ip_address="192.0.2.10",
        current_host=hostname,
        status="allocated",
    )


class SecurityGroupServiceJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = MagicMock()
        self.service = SecurityGroupService(self.repo)
        self.group = SecurityGroupInDB(
            security_group_id="sg-1",
            name="web",
            created_at=NOW,
            updated_at=NOW,
        )
        self.request = SecurityGroupRuleCreateRequest(
            direction=SecurityGroupDirection.INGRESS,
            protocol=SecurityGroupProtocol.TCP,
            port_from=443,
            cidr="10.0.0.0/24",
            ip_version=SecurityGroupIpVersion.IPV4,
        )
        self.rule = SecurityGroupRuleInDB(
            **self.request.model_dump(),
            rule_id="sgr-1",
            security_group_id=self.group.security_group_id,
            created_at=NOW,
        )
        self.attachment = SecurityGroupAttachmentInDB(
            allocation_id="alloc-a",
            security_group_id=self.group.security_group_id,
            attached_at=NOW,
        )
        self.repo.get_security_groups.return_value = [self.group]
        self.repo.create_security_group_rule.return_value = self.rule
        self.repo.attach_security_group.return_value = self.attachment

    def _set_allocations(self, allocations: dict[str, AllocationInDB]) -> None:
        self.repo.get_allocations.side_effect = lambda *, allocation_id: [
            allocations[allocation_id]
        ]

    def _return_host_jobs(self, job_ids: dict[str, int]) -> None:
        self.repo.enqueue_command.side_effect = (
            lambda command, payload, actor_id: JobID(
                job_id=job_ids[payload.hostname]
            )
        )

    @patch("kloigos.services.security_group.log_event")
    def test_add_rule_returns_one_job_per_unique_host_in_hostname_order(
        self,
        log_event,
    ) -> None:
        self.repo.get_security_group_rules.return_value = []
        self.repo.get_security_group_attachments.return_value = [
            SecurityGroupAttachmentInDB(
                allocation_id="alloc-b",
                security_group_id="sg-1",
                attached_at=NOW,
            ),
            SecurityGroupAttachmentInDB(
                allocation_id="alloc-a",
                security_group_id="sg-1",
                attached_at=NOW,
            ),
            SecurityGroupAttachmentInDB(
                allocation_id="alloc-c",
                security_group_id="sg-1",
                attached_at=NOW,
            ),
        ]
        self._set_allocations(
            {
                "alloc-a": _allocation("alloc-a", "host-a"),
                "alloc-b": _allocation("alloc-b", "host-b"),
                "alloc-c": _allocation("alloc-c", "host-a"),
            }
        )
        self._return_host_jobs({"host-a": 101, "host-b": 102})

        jobs = self.service.add_rule("actor", "sg-1", self.request)

        self.assertEqual([job.job_id for job in jobs], [101, 102])
        self.assertEqual(
            [call.args[1].hostname for call in self.repo.enqueue_command.call_args_list],
            ["host-a", "host-b"],
        )

    @patch("kloigos.services.security_group.log_event")
    def test_add_rule_returns_no_jobs_without_attached_hosts(self, log_event) -> None:
        self.repo.get_security_group_rules.return_value = []
        self.repo.get_security_group_attachments.return_value = []

        jobs = self.service.add_rule("actor", "sg-1", self.request)

        self.assertEqual(jobs, [])
        self.repo.enqueue_command.assert_not_called()

    @patch("kloigos.services.security_group.log_event")
    def test_delete_rule_returns_one_job_for_one_affected_host(
        self,
        log_event,
    ) -> None:
        self.repo.get_security_group_rules.return_value = [self.rule]
        self.repo.delete_security_group_rule.return_value = True
        self.repo.get_security_group_attachments.return_value = [self.attachment]
        self._set_allocations({"alloc-a": _allocation("alloc-a", "host-a")})
        self._return_host_jobs({"host-a": 103})

        jobs = self.service.delete_rule("actor", "sg-1", "sgr-1")

        self.assertEqual([job.job_id for job in jobs], [103])

    @patch("kloigos.services.security_group.log_event")
    def test_attach_returns_host_job_and_detach_hostless_returns_no_jobs(
        self,
        log_event,
    ) -> None:
        hosted = _allocation("alloc-a", "host-a")
        self.repo.get_allocations.return_value = [hosted]
        self._return_host_jobs({"host-a": 104})

        attached_jobs = self.service.attach_to_allocation("actor", "alloc-a", "sg-1")

        self.assertEqual([job.job_id for job in attached_jobs], [104])

        hostless = _allocation("alloc-a", None)
        self.repo.get_allocations.return_value = [hostless]
        self.repo.detach_security_group.return_value = True
        self.repo.enqueue_command.reset_mock()

        detached_jobs = self.service.detach_from_allocation(
            "actor",
            "alloc-a",
            "sg-1",
        )

        self.assertEqual(detached_jobs, [])
        self.repo.enqueue_command.assert_not_called()

    def test_missing_rule_and_attachment_are_distinct_from_zero_jobs(self) -> None:
        self.repo.get_security_group_rules.return_value = []
        self.assertIsNone(self.service.delete_rule("actor", "sg-1", "missing"))

        self.repo.get_allocations.return_value = [_allocation("alloc-a", "host-a")]
        self.repo.detach_security_group.return_value = False
        self.assertIsNone(
            self.service.detach_from_allocation("actor", "alloc-a", "sg-1")
        )


if __name__ == "__main__":
    unittest.main()
