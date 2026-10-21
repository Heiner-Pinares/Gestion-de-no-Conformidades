@echo off
setlocal
set "PORTAL_ACTION=%~1"
if "%PORTAL_ACTION%"=="" set "PORTAL_ACTION=status"
set "PORTAL_PORT=%~2"
if "%PORTAL_PORT%"=="" set "PORTAL_PORT=8001"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0gestionar_portal_windows.ps1" -Action "%PORTAL_ACTION%" -Port "%PORTAL_PORT%"
exit /b %ERRORLEVEL%
