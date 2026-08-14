@echo off
chcp 65001 > nul
title ZennyFLAC Player - Build Executable
echo ========================================================
echo   ZennyFLAC Player - Packaging Standalone EXE
echo ========================================================
echo.

if exist ".venv\Scripts\python.exe" (
    echo [+] Using Virtual Environment (.venv)...
    .venv\Scripts\python.exe build_exe.py
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        echo [+] Using System Python...
        python build_exe.py
    ) else (
        echo [!] Python is not installed or environment not setup.
        echo [*] Please run "setup_env.bat" first!
        echo.
        pause
    )
)

echo.
pause
