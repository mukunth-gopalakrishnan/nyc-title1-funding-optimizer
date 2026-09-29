<#
.SYNOPSIS
    One-command setup from a fresh clone, for Windows PowerShell.

.DESCRIPTION
    Creates a virtual environment in .venv, installs the package with its dev
    and dashboard extras, and verifies the installation reproduces the
    published results. Safe to re-run.

.EXAMPLE
    .\scripts\setup.ps1

    If PowerShell blocks the script, allow it for this session only:
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#>

$ErrorActionPreference = 'Stop'

Set-Location (Join-Path $PSScriptRoot '..')

$VenvDir  = if ($env:VENV)   { $env:VENV }   else { '.venv' }
$PythonEx = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
$MinMinor = 9

function Say  { param($m) Write-Host "`n$m" -ForegroundColor White }
function Die  { param($m) Write-Host "`nError: $m" -ForegroundColor Red; exit 1 }

if (-not (Get-Command $PythonEx -ErrorAction SilentlyContinue)) {
    Die "$PythonEx not found. Install Python 3.$MinMinor or newer from python.org, then re-run."
}

$major = & $PythonEx -c 'import sys; print(sys.version_info[0])'
$minor = & $PythonEx -c 'import sys; print(sys.version_info[1])'
if ([int]$major -lt 3 -or ([int]$major -eq 3 -and [int]$minor -lt $MinMinor)) {
    Die "Python 3.$MinMinor or newer required; found $major.$minor. Set `$env:PYTHON to a newer interpreter and re-run."
}

Say "1/3  Creating the virtual environment in $VenvDir"
if (Test-Path $VenvDir) {
    Write-Host '     already exists - reusing it'
} else {
    & $PythonEx -m venv $VenvDir
    Write-Host "     created with $(& $PythonEx --version)"
}

$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
if (-not (Test-Path $VenvPython)) { Die "virtual environment looks incomplete: $VenvPython is missing" }

Say '2/3  Installing dependencies'
& $VenvPython -m pip install --quiet --upgrade pip
& $VenvPython -m pip install --quiet -e '.[dev,dashboard]'
Write-Host '     installed'

Say '3/3  Verifying the installation'
& $VenvPython -m titlei verify
if ($LASTEXITCODE -ne 0) { Die 'verification failed - see the checks above' }

Write-Host @"

Setup complete. Activate the environment with:

    .\$VenvDir\Scripts\Activate.ps1

Then take the guided tour:

    titlei demo

"@
