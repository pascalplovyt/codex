param(
    [string]$ConfigPath = "$PSScriptRoot\config.json",
    [string]$Job = ""
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logPath = Join-Path $logDir "repo-sync-$stamp.log"
$scriptPath = Join-Path $PSScriptRoot "repo_sync.py"

$arguments = @("-3", $scriptPath, "--config", $ConfigPath)
if ($Job) {
    $arguments += @("--job", $Job)
}

try {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Starting GitHub repo sync" | Tee-Object -FilePath $logPath
    $process = Start-Process -FilePath "py.exe" -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$logPath.out" -RedirectStandardError "$logPath.err"
    if (Test-Path "$logPath.out") {
        Get-Content "$logPath.out" | Tee-Object -FilePath $logPath -Append
        Remove-Item "$logPath.out" -Force
    }
    if (Test-Path "$logPath.err") {
        Get-Content "$logPath.err" | Tee-Object -FilePath $logPath -Append
        Remove-Item "$logPath.err" -Force
    }
    if ($process.ExitCode -ne 0) {
        throw "repo_sync.py exited with code $($process.ExitCode)"
    }
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] GitHub repo sync finished successfully" | Tee-Object -FilePath $logPath -Append
}
catch {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: $_" | Tee-Object -FilePath $logPath -Append
    throw
}
