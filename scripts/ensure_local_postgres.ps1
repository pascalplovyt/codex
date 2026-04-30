$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$pgBin = "C:\Program Files\PostgreSQL\18\bin"
$pgRoot = Join-Path $workspace ".local-postgres"
$dataDir = Join-Path $pgRoot "data"
$logDir = Join-Path $pgRoot "logs"
$logFile = Join-Path $logDir "postgres.log"
$dbPort = 55432

function Test-LocalPostgresPort {
    param(
        [string]$HostName,
        [int]$Port
    )

    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(1000, $false)) {
            $client.Close()
            return $false
        }
        $client.EndConnect($async)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-Path (Join-Path $dataDir "PG_VERSION"))) {
    throw "Local PostgreSQL data directory is missing. Run setup_local_clone.ps1 first."
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-LocalPostgresPort -HostName "127.0.0.1" -Port $dbPort)) {
    & (Join-Path $pgBin "pg_ctl.exe") -D $dataDir -l $logFile -o "-p $dbPort" status 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        & (Join-Path $pgBin "pg_ctl.exe") -D $dataDir -l $logFile -o "-p $dbPort" -w start 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Start-Process -FilePath (Join-Path $pgBin "postgres.exe") `
                -ArgumentList @("-D", $dataDir, "-p", "$dbPort") `
                -WorkingDirectory $workspace `
                -WindowStyle Hidden | Out-Null
        }
    }
}

for ($i = 0; $i -lt 30; $i++) {
    if (Test-LocalPostgresPort -HostName "127.0.0.1" -Port $dbPort) {
        Write-Output "Local PostgreSQL is listening on 127.0.0.1:$dbPort"
        exit 0
    }
    Start-Sleep -Seconds 1
}

throw "Local PostgreSQL did not start listening on 127.0.0.1:$dbPort. Check $logFile for details."
