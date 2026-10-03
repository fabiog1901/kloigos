import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (PROJECT_ROOT / "kloigos/webapp/extension.js").read_text()
MARKUP = (PROJECT_ROOT / "kloigos/webapp/extension.html").read_text()
GUIDE = (PROJECT_ROOT / "docs/docs/ssh-keys.md").read_text()


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
            r"(?:localStorage|sessionStorage)\.setItem\([^\n]*(?:private_key|privateKey)",
        )
        self.assertNotRegex(
            SCRIPT,
            r"(?:URLSearchParams|history\.(?:pushState|replaceState))[^\n]*(?:private_key|privateKey)",
        )
        self.assertNotRegex(
            SCRIPT,
            r"(?:console\.|reportError|captureException|analytics|telemetry)[^\n]*(?:private_key|privateKey)",
        )
        self.assertIn("this.closeSSHKeyCreateModal();", SCRIPT)

    def test_private_key_is_cleared_on_navigation_and_page_teardown(self) -> None:
        self.assertIn('this.$watch("view", () => {', SCRIPT)
        self.assertIn(
            'window.addEventListener("pagehide", this._sshKeyPageHideHandler);',
            SCRIPT,
        )
        self.assertIn("destroy() {", SCRIPT)
        self.assertIn('this.modal.sshKeyCreate.private_key = "";', SCRIPT)
        self.assertIn('output.value = "";', SCRIPT)
        self.assertIn('autocomplete="off"', MARKUP)
        self.assertIn("isSSHKeyCreateActive(modal, generation)", SCRIPT)
        self.assertGreaterEqual(
            SCRIPT.count("isSSHKeyCreateActive(modal, createGeneration)"),
            3,
        )

    def test_one_time_private_key_controls_are_present(self) -> None:
        self.assertIn("Save this private key now.", MARKUP)
        self.assertIn("copyGeneratedPrivateKey()", MARKUP)
        self.assertIn("downloadGeneratedPrivateKey()", MARKUP)
        self.assertIn("I Have Saved It", MARKUP)
        self.assertIn("delete the stored public-key resource", MARKUP)
        self.assertIn("Clear the clipboard", MARKUP)

    def test_download_always_revokes_its_temporary_object_url(self) -> None:
        download_method = SCRIPT.split("downloadGeneratedPrivateKey() {", 1)[1]
        download_method = download_method.split("openSSHKeyDeleteConfirm", 1)[0]
        self.assertIn("try {", download_method)
        self.assertIn("finally {", download_method)
        self.assertIn("URL.revokeObjectURL(url);", download_method)

    def test_lost_delivery_recovery_is_documented(self) -> None:
        self.assertIn("Do not retry the generation request automatically", GUIDE)
        self.assertIn("delete the public-key resource", GUIDE)
        self.assertIn("does not\npersist generated private keys", GUIDE)
        self.assertIn("request or response bodies", GUIDE)

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
