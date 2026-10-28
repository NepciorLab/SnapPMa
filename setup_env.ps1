# Creates the .venv virtual environment and installs the dependencies (run once on a new computer).
# Needs Python 3.10+. -CheckOnly only reports which Python would be used.
# NOTE: keep this file ASCII-only (Windows PowerShell 5.1 reads BOM-less files as ANSI).
param([switch]$CheckOnly)
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

$found = $null
foreach ($c in @(@("py", "-3"), @("python"))) {
    $exe = $c[0]
    $extra = @()
    if ($c.Length -gt 1) { $extra = $c[1..($c.Length - 1)] }
    try {
        $v = (& $exe @extra --version 2>&1 | Out-String)
        if ($LASTEXITCODE -eq 0 -and $v -match "Python 3\.(\d+)" -and [int]$Matches[1] -ge 10) {
            $found = @{ Exe = $exe; Extra = $extra; Version = $v.Trim() }
            break
        }
    } catch { }
}
if (-not $found) {
    Write-Host "Python 3.10+ not found. Install it from https://www.python.org/downloads/ and run again."
    exit 1
}
Write-Host "Using: $($found.Exe) $($found.Extra -join ' ')  ($($found.Version))"
if ($CheckOnly) { exit 0 }

& $found.Exe @($found.Extra) -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Write-Host ""
Write-Host "Done. Run the program:  .\run.bat   tests:  .\.venv\Scripts\python.exe -m pytest tests   build exe:  .\build.ps1"
