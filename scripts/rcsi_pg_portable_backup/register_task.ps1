# ---------------------------------------------------------------------------
#   register_task.ps1 — install a Windows Scheduled Task that runs
#   backup.py every week.
#
#   Usage (run as Administrator):
#       Set-ExecutionPolicy -Scope Process Bypass
#       .\register_task.ps1
#       .\register_task.ps1 -Day Sunday -Time 03:00
#       .\register_task.ps1 -TaskName "PG Backup" -Uninstall
# ---------------------------------------------------------------------------

param(
    [string]$TaskName = "pg_portable_backup",
    [string]$Day      = "Sunday",          # Sunday | Monday | ... | Saturday
    [string]$Time     = "03:00",           # HH:mm, 24 h
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($Uninstall) {
    Write-Host "Uninstalling scheduled task '$TaskName' ..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Done."
    exit 0
}

# Resolve 'py' launcher, fall back to python.
$py = (Get-Command py -ErrorAction SilentlyContinue)
if ($py) {
    $exe = $py.Source
    $args = "-3 `"$scriptDir\backup.py`""
} else {
    $python = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $python) {
        Write-Error "Neither 'py' nor 'python' was found on PATH. Install Python first."
        exit 1
    }
    $exe = $python.Source
    $args = "`"$scriptDir\backup.py`""
}

Write-Host "Registering Windows Scheduled Task"
Write-Host "  name     : $TaskName"
Write-Host "  command  : $exe $args"
Write-Host "  schedule : Every $Day at $Time"
Write-Host "  workdir  : $scriptDir"

$action    = New-ScheduledTaskAction   -Execute $exe -Argument $args -WorkingDirectory $scriptDir
$trigger   = New-ScheduledTaskTrigger  -Weekly -DaysOfWeek $Day -At $Time
$settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Weekly portable PostgreSQL + app backup to Google Drive." `
    -Force

Write-Host ""
Write-Host "Registered. Verify with:  Get-ScheduledTask -TaskName $TaskName | Format-List *"
Write-Host "Trigger a dry-run now:    Start-ScheduledTask -TaskName $TaskName"
