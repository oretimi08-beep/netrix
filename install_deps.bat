@echo off
title NETRIX - Install Dependencies
cd /d "%~dp0"

echo.
echo  Installing NETRIX packages into the project virtual environment...
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo  [ERROR] Python not found. Install from https://www.python.org/downloads/
    echo  Enable "Add Python to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    if exist "venv\Scripts\python.exe" (
        echo  Using existing venv\
    ) else (
        echo  Creating .venv ...
        python -m venv .venv
        if errorlevel 1 (
            echo  [ERROR] Could not create virtual environment.
            pause
            exit /b 1
        )
    )
)

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=venv\Scripts\python.exe"
)

echo  Interpreter: %PY%
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo  [ERROR] pip install failed.
    pause
    exit /b 1
)

"%PY%" -c "import flask; print('OK Flask', flask.__version__)"
if errorlevel 1 (
    echo  [ERROR] Flask still missing after install.
    pause
    exit /b 1
)

echo.
echo  SUCCESS. In PyCharm:
echo    1. Interpreter = this .venv
echo    2. Run setup_pycharm.py once  (optional verify)
echo    3. Run run.py
echo.
echo  Or double-click start.bat
echo.
pause
