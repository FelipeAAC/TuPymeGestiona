#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

EXPECTED_RFS = [f"RF{i:02d}" for i in range(1, 27)]
ALLOWED_STATUSES = {
    "CUMPLE",
    "CUMPLE_EN_CODIGO",
    "CUMPLE_CON_DECISION_SEGURIDAD",
    "PARCIAL_FUNCIONAL",
    "PARCIAL_UI",
    "PARCIAL_QA",
    "PARCIAL_TRAZABILIDAD",
}
EXPECTED_SPECIAL = {
    "RF05": "PARCIAL_FUNCIONAL",
    "RF06": "PARCIAL_UI",
    "RF16": "PARCIAL_QA",
    "RF17": "PARCIAL_QA",
    "RF18": "CUMPLE_EN_CODIGO",
    "RF19": "CUMPLE_EN_CODIGO",
    "RF24": "PARCIAL_TRAZABILIDAD",
    "RF25": "CUMPLE_CON_DECISION_SEGURIDAD",
}


def fail(message: str) -> None:
    raise SystemExit(f"QA RF01-RF26: {message}")


def require_file(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file():
        fail(f"falta evidencia de archivo: {relative}")
    return path


def require_dir(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_dir():
        fail(f"falta evidencia de directorio: {relative}")
    return path


def require_text(root: Path, relative: str, needles: list[str]) -> None:
    path = require_file(root, relative)
    text = path.read_text(encoding="utf-8-sig")
    for needle in needles:
        if needle not in text:
            fail(f"{relative} no contiene la evidencia esperada: {needle}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica la línea base de trazabilidad RF01-RF26.")
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    root = Path(args.repository).resolve()
    if not (root / ".git").is_dir():
        fail("--repository no apunta a un repositorio Git")

    csv_path = require_file(root, "docs/qa/RF01_RF26_TRACEABILITY.csv")
    require_file(root, "docs/qa/RF01_RF26_TRACEABILITY.md")
    require_file(root, "docs/qa/QA_EVIDENCE_CHECKPOINT.md")
    require_file(root, "docs/quality/API_PUBLIC_CONTRACTS.md")
    require_file(root, "docs/quality/API_ERROR_POLICY.md")

    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required_columns = {
        "RF", "ERS_section", "Use_case", "Requirement", "API_evidence",
        "UI_evidence", "Automated_evidence", "Status", "Observation",
    }
    if not rows:
        fail("la matriz CSV está vacía")
    if set(rows[0]) != required_columns:
        fail(f"columnas CSV inesperadas: {sorted(rows[0])}")
    rfs = [row["RF"] for row in rows]
    if rfs != EXPECTED_RFS:
        fail(f"la matriz debe contener exactamente RF01-RF26 en orden; obtuvo {rfs}")
    if len(set(rfs)) != 26:
        fail("hay RF duplicados")
    for row in rows:
        for key in required_columns:
            if not row[key].strip():
                fail(f"{row['RF']} tiene el campo vacío: {key}")
        if row["Status"] not in ALLOWED_STATUSES:
            fail(f"{row['RF']} usa un estado no permitido: {row['Status']}")
    by_rf = {row["RF"]: row for row in rows}
    for rf, status in EXPECTED_SPECIAL.items():
        if by_rf[rf]["Status"] != status:
            fail(f"{rf} debe conservar la clasificación auditada {status}")

    # Evidencia transversal de código y contratos.
    checks = {
        "frontend/src/app/core/administration/administration.service.ts": [
            "/api/administration", "/companies/", "/branches/", "/users/", "/roles/",
            "/payment-methods/", "/order-statuses/", "/settings/",
        ],
        "frontend/src/app/core/catalog/catalog.service.ts": [
            "/api/catalog/products/", "/api/catalog/categories/",
        ],
        "frontend/src/app/core/customers/customers.service.ts": ["/api/customers/"],
        "frontend/src/app/core/inventory/inventory.service.ts": [
            "/api/inventory/stocks/", "/api/inventory/movements/", "/api/inventory/transfers/",
        ],
        "frontend/src/app/core/orders/orders.service.ts": [
            "/api/orders/", "/confirm/", "/prepare/", "/deliver/", "/cancel/",
        ],
        "frontend/src/app/core/sales/sales.service.ts": [
            "/api/sales/", "/payments/", "/cancel/",
        ],
        "frontend/src/app/core/portal/portal.service.ts": [
            "/api/portal/stores/", "/catalog/", "/products/", "/api/portal/orders/", "mercado-pago",
        ],
        "frontend/src/app/core/reports/reports.service.ts": [
            "/api/reports/sales/", "/api/reports/inventory/", "/export/",
        ],
        "frontend/src/app/core/auth/auth.service.ts": [
            "/api/auth/csrf/", "/api/auth/login/", "/api/auth/me/", "/api/auth/logout/",
        ],
    }
    for relative, needles in checks.items():
        require_text(root, relative, needles)

    # Las brechas RF05/RF06 se mantienen verificables: categorías no tiene endpoint detail
    # y la UI de productos no publica updateProduct en el servicio del checkpoint.
    catalog_urls = require_file(root, "backend/catalog/urls.py").read_text(encoding="utf-8-sig")
    if 'categories/<int:' in catalog_urls:
        fail("RF05 cambió: apareció endpoint de detalle de categoría; la matriz debe re-auditarse")
    catalog_service = require_file(root, "frontend/src/app/core/catalog/catalog.service.ts").read_text(encoding="utf-8-sig")
    if "updateCategory(" in catalog_service:
        fail("RF05 cambió: apareció updateCategory; la matriz debe re-auditarse")
    if "updateProduct(" in catalog_service:
        fail("RF06 cambió: apareció updateProduct en Angular; la matriz debe re-auditarse")

    # Pantallas clave.
    for page in [
        "administration", "categories", "products", "suppliers", "warehouses", "customers",
        "inventory", "orders", "sales", "portal", "portal-account", "payment-result", "reports", "login",
    ]:
        require_dir(root, f"frontend/src/app/pages/{page}")

    # En el checkpoint de Calidad Técnica existen exactamente 26 specs. Las brechas QA
    # se expresan, entre otras cosas, por ausencia de specs dedicadas en estas pantallas.
    specs = sorted((root / "frontend/src/app").rglob("*.spec.ts"))
    if len(specs) != 26:
        fail(f"el checkpoint QA espera 26 specs Angular antes de este slice; encontró {len(specs)}")
    for relative in [
        "frontend/src/app/pages/categories/categories.spec.ts",
        "frontend/src/app/pages/products/products.spec.ts",
        "frontend/src/app/pages/portal-account/portal-account.spec.ts",
    ]:
        if (root / relative).exists():
            fail(f"la brecha QA documentada cambió porque ahora existe {relative}; re-auditar matriz")

    # RF24: la administración está actualmente registrada como hija de /app en el mismo router.
    require_text(root, "frontend/src/app/app.routes.ts", ["path: 'app'", "path: 'administration'"])

    # Módulos backend relevantes.
    for module in [
        "accounts", "administration", "catalog", "customers", "inventory", "orders", "sales",
        "portal", "external_payments", "transactional_notifications", "reports", "organizations",
    ]:
        require_dir(root, f"backend/{module}")

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
    ).stdout.strip()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["Status"]] = counts.get(row["Status"], 0) + 1
    print(f"QA RF01-RF26 OK | HEAD {head}")
    print("Estados: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"Angular specs verificadas: {len(specs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
