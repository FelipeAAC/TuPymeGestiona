#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import subprocess
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"Higiene del repositorio: {message}")


def repository_files(root: Path) -> list[str]:
    return subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    root = Path(args.repository).resolve()
    files = repository_files(root)

    forbidden_prefixes = ("panel/", "docs/")
    forbidden_files = {
        "frontend/README.md",
        "backend/electronic_tax/OPERATIONS.md",
        "backend/transactional_notifications/OPERATIONS.md",
    }
    for relative in files:
        # Deleted tracked files remain in the index until the package stages deletions.
        # Hygiene is evaluated against the materialized filesystem before staging.
        if not (root / relative).exists():
            continue
        if relative.startswith(forbidden_prefixes):
            fail(f"permanece legado/documentación dispersa: {relative}")
        if relative in forbidden_files:
            fail(f"permanece documentación dispersa: {relative}")
        if "__pycache__/" in relative or relative.endswith(".pyc"):
            fail(f"bytecode versionado: {relative}")
        if relative.endswith(".sqlite3"):
            fail(f"base SQLite versionada: {relative}")
        if relative.endswith(".md") and relative != "README.md":
            fail(f"solo README.md debe quedar como documentación Markdown: {relative}")

    required = [
        "README.md",
        "backend/manage.py",
        "Revisar_MySQL.cmd",
        "Cargar_Datos_Demo.cmd",
        "backend/organizations/management/commands/diagnose_mysql.py",
        "backend/organizations/management/commands/seed_demo_data.py",
        "frontend/scripts/run-angular-specs.mjs",
    ]
    for relative in required:
        if not (root / relative).is_file():
            fail(f"falta archivo esperado: {relative}")

    # Todos los Python versionados fuera de migraciones deben parsear correctamente.
    for relative in files:
        if not relative.endswith(".py") or "/migrations/" in relative:
            continue
        path = root / relative
        if not path.is_file():
            continue
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=relative)

    readme = (root / "README.md").read_text(encoding="utf-8-sig")
    for heading in [
        "# TuPymeGestiona",
        "## ¿Qué es TuPymeGestiona?",
        "## Cómo levantar el proyecto localmente",
        "## Arquitectura actual",
        "## Módulos implementados",
        "## Base de datos MySQL",
        "## Datos demo",
        "## Pruebas y calidad",
        "## Estado actual",
    ]:
        if heading not in readme:
            fail(f"README incompleto; falta {heading}")

    print("Higiene del repositorio OK")
    print("Legado panel/: eliminado")
    print("Documentación dispersa: consolidada en README.md")
    print("Bytecode/SQLite versionados: ninguno")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
