@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo       iclass-mcp Installer (Windows)
echo ========================================

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Installation failed with exit code %ERRORLEVEL%.
    pause
    exit /b %ERRORLEVEL%
)

echo.
pause
exit /b 0
