# Validation-host preparation

`PREPARE_VALIDATION_HOST.yaml` idempotently prepares hosts explicitly designated for real-host
validation. It installs the bounded workload tools used by later profiles and utilities used to
inspect Kloigos-managed state. It does not create allocations, execute a validation profile,
generate load, or alter Kloigos configuration.

## Requirements

- An Ansible control environment with access to the target hosts.
- An inventory group named `validation_hosts`.
- A privilege-escalation method for package installation (`become: true`).
- Debian- or RedHat-family hosts with a supported package manager.

Example inventory:

```ini
[validation_hosts]
validation-host-01 ansible_host=192.0.2.10 ansible_user=admin
```

Run the preparation explicitly:

```bash
ansible-playbook -i validation/inventory.ini \
  validation/ansible/PREPARE_VALIDATION_HOST.yaml
```

Use `--check` to preview package and directory changes where the target package manager supports
check mode. Because package metadata may be refreshed by the package manager, a check run is not a
substitute for reviewing the target and its maintenance policy.

## Installed tools

The playbook requires and verifies these commands:

- Workload tools: `stress-ng`, `fio`, and `iperf3`.
- Network and firewall inspection: `ip`, `ss`, and `nft`.
- Process, mount, block-device, and service inspection: `ps`, `findmnt`, `lsblk`, and `systemctl`.
- Structured evidence support: `jq`.

On Debian-family systems it also installs AppArmor utilities and verifies `aa-status`. On
RedHat-family systems, AppArmor is not installed because it is not the platform-native mandatory
access-control implementation.

The playbook creates `/var/lib/kloigos-validation` as a local workspace for later phases. Generated
reports and artifacts remain owned by the future runner; preparation itself writes no report.
