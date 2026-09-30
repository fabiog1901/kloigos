import unittest
from unittest.mock import MagicMock, patch

from kloigos.models import SSHKeyCreate, SSHKeyInDB
from kloigos.repos.postgres import PostgresRepo

PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDk65l+4HPbBZRt6mV7tHcvap3PrhCUo79iaCEdE1exx fabio@hp"


class SSHKeyRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = PostgresRepo(MagicMock())
        self.key = SSHKeyCreate(
            name="workstation",
            algorithm="ssh-ed25519",
            public_key=PUBLIC_KEY,
            fingerprint="SHA256:example",
            creation_method="imported",
        )

    @patch("kloigos.repos.postgres.fetch_one")
    def test_create_ssh_key_returns_database_model(self, fetch_one) -> None:
        expected = MagicMock(spec=SSHKeyInDB)
        fetch_one.return_value = expected

        result = self.repo.create_ssh_key(self.key)

        self.assertIs(result, expected)
        args = fetch_one.call_args.args
        self.assertIn("INSERT INTO ssh_keys", args[0])
        self.assertEqual(
            args[1],
            (
                "workstation",
                "ssh-ed25519",
                PUBLIC_KEY,
                "SHA256:example",
                self.key.creation_method,
            ),
        )
        self.assertIs(args[2], SSHKeyInDB)

    @patch("kloigos.repos.postgres.fetch_all")
    def test_get_ssh_keys_can_list_or_filter_by_primary_key(self, fetch_all) -> None:
        fetch_all.return_value = []

        self.repo.get_ssh_keys()
        list_args = fetch_all.call_args.args
        self.assertNotIn("WHERE name", list_args[0])
        self.assertEqual(list_args[1], ())

        self.repo.get_ssh_keys(name="workstation")
        filtered_args = fetch_all.call_args.args
        self.assertIn("WHERE name = %s", filtered_args[0])
        self.assertEqual(filtered_args[1], ("workstation",))
        self.assertIs(filtered_args[2], SSHKeyInDB)

    @patch("kloigos.repos.postgres.fetch_scalar", return_value=1)
    def test_delete_ssh_key_reports_if_a_row_was_deleted(self, fetch_scalar) -> None:
        self.assertTrue(self.repo.delete_ssh_key("workstation"))
        args = fetch_scalar.call_args.args
        self.assertIn("DELETE", args[0])
        self.assertEqual(args[1], ("workstation",))


if __name__ == "__main__":
    unittest.main()
