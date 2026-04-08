param(
    [string]$PublicBaseUrl = "",
    [int]$Port = 7860
)

$ErrorActionPreference = "Stop"

function Get-CpolarPublicBaseUrl {
    function Get-PreferredTunnelUrl([string]$Line) {
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

    $logDir = Join-Path $env:USERPROFILE ".cpolar\\logs"
    if (-not (Test-Path -LiteralPath $logDir)) {
        return $null
    }

    $logFiles = Get-ChildItem -LiteralPath $logDir -Filter "cpolar_service.log*" -File |
        Sort-Object LastWriteTime -Descending

    foreach ($logFile in $logFiles) {
        $publicUrlMatch = Select-String -Path $logFile.FullName -Pattern 'PublicUrl.*https?://[a-zA-Z0-9.-]+' |
            Select-Object -Last 1
        if ($publicUrlMatch) {
            $resolvedUrl = Get-PreferredTunnelUrl $publicUrlMatch.Line
            if ($resolvedUrl) {
                return $resolvedUrl
            }
        }

        $newTunnelMatch = Select-String -Path $logFile.FullName -Pattern 'NewTunnel.*https?://[a-zA-Z0-9.-]+' |
            Select-Object -Last 1
        if ($newTunnelMatch) {
            $resolvedUrl = Get-PreferredTunnelUrl $newTunnelMatch.Line
            if ($resolvedUrl) {
                return $resolvedUrl
            }
        }
    }

    return $null
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$apiDir = Join-Path $repoRoot "api"

if (-not $PublicBaseUrl) {
    $PublicBaseUrl = Get-CpolarPublicBaseUrl
}

$env:DATABASE_URL = "postgresql://pgvector:pgvector@localhost:5432/debate_system"
$env:REDIS_HOST = "localhost"
$env:REDIS_PORT = "6379"
$env:REDIS_DB = "0"
$env:REDIS_PASSWORD = ""
$env:PUBLIC_BASE_URL = $PublicBaseUrl
$env:DEBUG = "false"
$env:SECRET_KEY = "local-delivery-secret-key"

if ($PublicBaseUrl) {
    Write-Output "Resolved PUBLIC_BASE_URL: $PublicBaseUrl"
} else {
    Write-Output "Resolved PUBLIC_BASE_URL: <empty>"
}

Set-Location $apiDir
& (Join-Path $apiDir "venv\\Scripts\\python.exe") -m uvicorn main:app --host 0.0.0.0 --port $Port
