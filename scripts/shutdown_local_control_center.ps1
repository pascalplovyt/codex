$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$pgBin = "C:\Program Files\PostgreSQL\18\bin"
$psql = Join-Path $pgBin "psql.exe"
$pgCtl = Join-Path $pgBin "pg_ctl.exe"
$dataDir = Join-Path $workspace ".local-postgres\data"
$logFile = Join-Path $workspace ".local-postgres\logs\postgres.log"
$dbPort = 55432
$dbName = "ofbiz_world_local"
$dbUser = "postgres"

function Stop-SyncWorkers {
    $patterns = @(
        "*sync_ofbiz_data.py*",
        "*sync_full.ps1*",
        "*sync_incremental.ps1*"
    )

    $processes = foreach ($process in Get-CimInstance Win32_Process) {
        if (-not $process.CommandLine) {
            continue
        }
        $matches = $false
        foreach ($pattern in $patterns) {
            if ($process.CommandLine -like $pattern) {
                $matches = $true
                break
            }
        }
        if ($matches) {
            $process
        }
    }

    foreach ($process in $processes) {
        try {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        } catch {
        }
    }
}

function Mark-RunningSyncsStopped {
    try {
        & $psql -X -h 127.0.0.1 -p $dbPort -U $dbUser -d $dbName -v ON_ERROR_STOP=1 -c "UPDATE codex_sync.sync_run SET status='failed', finished_at=now(), details = COALESCE(details, '{}'::jsonb) || jsonb_build_object('recovery_note','Stopped by Exit button in control center.') WHERE status='running';" | Out-Null
    } catch {
    }
}

function Stop-LocalPostgres {
    if (-not (Test-Path (Join-Path $dataDir "PG_VERSION"))) {
        return
    }

    try {
        & $pgCtl -D $dataDir -l $logFile -o "-p $dbPort" -m fast -w stop 2>$null | Out-Null
    } catch {
    }
}

function Stop-Dashboard {
    & (Join-Path $workspace "stop_local_ui.ps1") | Out-Null
}

Start-Sleep -Seconds 1
Stop-SyncWorkers
Mark-RunningSyncsStopped
Stop-LocalPostgres
Stop-Dashboard
