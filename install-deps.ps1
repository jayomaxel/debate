param(
  [switch]$SkipBackend,
  [switch]$SkipFrontend,
  [switch]$SkipWeasyPrintSystem,
  [switch]$WaitOnExit
)

$ErrorActionPreference = 'Stop'

function Write-Step {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Message
  )

  Write-Host ''
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Note {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Message
  )

  Write-Host $Message -ForegroundColor DarkGray
}

function Get-CommandPathOrNull {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name
  )

  $command = Get-Command $Name -ErrorAction SilentlyContinue
  if ($null -eq $command) {
    return $null
  }

  return $command.Source
}

function Test-IsWindowsHost {
  return [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT
}

function Get-VenvPythonPath {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ApiDir
  )

  if (Test-IsWindowsHost) {
    return Join-Path $ApiDir 'venv\Scripts\python.exe'
  }

  return Join-Path $ApiDir 'venv/bin/python'
}

function Invoke-ExternalCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,
    [string[]]$ArgumentList = @(),
    [string]$WorkingDirectory = (Get-Location).Path
  )

  Push-Location -LiteralPath $WorkingDirectory
  try {
    & $FilePath @ArgumentList
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
      throw "Command failed with exit code ${exitCode}: $FilePath $($ArgumentList -join ' ')"
    }
  }
  finally {
    Pop-Location
  }
}

function Invoke-CapturedCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,
    [string[]]$ArgumentList = @(),
    [string]$WorkingDirectory = (Get-Location).Path
  )

  Push-Location -LiteralPath $WorkingDirectory
  try {
    $output = & $FilePath @ArgumentList 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
      $text = ($output | Out-String).Trim()
      throw "Command failed with exit code ${exitCode}: $FilePath $($ArgumentList -join ' ')`n$text"
    }

    return ($output | Out-String).Trim()
  }
  finally {
    Pop-Location
  }
}

function Get-PythonInvocation {
  $pythonPath = Get-CommandPathOrNull -Name 'python'
  if ($pythonPath) {
    return @{
      FilePath = $pythonPath
      Prefix = @()
    }
  }

  $pyLauncher = Get-CommandPathOrNull -Name 'py'
  if ($pyLauncher) {
    return @{
      FilePath = $pyLauncher
      Prefix = @('-3')
    }
  }

  throw "Python 3.11+ is required, but neither 'python' nor 'py' was found in PATH."
}

function Get-PnpmSpec {
  param(
    [Parameter(Mandatory = $true)]
    [string]$PackageJsonPath
  )

  try {
    $packageJson = Get-Content -LiteralPath $PackageJsonPath -Raw | ConvertFrom-Json
    if ($packageJson.packageManager -match '^pnpm@.+$') {
      return $packageJson.packageManager
    }
  }
  catch {
    Write-Warning "Unable to read pnpm version from $PackageJsonPath. Falling back to pnpm@10.11.0."
  }

  return 'pnpm@10.11.0'
}

function Ensure-Pnpm {
  param(
    [Parameter(Mandatory = $true)]
    [string]$PackageJsonPath
  )

  $pnpmPath = Get-CommandPathOrNull -Name 'pnpm'
  if ($pnpmPath) {
    return $pnpmPath
  }

  $corepackPath = Get-CommandPathOrNull -Name 'corepack'
  if (-not $corepackPath) {
    throw "pnpm was not found, and corepack is unavailable. Install Node.js 18+ or pnpm manually."
  }

  $pnpmSpec = Get-PnpmSpec -PackageJsonPath $PackageJsonPath

  Write-Step "Activating $pnpmSpec via corepack"
  Invoke-ExternalCommand -FilePath $corepackPath -ArgumentList @('enable')
  Invoke-ExternalCommand -FilePath $corepackPath -ArgumentList @('prepare', $pnpmSpec, '--activate')

  $pnpmPath = Get-CommandPathOrNull -Name 'pnpm'
  if (-not $pnpmPath) {
    throw "pnpm is still unavailable after corepack activation."
  }

  return $pnpmPath
}

function Ensure-PythonVersion {
  param(
    [Parameter(Mandatory = $true)]
    [hashtable]$PythonInvocation
  )

  # Use single quotes inside the Python snippet so Windows PowerShell does not
  # strip embedded double quotes when forwarding native command arguments.
  $versionText = Invoke-CapturedCommand `
    -FilePath $PythonInvocation.FilePath `
    -ArgumentList ($PythonInvocation.Prefix + @('-c', "import sys; print('.'.join(map(str, sys.version_info[:3])))"))

  $version = [version]$versionText
  if ($version -lt [version]'3.11.0') {
    throw "Python 3.11+ is required. Found $versionText."
  }

  return $versionText
}

function Ensure-NodeVersion {
  param(
    [Parameter(Mandatory = $true)]
    [string]$NodePath
  )

  $rawVersion = Invoke-CapturedCommand -FilePath $NodePath -ArgumentList @('--version')
  $versionText = $rawVersion.TrimStart('v')
  $version = [version]$versionText
  if ($version -lt [version]'18.0.0') {
    throw "Node.js 18+ is required. Found $rawVersion."
  }

  return $rawVersion
}

function Install-WeasyPrintRuntime {
  if ($SkipWeasyPrintSystem) {
    Write-Note 'Skipping GTK runtime installation for WeasyPrint.'
    return
  }

  if (-not (Test-IsWindowsHost)) {
    Write-Note 'Skipping GTK runtime installation because this script only automates that step on Windows.'
    return
  }

  Write-Step 'Ensuring the Windows GTK runtime for WeasyPrint'

  $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
  )
  $chocoPath = Get-CommandPathOrNull -Name 'choco'

  if (-not $chocoPath) {
    Write-Warning 'Chocolatey was not found. If WeasyPrint PDF export fails later, install gtk-runtime manually or rerun after installing Chocolatey.'
    Write-Note 'Chocolatey: https://chocolatey.org/install'
    Write-Note 'GTK runtime: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases'
    return
  }

  if (-not $isAdmin) {
    Write-Warning 'This session is not elevated, so gtk-runtime was not installed automatically. Run PowerShell as Administrator and rerun this script if PDF export fails.'
    return
  }

  Invoke-ExternalCommand -FilePath $chocoPath -ArgumentList @('install', 'gtk-runtime', '-y')
}

function Invoke-BackendAcceptance {
  param(
    [Parameter(Mandatory = $true)]
    [string]$PythonPath,
    [Parameter(Mandatory = $true)]
    [string]$ApiDir,
    [switch]$SkipWeasyPrintPdfCheck
  )

  Write-Note 'Backend acceptance: importing FastAPI, Redis, and validating WeasyPrint.'

  $snippet = if ($SkipWeasyPrintPdfCheck) {
    "import importlib.metadata as m; import fastapi; import redis; import weasyprint; print('fastapi=' + m.version('fastapi')); print('redis=' + m.version('redis')); print('weasyprint=' + m.version('weasyprint')); print('pdf_render_check=skipped (--SkipWeasyPrintSystem)')"
  }
  else {
    "from weasyprint import HTML; import importlib.metadata as m; import fastapi; import redis; print('fastapi=' + m.version('fastapi')); print('redis=' + m.version('redis')); print('weasyprint=' + m.version('weasyprint')); print('pdf_bytes=' + str(len(HTML(string='<h1>AIDebate acceptance</h1>').write_pdf())))"
  }

  Invoke-ExternalCommand -FilePath $PythonPath -ArgumentList @('-c', $snippet) -WorkingDirectory $ApiDir
}

function Invoke-FrontendAcceptance {
  param(
    [Parameter(Mandatory = $true)]
    [string]$PnpmPath,
    [Parameter(Mandatory = $true)]
    [string]$WebDir
  )

  Write-Note 'Frontend acceptance: running the local Vite CLI.'
  Invoke-ExternalCommand -FilePath $PnpmPath -ArgumentList @('exec', 'vite', '--version') -WorkingDirectory $WebDir
}

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiDir = Join-Path $rootDir 'api'
$webDir = Join-Path $rootDir 'web'
$requirementsPath = Join-Path $apiDir 'requirements.txt'
$packageJsonPath = Join-Path $webDir 'package.json'
$apiVenvPython = Get-VenvPythonPath -ApiDir $apiDir
$pnpmPath = $null
$scriptSucceeded = $false

try {
  if (-not (Test-Path -LiteralPath $apiDir)) {
    throw "Missing api directory: $apiDir"
  }

  if (-not (Test-Path -LiteralPath $webDir)) {
    throw "Missing web directory: $webDir"
  }

  if (-not (Test-Path -LiteralPath $requirementsPath)) {
    throw "Missing backend requirements file: $requirementsPath"
  }

  if (-not (Test-Path -LiteralPath $packageJsonPath)) {
    throw "Missing frontend package.json: $packageJsonPath"
  }

  Write-Host '========================================' -ForegroundColor Cyan
  Write-Host 'AIDebate dependency installer' -ForegroundColor Cyan
  Write-Host '========================================' -ForegroundColor Cyan

  Install-WeasyPrintRuntime

  if (-not $SkipBackend) {
    Write-Step 'Installing backend dependencies'

    $pythonInvocation = Get-PythonInvocation
    $pythonVersion = Ensure-PythonVersion -PythonInvocation $pythonInvocation
    Write-Note "Using Python $pythonVersion"

    if (-not (Test-Path -LiteralPath $apiVenvPython)) {
      Write-Note 'Creating api\venv ...'
      Invoke-ExternalCommand `
        -FilePath $pythonInvocation.FilePath `
        -ArgumentList ($pythonInvocation.Prefix + @('-m', 'venv', 'venv')) `
        -WorkingDirectory $apiDir

      $apiVenvPython = Get-VenvPythonPath -ApiDir $apiDir
    }
    else {
      Write-Note 'Reusing existing api\venv'
    }

    if (-not (Test-Path -LiteralPath $apiVenvPython)) {
      throw "Virtual environment python executable was not found after setup: $apiVenvPython"
    }

    Invoke-ExternalCommand -FilePath $apiVenvPython -ArgumentList @('-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel') -WorkingDirectory $apiDir
    Invoke-ExternalCommand -FilePath $apiVenvPython -ArgumentList @('-m', 'pip', 'install', '-r', 'requirements.txt') -WorkingDirectory $apiDir
    Invoke-ExternalCommand -FilePath $apiVenvPython -ArgumentList @('-m', 'pip', 'install', 'redis>=5.0.1') -WorkingDirectory $apiDir
  }
  else {
    Write-Note 'Skipping backend dependency installation.'
  }

  if (-not $SkipFrontend) {
    Write-Step 'Installing frontend dependencies'

    $nodePath = Get-CommandPathOrNull -Name 'node'
    if (-not $nodePath) {
      throw "Node.js 18+ is required, but 'node' was not found in PATH."
    }

    $nodeVersion = Ensure-NodeVersion -NodePath $nodePath
    Write-Note "Using Node.js $nodeVersion"

    $pnpmPath = Ensure-Pnpm -PackageJsonPath $packageJsonPath
    Invoke-ExternalCommand -FilePath $pnpmPath -ArgumentList @('install') -WorkingDirectory $webDir
  }
  else {
    Write-Note 'Skipping frontend dependency installation.'
  }

  if ((-not $SkipBackend) -or (-not $SkipFrontend)) {
    Write-Step 'Running acceptance checks'
  }

  if (-not $SkipBackend) {
    Invoke-BackendAcceptance -PythonPath $apiVenvPython -ApiDir $apiDir -SkipWeasyPrintPdfCheck:$SkipWeasyPrintSystem
  }

  if (-not $SkipFrontend) {
    Invoke-FrontendAcceptance -PnpmPath $pnpmPath -WebDir $webDir
  }

  Write-Host ''
  Write-Host 'Dependencies installed. You can continue with project startup.' -ForegroundColor Green
  Write-Host 'All requested dependency steps and acceptance checks completed.' -ForegroundColor Green
  Write-Host "Backend venv: $apiVenvPython" -ForegroundColor Green
  Write-Host "Frontend dir: $webDir" -ForegroundColor Green
  Write-Host ''
  Write-Host 'Next steps:' -ForegroundColor Yellow
  Write-Host '1. Configure api\.env and web environment variables if needed.' -ForegroundColor White
  Write-Host '2. Start the project with .\start-dev.ps1 or .\start-dev.bat' -ForegroundColor White

  $scriptSucceeded = $true
}
catch {
  Write-Host ''
  Write-Host "Dependency installation failed: $($_.Exception.Message)" -ForegroundColor Red
}
finally {
  if ($WaitOnExit) {
    Write-Host ''
    if ($scriptSucceeded) {
      Read-Host 'Dependencies installed. Press Enter to close this window' | Out-Null
    }
    else {
      Read-Host 'Dependency installation failed. Press Enter to close this window' | Out-Null
    }
  }

  if (-not $scriptSucceeded) {
    exit 1
  }
}
