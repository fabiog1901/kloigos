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

Every invocation receives a controller-generated run ID. Remote runner files, reports, diagnostics,
and temporary workload paths are isolated under `/var/lib/kloigos-validation/runs/<run-id>`. Ansible
fetches the report and a compressed artifact bundle before removing successful-run state. Failed
runs retain their remote workspace as well as the fetched evidence for diagnosis.
