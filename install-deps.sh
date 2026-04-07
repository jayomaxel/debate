#!/usr/bin/env bash

set -euo pipefail

skip_backend=0
skip_frontend=0
skip_weasyprint_system=0

usage() {
  cat <<'EOF'
Usage: ./install-deps.sh [options]

Options:
  --skip-backend            Skip backend dependency installation
  --skip-frontend           Skip frontend dependency installation
  --skip-weasyprint-system  Skip system packages for WeasyPrint
  -h, --help                Show this help message
EOF
}

write_step() {
  printf '\n==> %s\n' "$1"
}

write_note() {
  printf '%s\n' "$1"
}

write_warn() {
  printf 'Warning: %s\n' "$1" >&2
}

is_root_user() {
  [ "${EUID:-$(id -u)}" -eq 0 ]
}

run_in_dir() {
  local workdir="$1"
  shift
  (
    cd "$workdir"
    "$@"
  )
}

ensure_privileged_prefix() {
  if is_root_user; then
    SUDO_CMD=()
    return
  fi

  if command -v sudo >/dev/null 2>&1; then
    SUDO_CMD=(sudo)
    return
  fi

  SUDO_CMD=()
}

install_weasyprint_system_deps() {
  if [ "$skip_weasyprint_system" -eq 1 ]; then
    write_note 'Skipping system packages for WeasyPrint.'
    return
  fi

  local os_name
  os_name="$(uname -s)"

  case "$os_name" in
    Linux)
      write_step 'Ensuring Linux system packages for WeasyPrint'
      ensure_privileged_prefix

      if command -v apt-get >/dev/null 2>&1; then
        if ! is_root_user && [ "${#SUDO_CMD[@]}" -eq 0 ]; then
          write_warn "Need root or sudo to install WeasyPrint packages with apt-get. Skipping this step."
          return
        fi

        "${SUDO_CMD[@]}" apt-get update
        "${SUDO_CMD[@]}" apt-get install -y \
          python3-pip \
          libpango-1.0-0 \
          libpangoft2-1.0-0 \
          libffi-dev \
          libjpeg-dev \
          libopenjp2-7-dev \
          shared-mime-info
        return
      fi

      if command -v dnf >/dev/null 2>&1; then
        if ! is_root_user && [ "${#SUDO_CMD[@]}" -eq 0 ]; then
          write_warn "Need root or sudo to install WeasyPrint packages with dnf. Skipping this step."
          return
        fi

        "${SUDO_CMD[@]}" dnf install -y \
          python3-pip \
          pango \
          gcc \
          python3-devel \
          gcc-c++ \
          zlib-devel \
          libjpeg-devel \
          openjpeg2-devel \
          libffi-devel
        return
      fi

      if command -v yum >/dev/null 2>&1; then
        if ! is_root_user && [ "${#SUDO_CMD[@]}" -eq 0 ]; then
          write_warn "Need root or sudo to install WeasyPrint packages with yum. Skipping this step."
          return
        fi

        "${SUDO_CMD[@]}" yum install -y \
          python3-pip \
          pango \
          gcc \
          python3-devel \
          gcc-c++ \
          zlib-devel \
          libjpeg-devel \
          openjpeg2-devel \
          libffi-devel
        return
      fi

      if command -v pacman >/dev/null 2>&1; then
        if ! is_root_user && [ "${#SUDO_CMD[@]}" -eq 0 ]; then
          write_warn "Need root or sudo to install WeasyPrint packages with pacman. Skipping this step."
          return
        fi

        "${SUDO_CMD[@]}" pacman -Sy --noconfirm \
          python-pip \
          pango \
          gcc \
          libjpeg-turbo \
          openjpeg2
        return
      fi

      write_warn "Unsupported Linux package manager. Install WeasyPrint system dependencies manually if PDF export fails."
      write_note 'Reference: https://doc.courtbouillon.org/weasyprint/latest/first_steps.html'
      ;;
    Darwin)
      write_step 'Ensuring macOS system packages for WeasyPrint'

      if ! command -v brew >/dev/null 2>&1; then
        write_warn "Homebrew was not found. Install it first or skip this step with --skip-weasyprint-system."
        write_note 'Homebrew: https://brew.sh/'
        return
      fi

      brew install pango gdk-pixbuf libffi
      ;;
    *)
      write_warn "Unsupported operating system: $os_name"
      ;;
  esac
}

find_python() {
  local candidate

  for candidate in python3 python; do
    if ! command -v "$candidate" >/dev/null 2>&1; then
      continue
    fi

    if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
    then
      printf '%s\n' "$candidate"
      return
    fi
  done

  write_warn "Python 3.11+ is required, but no compatible python executable was found in PATH."
  exit 1
}

python_version_text() {
  local python_cmd="$1"
  "$python_cmd" - <<'PY'
import sys
print(".".join(map(str, sys.version_info[:3])))
PY
}

find_node() {
  if ! command -v node >/dev/null 2>&1; then
    write_warn "Node.js 18+ is required, but 'node' was not found in PATH."
    exit 1
  fi

  if ! node - <<'JS' >/dev/null 2>&1
const major = Number(process.versions.node.split('.')[0]);
process.exit(major >= 18 ? 0 : 1);
JS
  then
    write_warn "Node.js 18+ is required. Found $(node --version)."
    exit 1
  fi
}

get_pnpm_spec() {
  local package_json_path="$1"

  node - "$package_json_path" <<'JS'
const fs = require('fs');
const path = process.argv[2];
const data = JSON.parse(fs.readFileSync(path, 'utf8'));
const value = data.packageManager;
process.stdout.write(
  typeof value === 'string' && value.startsWith('pnpm@') ? value : 'pnpm@10.11.0'
);
JS
}

ensure_pnpm() {
  local package_json_path="$1"

  if command -v pnpm >/dev/null 2>&1; then
    printf '%s\n' "pnpm"
    return
  fi

  if ! command -v corepack >/dev/null 2>&1; then
    write_warn "pnpm was not found, and corepack is unavailable. Install Node.js 18+ or pnpm manually."
    exit 1
  fi

  local pnpm_spec
  pnpm_spec="$(get_pnpm_spec "$package_json_path")"

  write_step "Activating ${pnpm_spec} via corepack"
  corepack enable
  corepack prepare "$pnpm_spec" --activate

  if ! command -v pnpm >/dev/null 2>&1; then
    write_warn "pnpm is still unavailable after corepack activation."
    exit 1
  fi

  printf '%s\n' "pnpm"
}

run_backend_acceptance() {
  local python_cmd="$1"
  local api_dir="$2"
  local skip_pdf_check="$3"

  (
    cd "$api_dir"

    if [ "$skip_pdf_check" -eq 1 ]; then
      "$python_cmd" - <<'PY'
import importlib.metadata as m
import fastapi
import redis
import weasyprint

print('fastapi=' + m.version('fastapi'))
print('redis=' + m.version('redis'))
print('weasyprint=' + m.version('weasyprint'))
print('pdf_render_check=skipped (--skip-weasyprint-system)')
PY
    else
      "$python_cmd" - <<'PY'
from weasyprint import HTML
import importlib.metadata as m
import fastapi
import redis

print('fastapi=' + m.version('fastapi'))
print('redis=' + m.version('redis'))
print('weasyprint=' + m.version('weasyprint'))
print('pdf_bytes=' + str(len(HTML(string='<h1>AIDebate acceptance</h1>').write_pdf())))
PY
    fi
  )
}

run_frontend_acceptance() {
  local pnpm_cmd="$1"
  local web_dir="$2"

  run_in_dir "$web_dir" "$pnpm_cmd" exec vite --version
}

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
API_DIR="${ROOT_DIR}/api"
WEB_DIR="${ROOT_DIR}/web"
REQUIREMENTS_PATH="${API_DIR}/requirements.txt"
PACKAGE_JSON_PATH="${WEB_DIR}/package.json"
API_VENV_DIR="${API_DIR}/venv"
API_VENV_PYTHON="${API_VENV_DIR}/bin/python"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --skip-backend)
      skip_backend=1
      ;;
    --skip-frontend)
      skip_frontend=1
      ;;
    --skip-weasyprint-system)
      skip_weasyprint_system=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      write_warn "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
  shift
done

if [ ! -d "$API_DIR" ]; then
  write_warn "Missing api directory: $API_DIR"
  exit 1
fi

if [ ! -d "$WEB_DIR" ]; then
  write_warn "Missing web directory: $WEB_DIR"
  exit 1
fi

if [ ! -f "$REQUIREMENTS_PATH" ]; then
  write_warn "Missing backend requirements file: $REQUIREMENTS_PATH"
  exit 1
fi

if [ ! -f "$PACKAGE_JSON_PATH" ]; then
  write_warn "Missing frontend package.json: $PACKAGE_JSON_PATH"
  exit 1
fi

printf '========================================\n'
printf 'AIDebate dependency installer\n'
printf '========================================\n'

install_weasyprint_system_deps

if [ "$skip_backend" -eq 0 ]; then
  write_step 'Installing backend dependencies'
  PYTHON_CMD="$(find_python)"
  write_note "Using Python $(python_version_text "$PYTHON_CMD")"

  if [ ! -x "$API_VENV_PYTHON" ]; then
    write_note 'Creating api/venv ...'
    run_in_dir "$API_DIR" "$PYTHON_CMD" -m venv venv
  else
    write_note 'Reusing existing api/venv'
  fi

  if [ ! -x "$API_VENV_PYTHON" ]; then
    write_warn "Virtual environment python executable was not found after setup: $API_VENV_PYTHON"
    exit 1
  fi

  run_in_dir "$API_DIR" "$API_VENV_PYTHON" -m pip install --upgrade pip setuptools wheel
  run_in_dir "$API_DIR" "$API_VENV_PYTHON" -m pip install -r requirements.txt
  run_in_dir "$API_DIR" "$API_VENV_PYTHON" -m pip install 'redis>=5.0.1'
else
  write_note 'Skipping backend dependency installation.'
fi

if [ "$skip_frontend" -eq 0 ]; then
  write_step 'Installing frontend dependencies'
  find_node
  write_note "Using Node.js $(node --version)"

  PNPM_CMD="$(ensure_pnpm "$PACKAGE_JSON_PATH")"
  run_in_dir "$WEB_DIR" "$PNPM_CMD" install
else
  write_note 'Skipping frontend dependency installation.'
fi

if [ "$skip_backend" -eq 0 ] || [ "$skip_frontend" -eq 0 ]; then
  write_step 'Running acceptance checks'
fi

if [ "$skip_backend" -eq 0 ]; then
  write_note 'Backend acceptance: importing FastAPI, Redis, and validating WeasyPrint.'
  run_backend_acceptance "$API_VENV_PYTHON" "$API_DIR" "$skip_weasyprint_system"
fi

if [ "$skip_frontend" -eq 0 ]; then
  write_note 'Frontend acceptance: running the local Vite CLI.'
  run_frontend_acceptance "$PNPM_CMD" "$WEB_DIR"
fi

printf '\n'
printf 'All requested dependency steps and acceptance checks completed.\n'
printf 'Backend venv: %s\n' "$API_VENV_PYTHON"
printf 'Frontend dir: %s\n' "$WEB_DIR"
printf '\n'
printf 'Next steps:\n'
printf '1. Configure api/.env and web environment variables if needed.\n'
printf '2. Start backend and frontend manually using the commands in readme.md.\n'
