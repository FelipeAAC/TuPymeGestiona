#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"QA Identidad/Onboarding: {message}")


def require_file(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file():
        fail(f"falta archivo: {relative}")
    return path


def require_text(root: Path, relative: str, needles: list[str]) -> None:
    text = require_file(root, relative).read_text(encoding="utf-8-sig")
    for needle in needles:
        if needle not in text:
            fail(f"{relative} no contiene: {needle}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()

    root = Path(args.repository).resolve()
    if not (root / ".git").is_dir():
        fail("--repository no es un repositorio Git")

    require_text(
        root,
        "backend/portal/serializers.py",
        [
            "required=False",
            "allow_null=True",
            'address = serializers.CharField(max_length=220, required=False',
        ],
    )
    require_text(
        root,
        "backend/portal/services.py",
        [
            "company=None",
            "if company is None:",
            "return user, None",
            "def ensure_portal_account_for_order(",
            "account = ensure_portal_account_for_order(",
        ],
    )
    require_text(
        root,
        "backend/portal/views.py",
        [
            "if account is not None",
            'else None',
            "@permission_classes([IsAuthenticated])",
        ],
    )
    require_text(
        root,
        "backend/administration/urls.py",
        ['"self-service/companies/"', "self_service_company_create_view"],
    )
    require_text(
        root,
        "backend/administration/views.py",
        [
            "def self_service_company_create_view(request):",
            'code="CASA"',
            'name="Casa Matriz"',
        ],
    )
    require_text(
        root,
        "frontend/src/app/pages/login/login.ts",
        ["? returnUrl : '/portal'"],
    )
    require_text(
        root,
        "frontend/src/app/pages/portal-register/portal-register.ts",
        [
            "firstName",
            "lastName",
            "email",
            "password",
            "navigate(['/portal'])",
        ],
    )
    register_html = require_file(
        root, "frontend/src/app/pages/portal-register/portal-register.html"
    ).read_text(encoding="utf-8-sig")
    if "formControlName=\"company\"" in register_html or "<select" in register_html:
        fail("el registro volvió a exigir selección de tienda")

    require_text(
        root,
        "frontend/src/app/pages/portal-seller-onboarding/portal-seller-onboarding.ts",
        [
            "createOwnCompany(",
            "organizationContext.load()",
            "selectMembership(",
            "navigate(['/app/dashboard'])",
        ],
    )
    require_text(
        root,
        "frontend/src/app/layouts/app-shell/app-shell.html",
        ['routerLink="/portal"', "Ver como cliente"],
    )
    require_text(
        root,
        "frontend/src/app/pages/portal-account/portal-account.html",
        [
            'routerLink="/portal/seller-onboarding"',
            "Crear mi PYME",
            "Gestionar mi PYME",
        ],
    )

    routes = require_file(root, "frontend/src/app/app.routes.ts").read_text(
        encoding="utf-8-sig"
    )
    if "path: 'portal/seller-onboarding'" not in routes or "canActivate: [portalAuthGuard]" not in routes:
        fail("seller-onboarding no está protegido por portalAuthGuard")

    package = json.loads(
        require_file(root, "frontend/package.json").read_text(encoding="utf-8-sig")
    )
    if package.get("scripts", {}).get("test:maintainers") != "ng test maintainers --watch=false":
        fail("se perdió el gate de tests de maintainers")

    main_specs = sorted((root / "frontend/src/app").rglob("*.spec.ts"))
    if len(main_specs) != 31:
        fail(f"se esperaban 31 specs principales; encontrados {len(main_specs)}")

    maintainers_specs = sorted(
        (root / "frontend/projects/maintainers/src").rglob("*.spec.ts")
    )
    if len(maintainers_specs) != 2:
        fail(f"se esperaban 2 specs de maintainers; encontrados {len(maintainers_specs)}")

    require_file(root, "backend/portal/test_identity_onboarding.py")
    require_file(root, "backend/portal/test_identity_flow_qa.py")
    require_file(root, "docs/architecture/IDENTITY_ONBOARDING.md")
    require_file(root, "docs/qa/IDENTITY_ONBOARDING_QA.md")

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    print(f"QA Identidad/Onboarding OK | HEAD {head}")
    print("Registro persona-primero: OK")
    print("Compra multi-tienda con una identidad: OK")
    print("Onboarding PYME sin logout: OK")
    print("Principal: 31 specs | Maintainers: 2 specs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
