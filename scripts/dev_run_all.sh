#!/usr/bin/env sh
set -e

# SUDO helper
if command -v sudo >/dev/null 2>&1 && [ "$(id -u)" -ne 0 ]; then SUDO=sudo; else SUDO=""; fi

APP_DIR="${HOME}/pi-live-detect-rstp"

# Ensure prerequisites (best-effort)
$SUDO apt-get update || true
$SUDO apt-get install -y python3-venv python3-dev ffmpeg redis-server || true

# Python env
python3 -m venv .venv 2>/dev/null || true
. .venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

# Run app (defaults use RTSP_URL_1 if set)
python -m app.main
