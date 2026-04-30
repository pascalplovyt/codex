$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = "C:\Users\PASCA\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$distRoot = Join-Path $workspace "outputs\exe"
$buildRoot = Join-Path $workspace "outputs\pyinstaller"
$specRoot = Join-Path $buildRoot "specs"
$entryScript = Join-Path $workspace "desktop_entry.py"

$launchers = @(
    "Launch Dashboard",
    "Stop Dashboard",
    "Rebuild Local Clone",
    "Run Full Sync",
    "Run Incremental Sync"
)

& $python -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Remove-Item -LiteralPath $distRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $buildRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $distRoot, $buildRoot, $specRoot | Out-Null

foreach ($launcher in $launchers) {
    & $python -m PyInstaller `
        --noconfirm `
        --onedir `
        --clean `
        --name $launcher `
        --distpath $distRoot `
        --workpath $buildRoot `
        --specpath $specRoot `
        $entryScript
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Write-Output "Packaged executables are available in $distRoot"
