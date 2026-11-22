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

echo ========================================================
echo   Building ZFPlayer (1-File Standalone Rust EXE)
echo ========================================================
cargo build --release
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build that bai!
    pause
    exit /b 1
)

if not exist "dist" mkdir "dist"
copy /Y "target\release\ZFPlayer.exe" "dist\ZFPlayer.exe" >nul

echo.
echo [SUCCESS] Ban build Standalone 1-File EXE da san sang tai:
echo   - dist\ZFPlayer.exe
pause
