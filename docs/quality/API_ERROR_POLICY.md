# HTTP Error Review Policy

This policy defines the semantics to verify during QA. It does not claim every legacy endpoint already has an identical JSON body.

- **400 Bad Request**: invalid input, malformed filters, missing required data, or validation failure.
- **403 Forbidden**: the authenticated principal lacks the required permission, company membership, branch scope, or operation authorization.
- **404 Not Found**: the resource is not available within the caller's authorized scope. Cross-tenant existence must not be disclosed.
- **409 Conflict**: a valid request cannot be completed because of current state, version, idempotency, duplicate transition, or other business conflict.
- **5xx**: unexpected server failure. Responses and UI messages must not expose stack traces, secrets, credentials, private keys, CAF/PFX material, tokens, or database passwords.

## Frontend review rule

When the backend provides a safe human-readable `detail`, the UI should preserve it when useful. Otherwise it should present a stable generic message and keep retryable form data when the workflow requires retry.

## QA evidence rule

For each RF/CU that can produce one of these status classes, QA must record:

1. endpoint and operation,
2. triggering condition,
3. expected HTTP status,
4. visible user behavior,
5. automated test or reproducible evidence,
6. tenant/isolation implications where applicable.

Any intentional deviation must be documented rather than normalized silently.
