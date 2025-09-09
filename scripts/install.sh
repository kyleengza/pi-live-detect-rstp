#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -eq 0 ]]; then
  echo "[install] Do not run as root directly (will sudo where needed)" >&2
fi

REPO_DIR=$(pwd)
USER_NAME=${SUDO_USER:-$USER}
HOME_DIR=$(eval echo ~"$USER_NAME")
BASE_DIR=${BASE_DIR:-$REPO_DIR}
VENV_DIR="$BASE_DIR/venv"
DATA_DIR="$BASE_DIR/data"
FRAMES_DIR="$DATA_DIR/frames"
LOG_DIR="$BASE_DIR/logs"
DB_PATH="$DATA_DIR/app.db"  # legacy (not used by runtime pipeline)
RUNTIME_DB=${RUNTIME_DB:-/dev/shm/pld_runtime.db}
CONFIG_SRC="$REPO_DIR/config.yaml"
CONFIG_DST="$BASE_DIR/config.yaml"
PY_BIN=python3
MODEL_PATH=${MODEL_PATH:-models/yolov8n.tflite}

normalize_perms() {
  local target="$1"
  [[ -d "$target" ]] || return 0
  if [[ ${EUID} -ne 0 && -n ${SUDO_USER:-} ]]; then sudo chown -R "$USER_NAME":"$USER_NAME" "$target"; fi || true
  chown -R "$USER_NAME":"$USER_NAME" "$target" 2>/dev/null || true
  find "$target" -type d -exec chmod 755 {} + 2>/dev/null || true
  find "$target" -type f -name '*.sh' -exec chmod 755 {} + 2>/dev/null || true
  find "$target" -type f -name '*.py' -exec chmod 644 {} + 2>/dev/null || true
}

echo "[install] Base dir: $BASE_DIR"

mkdir -p "$FRAMES_DIR" "$LOG_DIR" models
normalize_perms "$BASE_DIR"
# Copy config if not exists (legacy)
if [[ -f "$CONFIG_SRC" && ! -f "$CONFIG_DST" ]]; then
  cp "$CONFIG_SRC" "$CONFIG_DST"
fi
[[ -f config.yaml ]] || ln -sf "$CONFIG_DST" config.yaml || true

# Virtual environment
if [[ ! -d "$VENV_DIR" ]]; then
  $PY_BIN -m venv "$VENV_DIR" --system-site-packages
fi
. "$VENV_DIR/bin/activate"
pip install -U pip
if [[ -f requirements.txt ]]; then
  pip install -r requirements.txt
fi
pip install fastapi uvicorn

touch "$RUNTIME_DB" || true

mkdir -p "$BASE_DIR/bin"
cat > "$BASE_DIR/bin/pld_probe.sh" <<'EOF'
#!/usr/bin/env bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
REPO_ROOT=$(readlink -f "$SCRIPT_DIR/..")
export RUNTIME_DB=${RUNTIME_DB:-/dev/shm/pld_runtime.db}
echo "$(date): Health probe check" >> "$REPO_ROOT/logs/probe.log" 2>&1
curl -s http://localhost:8000/health >> "$REPO_ROOT/logs/probe.log" 2>&1 || echo "Service not available" >> "$REPO_ROOT/logs/probe.log" 2>&1
EOF
cat > "$BASE_DIR/bin/pld_detect.sh" <<'EOF'
#!/usr/bin/env bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
REPO_ROOT=$(readlink -f "$SCRIPT_DIR/..")
export RUNTIME_DB=${RUNTIME_DB:-/dev/shm/pld_runtime.db}
. "$REPO_ROOT/venv/bin/activate" && cd "$REPO_ROOT" && exec python -m src.pipeline.serve --host 0.0.0.0 --port 8001 >> "$REPO_ROOT/logs/detect.log" 2>&1
EOF
cat > "$BASE_DIR/bin/pld_restream.sh" <<'EOF'
#!/usr/bin/env bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
REPO_ROOT=$(readlink -f "$SCRIPT_DIR/..")
export RUNTIME_DB=${RUNTIME_DB:-/dev/shm/pld_runtime.db}
echo "$(date): Restream service placeholder - WebRTC/MJPEG served by main API" >> "$REPO_ROOT/logs/restream.log" 2>&1
EOF
cat > "$BASE_DIR/bin/pld_api.sh" <<'EOF'
#!/usr/bin/env bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
REPO_ROOT=$(readlink -f "$SCRIPT_DIR/..")
export RUNTIME_DB=${RUNTIME_DB:-/dev/shm/pld_runtime.db}
export API_TOKEN=${API_TOKEN:-changeme}
. "$REPO_ROOT/venv/bin/activate" && cd "$REPO_ROOT" && exec uvicorn src.pipeline.serve:app --host 0.0.0.0 --port 8000 >> "$REPO_ROOT/logs/api.log" 2>&1
EOF
chmod +x "$BASE_DIR/bin"/*.sh

# Verify wrapper scripts exist
for w in pld_probe.sh pld_detect.sh pld_restream.sh pld_api.sh; do
  if [[ ! -x "$BASE_DIR/bin/$w" ]]; then
    echo "[install] ERROR: Missing wrapper $BASE_DIR/bin/$w" >&2
    exit 1
  fi
done

SERVICE_USER=$USER_NAME
cat > /tmp/pld_probe.service <<EOF
[Unit]
Description=PLD Probe
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$BASE_DIR
Environment=RUNTIME_DB=$RUNTIME_DB
ExecStart=$BASE_DIR/bin/pld_probe.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
cat > /tmp/pld_detect.service <<EOF
[Unit]
Description=PLD Detect (TFLite)
After=pld_probe.service
Wants=pld_probe.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$BASE_DIR
Environment=RUNTIME_DB=$RUNTIME_DB
ExecStart=$BASE_DIR/bin/pld_detect.sh
Restart=always
RestartSec=4

[Install]
WantedBy=multi-user.target
EOF
cat > /tmp/pld_restream.service <<EOF
[Unit]
Description=PLD Restream
After=pld_detect.service
Wants=pld_detect.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$BASE_DIR
Environment=RUNTIME_DB=$RUNTIME_DB
ExecStart=$BASE_DIR/bin/pld_restream.sh
Restart=always
RestartSec=8

[Install]
WantedBy=multi-user.target
EOF
cat > /tmp/pld_api.service <<EOF
[Unit]
Description=PLD API Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$BASE_DIR
Environment=RUNTIME_DB=$RUNTIME_DB
Environment=API_TOKEN=${API_TOKEN:-changeme}
ExecStart=$BASE_DIR/bin/pld_api.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/pld_*.service /etc/systemd/system/
sudo systemctl daemon-reload

normalize_perms "$BASE_DIR"

echo "[install] Services installed (disabled). Enable with:"
echo "  sudo systemctl enable pld_probe pld_detect pld_restream pld_api"
echo "[install] Start with:"
echo "  sudo systemctl start pld_probe pld_detect pld_restream pld_api"
echo "[install] API token default is 'changeme' (override API_TOKEN env before install)."

if [[ ! -f "$MODEL_PATH" ]]; then
  echo "[install] WARNING: TFLite model missing ($MODEL_PATH). Detection will wait until file appears." >&2
fi

echo "[install] Done."
