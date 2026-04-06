param()

$ErrorActionPreference = 'Stop'

function Get-CommandPath {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name
  )

  return (Get-Command $Name -ErrorAction Stop).Source
}

function Start-DevWindow {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Title,
    [Parameter(Mandatory = $true)]
    [string]$WorkingDir,
    [Parameter(Mandatory = $true)]
    [string]$CommandText
  )

  $safeTitle = $Title.Replace("'", "''")
  $safeWorkingDir = $WorkingDir.Replace("'", "''")

  $bootstrap = @"
`$Host.UI.RawUI.WindowTitle = '$safeTitle'
Set-Location -LiteralPath '$safeWorkingDir'
$CommandText
"@

  Start-Process -FilePath "powershell.exe" `
    -WorkingDirectory $WorkingDir `
    -ArgumentList @(
      '-NoExit',
      '-NoProfile',
      '-ExecutionPolicy', 'Bypass',
      '-Command', $bootstrap
    ) | Out-Null
}

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiDir = Join-Path $rootDir 'api'
$webDir = Join-Path $rootDir 'web'
$apiPython = Join-Path $apiDir 'venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $apiDir)) {
  throw "Missing api directory: $apiDir"
}

if (-not (Test-Path -LiteralPath $webDir)) {
  throw "Missing web directory: $webDir"
}

if (-not (Test-Path -LiteralPath $apiPython)) {
  Write-Warning "api\\venv\\Scripts\\python.exe not found, falling back to system python."
  $apiPython = Get-CommandPath -Name 'python'
}

$pnpmPath = Get-CommandPath -Name 'pnpm'

if (-not (Test-Path -LiteralPath (Join-Path $webDir 'node_modules'))) {
  Write-Warning "web\\node_modules not found. Run 'pnpm install' in the web directory if the frontend fails to start."
}

$backendCommand = @"
`$env:DEBUG = 'true'
Write-Host 'Starting API on http://localhost:7860 (DEBUG=true)...' -ForegroundColor Cyan
& '$apiPython' -m uvicorn main:app --host 0.0.0.0 --port 7860 --reload
"@

$frontendCommand = @"
Write-Host 'Starting Web on http://localhost:5173 ...' -ForegroundColor Cyan
& '$pnpmPath' dev --host 0.0.0.0
"@

Start-DevWindow -Title 'AIDebate API' -WorkingDir $apiDir -CommandText $backendCommand
Start-DevWindow -Title 'AIDebate Web' -WorkingDir $webDir -CommandText $frontendCommand

Write-Host ''
Write-Host 'Development services are starting in two new PowerShell windows.' -ForegroundColor Green
Write-Host 'API:  http://localhost:7860' -ForegroundColor Green
Write-Host 'Web:  http://localhost:5173' -ForegroundColor Green
Write-Host ''
Write-Host "The API window forces DEBUG=true so the backend won't crash on a global DEBUG=release environment variable." -ForegroundColor Yellow
