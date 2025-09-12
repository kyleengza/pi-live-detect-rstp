#!/usr/bin/env sh
set -e

# SUDO helper (works if running as root or not)
if command -v sudo >/dev/null 2>&1 && [ "$(id -u)" -ne 0 ]; then SUDO=sudo; else SUDO=""; fi

# Detect target user/home (prefer the non-root invoking user)
RUN_USER=${SUDO_USER:-$USER}
HOME_DIR=$(getent passwd "$RUN_USER" 2>/dev/null | cut -d: -f6)
[ -z "$HOME_DIR" ] && HOME_DIR="$HOME"
APP_DIR="$HOME_DIR/pi-live-detect-rstp"

# Prompt for RTSP URLs if not set and create .env
if [ ! -f .env ]; then
  echo "Configuring RTSP stream URLs for detection..."
  read -p "Enter RTSP URL for stream 1 [rtsp://192.168.100.4:8554/stream]: " RTSP_URL_1
  RTSP_URL_1=${RTSP_URL_1:-rtsp://192.168.100.4:8554/stream}
  read -p "Enter RTSP URL for stream 2 (optional): " RTSP_URL_2
  echo "RTSP_URL_1=\"$RTSP_URL_1\"" > .env
  [ -n "$RTSP_URL_2" ] && echo "RTSP_URL_2=\"$RTSP_URL_2\"" >> .env
fi
if [ ! -f .env ]; then
  echo "ERROR: .env file not created. Aborting install."
  exit 1
fi
. .env

# Install system dependencies
$SUDO apt-get update
$SUDO apt-get install -y python3-venv python3-dev redis-server ffmpeg pkg-config libatlas-base-dev libjpeg-dev libopenblas-dev rsync

# Install HailoRT SDK and Python wheel if present in prereq
if [ -f prereq/hailort_4.22.0_arm64.deb ]; then
  $SUDO dpkg -i prereq/hailort_4.22.0_arm64.deb || true
fi
if [ -f prereq/hailort-pcie-driver_4.22.0_all.deb ]; then
  $SUDO dpkg -i prereq/hailort-pcie-driver_4.22.0_all.deb || true
fi
if [ -f prereq/hailort-4.22.0-cp311-cp311-linux_aarch64.whl ]; then
  python3 -m venv .venv
  . .venv/bin/activate
  pip install prereq/hailort-4.22.0-cp311-cp311-linux_aarch64.whl || true
fi

# Create app dir under target home if not there
if [ ! -d "$APP_DIR" ]; then
  $SUDO mkdir -p "$APP_DIR"
  $SUDO chown -R "$RUN_USER":"$RUN_USER" "$APP_DIR"
fi

# Copy project files from current directory to APP_DIR
rsync -a --delete ./ "$APP_DIR"/

# Python venv
cd "$APP_DIR"
. .env
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

# Configure Redis to be RAM-only (disable RDB/AOF), if config exists
if [ -f /etc/redis/redis.conf ]; then
  $SUDO sed -i 's/^save .*/save ""/g' /etc/redis/redis.conf || true
  $SUDO sed -i 's/^appendonly yes/appendonly no/g' /etc/redis/redis.conf || true
  $SUDO systemctl restart redis-server || true
fi

# Install systemd units
$SUDO cp systemd/pi-live-api.service /etc/systemd/system/
$SUDO cp systemd/pi-live-ingest@.service /etc/systemd/system/
$SUDO cp systemd/pi-live-pipeline@.service /etc/systemd/system/
$SUDO systemctl daemon-reload

# Patch systemd units for correct user/home
$SUDO sed -i "s|User=.*|User=$RUN_USER|g" /etc/systemd/system/pi-live-api.service
$SUDO sed -i "s|User=.*|User=$RUN_USER|g" /etc/systemd/system/pi-live-ingest@.service
$SUDO sed -i "s|User=.*|User=$RUN_USER|g" /etc/systemd/system/pi-live-pipeline@.service
$SUDO sed -i "s|/home/.*/pi-live-detect-rstp/.venv/bin/activate|$APP_DIR/.venv/bin/activate|g" /etc/systemd/system/pi-live-api.service
$SUDO sed -i "s|/home/.*/pi-live-detect-rstp/.venv/bin/activate|$APP_DIR/.venv/bin/activate|g" /etc/systemd/system/pi-live-ingest@.service
$SUDO sed -i "s|/home/.*/pi-live-detect-rstp/.venv/bin/activate|$APP_DIR/.venv/bin/activate|g" /etc/systemd/system/pi-live-pipeline@.service

# Enable and start services
$SUDO systemctl enable pi-live-api.service
$SUDO systemctl restart pi-live-api.service

# Enable default stream(s) based on config names
STREAM1=$(python3 - <<'PY'
from app.core.config import CONFIG
print(CONFIG.rtsp_streams[0].name)
PY
)
# STREAM2 optional if defined
STREAM2=$(python3 - <<'PY'
from app.core.config import CONFIG
print(CONFIG.rtsp_streams[1].name if len(CONFIG.rtsp_streams) > 1 else "")
PY
)

$SUDO systemctl enable "pi-live-ingest@${STREAM1}.service" || true
[ -n "$STREAM2" ] && $SUDO systemctl enable "pi-live-ingest@${STREAM2}.service" || true
$SUDO systemctl enable "pi-live-pipeline@${STREAM1}.service" || true
[ -n "$STREAM2" ] && $SUDO systemctl enable "pi-live-pipeline@${STREAM2}.service" || true

$SUDO systemctl start "pi-live-ingest@${STREAM1}.service" || true
[ -n "$STREAM2" ] && $SUDO systemctl start "pi-live-ingest@${STREAM2}.service" || true
$SUDO systemctl start "pi-live-pipeline@${STREAM1}.service" || true
[ -n "$STREAM2" ] && $SUDO systemctl start "pi-live-pipeline@${STREAM2}.service" || true

printf "\nInstalled. API at http://<pi-ip>:8000 (Basic auth)\n"
