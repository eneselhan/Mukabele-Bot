@echo off
echo Starting Antigravity System...

:: 1. Database Admin
start "Antigravity DB Admin" cmd /k "call .\venv\Scripts\activate && run_db_admin.bat"

:: 2. Backend API
start "Antigravity Backend API" cmd /k "call .\venv\Scripts\activate && python -m src.api_server"

:: 3. Frontend
start "Antigravity Frontend" cmd /k "cd tahkik-ui && npm run dev"

echo All services started in separate windows.
pause
