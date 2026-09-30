$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Set up the Python environment first. See README.md.'
}
if (-not (Test-Path 'frontend/dist/index.html')) {
    Push-Location frontend
    try { npm.cmd install; npm.cmd run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' } }
    finally { Pop-Location }
}
& .venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
