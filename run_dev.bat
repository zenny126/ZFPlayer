@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist "%USERPROFILE%\.cargo\bin\cargo.exe" (
    set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
)
for /d %%D in ("%USERPROFILE%\.llvm-mingw\llvm-mingw-*") do (
    if exist "%%D\bin\clang.exe" set "PATH=%%D\bin;%PATH%"
)

where cargo >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Chua cai dat Rust Toolchain! Vui long chay setup_rust.bat truoc.
    pause
    exit /b 1
)

echo [INFO] Dang khoi chay ZFPlayer (Rust Release Mode)...
cargo run --release
