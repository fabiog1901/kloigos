import datetime as dt
import unittest
from unittest.mock import MagicMock, patch

from psycopg.errors import UniqueViolation

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
PRIVATE_KEY_SENTINEL = "KLOIGOS-PRIVATE-KEY-SENTINEL"
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

    def _sentinel_private_key(self) -> MagicMock:
        private_key = MagicMock()
        private_key.public_key.return_value.public_bytes.return_value = (
            PUBLIC_KEY.encode("ascii")
        )
        private_key.private_bytes.return_value = PRIVATE_KEY_SENTINEL.encode(
            "ascii"
        )
        return private_key

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

    @patch("kloigos.services.ssh_key._generate_private_key")
    @patch("kloigos.services.ssh_key.log_event")
    def test_private_key_plaintext_exists_only_in_initial_response(
        self,
        log_event,
        generate_private_key,
    ) -> None:
        private_key = self._sentinel_private_key()

        def serialize_private_key(*_args):
            self.repo.create_ssh_key.assert_called_once()
            self.assertTrue(log_event.called)
            return PRIVATE_KEY_SENTINEL.encode("ascii")

        private_key.private_bytes.side_effect = serialize_private_key
        generate_private_key.return_value = private_key

        with self.assertNoLogs("kloigos.services.ssh_key", level="DEBUG"):
            result = self.service.create_ssh_key(
                "actor",
                SSHKeyCreateRequest(name="sentinel", generate=True),
            )

        persisted = self.repo.create_ssh_key.call_args.args[0]
        audit_details = log_event.call_args.args[3]
        self.assertEqual(result.private_key, PRIVATE_KEY_SENTINEL)
        self.assertNotIn(PRIVATE_KEY_SENTINEL, persisted.model_dump_json())
        self.assertNotIn(PRIVATE_KEY_SENTINEL, repr(audit_details))
        self.repo.enqueue_command.assert_not_called()

        self.repo.get_ssh_keys.return_value = [_stored_key(persisted)]
        self.assertNotIn(
            PRIVATE_KEY_SENTINEL,
            repr(self.service.list_ssh_keys()),
        )
        self.assertNotIn(
            PRIVATE_KEY_SENTINEL,
            repr(self.service.get_ssh_key("sentinel")),
        )

    @patch("kloigos.services.ssh_key._generate_private_key")
    def test_duplicate_name_is_rejected_before_key_generation(
        self,
        generate_private_key,
    ) -> None:
        self.repo.get_ssh_keys.return_value = [MagicMock()]

        with self.assertRaisesRegex(ComputeUnitOperationError, "already exists"):
            self.service.create_ssh_key(
                "actor",
                SSHKeyCreateRequest(name="duplicate", generate=True),
            )

        generate_private_key.assert_not_called()
        self.repo.create_ssh_key.assert_not_called()

    @patch("kloigos.services.ssh_key.log_event")
    def test_repeated_generated_request_never_replays_private_key(
        self,
        _log_event,
    ) -> None:
        created = []
        self.repo.get_ssh_keys.side_effect = lambda **_kwargs: list(created)

        def create(source):
            stored = _stored_key(source)
            created.append(stored)
            return stored

        self.repo.create_ssh_key.side_effect = create
        request = SSHKeyCreateRequest(name="generated", generate=True)

        initial = self.service.create_ssh_key("actor", request)
        with self.assertRaisesRegex(
            ComputeUnitOperationError, "already exists"
        ) as raised:
            self.service.create_ssh_key("actor", request)

        self.assertIsNotNone(initial.private_key)
        self.assertNotIn(initial.private_key, str(raised.exception))
        self.repo.create_ssh_key.assert_called_once()

    @patch("kloigos.services.ssh_key.log_event")
    def test_concurrent_duplicate_is_reported_without_a_response(
        self,
        log_event,
    ) -> None:
        self.repo.create_ssh_key.side_effect = UniqueViolation(PRIVATE_KEY_SENTINEL)

        with self.assertRaisesRegex(
            ComputeUnitOperationError, "already exists"
        ) as raised:
            self.service.create_ssh_key(
                "actor",
                SSHKeyCreateRequest(name="racing", generate=True),
            )

        self.assertNotIn(PRIVATE_KEY_SENTINEL, str(raised.exception))
        log_event.assert_not_called()

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
