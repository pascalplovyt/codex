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
$latestJsonPath = Join-Path $PSScriptRoot "latest_status.json"
$latestTextPath = Join-Path $PSScriptRoot "latest_status.txt"

$arguments = @("-3", $scriptPath, "--config", $ConfigPath)
if ($Job) {
    $arguments += @("--job", $Job)
}

function Get-RunReason {
    param(
        [string]$Status,
        [string[]]$OutputLines,
        [int]$ExitCode,
        [string]$ErrorText
    )

    if ($Status -eq "Success") {
        $completed = $OutputLines | Where-Object { $_ -match "Completed:" } | Select-Object -Last 1
        if ($completed) {
            return ($completed -replace "^\[[^\]]+\]\s*", "")
        }
        return "All configured sync jobs completed successfully."
    }

    $errorLine = $OutputLines | Where-Object { $_ -match "ERROR:" } | Select-Object -Last 1
    if ($errorLine) {
        return ($errorLine -replace "^\[[^\]]+\]\s*", "")
    }
    if ($ErrorText) {
        return $ErrorText
    }
    return "Sync failed with exit code $ExitCode."
}

function Write-RunStatus {
    param(
        [string]$Status,
        [string]$Reason,
        [int]$ExitCode,
        [string]$LogPath
    )

    $payload = [ordered]@{
        timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        status = $Status
        reason = $Reason
        exit_code = $ExitCode
        job = $Job
        config = $ConfigPath
        log = $LogPath
    }

    $payload | ConvertTo-Json -Depth 3 | Set-Content -Path $latestJsonPath -Encoding UTF8
    @(
        "GitHub repo sync: $Status"
        "Time: $($payload.timestamp)"
        "Reason: $Reason"
        "Exit code: $ExitCode"
        "Log: $LogPath"
    ) | Set-Content -Path $latestTextPath -Encoding UTF8
}

function Send-RunNotification {
    param(
        [string]$Status,
        [string]$Reason
    )

    $title = "GitHub repo sync: $Status"
    $message = $Reason
    if ($message.Length -gt 240) {
        $message = $message.Substring(0, 237) + "..."
    }

    try {
        Add-Type -AssemblyName System.Windows.Forms | Out-Null
        Add-Type -AssemblyName System.Drawing | Out-Null
        $notify = New-Object System.Windows.Forms.NotifyIcon
        $notify.Icon = [System.Drawing.SystemIcons]::Information
        if ($Status -ne "Success") {
            $notify.Icon = [System.Drawing.SystemIcons]::Warning
        }
        $notify.BalloonTipTitle = $title
        $notify.BalloonTipText = $message
        $notify.Visible = $true
        $notify.ShowBalloonTip(10000)
        Start-Sleep -Seconds 6
        $notify.Dispose()
    }
    catch {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Notification failed: $_" | Tee-Object -FilePath $logPath -Append
    }
}

$combinedOutput = @()
$exitCode = -1

try {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Starting GitHub repo sync" | Tee-Object -FilePath $logPath
    $process = Start-Process -FilePath "py.exe" -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$logPath.out" -RedirectStandardError "$logPath.err"
    if (Test-Path "$logPath.out") {
        $outLines = Get-Content "$logPath.out"
        $combinedOutput += $outLines
        $outLines | Tee-Object -FilePath $logPath -Append
        Remove-Item "$logPath.out" -Force
    }
    if (Test-Path "$logPath.err") {
        $errLines = Get-Content "$logPath.err"
        $combinedOutput += $errLines
        $errLines | Tee-Object -FilePath $logPath -Append
        Remove-Item "$logPath.err" -Force
    }
    $exitCode = $process.ExitCode
    if ($process.ExitCode -ne 0) {
        throw "repo_sync.py exited with code $($process.ExitCode)"
    }
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] GitHub repo sync finished successfully" | Tee-Object -FilePath $logPath -Append
    $reason = Get-RunReason -Status "Success" -OutputLines $combinedOutput -ExitCode $exitCode -ErrorText ""
    Write-RunStatus -Status "Success" -Reason $reason -ExitCode $exitCode -LogPath $logPath
    Send-RunNotification -Status "Success" -Reason $reason
}
catch {
    $errorText = "$_"
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: $errorText" | Tee-Object -FilePath $logPath -Append
    $reason = Get-RunReason -Status "Failure" -OutputLines $combinedOutput -ExitCode $exitCode -ErrorText $errorText
    Write-RunStatus -Status "Failure" -Reason $reason -ExitCode $exitCode -LogPath $logPath
    Send-RunNotification -Status "Failure" -Reason $reason
    throw
}
