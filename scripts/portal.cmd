@echo off
setlocal
set "PORTAL_ACTION=%~1"
if "%PORTAL_ACTION%"=="" set "PORTAL_ACTION=status"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0gestionar_portal_windows.ps1" -Action "%PORTAL_ACTION%"
exit /b %ERRORLEVEL%
