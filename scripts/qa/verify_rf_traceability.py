#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

EXPECTED_STATUS_BY_RF = {
    **{f"RF{i:02d}": "CUMPLE" for i in range(1, 27)},
    "RF18": "CUMPLE_EN_CODIGO",
    "RF19": "CUMPLE_EN_CODIGO",
    "RF25": "CUMPLE_CON_DECISION_SEGURIDAD",
}
EXPECTED_COUNTS = {
    "CUMPLE": 23,
    "CUMPLE_EN_CODIGO": 2,
    "CUMPLE_CON_DECISION_SEGURIDAD": 1,
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
    text = require_file(root, relative).read_text(encoding="utf-8-sig")
    for needle in needles:
        if needle not in text:
            fail(f"{relative} no contiene la evidencia esperada: {needle}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica la evidencia ejecutable RF01-RF26.")
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()

    root = Path(args.repository).resolve()
    if not (root / ".git").is_dir():
        fail("--repository no apunta a un repositorio Git")

    counts = dict(Counter(EXPECTED_STATUS_BY_RF.values()))
    if counts != EXPECTED_COUNTS:
        fail(f"clasificación RF interna inválida: {counts}")

    # Backend y contratos principales.
    expected_modules = [
        "accounts",
        "administration",
        "catalog",
        "customers",
        "dashboard",
        "electronic_tax",
        "external_payments",
        "inventory",
        "orders",
        "organizations",
        "portal",
        "reports",
        "sales",
        "transactional_notifications",
    ]
    for module in expected_modules:
        require_dir(root, f"backend/{module}")

    require_text(root, "backend/accounts/urls.py", ["csrf/", "login/", "me/", "logout/"])
    require_text(root, "backend/administration/urls.py", ["users/", "roles/", "companies/", "branches/", "settings/"])
    require_text(root, "backend/catalog/urls.py", ["categories/manage/", "products/", "suppliers/"])
    require_text(root, "backend/organizations/urls.py", ["context/", "warehouses/"])
    require_text(root, "backend/orders/urls.py", ["confirm/", "prepare/", "deliver/", "cancel/"])
    require_text(root, "backend/sales/urls.py", ["payments/", "cancel/"])
    require_text(root, "backend/portal/urls.py", ["stores/", "account/", "orders/"])
    require_text(root, "backend/reports/urls.py", ["sales/export/pdf/", "inventory/export/xls/"])
    require_file(root, "backend/catalog/migrations/0009_category_status.py")
    require_file(root, "backend/portal/test_identity_onboarding.py")
    require_file(root, "backend/portal/test_identity_flow_qa.py")

    # Dos proyectos Angular independientes para RF24.
    angular = json.loads(require_file(root, "frontend/angular.json").read_text(encoding="utf-8-sig"))
    package = json.loads(require_file(root, "frontend/package.json").read_text(encoding="utf-8-sig"))
    projects = angular.get("projects", {})
    if set(projects) != {"frontend", "maintainers"}:
        fail(f"angular.json debe registrar frontend y maintainers; obtuvo {sorted(projects)}")
    if projects["frontend"].get("sourceRoot") != "src":
        fail("sourceRoot de frontend inesperado")
    if projects["maintainers"].get("root") != "projects/maintainers":
        fail("root de maintainers inesperado")
    if projects["maintainers"].get("sourceRoot") != "projects/maintainers/src":
        fail("sourceRoot de maintainers inesperado")

    scripts = package.get("scripts", {})
    expected_scripts = {
        "start": "ng serve frontend",
        "build": "ng build frontend",
        "test": "ng test frontend",
        "start:maintainers": "ng serve maintainers --port 4300",
        "build:maintainers": "ng build maintainers",
        "test:maintainers": "ng test maintainers --watch=false",
        "test:isolated": "node scripts/run-angular-specs.mjs",
    }
    for name, expected in expected_scripts.items():
        if scripts.get(name) != expected:
            fail(f"script npm {name} inesperado: {scripts.get(name)!r}")

    for relative in [
        "frontend/projects/maintainers/src/main.ts",
        "frontend/projects/maintainers/src/index.html",
        "frontend/projects/maintainers/src/app/app.ts",
        "frontend/projects/maintainers/src/app/app.html",
        "frontend/projects/maintainers/src/app/api.service.ts",
        "frontend/projects/maintainers/src/app/app.spec.ts",
        "frontend/projects/maintainers/src/app/api.service.spec.ts",
    ]:
        require_file(root, relative)

    require_text(root, "frontend/projects/maintainers/src/main.ts", ["bootstrapApplication(", "MaintainersApp", "provideHttpClient()"])
    require_text(
        root,
        "frontend/projects/maintainers/src/app/api.service.ts",
        [
            "/api/auth/login/",
            "/api/organizations/context/",
            "/api/administration/overview/",
            "/api/catalog/categories/manage/",
            "/api/catalog/products/",
            "/api/catalog/suppliers/",
            "/api/organizations/warehouses/",
        ],
    )
    require_text(
        root,
        "frontend/projects/maintainers/src/app/app.ts",
        [
            "selectMembership(",
            "createUser(",
            "createRole(",
            "createCategory(",
            "createProduct(",
            "createSupplier(",
            "createWarehouse(",
            "createPaymentMethod(",
            "editSettings(",
        ],
    )
    require_text(root, "frontend/projects/maintainers/src/app/app.html", ["RF24 · SEGUNDA APLICACIÓN", "Administración de mantenedores"])

    main_specs = sorted((root / "frontend/src/app").rglob("*.spec.ts"))
    secondary_specs = sorted((root / "frontend/projects/maintainers/src").rglob("*.spec.ts"))
    if len(main_specs) != 31:
        fail(f"la aplicación principal espera 31 specs; encontró {len(main_specs)}")
    if len(secondary_specs) != 2:
        fail(f"maintainers espera 2 specs; encontró {len(secondary_specs)}")

    # Integraciones code-complete y decisión de secretos.
    require_text(root, "backend/external_payments/provider.py", ["MERCADO_PAGO_ACCESS_TOKEN_ENV", "create_preference", "get_payment"])
    require_text(root, "backend/transactional_notifications/services.py", ["TRANSACTIONAL_EMAIL_ENABLED", "enqueue_order_status_notification", "process_pending_notifications"])
    require_text(root, "backend/config/settings.py", ["SII_ADAPTER_ENABLED", "MERCADO_PAGO_ENABLED", "TRANSACTIONAL_EMAIL_ENABLED"])

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()

    print(f"QA RF01-RF26 OK | HEAD {head}")
    print("Estados: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print(f"Specs aplicación principal: {len(main_specs)}")
    print(f"Specs aplicación secundaria: {len(secondary_specs)}")
    print("RF24: CUMPLE | dos proyectos Angular ejecutables conectados al mismo backend")
    return 0


if __name__ == "__main__":
    sys.exit(main())
