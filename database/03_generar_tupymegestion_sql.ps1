[CmdletBinding()]
param(
    [string]$EnvFile = "backend\.env",
    [string]$OutputFile = "database\tupymegestion.sql",
    [string]$MysqlDump = "mysqldump"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ResolvedEnv = Join-Path $Root $EnvFile
$ResolvedOutput = Join-Path $Root $OutputFile

if (-not (Test-Path -LiteralPath $ResolvedEnv -PathType Leaf)) {
    throw "No se encontro $EnvFile. Crea backend\.env antes de generar el dump."
}

function Read-DotEnvValue([string]$Name) {
    $line = Get-Content -LiteralPath $ResolvedEnv | Where-Object {
        $_ -match "^\s*${Name}\s*="
    } | Select-Object -First 1
    if (-not $line) {
        return ""
    }
    $value = ($line -replace "^\s*${Name}\s*=\s*", "").Trim()
    if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    return $value
}

$dbName = Read-DotEnvValue "DB_NAME"
$dbUser = Read-DotEnvValue "DB_USER"
$dbPassword = Read-DotEnvValue "DB_PASSWORD"
$dbHost = Read-DotEnvValue "DB_HOST"
$dbPort = Read-DotEnvValue "DB_PORT"

if (-not $dbName) { $dbName = "tupymegestiona" }
if (-not $dbHost) { $dbHost = "127.0.0.1" }
if (-not $dbPort) { $dbPort = "3306" }
if (-not $dbUser) { throw "DB_USER no esta definido en $EnvFile." }

$outputDirectory = Split-Path -Parent $ResolvedOutput
if ($outputDirectory -and -not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory | Out-Null
}

$tempFile = [IO.Path]::GetTempFileName()
$stderrFile = [IO.Path]::GetTempFileName()
$previousMysqlPassword = $env:MYSQL_PWD
try {
    # MYSQL_PWD evita exponer la contraseña como argumento visible del proceso.
    $env:MYSQL_PWD = $dbPassword
    $dumpArgs = @(
        "--host=$dbHost",
        "--port=$dbPort",
        "--user=$dbUser",
        "--default-character-set=utf8mb4",
        "--single-transaction",
        "--skip-lock-tables",
        "--skip-comments",
        "--no-tablespaces",
        "--routines=false",
        "--events=false",
        "--triggers=false",
        "--add-drop-table",
        "--set-gtid-purged=OFF",
        "--column-statistics=0",
        "--no-create-db",
        "--result-file=$tempFile",
        $dbName
    )

    Write-Host "==> Generando dump MySQL de $dbName"
    & $MysqlDump @dumpArgs 2> $stderrFile
    if ($LASTEXITCODE -ne 0) {
        $details = Get-Content -Raw -LiteralPath $stderrFile
        throw "mysqldump termino con codigo $LASTEXITCODE.`n$details"
    }

    $body = Get-Content -Raw -LiteralPath $tempFile -Encoding UTF8
    $header = @"
-- TuPymeGestiona - snapshot academico reproducible
-- Generado desde una base MySQL migrada y poblada.
-- No contiene credenciales de integraciones externas.
-- Restauracion:
--   Get-Content .\database\tupymegestion.sql | mysql -u root -p

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;
CREATE DATABASE IF NOT EXISTS $dbName CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE $dbName;

"@
    $footer = @"

SET FOREIGN_KEY_CHECKS=1;
"@
    [IO.File]::WriteAllText($ResolvedOutput, $header + $body.Trim() + $footer, (New-Object Text.UTF8Encoding($false)))
    Write-Host "OK: dump generado en $OutputFile"
}
finally {
    if ($null -eq $previousMysqlPassword) {
        Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
    } else {
        $env:MYSQL_PWD = $previousMysqlPassword
    }
    Remove-Item -LiteralPath $tempFile, $stderrFile -Force -ErrorAction SilentlyContinue
}
