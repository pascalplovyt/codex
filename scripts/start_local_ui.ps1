$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = "C:\Users\PASCA\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$ensurePostgres = Join-Path $workspace "ensure_local_postgres.ps1"
$runDir = Join-Path $workspace ".local-postgres\run"
$pidFile = Join-Path $runDir "ui.pid"
$stdoutLog = Join-Path $runDir "ui.out.log"
$stderrLog = Join-Path $runDir "ui.err.log"
$port = 8787
$readyUrl = "http://127.0.0.1:$port/api/schema/objects"

function Test-DashboardResponsive {
    param(
        [string]$Url
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    } catch {
        return $false
    }
}

New-Item -ItemType Directory -Force -Path $runDir | Out-Null

if (-not (Test-Path $python)) {
    throw "Python runtime not found at $python"
}

& $ensurePostgres
if ($LASTEXITCODE -ne 0) {
    throw "Local PostgreSQL could not be started."
}

if (Test-DashboardResponsive -Url $readyUrl) {
    Write-Output "UI already running at http://127.0.0.1:8787"
    exit 0
}

if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile | Select-Object -First 1
    if ($existingPid) {
        $proc = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -match "python|pythonw|py") {
            Write-Output "Stopping stale dashboard process $existingPid"
            Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
        }
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

try {
    $netstatLines = netstat -ano -p tcp | Select-String ":$port\s+.*LISTENING\s+(\d+)$"
    foreach ($line in $netstatLines) {
        $listenerPid = [int]$line.Matches[0].Groups[1].Value
        $proc = Get-Process -Id $listenerPid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Output "Stopping stale listener on port $port (PID $listenerPid)"
            Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
        }
    }
} catch {
}

$serverScript = Join-Path $workspace "local_admin_server.py"
$process = Start-Process -FilePath $python `
    -ArgumentList @($serverScript) `
    -WorkingDirectory $workspace `
    -WindowStyle Minimized `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500

    $activeProcess = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
    if (-not $activeProcess) {
        $errorTail = ""
        if (Test-Path $stderrLog) {
            $errorTail = (Get-Content -Path $stderrLog -Tail 20) -join [Environment]::NewLine
        }
        if ($errorTail) {
            throw "Dashboard process exited immediately.`n$errorTail"
        }
        throw "Dashboard process exited immediately."
    }

    if (Test-DashboardResponsive -Url $readyUrl) {
        Set-Content -Path $pidFile -Value $process.Id
        Write-Output "UI started at http://127.0.0.1:8787"
        exit 0
    }
}

$errorTail = ""
if (Test-Path $stderrLog) {
    $errorTail = (Get-Content -Path $stderrLog -Tail 20) -join [Environment]::NewLine
}
if ($errorTail) {
    throw "Dashboard did not start listening on port $port.`n$errorTail"
}
throw "Dashboard did not start listening on port $port."
