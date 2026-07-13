# Authentication

Kloigos supports OIDC authentication and group-based authorization.

- Auth routes: `/api/auth/login`, `/api/auth/callback`, `/api/auth/logout`, `/api/auth/me`
- Protected APIs:
  - `/api/compute_units/*`
  - `/api/admin/*`
- If `oidc.enabled=false`, Kloigos runs in unauthenticated mode.

## API Key HMAC Authentication

API key clients can authenticate with these headers:

- `X-CP-Access-Key`
- `X-CP-Signature`
- `X-Timestamp`

The signature is an HMAC-SHA256 hex digest over this payload:

```text
METHOD + "\n" + PATH_AND_QUERY + "\n" + X-Timestamp + "\n" + BODY
```

For example, a `POST` to `/api/compute_units/allocate?region=us-east-1` signs the
exact method, request path plus raw query string, timestamp header value, and raw
request body bytes.

Requests are rejected when `X-Timestamp` falls outside the
`auth.api_key_signature_ttl_seconds` setting.

API key secrets are stored encrypted at rest with `KLOIGOS_MASTER_KEY`, which must
be a base64-encoded 32-byte key such as the output of `openssl rand -base64 32`.
Kloigos decrypts the stored secret before verifying the request HMAC.

Here is an example bash client

```bash
#!/bin/bash

# --- Configuration ---
ACCESS_KEY="kloigos-1234567890"
SECRET_KEY="xxxxxxyyyyyyzzzzzz"
API_URL="http://localhost:8000/api/compute_units/?compute_id=s35-cu01"

# --- 1. Extract Path and Query from URL ---
# We use 'cut' to separate the protocol/host from the path/query
PATH_AND_QUERY=$(echo "$API_URL" | cut -d'/' -f4-)
# If the path is empty, default to /
[ -z "$PATH_AND_QUERY" ] && PATH_AND_QUERY="/"

# --- 2. Prepare Request Data ---
METHOD="GET"
TIMESTAMP=$(date -u "+%Y-%m-%dT%H:%M:%SZ")
BODY=' '

# --- 3. Create the String-to-Sign ---
# Order: Method + PathAndQuery + Timestamp + Body
# Using printf to avoid unexpected newlines from 'echo'
STRING_TO_SIGN=$(printf "%s\n%s\n%s\n%s" "$METHOD" "/$PATH_AND_QUERY" "$TIMESTAMP" "$BODY")

# --- 4. Generate the HMAC-SHA256 Signature ---
# We use openssl to hash the string using our secret key
SIGNATURE=$(printf "%s" "$STRING_TO_SIGN" | openssl dgst -sha256 -hmac "$SECRET_KEY" -hex | sed 's/^.* //')

# --- 5. Execute the Curl Command ---
curl -X "$METHOD" "$API_URL" \
     -H "Content-Type: application/json" \
     -H "X-CP-Access-Key: $ACCESS_KEY" \
     -H "X-Timestamp: $TIMESTAMP" \
     -H "X-CP-Signature: $SIGNATURE" \
     -d "$BODY"
```

## Required Configuration

Set `KLOIGOS_MASTER_KEY` in `.env`; it is used to encrypt API key and OIDC
session secrets at rest. OIDC and authorization values are stored as Kloigos
settings:

- `oidc.enabled`
- `oidc.issuer_url`
- `oidc.client_id`
- `oidc.client_secret`
- `oidc.scopes`
- `oidc.audience`
- `oidc.extra_auth_params`
- `oidc.redirect_uri`
- `oidc.ui_username_claim`
- `oidc.authz_readonly_groups`
- `oidc.authz_user_groups`
- `oidc.authz_admin_groups`
- `oidc.authz_groups_claim`
- `auth.api_key_signature_ttl_seconds`

## Group-Based Authorization

Authenticated users must belong to at least one configured group.

- `CP_READONLY`: can call `GET` endpoints under `/api/compute_units/*`
- `CP_USER`: can call all `/api/compute_units/*` endpoints
- `CP_ADMIN`: can call all `/api/admin/*` endpoints and all compute unit endpoints

## Cookie and Callback Settings

Optional settings:

- `oidc.cookie_secure`
- `oidc.cookie_samesite`
- `oidc.cookie_domain`
- `OIDC_VERIFY_AUDIENCE`
- `OIDC_REDIRECT_URI`

If `OIDC_REDIRECT_URI` is empty, Kloigos derives the callback URL from the incoming request.

## Current Encryption Algorithm

Kloigos currently encrypts API key secrets at rest with `AES-256-GCM`.

- `AES`: the underlying symmetric cipher
- `256`: the key size, using a 32-byte master key from `KLOIGOS_MASTER_KEY`
- `GCM`: Galois/Counter Mode, which provides both encryption and integrity protection

This means the database value is not only unreadable without the master key, but
also tamper-evident. If the stored bytes are modified, truncated, or decrypted
with the wrong master key, decryption fails instead of returning corrupted data.

For each encrypted secret, Kloigos generates a fresh random 12-byte nonce and
stores a versioned payload in this format:

```text
0x01 || 12-byte nonce || ciphertext+authentication-tag
```

Notes:

- `0x01` is the payload version, so the encryption format can evolve in the future
- the nonce is not secret, but it must be unique for each encryption under the same key
- the authentication tag is produced by AES-GCM and is validated during decryption
- the application currently uses no additional authenticated data (AAD)

The version byte is especially important for long-term maintenance. If Kloigos
ever changes the encryption scheme in response to new attacks or updated best
practices, a new version value can be introduced and documented here without
breaking the ability to read older records during migration.
