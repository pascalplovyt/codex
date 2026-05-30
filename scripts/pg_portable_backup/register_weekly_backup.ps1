# Registers one weekly Windows Scheduled Task for the combined backup runner.

param(
    [string]$TaskName = "PASCA Combined Backup Visible",
    [string]$Day      = "Sunday",
    [string]$Time     = "02:59",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$dayMap = @{
    Sunday = "SUN"
    Monday = "MON"
    Tuesday = "TUE"
    Wednesday = "WED"
    Thursday = "THU"
    Friday = "FRI"
    Saturday = "SAT"
}

if (-not $dayMap.ContainsKey($Day)) {
    throw "Unsupported day '$Day'. Use one of: $($dayMap.Keys -join ', ')"
}

if ($Uninstall) {
    Write-Host "Uninstalling scheduled task '$TaskName' ..."
    & schtasks.exe /Delete /TN $TaskName /F | Write-Host
    Write-Host "Done."
    exit 0
}

$schtasks = Get-Command schtasks.exe -ErrorAction SilentlyContinue
if (-not $schtasks) {
    Write-Error "schtasks.exe was not found on PATH."
    exit 1
}
$taskRun = "cmd.exe /c `"`"$scriptDir\run_backup.bat`" --no-pause`""

Write-Host "Registering weekly combined backup task"
Write-Host "  name     : $TaskName"
Write-Host "  command  : $taskRun"
Write-Host "  schedule : Every $Day at $Time"
Write-Host "  workdir  : $scriptDir"

& schtasks.exe /Create /TN $TaskName /SC WEEKLY /D $dayMap[$Day] /ST $Time /TR $taskRun /F /IT | Write-Host
if ($LASTEXITCODE -ne 0) {
    throw "schtasks.exe failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Registered. Verify with: Get-ScheduledTask -TaskName '$TaskName' | Format-List *"
Write-Host "This task uses the visible batch launcher and runs when the user is logged on."
