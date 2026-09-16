# Control-plane fixture contract

Fixture manifests declare disposable Kloigos resources for real-host validation. They are explicit
controller inputs, not production discovery: servers, allocations, addresses, and tenancy scenarios
must all be named. Use `example.yaml` as an external template; never commit tokens or private keys.

The controller consumes this contract to create and delete declared fixture resources
deterministically when requested. It remains the only environment-specific validation
configuration source.

For the unauthenticated local demo, run `make validate ARGS="fixtures setup"` before validation and
`make validate ARGS="fixtures cleanup"` afterwards. Each queued allocation/deallocation job is polled
to terminal completion. The script touches only manifest-declared allocation IDs and IP addresses.
