# Local validation controller

The canonical manual entry point is:

```bash
make validate
```

Run it from the Ubuntu development machine that can reach designated Kloigos test servers over
SSH. Set `KLOIGOS_VALIDATION_INVENTORY` to an Ansible inventory outside this repository (or an
ignored local file). The controller rejects missing, nonexistent, and localhost inventories.

The controller invokes `validation/ansible/RUN_VALIDATION.yaml`. Ansible copies the runner and
profiles to each host, runs the selected profile there, fetches its JSON report into the controller
report directory, and then propagates the runner status. Ansible only transports and collects;
the remote harness determines PASS or FAIL. No GitHub Actions, hooks, or automatic triggers are
involved.
