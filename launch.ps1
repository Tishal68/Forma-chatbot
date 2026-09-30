param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$appUrl = 'http://127.0.0.1:8000'
function Test-Forma {
    try {
        $definition = Invoke-RestMethod "$appUrl/openapi.json" -TimeoutSec 2
        return $definition.info.title -eq 'Forma local assistant'
    } catch { return $false }
}
if (Test-Forma) {
    if (-not $NoBrowser) { Start-Process $appUrl }
    Write-Host 'Forma is ready at http://127.0.0.1:8000'
    exit 0
}
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    Write-Host 'First-time setup is needed. Follow the Quick start section in README.md.'
    exit 1
}
if (-not (Test-Path 'frontend/dist/index.html')) {
    Write-Host 'Building the interface for the first time...'
    Push-Location frontend
    try {
        npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
        npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
try { $null = Invoke-RestMethod 'http://localhost:11434/api/tags' -TimeoutSec 2 }
catch {
    $ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaCommand) { Start-Process -FilePath $ollamaCommand.Source -ArgumentList 'serve' -WindowStyle Hidden }
}
$logDirectory = Join-Path $PSScriptRoot 'data'
$null = New-Item -ItemType Directory -Path $logDirectory -Force
$serverProcess = Start-Process -FilePath (Join-Path $PSScriptRoot '.venv/Scripts/python.exe') -ArgumentList '-m','uvicorn','app.main:app','--app-dir','backend','--host','127.0.0.1','--port','8000' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'server.log') -RedirectStandardError (Join-Path $logDirectory 'server-error.log') -PassThru
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if (Test-Forma) {
        $serverProcess.Id | Set-Content (Join-Path $logDirectory 'server.pid')
        if (-not $NoBrowser) { Start-Process $appUrl }
        Write-Host 'Forma is ready at http://127.0.0.1:8000'
        exit 0
    }
    if ($serverProcess.HasExited) { break }
    Start-Sleep -Milliseconds 500
}
Write-Host 'Forma could not start. Port 8000 may already be in use. See data/server-error.log.'
exit 1
