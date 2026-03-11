# Authentication

Kloigos includes built-in OIDC authentication and group-based authorization.

- Auth routes: `/api/auth/login`, `/api/auth/callback`, `/api/auth/logout`, `/api/auth/me`
- Protected APIs:
  - `/api/compute_units/*`
  - `/api/admin/*`
- If `OIDC_ENABLED=false`, Kloigos runs in unauthenticated mode.

## Required Configuration

Set these values in `.env`:

- `OIDC_ENABLED`
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
