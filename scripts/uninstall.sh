#!/usr/bin/env sh
set -e

# SUDO helper
if command -v sudo >/dev/null 2>&1 && [ "$(id -u)" -ne 0 ]; then SUDO=sudo; else SUDO=""; fi

APP_DIR="${HOME}/pi-live-detect-rstp"

# Discover streams from current config (best-effort)
STREAM1=$(python3 - <<'PY'
from app.core.config import CONFIG
print(CONFIG.rtsp_streams[0].name if CONFIG.rtsp_streams else "")
PY
)
STREAM2=$(python3 - <<'PY'
from app.core.config import CONFIG
print(CONFIG.rtsp_streams[1].name if len(CONFIG.rtsp_streams) > 1 else "")
PY
)

# Stop services
[ -n "$STREAM2" ] && $SUDO systemctl stop "pi-live-pipeline@${STREAM2}.service" || true
[ -n "$STREAM1" ] && $SUDO systemctl stop "pi-live-pipeline@${STREAM1}.service" || true
[ -n "$STREAM2" ] && $SUDO systemctl stop "pi-live-ingest@${STREAM2}.service" || true
[ -n "$STREAM1" ] && $SUDO systemctl stop "pi-live-ingest@${STREAM1}.service" || true
$SUDO systemctl stop pi-live-api.service || true

# Disable services
[ -n "$STREAM2" ] && $SUDO systemctl disable "pi-live-pipeline@${STREAM2}.service" || true
[ -n "$STREAM1" ] && $SUDO systemctl disable "pi-live-pipeline@${STREAM1}.service" || true
[ -n "$STREAM2" ] && $SUDO systemctl disable "pi-live-ingest@${STREAM2}.service" || true
[ -n "$STREAM1" ] && $SUDO systemctl disable "pi-live-ingest@${STREAM1}.service" || true
$SUDO systemctl disable pi-live-api.service || true

# Remove unit files
$SUDO rm -f /etc/systemd/system/pi-live-api.service || true
$SUDO rm -f /etc/systemd/system/pi-live-ingest@.service || true
$SUDO rm -f /etc/systemd/system/pi-live-pipeline@.service || true
$SUDO systemctl daemon-reload || true

# Optional: remove app dir
# $SUDO rm -rf "$APP_DIR"

echo "Uninstalled services."
