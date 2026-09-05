@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul
title ZennyFLAC Player - Build Executable

echo ========================================================
echo   ZennyFLAC Player - Packaging Standalone EXE
echo ========================================================
echo.

cd /d "%~dp0"

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

echo [+] Launching: !PYTHON_EXE! build_exe.py
echo.
!PYTHON_EXE! build_exe.py

echo.
pause
