$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Venv = Join-Path $Root ".venv-win"
$VenvPython = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    if (Test-Path $Venv) {
        Remove-Item -Recurse -Force $Venv
    }
    py -3 -m venv $Venv
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $Root "requirements.txt")

Write-Host "Setup complete."
Write-Host "Activate with: .\\.venv-win\\Scripts\\Activate.ps1"
