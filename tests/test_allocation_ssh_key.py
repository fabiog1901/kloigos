import datetime as dt
import unittest
from unittest.mock import MagicMock, patch

from cpkit.jobs.types import JobID
from fastapi import HTTPException, status
from pydantic import ValidationError

from kloigos.api.allocation import allocate
from kloigos.models import (
    AllocationCreateRequest,
    ComputeUnitOverview,
    IpPoolAddressInDB,
    SSHKeyInDB,
    SSHKeyNotFoundError,
)
from kloigos.services.allocation import AllocationService

PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDk65l+4HPbBZRt6mV7tHcvap3PrhCUo79iaCEdE1exx fabio@hp"
NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


class AllocationSSHKeyRequestTests(unittest.TestCase):
    def test_request_accepts_exactly_one_key_source(self) -> None:
        inline = AllocationCreateRequest(ssh_public_key=PUBLIC_KEY)
        named = AllocationCreateRequest(ssh_key_name="  workstation  ")

        self.assertEqual(inline.ssh_public_key, PUBLIC_KEY)
        self.assertEqual(named.ssh_key_name, "workstation")

        with self.assertRaises(ValidationError):
            AllocationCreateRequest()
        with self.assertRaises(ValidationError):
            AllocationCreateRequest(
                ssh_public_key=PUBLIC_KEY,
                ssh_key_name="workstation",
            )


class AllocationSSHKeyServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = MagicMock()
        self.repo.get_allocations.return_value = []
        self.repo.lock_compute_unit.return_value = ComputeUnitOverview(
            compute_id="host-a-cu01",
            hostname="host-a",
            ordinal=1,
            cpu_range="0-1",
            cpu_count=2,
            cpu_set="0,1",
            nofile=65536,
            status="ALLOCATING",
            server_private_ip="192.0.2.10",
            server_admin_user="admin",
            region="us-east",
            zone="us-east-1",
        )
        self.repo.lock_ip_pool_address.return_value = IpPoolAddressInDB(
            ip_address="192.0.2.20",
            status="RESERVED",
        )
        self.repo.enqueue_command.return_value = JobID(job_id=101)
        self.repo.get_ssh_keys.return_value = [
            SSHKeyInDB(
                name="workstation",
                algorithm="ssh-ed25519",
                public_key=PUBLIC_KEY,
                fingerprint="SHA256:example",
                creation_method="imported",
                created_at=NOW,
                updated_at=NOW,
            )
        ]
        self.service = AllocationService(self.repo)

    @patch("kloigos.services.allocation.log_event")
    def test_named_key_is_resolved_before_queuing_existing_command(
        self,
        log_event,
    ) -> None:
        response = self.service.allocate(
            "actor",
            AllocationCreateRequest(
                allocation_id="allocation-a",
                ssh_key_name="workstation",
            ),
        )

        self.assertEqual(response.job_id, 101)
        self.repo.get_ssh_keys.assert_called_once_with(name="workstation")
        command = self.repo.enqueue_command.call_args.args[1]
        self.assertEqual(command.ssh_public_key, PUBLIC_KEY)
        self.assertFalse(hasattr(command, "ssh_key_name"))

    @patch("kloigos.services.allocation.log_event")
    def test_inline_key_preserves_existing_command_contract(self, log_event) -> None:
        self.service.allocate(
            "actor",
            AllocationCreateRequest(
                allocation_id="allocation-a",
                ssh_public_key=PUBLIC_KEY,
            ),
        )

        self.repo.get_ssh_keys.assert_not_called()
        command = self.repo.enqueue_command.call_args.args[1]
        self.assertEqual(command.ssh_public_key, PUBLIC_KEY)

    def test_missing_named_key_fails_before_capacity_is_reserved(self) -> None:
        self.repo.get_ssh_keys.return_value = []

        with self.assertRaisesRegex(SSHKeyNotFoundError, "missing"):
            self.service.allocate(
                "actor",
                AllocationCreateRequest(ssh_key_name="missing"),
            )

        self.repo.lock_compute_unit.assert_not_called()
        self.repo.lock_ip_pool_address.assert_not_called()


class AllocationSSHKeyApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_named_key_returns_not_found(self) -> None:
        service = MagicMock()
        service.allocate.side_effect = SSHKeyNotFoundError("missing")

        with self.assertRaises(HTTPException) as raised:
            await allocate(
                AllocationCreateRequest(ssh_key_name="missing"),
                "actor",
                service,
            )

        self.assertEqual(raised.exception.status_code, status.HTTP_404_NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
