@echo off
setlocal
chcp 65001 >nul
where cargo >nul 2>nul || (echo Rust toolchain is required: https://rustup.rs/ & exit /b 1)
cargo build --release --bin uninstaller --target x86_64-pc-windows-msvc
if errorlevel 1 exit /b 1
if not exist dist2 mkdir dist2
copy /Y target\x86_64-pc-windows-msvc\release\uninstaller.exe dist2\AntiGameControllerUninstaller.exe