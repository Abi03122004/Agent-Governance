$rootDir = $PSScriptRoot
if (-not $rootDir) { $rootDir = (Get-Location).Path }

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "Starting Agent Governance Platform (Local Dev)" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

Write-Host "[1/2] Launching Backend on http://localhost:8000 ..." -ForegroundColor Green
Start-Process powershell -WorkingDirectory "$rootDir\backend" -ArgumentList "-NoExit", "-Command", "`$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m uvicorn agent_security.main:app --host 0.0.0.0 --port 8000 --reload"

Write-Host "[2/2] Launching Frontend on http://localhost:3000 ..." -ForegroundColor Green
Start-Process powershell -WorkingDirectory "$rootDir\frontend" -ArgumentList "-NoExit", "-Command", "npm run dev"

Write-Host ""
Write-Host "Both services are starting in dedicated terminal windows!" -ForegroundColor Yellow
Write-Host "- Backend API & Docs: http://localhost:8000/docs"
Write-Host "- Frontend Dashboard: http://localhost:3000"
