@echo off
chcp 65001 >nul
echo ========================================================
echo   ZennyFLAC Player (Rust Edition) - Toolchain Setup
echo ========================================================

where cargo >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Rust Toolchain da duoc cai dat:
    rustc --version
    cargo --version
    pause
    exit /b 0
)

echo [INFO] Chua tim thay Rust (rustc/cargo). Dang tai rustup-init.exe...
curl --proto "=https" --tlsv1.2 -sSf https://win.rustup.rs/x86_64 -o rustup-init.exe
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Khong the tai rustup-init.exe. Vui long kiem tra ket noi mang.
    pause
    exit /b 1
)

echo [INFO] Dang cai dat Rust toolchain x86_64-pc-windows-gnullvm...
echo Toolchain gnullvm + llvm-mingw khong yeu cau cai Visual Studio C++ Build Tools.
rustup-init.exe -y --default-toolchain stable-x86_64-pc-windows-gnullvm
del /f /q rustup-init.exe >nul 2>&1

echo.
echo [DONE] Cai dat hoan tat! Hay dam bao llvm-mingw da co trong PATH va khoi dong lai terminal.
pause
