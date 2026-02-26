$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $Root ".venv-win\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Missing .venv-win. Run .\\scripts\\setup.ps1 first."
}

Set-Location $Root
& $VenvPython -m uvicorn main:app --host 0.0.0.0 --port 8080
