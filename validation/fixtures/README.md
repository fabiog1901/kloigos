# Control-plane fixture contract

Fixture manifests declare disposable Kloigos resources for real-host validation. They are explicit
controller inputs, not production discovery: servers, allocations, addresses, and tenancy scenarios
must all be named. Use `example.yaml` as an external template; never commit tokens or private keys.

The provisioning phase consumes this contract to create and delete resources deterministically.
Until then, the manifest is configuration only.

For the unauthenticated local demo, run `validation/validate fixtures setup` before validation and
`validation/validate fixtures cleanup` afterwards. Each queued allocation/deallocation job is polled
to terminal completion. The script touches only manifest-declared allocation IDs and IP addresses.
