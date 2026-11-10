@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (set "PYTHON=python") else (set "PYTHON=py -3")
if not exist ".venv\Scripts\python.exe" (
    %PYTHON% -m venv .venv
    if errorlevel 1 goto :fail
)
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean TextFileTool-v2.spec
if errorlevel 1 goto :fail
if not exist "dist\config.json" (
    if exist "config.json" (
        copy "config.json" "dist\config.json" >nul
    ) else (
        copy "config.example.json" "dist\config.json" >nul
    )
)
echo.
echo Build OK: %~dp0dist\TextFileTool-v2.exe
if not "%~1"=="--no-pause" pause
exit /b 0
:fail
echo Build failed. Check Python installation and network connection.
if not "%~1"=="--no-pause" pause
exit /b 1
