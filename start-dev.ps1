param(
  [string]$PublicBaseUrl = "",
  [int]$ApiPort = 7860,
  [int]$WebPort = 8860
)

$ErrorActionPreference = 'Stop'

function Get-CommandPath {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name
  )

  return (Get-Command $Name -ErrorAction Stop).Source
}

function Get-CpolarPublicBaseUrl {
  function Get-PreferredTunnelUrl {
    param(
      [Parameter(Mandatory = $true)]
      [string]$Line
    )

    $urlMatches = [regex]::Matches($Line, 'https?://[a-zA-Z0-9.-]+')
    if ($urlMatches.Count -eq 0) {
      return $null
    }

    $httpsMatch = $urlMatches | Where-Object { $_.Value -like 'https://*' } | Select-Object -Last 1
    if ($httpsMatch) {
      return $httpsMatch.Value.TrimEnd('/')
    }

    return $urlMatches[$urlMatches.Count - 1].Value.TrimEnd('/')
  }

  $logDir = Join-Path $env:USERPROFILE '.cpolar\logs'
  if (-not (Test-Path -LiteralPath $logDir)) {
    return $null
  }

  $logFiles = Get-ChildItem -LiteralPath $logDir -Filter 'cpolar_service.log*' -File |
    Sort-Object LastWriteTime -Descending

  foreach ($logFile in $logFiles) {
    $publicUrlMatch = Select-String -Path $logFile.FullName -Pattern 'PublicUrl.*https?://[a-zA-Z0-9.-]+' |
      Select-Object -Last 1
    if ($publicUrlMatch) {
      $resolvedUrl = Get-PreferredTunnelUrl -Line $publicUrlMatch.Line
      if ($resolvedUrl) {
        return $resolvedUrl
      }
    }

    $newTunnelMatch = Select-String -Path $logFile.FullName -Pattern 'NewTunnel.*https?://[a-zA-Z0-9.-]+' |
      Select-Object -Last 1
    if ($newTunnelMatch) {
      $resolvedUrl = Get-PreferredTunnelUrl -Line $newTunnelMatch.Line
      if ($resolvedUrl) {
        return $resolvedUrl
      }
    }
  }

  return $null
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

if (-not $PublicBaseUrl) {
  $PublicBaseUrl = Get-CpolarPublicBaseUrl
}

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

$escapedPublicBaseUrl = $PublicBaseUrl.Replace("'", "''")

$backendCommand = @"
`$env:DEBUG = 'true'
Write-Host 'Starting API on http://localhost:$ApiPort (DEBUG=true)...' -ForegroundColor Cyan
if ('$escapedPublicBaseUrl') {
  `$env:PUBLIC_BASE_URL = '$escapedPublicBaseUrl'
  Write-Host "Resolved PUBLIC_BASE_URL: `$env:PUBLIC_BASE_URL" -ForegroundColor Green
} else {
  Remove-Item Env:PUBLIC_BASE_URL -ErrorAction SilentlyContinue
  Write-Warning 'PUBLIC_BASE_URL was not auto-detected. The backend will fall back to api/.env if it exists.'
}
& '$apiPython' -m uvicorn main:app --host 0.0.0.0 --port $ApiPort --reload
"@

$frontendCommand = @"
Write-Host "Starting Web on http://localhost:$WebPort ..." -ForegroundColor Cyan
& '$pnpmPath' dev --host 0.0.0.0 --port $WebPort
"@

Start-DevWindow -Title 'AIDebate API' -WorkingDir $apiDir -CommandText $backendCommand
Start-DevWindow -Title 'AIDebate Web' -WorkingDir $webDir -CommandText $frontendCommand

Write-Host ''
Write-Host 'Development services are starting in two new PowerShell windows.' -ForegroundColor Green
Write-Host "API:  http://localhost:$ApiPort" -ForegroundColor Green
Write-Host "Web:  http://localhost:$WebPort" -ForegroundColor Green
if ($PublicBaseUrl) {
  Write-Host "Public Base URL: $PublicBaseUrl" -ForegroundColor Green
} else {
  Write-Warning 'No cpolar public URL detected. Start cpolar first or pass -PublicBaseUrl to enable public uploads/ASR.'
}
Write-Host ''
Write-Host "The API window forces DEBUG=true so the backend won't crash on a global DEBUG=release environment variable." -ForegroundColor Yellow
