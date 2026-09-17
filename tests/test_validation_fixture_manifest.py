import copy
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import yaml

from validation.fixture_manifest import FixtureManifestError, normalize_fixture_manifest
from validation.report import ValidationError, fixture_manifest, manage_fixtures

EXAMPLE = Path(__file__).parents[1] / "validation" / "fixtures.example.yaml"


def example_manifest() -> dict:
    return yaml.safe_load(EXAMPLE.read_text())


class FixtureManifestTests(unittest.TestCase):
    def test_documented_example_normalizes_all_fixture_relationships(self) -> None:
        manifest, allocations = fixture_manifest(EXAMPLE)

        self.assertEqual(len(allocations), 3)
        self.assertEqual(
            manifest["compute_units"][0]["fixture_id"],
            "validation-host-01-cu01",
        )
        self.assertEqual(allocations[0]["expected_host"], "validation-host-01")
        self.assertEqual(
            manifest["security_groups"][0]["rules"][0]["cidr"],
            "192.0.2.100/32",
        )
        self.assertEqual(
            manifest["security_groups"][0]["attachments"], ["validation-a"]
        )
        self.assertEqual(len(manifest["network_connection_probes"]), 6)

    def test_normalization_does_not_mutate_the_input_document(self) -> None:
        source = example_manifest()
        source["security_groups"][0]["rules"][0].pop("port_to")
        original = copy.deepcopy(source)

        normalized = normalize_fixture_manifest(source)

        self.assertEqual(source, original)
        self.assertEqual(normalized["security_groups"][0]["rules"][0]["port_to"], 18080)

    def test_non_security_group_manifest_remains_valid(self) -> None:
        manifest = normalize_fixture_manifest(
            {"schema_version": 1, "allocations": [{"allocation_id": "fixture-a"}]}
        )

        self.assertEqual(manifest["security_groups"], [])
        self.assertEqual(manifest["network_connection_probes"], [])

    def test_representative_invalid_manifests_report_precise_paths(self) -> None:
        cases = []

        duplicate_rule = example_manifest()
        duplicate_rule["security_groups"][0]["rules"].append(
            copy.deepcopy(duplicate_rule["security_groups"][0]["rules"][0])
        )
        cases.append(
            (
                "duplicate rule",
                duplicate_rule,
                "security_groups[0].rules[5].fixture_rule_id: duplicates fixture rule ID",
            )
        )

        duplicate_rule_fields = example_manifest()
        duplicated = copy.deepcopy(
            duplicate_rule_fields["security_groups"][0]["rules"][0]
        )
        duplicated["fixture_rule_id"] = "different-id-same-rule"
        duplicate_rule_fields["security_groups"][0]["rules"].append(duplicated)
        cases.append(
            (
                "duplicate rule fields",
                duplicate_rule_fields,
                "security_groups[0].rules[5]: duplicates rule fields declared at security_groups[0].rules[0]",
            )
        )

        duplicate_group_name = example_manifest()
        duplicated_group = copy.deepcopy(duplicate_group_name["security_groups"][0])
        duplicated_group["fixture_id"] = "different-fixture-id"
        duplicate_group_name["security_groups"].append(duplicated_group)
        cases.append(
            (
                "duplicate Security Group name",
                duplicate_group_name,
                "security_groups[1].name: duplicates Security Group name",
            )
        )

        missing_attachment = example_manifest()
        missing_attachment["security_groups"][0]["attachments"] = ["missing"]
        cases.append(
            (
                "missing attachment",
                missing_attachment,
                "security_groups[0].attachments[0]: references undeclared allocation 'missing'",
            )
        )

        missing_endpoint = example_manifest()
        missing_endpoint["network_connection_probes"][0]["source"] = {
            "kind": "validation_host",
            "hostname": "missing",
        }
        cases.append(
            (
                "missing endpoint",
                missing_endpoint,
                "network_connection_probes[0].source.hostname: references undeclared server 'missing'",
            )
        )

        invalid_compute_unit = example_manifest()
        invalid_compute_unit["allocations"][0]["compute_unit"] = "missing-cu"
        cases.append(
            (
                "invalid compute unit",
                invalid_compute_unit,
                "allocations[0].compute_unit: references undeclared compute unit 'missing-cu'",
            )
        )

        incomplete_attachment = example_manifest()
        incomplete_attachment["allocations"][0].pop("ip_address")
        cases.append(
            (
                "incomplete attached allocation",
                incomplete_attachment,
                "security_groups[0].attachments[0]: allocation 'validation-a' requires ip_address",
            )
        )

        incompatible_rule = example_manifest()
        incompatible_rule["network_connection_probes"][0]["port"] = 18082
        cases.append(
            (
                "incompatible allowed rule",
                incompatible_rule,
                "network_connection_probes[0].fixture_rule_id: rule 'ingress-runner-host' does not allow",
            )
        )

        denied_rule_reference = example_manifest()
        denied_rule_reference["network_connection_probes"][1][
            "fixture_rule_id"
        ] = "ingress-runner-host"
        cases.append(
            (
                "denied rule reference",
                denied_rule_reference,
                "network_connection_probes[1].fixture_rule_id: must be omitted for a denied probe",
            )
        )

        denied_but_allowed = example_manifest()
        denied_but_allowed["network_connection_probes"][1]["port"] = 18080
        cases.append(
            (
                "denied probe covered by a rule",
                denied_but_allowed,
                "network_connection_probes[1].expected: is denied but the connection is allowed",
            )
        )

        invalid_direction = example_manifest()
        invalid_direction["network_connection_probes"][0]["destination"] = {
            "kind": "validation_host",
            "hostname": "validation-host-02",
        }
        cases.append(
            (
                "invalid direction",
                invalid_direction,
                "network_connection_probes[0].destination.kind: ingress probes must target an allocation",
            )
        )

        mixed_ip_versions = example_manifest()
        mixed_ip_versions["servers"][0]["probe_source_ip"] = "2001:db8::100"
        cases.append(
            (
                "mixed endpoint IP versions",
                mixed_ip_versions,
                "network_connection_probes[0].destination: source and destination addresses must use the same IP version",
            )
        )

        default_allow_egress = example_manifest()
        default_allow_egress["security_groups"][0]["rules"] = default_allow_egress[
            "security_groups"
        ][0]["rules"][:3]
        default_allow_egress["network_connection_probes"] = [
            default_allow_egress["network_connection_probes"][-1]
        ]
        cases.append(
            (
                "default allow egress",
                default_allow_egress,
                "network_connection_probes[0].expected: cannot be denied because the protected allocation has no effective egress rules",
            )
        )

        invalid_port_range = example_manifest()
        invalid_port_range["security_groups"][0]["rules"][0]["port_from"] = 18081
        cases.append(
            (
                "invalid port range",
                invalid_port_range,
                "security_groups[0].rules[0].port_from: must be less than or equal to port_to",
            )
        )

        for name, document, message in cases:
            with self.subTest(name=name):
                with self.assertRaises(FixtureManifestError) as raised:
                    normalize_fixture_manifest(document)
                self.assertIn(message, str(raised.exception))

    def test_invalid_manifest_prevents_every_setup_api_call(self) -> None:
        document = example_manifest()
        document["network_connection_probes"][1]["probe_id"] = document[
            "network_connection_probes"
        ][0]["probe_id"]
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "fixtures.yaml"
            manifest_path.write_text(yaml.safe_dump(document, sort_keys=False))
            args = Namespace(
                action="setup",
                api_url="https://controller.invalid/api",
                fixture_manifest=manifest_path,
            )

            with patch("validation.report.api_call") as api_call:
                with self.assertRaisesRegex(
                    ValidationError,
                    r"network_connection_probes\[1\]\.probe_id: duplicates probe ID",
                ):
                    manage_fixtures(args)

            api_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
