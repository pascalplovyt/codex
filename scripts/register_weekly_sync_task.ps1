param(
    [string]$TaskName = "OFBiz Local Incremental Sync",
    [string]$DayOfWeek = "Sunday",
    [string]$Time = "02:00"
)

$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$pwsh = "C:\Program Files\PowerShell\7\pwsh.exe"
$script = Join-Path $workspace "sync_incremental.ps1"

$action = New-ScheduledTaskAction -Execute $pwsh -Argument "-ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DayOfWeek -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Incremental sync from remote OFBiz into the local PostgreSQL clone." -Force | Out-Null

Write-Output "Registered scheduled task '$TaskName' for $DayOfWeek at $Time."
