# Validation Ansible internals

`RUN_VALIDATION.yaml` is invoked only by `make validate`. It creates a per-run host workspace,
runs the selected group's Linux tools, fetches evidence and raw artifacts, and leaves a failed
workspace for diagnosis. `PREPARE_VALIDATION_HOST.yaml` is an administrator preparation aid; it
does not run a validation group or create fixtures.
