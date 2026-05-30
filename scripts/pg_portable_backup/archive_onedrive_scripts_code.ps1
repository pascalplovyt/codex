[CmdletBinding()]
param(
    [string]$SourceRoot = "C:\Users\PASCA\OneDrive\Documents\Scripts",
    [string]$DestinationRoot = "G:\My Drive\PG_Backups\onedrive_scripts_code",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$systemName = "onedrive_scripts_code"
$timestamp = Get-Date -Format "yyyyMMddTHHmmss"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$stagingRoot = Join-Path $scriptDir "staging\onedrive_scripts_code"
$logsRoot = Join-Path $scriptDir "logs\onedrive_scripts_code"
$workDir = Join-Path $stagingRoot "${systemName}_${timestamp}"
$payloadDir = Join-Path $workDir "payload"
$metadataDir = Join-Path $workDir "metadata"
$logPath = Join-Path $logsRoot "${systemName}_${timestamp}.log"
$archivePath = Join-Path $DestinationRoot "${systemName}_${timestamp}.tar.gz"

$excludedDirectoryNames = @(
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "logs",
    "staging",
    "portable_restore_staging",
    "portable_archives",
    ".local-postgres"
)

$excludedFileExtensions = @(
    ".pyc",
    ".pyo",
    ".log",
    ".tmp",
    ".tar",
    ".gz",
    ".zip",
    ".7z"
)

function Write-ArchiveLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -LiteralPath $logPath -Encoding UTF8 -Value $line
}

function Get-RelativePath {
    param(
        [string]$BasePath,
        [string]$TargetPath
    )
    $baseUri = [System.Uri]::new(($BasePath.TrimEnd("\") + "\"))
    $targetUri = [System.Uri]::new($TargetPath)
    [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($targetUri).ToString()).Replace("/", "\")
}

function Test-IsExcluded {
    param([System.IO.FileInfo]$File)

    foreach ($part in $File.FullName.Substring($SourceRoot.Length).TrimStart("\").Split("\")) {
        if ($excludedDirectoryNames -contains $part) {
            return $true
        }
    }

    if ($excludedFileExtensions -contains $File.Extension.ToLowerInvariant()) {
        return $true
    }

    return $false
}

if (-not (Test-Path -LiteralPath $SourceRoot)) {
    throw "Source root not found: $SourceRoot"
}

if (-not (Test-Path -LiteralPath (Split-Path -Parent $DestinationRoot))) {
    throw "Destination parent not found: $(Split-Path -Parent $DestinationRoot)"
}

New-Item -ItemType Directory -Force -Path $logsRoot | Out-Null
New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
if (Test-Path -LiteralPath $workDir) {
    Remove-Item -LiteralPath $workDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $payloadDir | Out-Null
New-Item -ItemType Directory -Force -Path $metadataDir | Out-Null

Write-ArchiveLog "Starting $systemName backup"
Write-ArchiveLog "Source root: $SourceRoot"
Write-ArchiveLog "Destination: $archivePath"

$files = Get-ChildItem -LiteralPath $SourceRoot -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { -not (Test-IsExcluded -File $_) } |
    Sort-Object FullName

$manifest = [System.Collections.Generic.List[object]]::new()
$totalBytes = 0L
$count = 0

foreach ($file in $files) {
    $relative = Get-RelativePath -BasePath $SourceRoot -TargetPath $file.FullName
    $payloadRelative = Join-Path "C\Users\PASCA\OneDrive\Documents\Scripts" $relative
    $destination = Join-Path $payloadDir $payloadRelative
    $totalBytes += $file.Length
    $count += 1

    if (($count % 250) -eq 0) {
        Write-ArchiveLog "Scanned $count files..."
    }

    $manifest.Add([ordered]@{
        original_absolute_path = $file.FullName
        restore_relative_path = $payloadRelative
        size_bytes = $file.Length
        last_write_time = $file.LastWriteTime.ToString("s")
    }) | Out-Null

    if (-not $DryRun) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
    }
}

$metadata = [ordered]@{
    system_name = $systemName
    created_at = (Get-Date).ToString("s")
    source_root = $SourceRoot
    intended_restore_root = "C:\Users\PASCA\OneDrive\Documents\Scripts"
    archive_path = $archivePath
    file_count = $manifest.Count
    total_bytes = $totalBytes
    exclusions = [ordered]@{
        directory_names = $excludedDirectoryNames
        file_extensions = $excludedFileExtensions
    }
    notes = @(
        "This archive is for disaster recovery of the OneDrive Scripts project tree.",
        "Files are stored under payload/C/Users/PASCA/OneDrive/Documents/Scripts to make the original Windows path obvious.",
        "metadata/manifest.json records each original absolute path."
    )
}

if ($DryRun) {
    Write-ArchiveLog "DRY-RUN: would archive $($manifest.Count) files, $totalBytes bytes"
    exit 0
}

($metadata | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath (Join-Path $metadataDir "metadata.json") -Encoding UTF8
($manifest | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath (Join-Path $metadataDir "manifest.json") -Encoding UTF8

$restoreReadme = @"
# Restore Map - onedrive_scripts_code

Original source root:

```
$SourceRoot
```

Intended restore root on a rebuilt computer:

```
C:\Users\PASCA\OneDrive\Documents\Scripts
```

The archive stores files under:

```
payload\C\Users\PASCA\OneDrive\Documents\Scripts
```

Use `metadata\manifest.json` to see the original absolute path for every file.
"@
$restoreReadme | Set-Content -LiteralPath (Join-Path $metadataDir "RESTORE_MAP.md") -Encoding UTF8

Write-ArchiveLog "Copied $($manifest.Count) files into staging"
Write-ArchiveLog "Creating archive..."
& tar.exe -czf $archivePath -C $workDir .
if ($LASTEXITCODE -ne 0) {
    throw "tar.exe failed with exit code $LASTEXITCODE"
}

$archive = Get-Item -LiteralPath $archivePath
Write-ArchiveLog "Archive created: $($archive.FullName) ($($archive.Length) bytes)"

Remove-Item -LiteralPath $workDir -Recurse -Force
Write-ArchiveLog "Done"
exit 0
