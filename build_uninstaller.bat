@echo off
chcp 65001 >nul
echo ========================================
echo Build Anti-Game Controller Uninstaller to EXE
echo ========================================

where pyinstaller >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo PyInstaller not found. Installing...
    py -m pip install pyinstaller
)

echo.
echo Очистка предыдущей сборки uninstaller...
if exist build_uninstaller rmdir /s /q build_uninstaller
if exist AntiGameControllerUninstaller.spec del AntiGameControllerUninstaller.spec
if exist dist2\AntiGameControllerUninstaller.exe del /f /q dist2\AntiGameControllerUninstaller.exe

for /f %%I in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString()"') do set "BUILD_ID=%%I"
set "BUILD_DIR=%TEMP%\agc_uninstaller_build_%BUILD_ID%"
mkdir "%BUILD_DIR%"

py -m PyInstaller ^
 --name=AntiGameControllerUninstaller ^
 --onefile ^
 --noconsole ^
 --workpath="%BUILD_DIR%\build" ^
 --distpath="%BUILD_DIR%\dist_temp" ^
 --hidden-import=winreg ^
 uninstaller.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo BUILD ERROR!
    echo ========================================
    pause
    exit /b 1
)

echo.
echo Копирование EXE в dist2...
if not exist dist2 mkdir dist2
copy /y "%BUILD_DIR%\dist_temp\AntiGameControllerUninstaller.exe" "dist2\AntiGameControllerUninstaller.exe"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo COPY ERROR!
    echo ========================================
    pause
    exit /b 1
)

echo Очистка временной папки...
rmdir /s /q "%BUILD_DIR%"

echo.
echo ========================================
echo Uninstaller build completed successfully!
echo EXE file: dist2\AntiGameControllerUninstaller.exe
echo ========================================
pause