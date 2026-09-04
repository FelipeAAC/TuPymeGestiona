# Public API Route Inventory

Checkpoint: `develop-v2` at `29e83753a18fe60a479591dcd815581ce4d51b7a`.

This document records the public route namespaces currently registered by `backend/config/urls.py`. It is a routing contract, not a replacement for endpoint-level request/response tests.

## Registered API roots

- `/api/health/`
- `/api/auth/`
- `/api/organizations/`
- `/api/catalog/`
- `/api/inventory/`
- `/api/customers/`
- `/api/orders/`
- `/api/sales/`
- `/api/v1/electronic-tax-documents/`
- `/api/v1/folio-authorizations/`
- `/api/v1/electronic-tax-operations/`
- `/api/administration/`
- `/api/portal/`
- `/api/portal/payments/`
- `/api/reports/`
- `/api/dashboard/`

`transactional_notifications` does not expose a dedicated public root at this checkpoint; it is an internal transactional capability used by business flows.

## Reports

Under `/api/reports/`:

- `options/`
- `sales/`
- `sales/export/pdf/`
- `sales/export/xls/`
- `inventory/`
- `inventory/export/pdf/`
- `inventory/export/xls/`

The Reportes slice owns authorization, tenant isolation, filtering, and exported-file content through backend tests.

## Dashboard

Under `/api/dashboard/`:

- `overview/`

The Dashboard slice owns company/sucursal scoping, operational metrics, alerts, and recent activity through backend and Angular tests.

## Contract maintenance rule

A future public endpoint addition, removal, or path rename must update this inventory in the same commit. QA RF01-RF26 will map each applicable requirement to the precise endpoint, screen, test, and evidence.
