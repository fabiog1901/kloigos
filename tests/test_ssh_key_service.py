import datetime as dt
import unittest
from unittest.mock import MagicMock, patch

from kloigos.models import (
    ComputeUnitOperationError,
    Event,
    SSHKeyCreateRequest,
    SSHKeyCreationMethod,
    SSHKeyInDB,
    SSHKeyNotFoundError,
)
from kloigos.services.ssh_key import SSHKeyService

PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDk65l+4HPbBZRt6mV7tHcvap3PrhCUo79iaCEdE1exx fabio@hp"
NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


def _stored_key(source) -> SSHKeyInDB:
    return SSHKeyInDB(
        **source.model_dump(),
        created_at=NOW,
        updated_at=NOW,
    )


class SSHKeyServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = MagicMock()
        self.repo.get_ssh_keys.return_value = []
        self.repo.create_ssh_key.side_effect = _stored_key
        self.service = SSHKeyService(self.repo)

    @patch("kloigos.services.ssh_key.log_event")
    def test_import_calculates_metadata_and_returns_no_private_key(
        self,
        log_event,
    ) -> None:
        result = self.service.create_ssh_key(
            "actor",
            SSHKeyCreateRequest(name="workstation", public_key=PUBLIC_KEY),
        )

        stored = self.repo.create_ssh_key.call_args.args[0]
        self.assertEqual(stored.name, "workstation")
        self.assertEqual(stored.algorithm, "ssh-ed25519")
        self.assertEqual(stored.creation_method, SSHKeyCreationMethod.IMPORTED)
        self.assertEqual(
            stored.fingerprint,
            "SHA256:WnE3YF9NpZSKOShzSvLoW7NHgEX8Jp5LL9hG9R0Wvrg",
        )
        self.assertIsNone(result.private_key)
        self.assertEqual(log_event.call_args.args[2], Event.SSH_KEY_CREATED)
        self.assertNotIn("public_key", log_event.call_args.args[3])
        self.assertNotIn("private_key", log_event.call_args.args[3])

    @patch("kloigos.services.ssh_key.log_event")
    def test_generate_defaults_to_ed25519_and_returns_private_key_once(
        self,
        log_event,
    ) -> None:
        result = self.service.create_ssh_key(
            "actor",
            SSHKeyCreateRequest(name="generated", generate=True),
        )

        stored = self.repo.create_ssh_key.call_args.args[0]
        self.assertEqual(stored.algorithm, "ssh-ed25519")
        self.assertTrue(stored.public_key.startswith("ssh-ed25519 "))
        self.assertEqual(stored.creation_method, SSHKeyCreationMethod.GENERATED)
        self.assertIn("BEGIN OPENSSH PRIVATE KEY", result.private_key)
        self.assertNotIn("private_key", stored.model_dump())
        self.assertNotIn("private_key", log_event.call_args.args[3])

    def test_duplicate_name_is_rejected_before_key_generation(self) -> None:
        self.repo.get_ssh_keys.return_value = [MagicMock()]

        with self.assertRaisesRegex(ComputeUnitOperationError, "already exists"):
            self.service.create_ssh_key(
                "actor",
                SSHKeyCreateRequest(name="duplicate", generate=True),
            )

        self.repo.create_ssh_key.assert_not_called()

    def test_list_and_get_return_stored_public_records(self) -> None:
        stored = SSHKeyInDB(
            name="workstation",
            algorithm="ssh-ed25519",
            public_key=PUBLIC_KEY,
            fingerprint="SHA256:example",
            creation_method="imported",
            created_at=NOW,
            updated_at=NOW,
        )
        self.repo.get_ssh_keys.return_value = [stored]

        self.assertEqual(self.service.list_ssh_keys(), [stored])
        self.assertIs(self.service.get_ssh_key("workstation"), stored)

    def test_get_missing_key_raises_not_found(self) -> None:
        with self.assertRaisesRegex(SSHKeyNotFoundError, "missing"):
            self.service.get_ssh_key("missing")

    @patch("kloigos.services.ssh_key.log_event")
    def test_delete_audits_public_metadata(self, log_event) -> None:
        stored = SSHKeyInDB(
            name="workstation",
            algorithm="ssh-ed25519",
            public_key=PUBLIC_KEY,
            fingerprint="SHA256:example",
            creation_method="imported",
            created_at=NOW,
            updated_at=NOW,
        )
        self.repo.get_ssh_keys.return_value = [stored]
        self.repo.delete_ssh_key.return_value = True

        self.assertTrue(self.service.delete_ssh_key("actor", "workstation"))
        self.assertEqual(log_event.call_args.args[2], Event.SSH_KEY_DELETED)
        self.assertNotIn("public_key", log_event.call_args.args[3])


if __name__ == "__main__":
    unittest.main()
