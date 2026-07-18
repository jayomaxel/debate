#!/usr/bin/env bash
set -euo pipefail

base_url="${1:-${SMOKE_BASE_URL:-http://127.0.0.1:8860}}"
base_url="${base_url%/}"

check_url() {
  local label="$1"
  local url="$2"
  curl --fail --silent --show-error --max-time 30 "$url" >/dev/null
  echo "PASS: ${label}"
}

check_url "web gateway" "${base_url}/healthz"
check_url "API through gateway" "${base_url}/api/health"

credential_count=0
for variable in SMOKE_ACCOUNT SMOKE_PASSWORD SMOKE_USER_TYPE; do
  if [[ -n "${!variable:-}" ]]; then
    credential_count=$((credential_count + 1))
  fi
done
if [[ "$credential_count" -ne 0 && "$credential_count" -ne 3 ]]; then
  echo "SMOKE_ACCOUNT, SMOKE_PASSWORD and SMOKE_USER_TYPE must be set together" >&2
  exit 2
fi
if [[ "$credential_count" -eq 3 ]]; then
  login_payload=$(printf '{"account":"%s","password":"%s","user_type":"%s"}' \
    "$SMOKE_ACCOUNT" "$SMOKE_PASSWORD" "$SMOKE_USER_TYPE")
  login_response=$(curl --fail --silent --show-error --max-time 30 \
    -H "Content-Type: application/json" \
    --data "$login_payload" \
    "${base_url}/api/auth/login")
  if [[ "$login_response" != *'"access_token"'* ]]; then
    echo "Login response did not contain an access token" >&2
    exit 1
  fi
  echo "PASS: authenticated login"
fi

provider_count=0
for variable in PROVIDER_BASE_URL PROVIDER_API_KEY PROVIDER_MODEL; do
  if [[ -n "${!variable:-}" ]]; then
    provider_count=$((provider_count + 1))
  fi
done
if [[ "$provider_count" -ne 0 && "$provider_count" -ne 3 ]]; then
  echo "PROVIDER_BASE_URL, PROVIDER_API_KEY and PROVIDER_MODEL must be set together" >&2
  exit 2
fi
if [[ "$provider_count" -eq 3 ]]; then
  provider_url="${PROVIDER_BASE_URL%/}/chat/completions"
  provider_payload=$(printf '{"model":"%s","messages":[{"role":"user","content":"Reply with OK"}],"max_tokens":8}' "$PROVIDER_MODEL")
  provider_response=$(curl --fail --silent --show-error --max-time 90 \
    -H "Authorization: Bearer ${PROVIDER_API_KEY}" \
    -H "Content-Type: application/json" \
    --data "$provider_payload" \
    "$provider_url")
  if [[ "$provider_response" != *'"choices"'* ]]; then
    echo "Provider response did not contain choices" >&2
    exit 1
  fi
  echo "PASS: real provider completion"
fi

echo "Production smoke passed for ${base_url}"
