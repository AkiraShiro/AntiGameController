@echo off
chcp 65001 >nul
echo ========================================
echo Build Anti-Game Controller to EXE (v2)
echo ========================================

where pyinstaller >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo PyInstaller not found. Installing...
    py -m pip install pyinstaller
)

echo.
echo Очистка предыдущей сборки...
if exist build rmdir /s /q build
if exist AntiGameController.spec del AntiGameController.spec
:: Старую заблокированную папку dist вообще не трогаем, чтобы скрипт не падал
if exist dist2 rmdir /s /q dist2

echo.
echo Building into %%TEMP%%\agc_build to avoid AV lock on project folder...
for /f %%I in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString()"') do set "BUILD_ID=%%I"
set "BUILD_DIR=%TEMP%\agc_build_%BUILD_ID%"
mkdir "%BUILD_DIR%"

py -m PyInstaller ^
 --name=AntiGameController ^
 --onefile ^
 --noconsole ^
 --workpath="%BUILD_DIR%\build" ^
 --distpath="%BUILD_DIR%\dist_temp" ^
 --add-data="styles.py;." ^
 --add-data="config_manager.py;." ^
 --add-data="process_manager.py;." ^
 --add-data="hosts_manager.py;." ^
 --add-data="autostart_manager.py;." ^
 --add-data="logger.py;." ^
 --add-data="config_storage.py;." ^
 --add-data="network_agent.py;." ^
 --add-data="network_server.py;." ^
 --add-data="auto_updater.py;." ^
 --hidden-import=PyQt5.sip ^
 --hidden-import=PyQt5.QtCore ^
 --hidden-import=PyQt5.QtGui ^
 --hidden-import=PyQt5.QtWidgets ^
 main.py

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
copy /y "%BUILD_DIR%\dist_temp\AntiGameController.exe" "dist2\AntiGameController.exe"
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
echo Build completed successfully!
echo EXE file: dist2\AntiGameController.exe
echo ========================================
pause