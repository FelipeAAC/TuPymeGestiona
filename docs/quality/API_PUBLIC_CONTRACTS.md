# Public API Route Inventory

Checkpoint: `develop-v2` after QA corrections, based on `41306f3c826f17e87e4a8bec19ed4a6562597f38`.

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

## Catalog corrections

Under `/api/catalog/` the RF05/RF06 correction slice confirms these management contracts:

- `categories/` — list/create compatibility endpoint.
- `categories/manage/` — management list including category operational status.
- `categories/<id>/` — retrieve/update category, including `ACTIVE`/`INACTIVE` state.
- `products/<id>/` — retrieve/update product; Angular now exposes this existing PATCH contract.

Inactive categories are excluded from product management options so new/updated products cannot be assigned to a disabled category.

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
