$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$pgBin = "C:\Program Files\PostgreSQL\18\bin"
$python = "C:\Users\PASCA\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

$pgRoot = Join-Path $workspace ".local-postgres"
$dataDir = Join-Path $pgRoot "data"
$logDir = Join-Path $pgRoot "logs"
$runDir = Join-Path $pgRoot "run"
$schemaSql = Join-Path $workspace "schema_local.sql"
$schemaJson = Join-Path $workspace "schema_export.json"
$dbName = "ofbiz_world_local"
$dbPort = 55432

New-Item -ItemType Directory -Force -Path $pgRoot, $logDir, $runDir | Out-Null

if (-not (Test-Path (Join-Path $dataDir "PG_VERSION"))) {
    & (Join-Path $pgBin "initdb.exe") -D $dataDir -U postgres -A trust --encoding UTF8 --locale C
    Add-Content -Path (Join-Path $dataDir "postgresql.conf") -Value ""
    Add-Content -Path (Join-Path $dataDir "postgresql.conf") -Value "port = $dbPort"
    Add-Content -Path (Join-Path $dataDir "postgresql.conf") -Value "listen_addresses = '127.0.0.1'"
}

& (Join-Path $pgBin "pg_ctl.exe") -D $dataDir -l (Join-Path $logDir "postgres.log") -o "-p $dbPort" status 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    & (Join-Path $pgBin "pg_ctl.exe") -D $dataDir -l (Join-Path $logDir "postgres.log") -o "-p $dbPort" -w start
}

& $python (Join-Path $workspace "generate_schema_sql.py") --input $schemaJson --output $schemaSql
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$dbExists = [string](& (Join-Path $pgBin "psql.exe") -X -h 127.0.0.1 -p $dbPort -U postgres -d postgres -t -A -c "SELECT 1 FROM pg_database WHERE datname = '$dbName';")
if ($dbExists -and $dbExists.Trim()) {
    & (Join-Path $pgBin "psql.exe") -X -h 127.0.0.1 -p $dbPort -U postgres -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $dbName;"
}
& (Join-Path $pgBin "createdb.exe") -h 127.0.0.1 -p $dbPort -U postgres $dbName

& (Join-Path $pgBin "psql.exe") -X -h 127.0.0.1 -p $dbPort -U postgres -d $dbName -v ON_ERROR_STOP=1 -f $schemaSql
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Output "Local PostgreSQL clone is ready."
Write-Output "Host=127.0.0.1 Port=$dbPort Database=$dbName User=postgres"
