# Authentication

Kloigos includes built-in OIDC authentication and group-based authorization.

- Auth routes: `/api/auth/login`, `/api/auth/callback`, `/api/auth/logout`, `/api/auth/me`
- Protected APIs:
  - `/api/compute_units/*`
  - `/api/admin/*`
- If `OIDC_ENABLED=false`, Kloigos runs in unauthenticated mode.

## API Key HMAC Authentication

API key clients can authenticate with these headers:

- `X-Kloigos-Access-Key`
- `X-Kloigos-Signature`
- `X-Timestamp`

The signature is an HMAC-SHA256 hex digest over this payload:

```text
METHOD + "\n" + PATH_AND_QUERY + "\n" + X-Timestamp + "\n" + BODY
```

For example, a `POST` to `/api/compute_units/allocate?region=us-east-1` signs the
exact method, request path plus raw query string, timestamp header value, and raw
request body bytes.

Requests are rejected when `X-Timestamp` falls outside
`API_KEY_SIGNATURE_TTL_SECONDS` (default: `300` seconds).

API key secrets are stored encrypted at rest with `API_KEY_MASTER_KEY`, which must
be a base64-encoded 32-byte key such as the output of `openssl rand -base64 32`.
Kloigos decrypts the stored secret before verifying the request HMAC.

Here is an example bash client

```bash
#!/bin/bash

# --- Configuration ---
ACCESS_KEY="kloigos-1234567890"
SECRET_KEY="xxxxxxyyyyyyzzzzzz"
API_URL="http://localhost:8000/api/compute_units/?compute_id=ec2-15.156.145.186_4-5"

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
     -H "X-Kloigos-Access-Key: $ACCESS_KEY" \
     -H "X-Timestamp: $TIMESTAMP" \
     -H "X-Kloigos-Signature: $SIGNATURE" \
     -d "$BODY"
```

## Required Configuration

Set these values in `.env`:

- `OIDC_ENABLED`
- `API_KEY_MASTER_KEY`
- `OIDC_ISSUER_URL`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET`
- `OIDC_SCOPES` (default: `openid profile email`)
- `OIDC_AUDIENCE` (optional)
- `OIDC_EXTRA_AUTH_PARAMS` (optional JSON object)
- `OIDC_REDIRECT_URI` (optional)
- `OIDC_UI_USERNAME_CLAIM` (default: `preferred_username`)
- `OIDC_AUTHZ_READONLY_GROUPS`
- `OIDC_AUTHZ_USER_GROUPS`
- `OIDC_AUTHZ_ADMIN_GROUPS`
- `OIDC_AUTHZ_GROUPS_CLAIM` (default: `groups`)
- `API_KEY_SIGNATURE_TTL_SECONDS` (default: `300`)

## Group-Based Authorization

Authenticated users must belong to at least one configured group.

- `OIDC_AUTHZ_READONLY_GROUPS`: can call `GET` endpoints under `/api/compute_units/*`
- `OIDC_AUTHZ_USER_GROUPS`: can call all `/api/compute_units/*` endpoints
- `OIDC_AUTHZ_ADMIN_GROUPS`: can call all `/api/admin/*` endpoints and all compute unit endpoints

## Cookie and Callback Settings

Optional settings:

- `OIDC_SESSION_COOKIE_NAME`
- `OIDC_COOKIE_SECURE`
- `OIDC_COOKIE_SAMESITE`
- `OIDC_COOKIE_DOMAIN`
- `OIDC_VERIFY_AUDIENCE`
- `OIDC_REDIRECT_URI`

If `OIDC_REDIRECT_URI` is empty, Kloigos derives the callback URL from the incoming request.

## Current Encryption Algorithm

Kloigos currently encrypts API key secrets at rest with `AES-256-GCM`.

- `AES`: the underlying symmetric cipher
- `256`: the key size, using a 32-byte master key from `API_KEY_MASTER_KEY`
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
