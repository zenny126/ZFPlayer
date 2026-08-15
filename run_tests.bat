@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   ZennyFLAC Player - Automated Unit Test Suite
echo ========================================================
echo.

cd /d "%~dp0"

REM 1. Check if virtual environment exists
if exist ".venv\Scripts\pytest.exe" (
    set "PYTEST_CMD=.venv\Scripts\pytest.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "PYTEST_CMD=.venv\Scripts\python.exe -m pytest"
) else (
    set "PYTEST_CMD=pytest"
)

echo [INFO] Running test suite via: !PYTEST_CMD!
echo --------------------------------------------------------
!PYTEST_CMD! -v tests/

if %ERRORLEVEL% equ 0 (
    echo.
    echo --------------------------------------------------------
    echo [SUCCESS] All unit tests PASSED successfully!
    echo --------------------------------------------------------
) else (
    echo.
    echo --------------------------------------------------------
    echo [FAILURE] Some tests failed. Please review the errors above.
    echo --------------------------------------------------------
)

echo.
pause
