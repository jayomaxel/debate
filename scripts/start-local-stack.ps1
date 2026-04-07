param(
    [string]$PublicBaseUrl = "https://62c52b1f.r22.cpolar.top",
    [int]$ApiPort = 7860,
    [int]$WebPort = 8860
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$logDir = Join-Path $repoRoot "runtime-logs"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$apiScript = Join-Path $scriptDir "start-local-api.ps1"
$webScript = Join-Path $scriptDir "start-local-web.ps1"

$apiProcess = Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile", "-File", $apiScript, "-PublicBaseUrl", $PublicBaseUrl, "-Port", $ApiPort `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput (Join-Path $logDir "api.stdout.log") `
    -RedirectStandardError (Join-Path $logDir "api.stderr.log") `
    -WindowStyle Hidden `
    -PassThru

$webProcess = Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile", "-File", $webScript, "-Port", $WebPort `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput (Join-Path $logDir "web.stdout.log") `
    -RedirectStandardError (Join-Path $logDir "web.stderr.log") `
    -WindowStyle Hidden `
    -PassThru

Write-Output "API PID: $($apiProcess.Id)"
Write-Output "Web PID: $($webProcess.Id)"
Write-Output "API Log: $(Join-Path $logDir 'api.stderr.log')"
Write-Output "Web Log: $(Join-Path $logDir 'web.stdout.log')"
