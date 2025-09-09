#!/usr/bin/env bash
set -euo pipefail
REPO_URL=${REPO_URL:-https://github.com/kyleengza/pi-live-detect-rstp.git}
BASE_DIR=${BASE_DIR:-$HOME/pi-live-detect}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git clone --depth 1 "$REPO_URL" "$TMP/repo"
cd "$TMP/repo"
bash scripts/install.sh
echo "Reinstall complete."
