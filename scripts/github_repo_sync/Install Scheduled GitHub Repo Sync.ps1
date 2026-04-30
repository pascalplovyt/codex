param(
    [string]$TaskName = "GitHub Repo Sync",
    [string]$Time = "19:00",
    [string]$ConfigPath = "$PSScriptRoot\config.json",
    [string]$Job = ""
)

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "Run GitHub Repo Sync Scheduled.ps1"
if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "Sync script not found: $scriptPath"
}
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Config not found: $ConfigPath"
}

$argsList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$scriptPath`"", "-ConfigPath", "`"$ConfigPath`"")
if ($Job) {
    $argsList += @("-Job", "`"$Job`"")
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($argsList -join " ") -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::ParseExact($Time, "HH:mm", $null))
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Incrementally mirrors configured local folders to GitHub." -Force | Out-Null

Write-Host "Scheduled task registered: $TaskName"
Write-Host "Daily run time: $Time"
Write-Host "Config: $ConfigPath"
Write-Host "Logs: $PSScriptRoot\logs"
Write-Host "Manual run: $PSScriptRoot\Run GitHub Repo Sync.cmd"
