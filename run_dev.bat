@echo off
chcp 65001 > nul
title ZennyFLAC Player - Development Mode
echo ========================================================
echo   Starting ZennyFLAC Player in Development Mode
echo ========================================================
echo.

if exist ".venv\Scripts\python.exe" (
    echo [+] Using Virtual Environment (.venv)...
    .venv\Scripts\python.exe backend\app.py --debug
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        echo [+] Using System Python...
        python backend\app.py --debug
    ) else (
        echo [!] Python is not installed or environment not setup.
        echo [*] Please run "setup_env.bat" first!
        echo.
        pause
    )
)
