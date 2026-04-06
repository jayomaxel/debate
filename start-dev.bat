@echo off
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1"

if errorlevel 1 (
  echo.
  echo Failed to start the development services.
  pause
)
