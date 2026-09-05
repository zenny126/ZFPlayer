@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul
title ZennyFLAC Player - Development Mode

echo ========================================================
echo   Starting ZennyFLAC Player in Development Mode
echo ========================================================
echo.

cd /d "%~dp0"

REM Check for virtual environment first
if exist ".venv\Scripts\python.exe" (
    echo [+] Using Virtual Environment: .venv
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if !errorlevel! equ 0 (
        echo [+] Using System Python...
        set "PYTHON_EXE=python"
    ) else (
        echo [!] Python is not installed or environment not setup.
        echo [*] Please run "setup_env.bat" first!
        echo.
        pause
        exit /b 1
    )
)

echo [+] Launching: !PYTHON_EXE! backend\app.py --debug
echo.
!PYTHON_EXE! backend\app.py --debug

if !errorlevel! neq 0 (
    echo.
    echo ========================================================
    echo [!] ZennyFLAC Player exited with error code !errorlevel!.
    echo [*] Check logs at: logs\app.log or logs\crash.log
    echo ========================================================
    pause
)
