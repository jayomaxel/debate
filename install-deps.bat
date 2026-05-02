@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%install-deps.ps1"
set "POWERSHELL_EXE="
set "PS_ARGS="
set "WAIT_ON_EXIT=1"

if not exist "%PS_SCRIPT%" (
  echo install-deps.ps1 was not found next to this batch file.
  echo Expected: "%PS_SCRIPT%"
  exit /b 1
)

where pwsh.exe >nul 2>nul
if not errorlevel 1 set "POWERSHELL_EXE=pwsh.exe"

if not defined POWERSHELL_EXE (
  where powershell.exe >nul 2>nul
  if not errorlevel 1 set "POWERSHELL_EXE=powershell.exe"
)

if not defined POWERSHELL_EXE (
  echo PowerShell was not found in PATH.
  echo Install PowerShell or run this script from a Windows environment that includes powershell.exe.
  exit /b 1
)

if "%~1"=="" goto run

:parse_args
if "%~1"=="" goto run

if /i "%~1"=="-h" goto usage
if /i "%~1"=="--help" goto usage
if /i "%~1"=="/?" goto usage
if /i "%~1"=="help" goto usage

if /i "%~1"=="--skip-backend" (
  set "PS_ARGS=%PS_ARGS% -SkipBackend"
  shift
  goto parse_args
)
if /i "%~1"=="/skip-backend" (
  set "PS_ARGS=%PS_ARGS% -SkipBackend"
  shift
  goto parse_args
)
if /i "%~1"=="-SkipBackend" (
  set "PS_ARGS=%PS_ARGS% -SkipBackend"
  shift
  goto parse_args
)

if /i "%~1"=="--skip-frontend" (
  set "PS_ARGS=%PS_ARGS% -SkipFrontend"
  shift
  goto parse_args
)
if /i "%~1"=="/skip-frontend" (
  set "PS_ARGS=%PS_ARGS% -SkipFrontend"
  shift
  goto parse_args
)
if /i "%~1"=="-SkipFrontend" (
  set "PS_ARGS=%PS_ARGS% -SkipFrontend"
  shift
  goto parse_args
)

if /i "%~1"=="--skip-weasyprint-system" (
  set "PS_ARGS=%PS_ARGS% -SkipWeasyPrintSystem"
  shift
  goto parse_args
)
if /i "%~1"=="/skip-weasyprint-system" (
  set "PS_ARGS=%PS_ARGS% -SkipWeasyPrintSystem"
  shift
  goto parse_args
)
if /i "%~1"=="-SkipWeasyPrintSystem" (
  set "PS_ARGS=%PS_ARGS% -SkipWeasyPrintSystem"
  shift
  goto parse_args
)

if /i "%~1"=="--no-wait" (
  set "WAIT_ON_EXIT=0"
  shift
  goto parse_args
)
if /i "%~1"=="/no-wait" (
  set "WAIT_ON_EXIT=0"
  shift
  goto parse_args
)

echo Unknown option: %~1
echo.
goto usage_error

:run
if "%WAIT_ON_EXIT%"=="1" (
  "%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" -WaitOnExit %PS_ARGS%
) else (
  "%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %PS_ARGS%
)

exit /b %errorlevel%

:usage
echo Usage: install-deps.bat [options]
echo.
echo Options:
echo   --skip-backend             Skip backend Python dependency installation
echo   --skip-frontend            Skip frontend pnpm dependency installation
echo   --skip-weasyprint-system   Skip Windows GTK runtime check/install step
echo   --no-wait                  Do not wait for Enter before closing
echo   -h, --help, /?             Show this help message
echo.
echo Notes:
echo   By default this wrapper pauses at the end so double-click users can read the result.
echo   Use --no-wait when running from an existing terminal or automation.
exit /b 0

:usage_error
call :usage
exit /b 1
