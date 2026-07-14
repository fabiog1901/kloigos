# Getting started

This guide walks through a first Kloigos setup in standalone mode. It keeps
authentication disabled, uses the built-in demo database, initializes one Linux
server, and creates one Allocation.

For production installation details, see the [deployment guide](deployment.md).

## 1. Start Kloigos in standalone mode

Install Kloigos as described in the [deployment guide](deployment.md), then start
the built-in demo environment:

```bash
kloigos demo
```

Demo mode starts a local embedded PostgreSQL database, creates a master key if
needed, initializes the database, loads the packaged playbooks, and starts the
Kloigos web application.

When startup completes, open the URL printed by the command. By default this is:

```text
http://127.0.0.1:8000
```

For this first walkthrough, unauthenticated mode is fine.

## 2. Prepare a target Linux server

Choose a Linux server that Kloigos can manage over SSH.

The server should have:

- a reachable hostname or IP address
- a sudo-capable administrative user, such as `ubuntu`
- enough free CPU and memory for the Compute Units you want to create
- storage available for Kloigos-managed volumes
- AppArmor available on Ubuntu or Debian hosts

At the moment, the Kloigos process assumes that an SSH agent is already loaded
with a private key that can log in to the target server.

From the same shell where you run `kloigos demo`, verify access before continuing:

```bash
ssh-add -l
ssh ubuntu@your-server-hostname
```

If `ssh-add -l` reports that no identities are loaded, add the key first:

```bash
ssh-add ~/.ssh/id_ed25519
```

## 3. Reserve floating IP addresses

Kloigos assigns IP addresses to Allocations, not directly to Compute Units. Before
creating Allocations, add one or more floating IP addresses to the Kloigos IP pool.

Pick addresses from the same network as the managed server, but make sure they
will not be handed out by DHCP.

A typical home lab process is:

1. Open your router or switch management interface.
2. Find the DHCP range, for example `192.168.1.100` through `192.168.1.200`.
3. Choose a small static pool outside that range, for example:

```text
192.168.1.80
192.168.1.81
192.168.1.82
```

4. Confirm those addresses are not already assigned to another device.
5. In Kloigos, open **Admin**.
6. Open **IP Pool**.
7. Select **Add new** and add each reserved address.

These IPs will later be assigned to Allocations automatically.

## 4. Add a server

Open the Kloigos web application and go to **Servers**.

Select **Add new** to open the server wizard. The exact fields may evolve, but the
wizard will ask for the information Kloigos needs to connect to the host and
prepare Compute Units.

For a first server, expect to provide:

- hostname, such as `k01`
- server admin user, such as `ubuntu`
- region and zone labels
- runtime profile, such as `standard`
- private IP address
- Compute Unit definitions, including CPU count and memory limits
- storage sizing for each Compute Unit

Submit the wizard to schedule the server initialization job.

## 5. Watch the initialization job

After submitting the server wizard, Kloigos schedules a background job.

Open **Jobs** and select the new job to watch progress. Server initialization uses
versioned Ansible playbooks to prepare the host, create Compute Unit capacity,
configure storage, install platform helpers, and set up the base networking and
security controls. See [Playbooks](playbooks.md) for details about the built-in playbooks and how
Kloigos records playbook versions.

The server is ready for allocations when the job reaches a successful terminal
state and the Compute Units appear as available.

## 6. Create the first Allocation

Open **Allocations** and select **Add new**.

For a first Allocation, provide:

- allocation ID, such as `hello-world`
- login user, such as `hello-world`
- requested CPU count
- SSH public key for the key pair the user will use to log in
- optional tags

Use the public key, not the private key. For example:

```bash
cat ~/.ssh/id_ed25519.pub
```

The value should look similar to:

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... user@workstation
```

Kloigos will choose a suitable free Compute Unit, assign a floating IP from the
IP pool, create the Linux user identity, prepare storage, configure resource
limits, and start the Allocation job.

Open **Jobs** again to watch the Allocation creation job. When the job completes,
the Allocation page shows the assigned login user, IP address, status, and current
Compute Unit placement.

At that point, you can SSH to the Allocation using the assigned floating IP and
login user:

```bash
ssh hello-world@192.168.1.80
```

The exact IP address will be the one assigned by Kloigos from your IP pool.

## Next steps

After the first Allocation works, the rest of the lifecycle should feel familiar:

- create additional Allocations from the Allocations page
- inspect Compute Unit capacity from the Compute Units page
- review operational history from Events
- monitor and retry background jobs from Jobs
- use server decommissioning when a host should leave Kloigos management
