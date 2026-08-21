param(
    [string]$BaseUrl = $(if ($env:SMOKE_BASE_URL) { $env:SMOKE_BASE_URL } else { "http://127.0.0.1:8860" })
)

$ErrorActionPreference = "Stop"
$BaseUrl = $BaseUrl.TrimEnd("/")

function Test-SmokeUrl {
    param([string]$Label, [string]$Url)
    Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 30 -UseBasicParsing | Out-Null
    Write-Host "PASS: $Label"
}

Test-SmokeUrl -Label "web gateway" -Url "$BaseUrl/healthz"
Test-SmokeUrl -Label "API through gateway" -Url "$BaseUrl/api/health"

$credentials = @($env:SMOKE_ACCOUNT, $env:SMOKE_PASSWORD, $env:SMOKE_USER_TYPE)
$credentialCount = @($credentials | Where-Object { $_ }).Count
if ($credentialCount -ne 0 -and $credentialCount -ne 3) {
    throw "SMOKE_ACCOUNT, SMOKE_PASSWORD and SMOKE_USER_TYPE must be set together"
}
if ($credentialCount -eq 3) {
    $loginBody = @{
        account = $env:SMOKE_ACCOUNT
        password = $env:SMOKE_PASSWORD
        user_type = $env:SMOKE_USER_TYPE
    } | ConvertTo-Json
    $login = Invoke-RestMethod -Uri "$BaseUrl/api/auth/login" -Method Post `
        -ContentType "application/json" -Body $loginBody -TimeoutSec 30
    if (-not $login.data.access_token) {
        throw "Login response did not contain an access token"
    }
    Write-Host "PASS: authenticated login"
}

$providerSettings = @($env:PROVIDER_BASE_URL, $env:PROVIDER_API_KEY, $env:PROVIDER_MODEL)
$providerCount = @($providerSettings | Where-Object { $_ }).Count
if ($providerCount -ne 0 -and $providerCount -ne 3) {
    throw "PROVIDER_BASE_URL, PROVIDER_API_KEY and PROVIDER_MODEL must be set together"
}
if ($providerCount -eq 3) {
    $providerBody = @{
        model = $env:PROVIDER_MODEL
        messages = @(@{ role = "user"; content = "Reply with OK" })
        max_tokens = 8
    } | ConvertTo-Json -Depth 5
    $headers = @{ Authorization = "Bearer $($env:PROVIDER_API_KEY)" }
    $providerUrl = "$($env:PROVIDER_BASE_URL.TrimEnd('/'))/chat/completions"
    $completion = Invoke-RestMethod -Uri $providerUrl -Method Post -Headers $headers `
        -ContentType "application/json" -Body $providerBody -TimeoutSec 90
    if (-not $completion.choices) {
        throw "Provider response did not contain choices"
    }
    Write-Host "PASS: real provider completion"
}

Write-Host "Production smoke passed for $BaseUrl"
