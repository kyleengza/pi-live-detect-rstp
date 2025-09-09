#!/usr/bin/env sh
set -e

APP_DIR=/home/pi/pi-live-detect-rstp

# Discover streams from current config
STREAM1=$(python3 - <<'PY'
from app.core.config import CONFIG
print(CONFIG.rtsp_streams[0].name)
PY
)
STREAM2=$(python3 - <<'PY'
from app.core.config import CONFIG
print(CONFIG.rtsp_streams[1].name)
PY
)

sudo systemctl stop pi-live-pipeline@${STREAM2}.service || true
sudo systemctl stop pi-live-pipeline@${STREAM1}.service || true
sudo systemctl stop pi-live-ingest@${STREAM2}.service || true
sudo systemctl stop pi-live-ingest@${STREAM1}.service || true
sudo systemctl stop pi-live-api.service || true

sudo systemctl disable pi-live-pipeline@${STREAM2}.service || true
sudo systemctl disable pi-live-pipeline@${STREAM1}.service || true
sudo systemctl disable pi-live-ingest@${STREAM2}.service || true
sudo systemctl disable pi-live-ingest@${STREAM1}.service || true
sudo systemctl disable pi-live-api.service || true

sudo rm -f /etc/systemd/system/pi-live-api.service
sudo rm -f /etc/systemd/system/pi-live-ingest@.service
sudo rm -f /etc/systemd/system/pi-live-pipeline@.service
sudo systemctl daemon-reload

# Optional: remove app dir
# sudo rm -rf "$APP_DIR"

echo "Uninstalled services."
