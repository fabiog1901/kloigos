# 🧩 Kloigos Enterprise

The contents of this directory are part of **Kloigos Enterprise**.

## ⚖️ License

All code and materials under `enterprise/` are **source-available** under the
**Kloigos Enterprise License** and are **not open source**.

Use in production requires a valid commercial license.
Redistribution and modification are governed by `LICENSE-ENTERPRISE`.

## 🤝 Contributions

External contributions to this directory are **not accepted**.

To contribute to Kloigos, please use the Apache-licensed core components in the main repository.

## 📬 More Information

For licensing, commercial use, or enterprise support, refer to project documentation or contact the Kloigos team.

---

## 🔐 Enterprise Feature: OIDC AuthN + AuthZ

Kloigos supports provider-agnostic OIDC integration (Keycloak, Okta, Entra ID, Google, Auth0, and others).

- OIDC is an enterprise feature and requires a valid license key.
- If no valid enterprise license is configured, Kloigos runs in unauthenticated mode.
- Auth routes: `/api/auth/login`, `/api/auth/callback`, `/api/auth/logout`, `/api/auth/me`
- SPA behavior: when OIDC is active and API returns `401`/`403`, the frontend shows a `Login with SSO` button.

### ⚙️ Required Configuration

Set these values in `.env` (see `.env.example`):

- `KLOIGOS_ENTERPRISE_LICENSE_KEY`
- `OIDC_ENABLED`
- `OIDC_ISSUER_URL`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET`
- `OIDC_SCOPES` (default: `openid profile email`)
- `OIDC_AUDIENCE` (optional)
- `OIDC_EXTRA_AUTH_PARAMS` (optional JSON)
- `OIDC_UI_USERNAME_CLAIM` (claim used by UI for display name; default: `preferred_username`)
- `OIDC_AUTHZ_ALLOWED_GROUPS` (required when OIDC is enabled; CSV list)
- `OIDC_AUTHZ_GROUPS_CLAIM` (claim name with user groups; default: `groups`)

### 👥 Group-Based Authorization

Authenticated users are authorized only if they belong to at least one group listed in `OIDC_AUTHZ_ALLOWED_GROUPS`.

- `OIDC_AUTHZ_ALLOWED_GROUPS`: comma-separated allowed groups (example: `aa,bb,cc,eng`)
- `OIDC_AUTHZ_GROUPS_CLAIM`: token claim containing user groups (default: `groups`)

If OIDC is disabled, or the enterprise license key is missing/invalid, Kloigos falls back to unauthenticated mode.
