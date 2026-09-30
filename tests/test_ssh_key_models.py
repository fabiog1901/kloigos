import datetime as dt
import unittest

from pydantic import ValidationError

from kloigos.models import SSHKeyCreate, SSHKeyInDB

PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDk65l+4HPbBZRt6mV7tHcvap3PrhCUo79iaCEdE1exx fabio@hp"


class SSHKeyModelTests(unittest.TestCase):
    def test_name_is_trimmed_and_creation_method_is_normalized(self) -> None:
        key = SSHKeyCreate(
            name="  workstation  ",
            algorithm="ssh-ed25519",
            public_key=PUBLIC_KEY,
            fingerprint="SHA256:example",
            creation_method="imported",
        )

        self.assertEqual(key.name, "workstation")
        self.assertEqual(key.creation_method.value, "imported")

    def test_name_must_not_exceed_fifty_characters_after_trimming(self) -> None:
        key = SSHKeyCreate(
            name=f"  {'k' * 50}  ",
            algorithm="ssh-ed25519",
            public_key=PUBLIC_KEY,
            fingerprint="SHA256:example",
            creation_method="generated",
        )
        self.assertEqual(len(key.name), 50)

        with self.assertRaises(ValidationError):
            SSHKeyCreate(
                name="k" * 51,
                algorithm="ssh-ed25519",
                public_key=PUBLIC_KEY,
                fingerprint="SHA256:example",
                creation_method="generated",
            )

    def test_algorithm_must_match_public_key_type(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "algorithm must match the OpenSSH public-key type",
        ):
            SSHKeyCreate(
                name="workstation",
                algorithm="ssh-rsa",
                public_key=PUBLIC_KEY,
                fingerprint="SHA256:example",
                creation_method="imported",
            )

    def test_database_model_requires_timestamps(self) -> None:
        now = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
        key = SSHKeyInDB(
            name="workstation",
            algorithm="ssh-ed25519",
            public_key=PUBLIC_KEY,
            fingerprint="SHA256:example",
            creation_method="imported",
            created_at=now,
            updated_at=now,
        )

        self.assertEqual(key.created_at, now)
        self.assertEqual(key.updated_at, now)


if __name__ == "__main__":
    unittest.main()
