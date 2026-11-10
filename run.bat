@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "app.py"
    exit /b
)
where py >nul 2>nul
if errorlevel 1 (python app.py) else (py -3 app.py)
if errorlevel 1 pause
