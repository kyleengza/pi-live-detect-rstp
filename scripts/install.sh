#!/usr/bin/env sh
set -e

# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev redis-server ffmpeg pkg-config libatlas-base-dev libjpeg-dev libopenblas-dev rsync

# Create app dir under /home/pi if not there
APP_DIR=/home/pi/pi-live-detect-rstp
if [ ! -d "$APP_DIR" ]; then
  sudo mkdir -p "$APP_DIR"
  sudo chown -R pi:pi "$APP_DIR"
fi

# Copy project files
rsync -a --delete ./ "$APP_DIR"/

# Python venv
cd "$APP_DIR"
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

# Enable redis persistence off (RAM-only) by disabling RDB/AOF
sudo sed -i 's/^save .*/save ""/g' /etc/redis/redis.conf || true
sudo sed -i 's/^appendonly yes/appendonly no/g' /etc/redis/redis.conf || true
sudo systemctl restart redis-server

# Install systemd units
sudo cp systemd/pi-live-api.service /etc/systemd/system/
sudo cp systemd/pi-live-ingest@.service /etc/systemd/system/
sudo cp systemd/pi-live-pipeline@.service /etc/systemd/system/

sudo systemctl daemon-reload

# Enable default two streams based on config names
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

sudo systemctl enable pi-live-api.service
sudo systemctl enable pi-live-ingest@${STREAM1}.service
sudo systemctl enable pi-live-ingest@${STREAM2}.service
sudo systemctl enable pi-live-pipeline@${STREAM1}.service
sudo systemctl enable pi-live-pipeline@${STREAM2}.service

sudo systemctl start pi-live-api.service
sudo systemctl start pi-live-ingest@${STREAM1}.service
sudo systemctl start pi-live-ingest@${STREAM2}.service
sudo systemctl start pi-live-pipeline@${STREAM1}.service
sudo systemctl start pi-live-pipeline@${STREAM2}.service

printf "\nInstalled. API at http://<pi-ip>:8000 (Basic auth)\n"
