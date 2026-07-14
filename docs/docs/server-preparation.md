# Server preparation

Before adding a Linux server to Kloigos, prepare the host so the server
initialization playbook can safely create Compute Unit storage.

Kloigos expects a normal Linux installation plus storage that can be managed
through LVM. The server does not need to be dedicated from an operating-system
point of view, but any storage made available to Kloigos should be considered
owned by Kloigos after initialization.

## Disk model

Kloigos creates one logical volume per Compute Unit during server initialization.
Those logical volumes are formatted as `ext4` and mounted under:

```text
/mnt/kloigos/<hostname>/cuNN
```

For example:

```text
/mnt/kloigos/k01/cu01
/mnt/kloigos/k01/cu02
/mnt/kloigos/k01/cu03
```

When an Allocation is created, Kloigos bind-mounts the Compute Unit storage into
the Allocation's user-facing filesystem layout.

## Supported storage layouts

The built-in `SERVER_INIT` playbook can use either:

- an existing LVM volume group with free space
- one or more unused whole disks with no partitions

If an existing volume group is present, Kloigos uses the volume group with the
largest amount of free space unless a customized playbook version sets
`kloigos_vg_name`.

If no suitable volume group exists, Kloigos looks for unused whole disks,
initializes them as LVM physical volumes, and creates a volume group named:

```text
kloigos-vg
```

## Recommended bare-metal layout

For a single-disk home lab server, a practical layout is:

- EFI system partition
- `/boot`
- one LVM physical volume for the remaining disk
- a root logical volume sized conservatively
- free space left in the volume group for Kloigos Compute Units

Example:

```text
NAME                     MAJ:MIN RM   SIZE RO TYPE MOUNTPOINTS
sda                        8:0    0 119.2G  0 disk
├─sda1                     8:1    0     1G  0 part /boot/efi
├─sda2                     8:2    0     2G  0 part /boot
└─sda3                     8:3    0 116.2G  0 part
  └─ubuntu--vg-ubuntu--lv
                         252:0    0  30.1G  0 lvm  /
```

In this example, the root filesystem uses about 30 GB and the remaining free
space in `ubuntu-vg` is available for Kloigos to split across Compute Unit
logical volumes.

Confirm free space with:

```bash
sudo vgs
sudo lvs
```

The important value is free space in the volume group. `lsblk` shows the
existing logical volumes, while `vgs` shows whether the volume group still has
free extents available for Kloigos.

## How Kloigos consumes free space

During server initialization, Kloigos creates one logical volume per requested
Compute Unit:

```text
cu01
cu02
cu03
...
```

The built-in playbook divides the currently free volume-group space across the
Compute Units that still need logical volumes.

For example, if a server has enough free space for three Compute Units, the
result may look like:

```text
NAME                      MAJ:MIN RM   SIZE RO TYPE MOUNTPOINTS
sda                         8:0    0 119.2G  0 disk
├─sda1                      8:1    0     1G  0 part /boot/efi
├─sda2                      8:2    0     2G  0 part /boot
└─sda3                      8:3    0 116.2G  0 part
  ├─ubuntu--vg-ubuntu--lv 252:0    0  30.1G  0 lvm  /
  ├─ubuntu--vg-cu01       252:1    0  28.7G  0 lvm  /mnt/kloigos/k01/cu01
  ├─ubuntu--vg-cu02       252:2    0  28.7G  0 lvm  /mnt/kloigos/k01/cu02
  └─ubuntu--vg-cu03       252:3    0  28.7G  0 lvm  /mnt/kloigos/k01/cu03
```

## What to avoid

Avoid adding a server if:

- the root filesystem consumes all volume-group space
- there is no existing LVM volume group and no unused whole disk
- important non-Kloigos data lives in the free storage you expect Kloigos to use
- the server cannot be accessed with the configured sudo-capable admin user

Server initialization is intentionally infrastructure-changing. It installs
packages, creates logical volumes, formats filesystems, writes mount entries,
configures nftables, and installs Kloigos helper files.

## Quick checklist

Before running server initialization:

- verify SSH access from the Kloigos control plane
- verify the admin user can run `sudo`
- run `lsblk`
- run `sudo vgs`
- confirm the volume group has enough free space for the requested Compute Units
- confirm the server hostname and private IP are stable
- reserve floating IPs separately in the Kloigos IP pool
