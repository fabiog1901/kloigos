"""Validate and normalize declarative real-host validation fixtures."""

from __future__ import annotations

import ipaddress
from copy import deepcopy
from typing import Any


class FixtureManifestError(ValueError):
    """A fixture manifest value is structurally or semantically invalid."""


def _fail(path: str, message: str) -> None:
    raise FixtureManifestError(f"{path}: {message}")


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, "must be a list")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(path, "must be a non-empty string")
    return value.strip()


def _optional_string(value: Any, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(path, "must be a string or null")
    return value.strip() or None


def _choice(value: Any, path: str, choices: set[str]) -> str:
    normalized = _string(value, path).lower()
    if normalized not in choices:
        _fail(path, f"must be one of: {', '.join(sorted(choices))}")
    return normalized


def _port(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 65535:
        _fail(path, "must be an integer between 1 and 65535")
    return value


def _unique(identifier: str, path: str, seen: dict[str, str], kind: str) -> None:
    if identifier in seen:
        _fail(path, f"duplicates {kind} declared at {seen[identifier]}")
    seen[identifier] = path


def _ip(value: Any, path: str) -> str:
    text = _string(value, path)
    try:
        return str(ipaddress.ip_address(text))
    except ValueError as exc:
        _fail(path, f"must be a valid IP address ({exc})")


def _compute_unit_id(hostname: str, ordinal: int) -> str:
    return f"{hostname}-cu{ordinal:02d}"


def _normalize_servers(
    document: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    servers: list[dict[str, Any]] = []
    by_hostname: dict[str, dict[str, Any]] = {}
    seen: dict[str, str] = {}
    for index, raw in enumerate(_list(document.get("servers", []), "servers")):
        path = f"servers[{index}]"
        server = deepcopy(_mapping(raw, path))
        hostname = _string(server.get("hostname"), f"{path}.hostname")
        _unique(hostname, f"{path}.hostname", seen, "server hostname")
        server["hostname"] = hostname
        if "probe_source_ip" in server:
            server["probe_source_ip"] = _ip(
                server["probe_source_ip"], f"{path}.probe_source_ip"
            )
        servers.append(server)
        by_hostname[hostname] = server
    return servers, by_hostname


def _normalize_compute_units(
    document: dict[str, Any], servers: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    compute_units: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    seen: dict[str, str] = {}
    for index, raw in enumerate(
        _list(document.get("compute_units", []), "compute_units")
    ):
        path = f"compute_units[{index}]"
        compute_unit = deepcopy(_mapping(raw, path))
        hostname = _string(compute_unit.get("hostname"), f"{path}.hostname")
        if hostname not in servers:
            _fail(f"{path}.hostname", f"references undeclared server '{hostname}'")
        ordinal = compute_unit.get("ordinal")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1:
            _fail(f"{path}.ordinal", "must be a positive integer")
        fixture_id = _compute_unit_id(hostname, ordinal)
        _unique(fixture_id, path, seen, "compute unit")
        compute_unit["hostname"] = hostname
        compute_unit["ordinal"] = ordinal
        compute_unit["fixture_id"] = fixture_id
        compute_units.append(compute_unit)
        by_id[fixture_id] = compute_unit
    return compute_units, by_id


def _normalize_allocations(
    document: dict[str, Any], compute_units: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    allocations: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    seen_ids: dict[str, str] = {}
    seen_addresses: dict[str, str] = {}
    for index, raw in enumerate(_list(document.get("allocations"), "allocations")):
        path = f"allocations[{index}]"
        allocation = deepcopy(_mapping(raw, path))
        allocation_id = _string(
            allocation.get("allocation_id"), f"{path}.allocation_id"
        )
        _unique(allocation_id, f"{path}.allocation_id", seen_ids, "allocation ID")
        allocation["allocation_id"] = allocation_id
        if "ip_address" in allocation:
            address = _ip(allocation["ip_address"], f"{path}.ip_address")
            _unique(address, f"{path}.ip_address", seen_addresses, "allocation address")
            allocation["ip_address"] = address
        if "compute_unit" in allocation:
            compute_unit = _string(allocation["compute_unit"], f"{path}.compute_unit")
            if compute_unit not in compute_units:
                _fail(
                    f"{path}.compute_unit",
                    f"references undeclared compute unit '{compute_unit}'",
                )
            allocation["compute_unit"] = compute_unit
            allocation["expected_host"] = compute_units[compute_unit]["hostname"]
        allocations.append(allocation)
        by_id[allocation_id] = allocation
    return allocations, by_id


def _normalize_rule(raw: Any, path: str) -> dict[str, Any]:
    rule = deepcopy(_mapping(raw, path))
    rule["fixture_rule_id"] = _string(
        rule.get("fixture_rule_id"), f"{path}.fixture_rule_id"
    )
    rule["direction"] = _choice(
        rule.get("direction"), f"{path}.direction", {"ingress", "egress"}
    )
    rule["protocol"] = _choice(
        rule.get("protocol"),
        f"{path}.protocol",
        {"tcp", "udp", "icmp", "icmpv6", "all"},
    )
    rule["ip_version"] = _choice(
        rule.get("ip_version"), f"{path}.ip_version", {"ipv4", "ipv6"}
    )
    cidr = _string(rule.get("cidr"), f"{path}.cidr")
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError as exc:
        _fail(f"{path}.cidr", f"must be a valid CIDR range ({exc})")
    required_version = 4 if rule["ip_version"] == "ipv4" else 6
    if network.version != required_version:
        _fail(
            f"{path}.ip_version",
            f"is {rule['ip_version']} but {cidr!r} has IPv{network.version}",
        )
    rule["cidr"] = str(network)

    port_from = rule.get("port_from")
    port_to = rule.get("port_to")
    if rule["protocol"] in {"icmp", "icmpv6", "all"}:
        if port_from is not None or port_to is not None:
            _fail(
                f"{path}.port_from", f"{rule['protocol']} rules must not define ports"
            )
        rule["port_from"] = None
        rule["port_to"] = None
    else:
        if port_from is not None:
            port_from = _port(port_from, f"{path}.port_from")
        if port_to is not None:
            port_to = _port(port_to, f"{path}.port_to")
        if port_from is None and port_to is not None:
            _fail(f"{path}.port_from", "is required when port_to is set")
        if port_from is not None and port_to is None:
            port_to = port_from
        if port_from is not None and port_to is not None and port_from > port_to:
            _fail(f"{path}.port_from", "must be less than or equal to port_to")
        rule["port_from"] = port_from
        rule["port_to"] = port_to

    if rule["protocol"] == "icmp" and rule["ip_version"] != "ipv4":
        _fail(f"{path}.ip_version", "icmp rules must use ipv4")
    if rule["protocol"] == "icmpv6" and rule["ip_version"] != "ipv6":
        _fail(f"{path}.ip_version", "icmpv6 rules must use ipv6")
    rule["description"] = _optional_string(
        rule.get("description"), f"{path}.description"
    )
    return rule


def _normalize_security_groups(
    document: dict[str, Any], allocations: dict[str, dict[str, Any]]
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, tuple[dict[str, Any], dict[str, Any]]],
]:
    security_groups: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    rules_by_id: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    seen_groups: dict[str, str] = {}
    seen_group_names: dict[str, str] = {}
    seen_rules: dict[str, str] = {}
    for group_index, raw in enumerate(
        _list(document.get("security_groups", []), "security_groups")
    ):
        path = f"security_groups[{group_index}]"
        group = deepcopy(_mapping(raw, path))
        fixture_id = _string(group.get("fixture_id"), f"{path}.fixture_id")
        _unique(
            fixture_id, f"{path}.fixture_id", seen_groups, "Security Group fixture ID"
        )
        group["fixture_id"] = fixture_id
        group["name"] = _string(group.get("name"), f"{path}.name")
        _unique(
            group["name"],
            f"{path}.name",
            seen_group_names,
            "Security Group name",
        )
        group["description"] = _optional_string(
            group.get("description"), f"{path}.description"
        )
        attachments = _list(group.get("attachments"), f"{path}.attachments")
        if not attachments:
            _fail(f"{path}.attachments", "must contain at least one allocation ID")
        normalized_attachments: list[str] = []
        seen_attachments: set[str] = set()
        for attachment_index, value in enumerate(attachments):
            attachment_path = f"{path}.attachments[{attachment_index}]"
            allocation_id = _string(value, attachment_path)
            if allocation_id not in allocations:
                _fail(
                    attachment_path,
                    f"references undeclared allocation '{allocation_id}'",
                )
            for field in ("ip_address", "compute_unit", "expected_host"):
                if field not in allocations[allocation_id]:
                    _fail(
                        attachment_path,
                        f"allocation '{allocation_id}' requires {field} when used by a Security Group attachment",
                    )
            if allocation_id in seen_attachments:
                _fail(attachment_path, f"duplicates allocation '{allocation_id}'")
            seen_attachments.add(allocation_id)
            normalized_attachments.append(allocation_id)
        group["attachments"] = normalized_attachments

        rules = _list(group.get("rules"), f"{path}.rules")
        if not rules:
            _fail(f"{path}.rules", "must contain at least one rule")
        normalized_rules: list[dict[str, Any]] = []
        rule_signatures: dict[tuple[Any, ...], str] = {}
        for rule_index, raw_rule in enumerate(rules):
            rule_path = f"{path}.rules[{rule_index}]"
            rule = _normalize_rule(raw_rule, rule_path)
            rule_id = rule["fixture_rule_id"]
            _unique(
                rule_id, f"{rule_path}.fixture_rule_id", seen_rules, "fixture rule ID"
            )
            signature = (
                rule["direction"],
                rule["protocol"],
                rule["port_from"],
                rule["port_to"],
                rule["cidr"],
                rule["ip_version"],
            )
            if signature in rule_signatures:
                _fail(
                    rule_path,
                    f"duplicates rule fields declared at {rule_signatures[signature]}",
                )
            rule_signatures[signature] = rule_path
            normalized_rules.append(rule)
            rules_by_id[rule_id] = (group, rule)
        group["rules"] = normalized_rules
        security_groups.append(group)
        by_id[fixture_id] = group
    return security_groups, by_id, rules_by_id


def _normalize_endpoint(
    raw: Any,
    path: str,
    servers: dict[str, dict[str, Any]],
    allocations: dict[str, dict[str, Any]],
) -> dict[str, str]:
    endpoint = _mapping(raw, path)
    kind = _choice(
        endpoint.get("kind"), f"{path}.kind", {"validation_host", "allocation"}
    )
    if kind == "validation_host":
        hostname = _string(endpoint.get("hostname"), f"{path}.hostname")
        server = servers.get(hostname)
        if server is None:
            _fail(f"{path}.hostname", f"references undeclared server '{hostname}'")
        if "probe_source_ip" not in server:
            _fail(
                f"{path}.hostname",
                f"server '{hostname}' requires probe_source_ip when used by a probe",
            )
        return {"kind": kind, "hostname": hostname}

    allocation_id = _string(endpoint.get("allocation_id"), f"{path}.allocation_id")
    allocation = allocations.get(allocation_id)
    if allocation is None:
        _fail(
            f"{path}.allocation_id",
            f"references undeclared allocation '{allocation_id}'",
        )
    for field in ("ip_address", "compute_unit", "expected_host"):
        if field not in allocation:
            _fail(
                f"{path}.allocation_id",
                f"allocation '{allocation_id}' requires {field} when used by a probe",
            )
    return {"kind": kind, "allocation_id": allocation_id}


def _endpoint_address(
    endpoint: dict[str, str],
    servers: dict[str, dict[str, Any]],
    allocations: dict[str, dict[str, Any]],
) -> str:
    if endpoint["kind"] == "validation_host":
        return servers[endpoint["hostname"]]["probe_source_ip"]
    return allocations[endpoint["allocation_id"]]["ip_address"]


def _protected_allocation(probe: dict[str, Any], path: str) -> str:
    if probe["direction"] == "ingress":
        if probe["destination"]["kind"] != "allocation":
            _fail(
                f"{path}.destination.kind",
                "ingress probes must target an allocation",
            )
        return probe["destination"]["allocation_id"]
    if probe["source"]["kind"] != "allocation":
        _fail(f"{path}.source.kind", "egress probes must originate from an allocation")
    return probe["source"]["allocation_id"]


def _rule_matches_probe(
    rule: dict[str, Any],
    probe: dict[str, Any],
    peer_address: str,
) -> bool:
    if rule["direction"] != probe["direction"]:
        return False
    if rule["protocol"] not in {probe["protocol"], "all"}:
        return False
    address = ipaddress.ip_address(peer_address)
    if address.version != (4 if rule["ip_version"] == "ipv4" else 6):
        return False
    if address not in ipaddress.ip_network(rule["cidr"]):
        return False
    if rule["protocol"] in {"tcp", "udp"} and rule["port_from"] is not None:
        if not rule["port_from"] <= probe["port"] <= rule["port_to"]:
            return False
    return True


def _normalize_probes(
    document: dict[str, Any],
    servers: dict[str, dict[str, Any]],
    allocations: dict[str, dict[str, Any]],
    security_groups: list[dict[str, Any]],
    rules_by_id: dict[str, tuple[dict[str, Any], dict[str, Any]]],
) -> list[dict[str, Any]]:
    probes: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for index, raw in enumerate(
        _list(
            document.get("network_connection_probes", []), "network_connection_probes"
        )
    ):
        path = f"network_connection_probes[{index}]"
        probe = deepcopy(_mapping(raw, path))
        probe_id = _string(probe.get("probe_id"), f"{path}.probe_id")
        _unique(probe_id, f"{path}.probe_id", seen, "probe ID")
        probe["probe_id"] = probe_id
        probe["direction"] = _choice(
            probe.get("direction"), f"{path}.direction", {"ingress", "egress"}
        )
        probe["protocol"] = _choice(probe.get("protocol"), f"{path}.protocol", {"tcp"})
        probe["port"] = _port(probe.get("port"), f"{path}.port")
        probe["expected"] = _choice(
            probe.get("expected"), f"{path}.expected", {"allowed", "denied"}
        )
        probe["source"] = _normalize_endpoint(
            probe.get("source"), f"{path}.source", servers, allocations
        )
        probe["destination"] = _normalize_endpoint(
            probe.get("destination"),
            f"{path}.destination",
            servers,
            allocations,
        )
        protected_allocation = _protected_allocation(probe, path)
        peer_endpoint = (
            probe["source"] if probe["direction"] == "ingress" else probe["destination"]
        )
        peer_address = _endpoint_address(peer_endpoint, servers, allocations)
        source_address = _endpoint_address(probe["source"], servers, allocations)
        destination_address = _endpoint_address(
            probe["destination"], servers, allocations
        )
        if (
            ipaddress.ip_address(source_address).version
            != ipaddress.ip_address(destination_address).version
        ):
            _fail(
                f"{path}.destination",
                "source and destination addresses must use the same IP version",
            )
        attached_groups = [
            group
            for group in security_groups
            if protected_allocation in group["attachments"]
        ]
        if not attached_groups:
            _fail(
                f"{path}.{'destination' if probe['direction'] == 'ingress' else 'source'}",
                f"protected allocation '{protected_allocation}' has no declared Security Group attachment",
            )

        rule_id = probe.get("fixture_rule_id")
        if probe["expected"] == "allowed":
            rule_id = _string(rule_id, f"{path}.fixture_rule_id")
            match = rules_by_id.get(rule_id)
            if match is None:
                _fail(
                    f"{path}.fixture_rule_id",
                    f"references undeclared fixture rule '{rule_id}'",
                )
            group, rule = match
            if protected_allocation not in group["attachments"]:
                _fail(
                    f"{path}.fixture_rule_id",
                    f"rule '{rule_id}' belongs to a Security Group not attached to allocation '{protected_allocation}'",
                )
            if not _rule_matches_probe(rule, probe, peer_address):
                _fail(
                    f"{path}.fixture_rule_id",
                    f"rule '{rule_id}' does not allow the declared direction, protocol, port, and peer address",
                )
            probe["fixture_rule_id"] = rule_id
        else:
            if rule_id is not None:
                _fail(
                    f"{path}.fixture_rule_id",
                    "must be omitted for a denied probe",
                )
            matching_rules = [
                rule["fixture_rule_id"]
                for group in attached_groups
                for rule in group["rules"]
                if _rule_matches_probe(rule, probe, peer_address)
            ]
            if matching_rules:
                _fail(
                    f"{path}.expected",
                    "is denied but the connection is allowed by fixture rule(s): "
                    + ", ".join(matching_rules),
                )
            if probe["direction"] == "egress":
                protected_version = ipaddress.ip_address(
                    allocations[protected_allocation]["ip_address"]
                ).version
                effective_egress_rules = [
                    rule
                    for group in attached_groups
                    for rule in group["rules"]
                    if rule["direction"] == "egress"
                    and (4 if rule["ip_version"] == "ipv4" else 6) == protected_version
                ]
                if not effective_egress_rules:
                    _fail(
                        f"{path}.expected",
                        "cannot be denied because the protected allocation has no effective egress rules and therefore uses default-allow egress",
                    )
            probe.pop("fixture_rule_id", None)
        probes.append(probe)
    return probes


def normalize_fixture_manifest(value: Any) -> dict[str, Any]:
    """Return one fully validated, normalized fixture manifest.

    Every cross-reference is resolved during this pass. Callers can therefore invoke
    this function before any API request and safely consume the returned relationships
    without reinterpreting raw YAML values.
    """

    document = deepcopy(_mapping(value, "manifest"))
    schema_version = document.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != 1
    ):
        _fail("schema_version", "must be 1")

    servers, servers_by_hostname = _normalize_servers(document)
    compute_units, compute_units_by_id = _normalize_compute_units(
        document, servers_by_hostname
    )
    allocations, allocations_by_id = _normalize_allocations(
        document, compute_units_by_id
    )
    security_groups, _, rules_by_id = _normalize_security_groups(
        document, allocations_by_id
    )
    probes = _normalize_probes(
        document,
        servers_by_hostname,
        allocations_by_id,
        security_groups,
        rules_by_id,
    )

    document["servers"] = servers
    document["compute_units"] = compute_units
    document["allocations"] = allocations
    document["security_groups"] = security_groups
    document["network_connection_probes"] = probes
    return document
