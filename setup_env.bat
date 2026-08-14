@echo off
chcp 65001 > nul
title ZennyFLAC Player - Setup Environment
echo ========================================================
echo   ZennyFLAC Player - Automated Environment Setup
echo ========================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] ERROR: Python not found in system PATH.
    echo [*] Please install Python 3.11+ from https://www.python.org/downloads/
    echo [*] IMPORTANT: Make sure to check "Add python.exe to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [+] Detected Python:
python --version
echo.

echo [+] Creating Python Virtual Environment (.venv)...
if not exist ".venv" (
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [!] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [+] Virtual environment created successfully.
) else (
    echo [+] .venv already exists.
)

echo.
echo [+] Upgrading pip and installing dependencies from requirements.txt...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo   SETUP COMPLETED SUCCESSFULLY!
    echo ========================================================
    echo - Run Development: double click "run_dev.bat"
    echo - Build Standalone EXE: double click "build.bat"
    echo ========================================================
) else (
    echo.
    echo [!] Errors occurred during dependency installation.
)

echo.
pause
