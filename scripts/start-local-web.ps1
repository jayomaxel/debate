param(
    [int]$Port = 8860
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$webDir = Join-Path $repoRoot "web"

Set-Location $webDir
& pnpm dev --host 0.0.0.0 --port $Port
