import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (PROJECT_ROOT / "kloigos/webapp/extension.js").read_text()
MARKUP = (PROJECT_ROOT / "kloigos/webapp/extension.html").read_text()


class SSHKeyWebappContractTests(unittest.TestCase):
    def test_admin_view_exposes_list_create_and_delete_actions(self) -> None:
        self.assertIn('view: "ssh_keys"', SCRIPT)
        self.assertIn('countKey: "sshKeys"', SCRIPT)
        self.assertIn('this.apiFetch("/ssh-keys/", { method: "GET" })', SCRIPT)
        self.assertIn('this.apiFetch("/ssh-keys/", { method: "POST", body })', SCRIPT)
        self.assertIn("openSSHKeyDeleteConfirm(sshKey)", MARKUP)

    def test_generated_private_key_is_kept_out_of_metadata_and_storage(self) -> None:
        self.assertIn(
            "const { private_key: privateKey, ...metadata } = result;",
            SCRIPT,
        )
        self.assertIn('private_key: ""', SCRIPT)
        self.assertNotRegex(
            SCRIPT,
            r"(?:localStorage|sessionStorage)\.setItem\([^\n]*private_key",
        )
        self.assertIn("this.closeSSHKeyCreateModal();", SCRIPT)

    def test_one_time_private_key_controls_are_present(self) -> None:
        self.assertIn("Save this private key now.", MARKUP)
        self.assertIn("copyGeneratedPrivateKey()", MARKUP)
        self.assertIn("downloadGeneratedPrivateKey()", MARKUP)
        self.assertIn("I Have Saved It", MARKUP)

    def test_key_creation_post_is_attempted_only_once(self) -> None:
        creation_call = 'this.apiFetch("/ssh-keys/", { method: "POST", body })'
        self.assertEqual(SCRIPT.count(creation_call), 1)
        self.assertIn("non-idempotent request is deliberately attempted once", SCRIPT)

    def test_allocation_form_supports_named_and_inline_keys(self) -> None:
        self.assertIn("payload.ssh_key_name = sshKeyName;", SCRIPT)
        self.assertIn("payload.ssh_public_key = sshPublicKey;", SCRIPT)
        self.assertIn('value="stored"', MARKUP)
        self.assertIn('value="inline"', MARKUP)


if __name__ == "__main__":
    unittest.main()
