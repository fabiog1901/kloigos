# Kloigos Enterprise License Tool

`tools/license.py` is a standalone CLI for working with offline Kloigos enterprise
license JWTs. It can:

- sign a license payload YAML file
- decode a JWT without verifying it
- validate a JWT with an Ed25519 public key

The JWT is signed, not encrypted. Customers can inspect the payload, but cannot
change it without invalidating the signature.

## Generate Keys

Generate an Ed25519 private key:

```bash
openssl genpkey -algorithm Ed25519 -out tools/license_secret_key.pem
```

Export the matching public key:

```bash
openssl pkey -in tools/license_secret_key.pem -pubout -out tools/license_public_key.pem
```

Keep the private key secret. The public key is safe to embed in Kloigos'
`TRUSTED_LICENSE_KEYS`.

## Payload YAML

Create a payload file such as `tools/license.yaml`:

```yaml
license_id: lic-example-001
customer: Example Customer LLC
issued_at: 1782604800
expires_at: 1814140800
features:
  - rbac
  - audit_log
  - networking
  - ssh_ca
  - ha
limits:
  hosts: 20
  compute_units: 1000
  networks: 5
```

`issued_at` and `expires_at` must be Unix timestamp integers.

## Sign A License

```bash
poetry run python tools/license.py sign tools/license.yaml tools/license_secret_key.pem --kid kloigos-2026-01 -o tools/license.jwt
```

The `kid` is the signing key id placed in the JWT header. Kloigos uses it to pick
the matching public key from `TRUSTED_LICENSE_KEYS`.

## Decode A License

Decode without verifying the signature:

```bash
poetry run python tools/license.py decode tools/license.jwt
```

This prints the JWT header and payload as formatted JSON.

## Validate A License

Validate the JWT signature and payload with a public key:

```bash
poetry run python tools/license.py validate tools/license.jwt tools/license_public_key.pem
```

On success, the command prints:

```json
{
  "valid": true,
  "license": {
    "license_id": "lic-example-001"
  }
}
```

On failure, it exits non-zero and prints an error such as:

```text
invalid: Enterprise license signature is invalid.
```

## Install In Kloigos

Install the generated JWT through the cpkit settings API/UI by setting:

```text
enterprise.license = <contents of tools/license.jwt>
```

Kloigos reads this setting and exposes validated display information through:

```text
GET /api/license/status
```
