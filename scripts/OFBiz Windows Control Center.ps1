$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$ensurePostgres = Join-Path $workspace "ensure_local_postgres.ps1"
$startScript = Join-Path $workspace "start_local_ui.ps1"

Write-Output "Starting local PostgreSQL..."
& $ensurePostgres
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Output "Starting dashboard service..."
& $startScript
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Output "Dashboard service is ready at http://127.0.0.1:8787/"
