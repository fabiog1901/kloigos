# Local validation controller

The canonical manual entry point is:

```bash
make validate
```

Run it from the Ubuntu development machine that can reach designated Kloigos test servers over
SSH. Set `KLOIGOS_VALIDATION_INVENTORY` to an Ansible inventory outside this repository (or an
ignored local file). The controller rejects missing, nonexistent, and localhost inventories.

This phase establishes the safe invocation contract only. It deliberately exits nonzero rather
than claim validation passed until the next phase installs remote Ansible orchestration. No GitHub
Actions, hooks, or automatic triggers are involved.
