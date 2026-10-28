# Builds dist\SnapPMa.exe (single file, no console window).
#   .\build.ps1             - run the headless tests, then build
#   .\build.ps1 -SkipTests  - build only
# Release on GitHub: raise __version__ (and __date__) in snappma\version.py, build, then create a GitHub Release
# whose tag is v<version> (e.g. v1.0.1) and attach dist\SnapPMa.exe to it. Running copies update themselves from it.
# NOTE: keep this file ASCII-only (Windows PowerShell 5.1 reads BOM-less files as ANSI).
param(
    [switch]$SkipTests,
    [string]$DistPath = "dist"
)
# PyInstaller logs to stderr; with "Stop" PowerShell 5.1 would treat that as an error, so success is judged by exit code.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$ver = & $py -c "from snappma.version import __version__; print(__version__)"

if (-not $SkipTests) {
    & $py -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
}

$exclude = @(
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtQuick",
    "PySide6.QtQml", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.Qt3DCore", "PySide6.QtMultimedia",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtNetwork", "PySide6.QtSql", "PySide6.QtTest",
    "matplotlib", "scipy", "numpy", "cv2", "PIL", "pytest"
) | ForEach-Object { "--exclude-module"; $_ }

& $py -m PyInstaller --noconfirm --clean --onefile --windowed --name SnapPMa `
    --icon "$PSScriptRoot\assets\SnapPMa.ico" --distpath $DistPath --workpath "build\work_$ver" --specpath build @exclude "$PSScriptRoot\main.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
Write-Host "Built $DistPath\SnapPMa.exe, version $ver"
Write-Host "Self-test:  $DistPath\SnapPMa.exe --selftest result.txt   (no window; writes ALL OK on success)"
