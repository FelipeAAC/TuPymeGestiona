[CmdletBinding()]
param(
    [string]$Seed = "local-2026",
    [ValidateRange(1, 8)]
    [int]$Companies = 5,
    [ValidateRange(4, 120)]
    [int]$Products = 48,
    [ValidateRange(5, 250)]
    [int]$Customers = 70,
    [ValidateRange(4, 120)]
    [int]$Orders = 36,
    [string]$Password = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "No se encontro backend\.venv\Scripts\python.exe. Crea el entorno virtual e instala backend\requirements.txt."
}

Push-Location (Join-Path $Root "backend")
try {
    Write-Host "==> Validar configuracion Django"
    & $Python manage.py check
    if ($LASTEXITCODE -ne 0) {
        throw "manage.py check termino con codigo $LASTEXITCODE."
    }

    Write-Host "==> Aplicar migraciones pendientes"
    & $Python manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) {
        throw "manage.py migrate termino con codigo $LASTEXITCODE."
    }

    $SeedArgs = @(
        "manage.py",
        "seed_demo_data",
        "--seed", $Seed,
        "--companies", $Companies,
        "--products", $Products,
        "--customers", $Customers,
        "--orders", $Orders
    )
    if ($Password) {
        $SeedArgs += @("--password", $Password)
    }
    Write-Host "==> Poblar dataset demo mediante los servicios del dominio"
    & $Python @SeedArgs
    if ($LASTEXITCODE -ne 0) {
        throw "seed_demo_data termino con codigo $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

Write-Host "OK: base migrada y dataset demo disponible."
