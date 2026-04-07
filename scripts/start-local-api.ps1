param(
    [string]$PublicBaseUrl = "https://62c52b1f.r22.cpolar.top",
    [int]$Port = 7860
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$apiDir = Join-Path $repoRoot "api"

$env:DATABASE_URL = "postgresql://pgvector:pgvector@localhost:5432/debate_system"
$env:REDIS_HOST = "localhost"
$env:REDIS_PORT = "6379"
$env:REDIS_DB = "0"
$env:REDIS_PASSWORD = ""
$env:PUBLIC_BASE_URL = $PublicBaseUrl
$env:DEBUG = "false"
$env:SECRET_KEY = "local-delivery-secret-key"

Set-Location $apiDir
& (Join-Path $apiDir "venv\\Scripts\\python.exe") -m uvicorn main:app --host 0.0.0.0 --port $Port
