# Playbooks

Kloigos externalizes host operations into versioned Ansible playbooks.

The control plane decides *what* should happen, records intent and state in
PostgreSQL, and schedules jobs. The playbooks define *how* a host is changed:
initializing capacity, creating allocation users, moving floating IPs, applying
AppArmor profiles, and cleaning up resources.

This is an intentional design choice. Infrastructure teams often need to adapt
host preparation to their own Linux images, storage layout, SSH access model, or
security requirements. Kloigos keeps those operational details in auditable,
replaceable playbooks instead of hardcoding every host action in Python.

## Design philosophy

Playbooks are treated as operational artifacts:

- They are stored in PostgreSQL with explicit versions.
- Jobs record the playbook version they ran.
- Operators can inspect, replace, and roll back playbook versions.
- The backend stays focused on orchestration and state transitions.
- Host-specific implementation details remain outside the control-plane code.

This lets organizations adapt Kloigos to their environment without forking the
backend.

## How packaged playbooks are initialized

The Kloigos wheel includes the built-in playbooks under:

```text
kloigos/resources/playbooks/
```

Run:

```bash
kloigos init
```

The command initializes the database schema and loads packaged playbooks into
the playbook store. Re-run it after upgrading Kloigos when a release adds new
packaged playbooks.

## Built-in Kloigos playbooks

| Playbook | Purpose |
| --- | --- |
| `SERVER_INIT` | Prepares a server for Kloigos management. It installs bootstrap packages, installs the selected host runtime profile, prepares LVM storage, creates Compute Unit logical volumes, configures base nftables state, installs helper scripts, and prepares AppArmor support on supported hosts. |
| `SERVER_DECOMM` | Resets a server back toward a non-Kloigos-managed state. It removes Kloigos users, mounts, logical volumes, nftables state, AppArmor profiles, timers, helper scripts, and local directories created by Kloigos. |
| `ALLOCATION_CREATE` | Creates a workload Allocation on a Compute Unit. It creates the login user, mounts storage, configures ownership, installs the SSH public key, applies systemd resource placement, configures floating IP and nftables rules, and loads the allocation AppArmor profile. |
| `ALLOCATION_DELETE` | Deallocates an Allocation. It stops user sessions and services, removes network and AppArmor state, releases mounts, cleans allocation-specific host resources, and leaves durable allocation history in the database. |
| `ALLOCATION_SCALE` | Moves an Allocation from one Compute Unit to another. It migrates data, moves the floating IP, updates resource placement, applies target host rules, starts the workload on the target, and releases source capacity after success. |

## SSH credential hook playbooks

Some environments do not allow Kloigos to access servers using a long-lived SSH
key or a preloaded `ssh-agent` identity. Instead, access may require a short-lived
SSH certificate issued by a third-party CA, such as Smallstep, Teleport, Vault
SSH CA, or an internal certificate service.

Kloigos does not hardcode those provider-specific workflows. Instead, it
provides an optional SSH credential hook mechanism using two reserved playbook
names:

| Playbook | Purpose |
| --- | --- |
| `SSH_CREDENTIAL_PREPARE` | Optional local hook that runs before a target playbook. It obtains or creates temporary SSH credential material for the job. |
| `SSH_CREDENTIAL_CLEANUP` | Optional local hook that runs after the target playbook attempt. It can revoke provider-side credentials and clean up local material. |

These hook playbooks are intentionally environment-specific. Kloigos packages
no-op placeholders for the reserved names, and operators replace them with
environment-specific versions through the Playbooks page or Playbooks API.

When enabled, the flow is:

```text
job starts
  -> Kloigos runs SSH_CREDENTIAL_PREPARE on localhost
  -> Kloigos runs the target playbook using the produced SSH material
  -> Kloigos runs SSH_CREDENTIAL_CLEANUP on localhost, if configured
  -> Kloigos removes job-scoped credential files
job ends
```

The prepare hook receives job and target context and writes credential artifacts
into a job-scoped directory, normally under:

```text
/tmp/cpkit/jobs/{job_id}/ssh/
```

Common artifact names are:

```text
id_key
id_key-cert.pub
known_hosts
ssh_config
```

The playbook runner detects these files and passes the corresponding SSH options
to `ansible-runner`.

## SSH credential hook settings

The hook is controlled through these settings:

| Setting | Default | Meaning |
| --- | --- | --- |
| `playbooks.ssh_credential_hook.enabled` | `false` | Enables the prepare/cleanup hook flow. |
| `playbooks.ssh_credential_hook.prepare_playbook` | `SSH_CREDENTIAL_PREPARE` | Playbook name used for credential preparation. |
| `playbooks.ssh_credential_hook.cleanup_playbook` | `SSH_CREDENTIAL_CLEANUP` | Playbook name used for credential cleanup. |
| `playbooks.ssh_credential_hook.dir_root` | `/tmp/cpkit/jobs` | Base directory for job-scoped credential material. |
| `playbooks.ssh_credential_hook.retain_artifacts_on_failure` | `false` | Keeps credential artifacts after failed jobs for debugging. Use carefully. |

These settings can be changed from the Settings UI/API. A Kloigos restart is required to load the new configuration.

## Example SSH credential prepare hook

This example is intentionally generic. Replace `request-ssh-cert` with the tool
used by your CA or access broker.

```yaml
- name: Prepare temporary SSH credential
  hosts: localhost
  connection: local
  gather_facts: no
  tasks:
    - name: Create credential directory
      file:
        path: "{{ cpkit_credential_dir }}"
        state: directory
        mode: "0700"

    - name: Generate temporary key pair
      command: ssh-keygen -t ed25519 -N "" -f "{{ cpkit_credential_dir }}/id_key"
      args:
        creates: "{{ cpkit_credential_dir }}/id_key"

    - name: Request short-lived SSH certificate
      command: >
        /usr/local/bin/request-ssh-cert
        --principal {{ target_ansible_user }}
        --host {{ target_ansible_host }}
        --public-key {{ cpkit_credential_dir }}/id_key.pub
        --out {{ cpkit_credential_dir }}/id_key-cert.pub

    - name: Restrict private key permissions
      file:
        path: "{{ cpkit_credential_dir }}/id_key"
        mode: "0600"
```

## Example SSH credential cleanup hook

```yaml
- name: Cleanup temporary SSH credential
  hosts: localhost
  connection: local
  gather_facts: no
  tasks:
    - name: Revoke certificate if supported
      command: >
        /usr/local/bin/revoke-ssh-cert
        --cert {{ cpkit_credential_dir }}/id_key-cert.pub
      failed_when: false
```

Kloigos removes the job-scoped credential directory after the run unless
artifact retention is enabled.

## Editing playbooks

Use the Playbooks page to inspect built-in playbooks, save new versions, and set
defaults. A new version affects future jobs; already-running jobs continue with
the version they started with.

Treat playbook changes like infrastructure code:

- review changes before making a version default
- test on non-production hosts first
- keep provider-specific secrets outside playbook content when possible
- prefer job-scoped temporary files over global SSH configuration
- avoid logging private keys, bearer tokens, or SSH certificate contents
