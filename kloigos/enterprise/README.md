# Kloigos Enterprise Features

The contents of this directory are part of **Kloigos Enterprise**.

## License

All code and materials under the `enterprise/` directory are **source-available** and are
licensed under the **Kloigos Enterprise License**. They are **not open source**.

Use of these components in production environments requires a valid commercial license.
Redistribution or modification is governed by the terms of `LICENSE-ENTERPRISE`.

## Contributions

External contributions to this directory are **not accepted**.

If you are interested in contributing to Kloigos, please see the open-source components in the
main repository and refer to the contribution guidelines for the Apache-licensed core.

## More information

For licensing inquiries, commercial use, or enterprise support, please contact the Kloigos team or refer to the project documentation.

## OIDC Authentication (FastAPI + SPA)

Kloigos supports provider-agnostic OIDC authentication (Keycloak, Okta, Entra ID, Google, Auth0, others) via environment variables.

- OIDC is an enterprise feature and requires a license key.
- If no valid enterprise license is configured, Kloigos runs in unauthenticated mode (all visitors can access the dashboard and API actions).
- Protected API routes (when OIDC is active): `/api/admin/*`, `/api/compute_units/*`
- Auth routes: `/api/auth/login`, `/api/auth/callback`, `/api/auth/logout`, `/api/auth/me`
- SPA behavior: when OIDC is active and API returns `401`/`403`, frontend shows a `Login with SSO` button

Configure values in `.env` (see `.env.example`):

- `KLOIGOS_ENTERPRISE_LICENSE_KEY`
- `OIDC_ENABLED`
- `OIDC_ISSUER_URL`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET`
- `OIDC_SCOPES` (default: `openid profile email`)
- `OIDC_AUDIENCE` (optional)
- `OIDC_EXTRA_AUTH_PARAMS` (optional JSON)
