$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = "C:\Users\PASCA\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

& (Join-Path $workspace "ensure_local_postgres.ps1")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $python (Join-Path $workspace "sync_ofbiz_data.py") --config "sync_config.json" --mode incremental @args
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
