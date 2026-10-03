# SSH key management

Kloigos stores reusable SSH public keys for Allocation access. It does not
persist generated private keys or provide private-key escrow.

## Import an existing public key

Importing is the preferred workflow when you already manage an SSH identity.
Open **Admin → SSH Keys**, select **Add New**, choose **Import public key**, and
paste the contents of the `.pub` file. Never paste a private key into this form.

## Generate a key pair

When you select **Generate key pair**, Kloigos creates the key pair, stores only
the public key, and returns the private key in the successful creation response.
The browser holds it only in the open creation dialog.

Save the key immediately by downloading it or copying it into an approved secret
manager. Restrict a downloaded key before using it:

```bash
chmod 600 ~/Downloads/kloigos-key.pem
```

Copying the key places it on the system clipboard, which is outside Kloigos'
control. Clear the clipboard after saving the key securely.

Closing the dialog, changing views, leaving the page, or tearing down the web
application clears the key from application state. Kloigos does not write it to
local storage, session storage, URL state, analytics, or browser-side error
messages.

## Interrupted or lost creation responses

Do not retry the generation request automatically. The first request may have
created the public-key resource even when its response did not reach the browser,
and Kloigos cannot replay the private key.

If delivery is interrupted or the private key is lost:

1. List the SSH keys and check whether the requested name exists.
2. If it exists, delete the public-key resource.
3. Create a replacement key pair and save the new private key immediately.
4. Use the replacement key for new Allocations.

Deleting a stored key definition does not alter an already-provisioned
Allocation. Manage access to existing Allocations separately.

## Operator guidance

Treat `POST /ssh-keys/` responses as sensitive even though they are short-lived.
Deployments should:

- use TLS for browser-to-proxy and proxy-to-application traffic
- preserve the application's `Cache-Control: no-store`, `Pragma: no-cache`, and
  `Expires: 0` response headers
- disable capture of request or response bodies in proxies, gateways, tracing,
  diagnostics, and error-reporting systems
- verify that access logs record metadata such as status and duration, not bodies
- test the deployed path after changing proxy or observability configuration

The creation operation is intentionally non-idempotent. A duplicate key name
returns `409 Conflict` without returning any private-key material.
