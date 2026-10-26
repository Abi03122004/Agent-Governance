@echo off
set "ROOT_DIR=%~dp0"
echo ===================================================
echo Starting Agent Governance Platform (Local Dev)
echo ===================================================
echo [1/2] Launching Backend on http://localhost:8000 ...
start "Agent Governance - Backend" /D "%ROOT_DIR%backend" cmd /k "set PYTHONPATH=src && .venv\Scripts\python.exe -m uvicorn agent_security.main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/2] Launching Frontend on http://localhost:3000 ...
start "Agent Governance - Frontend" /D "%ROOT_DIR%frontend" cmd /k "npm run dev"

echo.
echo Both services are starting in dedicated terminal windows!
echo - Backend API ^& Docs: http://localhost:8000/docs
echo - Frontend Dashboard: http://localhost:3000
