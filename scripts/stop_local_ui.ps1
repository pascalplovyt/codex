$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $workspace ".local-postgres\run\ui.pid"
$port = 8787
$stopped = $false

if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile | Select-Object -First 1
    if ($existingPid) {
        $proc = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -match "python|pythonw|py") {
            Stop-Process -Id $existingPid -Force
            $stopped = $true
        }
    }
}

try {
    $netstatLines = netstat -ano -p tcp | Select-String ":$port\s+.*LISTENING\s+(\d+)$"
    foreach ($line in $netstatLines) {
        $pid = [int]$line.Matches[0].Groups[1].Value
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $pid -Force
            $stopped = $true
        }
    }
} catch {
}

Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
if ($stopped) {
    Write-Output "Dashboard stopped."
} else {
    Write-Output "Dashboard is not running."
}
