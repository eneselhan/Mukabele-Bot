@echo off
echo Starting SQLite Web Interface...
echo Database: tahkik_data/projects/tahkik_global.db
echo.
echo Access the interface at: http://127.0.0.1:8080
echo.
python -m sqlite_web "tahkik_data/projects/tahkik_global.db" --port 8080 --host 127.0.0.1
pause
