@echo off
title NETRIX Server
cd /d "%~dp0"

echo.
echo  ========================================
echo   NETRIX - Enterprise Network Planning
echo  ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo  [ERROR] Python is not installed or not on PATH.
    echo  Install Python 3 from https://www.python.org/downloads/
    echo  Check "Add Python to PATH".
    pause
    exit /b 1
)

set "VENV_DIR="
if exist ".venv\Scripts\python.exe" set "VENV_DIR=.venv"
if exist "venv\Scripts\python.exe" if "%VENV_DIR%"=="" set "VENV_DIR=venv"

if "%VENV_DIR%"=="" (
    echo  Creating virtual environment (.venv)...
    python -m venv .venv
    set "VENV_DIR=.venv"
)

echo  Using interpreter: %VENV_DIR%\Scripts\python.exe
call "%VENV_DIR%\Scripts\activate.bat"

echo  Ensuring dependencies are installed...
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo  [ERROR] pip install failed. Try: install_deps.bat
    pause
    exit /b 1
)

echo.
echo  Starting server...
echo  Browser:  http://127.0.0.1:5000
echo  Register at /register   Login at /login
echo  Press Ctrl+C to stop.
echo.
python run.py
pause
