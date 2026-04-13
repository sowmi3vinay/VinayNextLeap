# Start API + static UI. Run from anywhere:  powershell -File scripts/run_server.ps1
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
Write-Host ""
Write-Host "Serving from: $RepoRoot" -ForegroundColor Cyan
Write-Host "Open: http://127.0.0.1:8000/  (first recommendation may download HF data — be patient)" -ForegroundColor Green
Write-Host ""
python -m uvicorn phase_6.main:app --host 127.0.0.1 --port 8000 --reload
