#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
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
    "RF05": "CUMPLE",
    "RF06": "CUMPLE",
    "RF16": "CUMPLE",
    "RF17": "CUMPLE",
    "RF18": "CUMPLE_EN_CODIGO",
    "RF19": "CUMPLE_EN_CODIGO",
    "RF24": "CUMPLE",
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
    path = require_file(root, relative)
    text = path.read_text(encoding="utf-8-sig")
    for needle in needles:
        if needle not in text:
            fail(f"{relative} no contiene la evidencia esperada: {needle}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica trazabilidad final RF01-RF26.")
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()

    root = Path(args.repository).resolve()
    if not (root / ".git").is_dir():
        fail("--repository no apunta a un repositorio Git")

    csv_path = require_file(root, "docs/qa/RF01_RF26_TRACEABILITY.csv")
    for relative in [
        "docs/qa/RF01_RF26_TRACEABILITY.md",
        "docs/qa/QA_EVIDENCE_CHECKPOINT.md",
        "docs/qa/RF24_ACCEPTANCE_DECISION.md",
        "docs/qa/RF24_SECONDARY_APP_IMPLEMENTATION.md",
        "docs/qa/RF24_TWO_APPS_VALIDATION.md",
        "docs/quality/API_PUBLIC_CONTRACTS.md",
        "docs/quality/API_ERROR_POLICY.md",
    ]:
        require_file(root, relative)

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

    for row in rows:
        for key in required_columns:
            if not row[key].strip():
                fail(f"{row['RF']} tiene el campo vacío: {key}")
        if row["Status"] not in ALLOWED_STATUSES:
            fail(f"{row['RF']} usa un estado no permitido: {row['Status']}")

    by_rf = {row["RF"]: row for row in rows}
    for rf, expected in EXPECTED_SPECIAL.items():
        if by_rf[rf]["Status"] != expected:
            fail(f"{rf} debe conservar la clasificación auditada {expected}")

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["Status"]] = counts.get(row["Status"], 0) + 1
    if counts != EXPECTED_COUNTS:
        fail(f"conteo inesperado: {counts}; esperado {EXPECTED_COUNTS}")

    # Evidencia ya cerrada de RF05/RF06/RF16/RF17.
    require_text(root, "backend/catalog/urls.py", ["categories/manage/", "categories/<int:category_id>/"])
    require_text(root, "backend/catalog/models.py", ["class Status(models.TextChoices):", 'INACTIVE = "INACTIVE"'])
    require_file(root, "backend/catalog/migrations/0009_category_status.py")
    require_file(root, "backend/catalog/test_qa_corrections.py")
    require_text(
        root,
        "frontend/src/app/pages/portal/portal.spec.ts",
        ["dedicated product detail", "/api/portal/stores/1/products/4/"],
    )
    require_file(root, "frontend/src/app/pages/portal-account/portal-account.spec.ts")

    # Dos proyectos Angular.
    angular = json.loads(require_file(root, "frontend/angular.json").read_text(encoding="utf-8-sig"))
    package = json.loads(require_file(root, "frontend/package.json").read_text(encoding="utf-8-sig"))

    projects = angular.get("projects", {})
    if set(projects) != {"frontend", "maintainers"}:
        fail(f"angular.json debe registrar exactamente frontend y maintainers; obtuvo {sorted(projects)}")

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
    }
    for name, expected in expected_scripts.items():
        if scripts.get(name) != expected:
            fail(f"script npm {name} inesperado: {scripts.get(name)!r}")

    secondary_files = [
        "frontend/projects/maintainers/src/main.ts",
        "frontend/projects/maintainers/src/index.html",
        "frontend/projects/maintainers/src/styles.scss",
        "frontend/projects/maintainers/src/proxy.conf.json",
        "frontend/projects/maintainers/tsconfig.app.json",
        "frontend/projects/maintainers/tsconfig.spec.json",
        "frontend/projects/maintainers/src/app/app.ts",
        "frontend/projects/maintainers/src/app/app.html",
        "frontend/projects/maintainers/src/app/app.scss",
        "frontend/projects/maintainers/src/app/api.service.ts",
        "frontend/projects/maintainers/src/app/models.ts",
        "frontend/projects/maintainers/src/app/app.spec.ts",
        "frontend/projects/maintainers/src/app/api.service.spec.ts",
    ]
    for relative in secondary_files:
        require_file(root, relative)

    require_text(
        root,
        "frontend/projects/maintainers/src/main.ts",
        ["bootstrapApplication(", "MaintainersApp", "provideHttpClient()"],
    )
    require_text(
        root,
        "frontend/projects/maintainers/src/app/api.service.ts",
        [
            "/api/auth/login/",
            "/api/auth/me/",
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
    require_text(
        root,
        "frontend/projects/maintainers/src/app/app.html",
        ["RF24 · SEGUNDA APLICACIÓN", "Administración de mantenedores"],
    )

    main_specs = sorted((root / "frontend/src/app").rglob("*.spec.ts"))
    if len(main_specs) != 29:
        fail(f"la aplicación principal espera 29 specs; encontró {len(main_specs)}")

    secondary_specs = sorted((root / "frontend/projects/maintainers/src").rglob("*.spec.ts"))
    if len(secondary_specs) != 2:
        fail(f"maintainers espera 2 specs; encontró {len(secondary_specs)}")

    for module in [
        "accounts", "administration", "catalog", "customers", "inventory", "orders",
        "sales", "portal", "external_payments", "transactional_notifications",
        "reports", "organizations",
    ]:
        require_dir(root, f"backend/{module}")

    require_text(root, "docs/qa/RF24_ACCEPTANCE_DECISION.md", ["`CUMPLE`", "sourceRoot propio"])
    require_text(
        root,
        "docs/qa/RF24_TWO_APPS_VALIDATION.md",
        ["Aplicación 1", "Aplicación 2", "npm run start:maintainers", "dist/maintainers"],
    )

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()

    print(f"QA RF01-RF26 OK | HEAD {head}")
    print("Estados: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"Specs aplicación principal: {len(main_specs)}")
    print(f"Specs aplicación secundaria: {len(secondary_specs)}")
    print("RF24: CUMPLE | dos proyectos ejecutables conectados al mismo backend")
    return 0


if __name__ == "__main__":
    sys.exit(main())
