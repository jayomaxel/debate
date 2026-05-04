param(
  [string]$PublicBaseUrl = "",
  [int]$ApiPort = 7860,
  [int]$WebPort = 8860
)

$ErrorActionPreference = 'Stop'

function Get-CommandPath {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [switch]$PreferCmdWrapper
  )

  if ($PreferCmdWrapper -and $IsWindows) {
    $cmdCommand = Get-Command "$Name.cmd" -ErrorAction SilentlyContinue
    if ($cmdCommand) {
      return $cmdCommand.Source
    }
  }

  return (Get-Command $Name -ErrorAction Stop).Source
}

function Get-FrontendDevCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string]$WebDir
  )

  $pnpmCommand = Get-Command 'pnpm.cmd' -ErrorAction SilentlyContinue
  if (-not $pnpmCommand) {
    $pnpmCommand = Get-Command 'pnpm' -ErrorAction SilentlyContinue
  }
  if ($pnpmCommand) {
    return "& '$($pnpmCommand.Source)' dev --host 0.0.0.0 --port $WebPort"
  }

  $localVite = Join-Path $WebDir 'node_modules\.bin\vite.CMD'
  if (Test-Path -LiteralPath $localVite) {
    return "& '$localVite' --host 0.0.0.0 --port $WebPort"
  }

  $npmCommand = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
  if (-not $npmCommand) {
    $npmCommand = Get-Command 'npm' -ErrorAction SilentlyContinue
  }
  if ($npmCommand) {
    return "& '$($npmCommand.Source)' exec -- vite --host 0.0.0.0 --port $WebPort"
  }

  throw "Missing frontend runner. Install pnpm or run npm install in the web directory."
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

if (-not (Test-Path -LiteralPath (Join-Path $webDir 'node_modules'))) {
  Write-Warning "web\\node_modules not found. Run 'pnpm install' in the web directory if the frontend fails to start."
}

$escapedPublicBaseUrl = $PublicBaseUrl.Replace("'", "''")
$frontendDevCommand = Get-FrontendDevCommand -WebDir $webDir

$backendCommand = @"
`$env:DEBUG = 'true'
Write-Host 'Starting API on http://localhost:$ApiPort (DEBUG=true)...' -ForegroundColor Cyan
if ('$escapedPublicBaseUrl') {
  `$env:PUBLIC_BASE_URL = '$escapedPublicBaseUrl'
  Write-Host "Resolved PUBLIC_BASE_URL: `$env:PUBLIC_BASE_URL" -ForegroundColor Green
} else {
  Remove-Item Env:PUBLIC_BASE_URL -ErrorAction SilentlyContinue
  Write-Host 'PUBLIC_BASE_URL was not provided. The backend will fall back to api/.env.' -ForegroundColor Yellow
}
& '$apiPython' -m uvicorn main:app --host 0.0.0.0 --port $ApiPort --reload
"@

$frontendCommand = @"
Write-Host "Starting Web on http://localhost:$WebPort ..." -ForegroundColor Cyan
Write-Host "Web working directory: $webDir" -ForegroundColor Green
$frontendDevCommand
"@

Start-DevWindow -Title 'AIDebate API' -WorkingDir $apiDir -CommandText $backendCommand
Start-DevWindow -Title 'AIDebate Web' -WorkingDir $webDir -CommandText $frontendCommand

Write-Host ''
Write-Host 'Development services are starting in two new PowerShell windows.' -ForegroundColor Green
Write-Host "Project root: $rootDir" -ForegroundColor Green
Write-Host "API:  http://localhost:$ApiPort" -ForegroundColor Green
Write-Host "Web:  http://localhost:$WebPort" -ForegroundColor Green
if ($PublicBaseUrl) {
  Write-Host "Public Base URL: $PublicBaseUrl" -ForegroundColor Green
} else {
  Write-Host 'Public Base URL: not set for this local session.' -ForegroundColor Yellow
}
Write-Host ''
Write-Host "The API window forces DEBUG=true so the backend won't crash on a global DEBUG=release environment variable." -ForegroundColor Yellow
