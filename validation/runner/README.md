# Validation report evaluator

`run.py` is the single runner entry point. It does not execute Linux commands: Ansible collects
per-run `evidence.json`, including commands expected to be denied by an isolation boundary, and
this program evaluates it into the versioned JSON report and exit status (`0` pass, `1` failed
check, `2` invalid input or evidence).
