#!/usr/bin/env bash
# One-shot preparation script (TFLite + RAM DB version)
set -euo pipefail

REPO_URL=${REPO_URL:-https://github.com/kyleengza/pi-live-detect-rstp.git}
TARGET_DIR=${TARGET_DIR:-$HOME/pi-live-detect-rstp}
BRANCH=${BRANCH:-main}
BASE_DIR=${BASE_DIR:-$TARGET_DIR}
USER_NAME=${SUDO_USER:-$USER}

normalize_perms() {
  local target="$1"
  [[ -d "$target" ]] || return 0
  if [[ ${EUID} -ne 0 && -n ${SUDO_USER:-} ]]; then sudo chown -R "$USER_NAME":"$USER_NAME" "$target"; fi || true
  chown -R "$USER_NAME":"$USER_NAME" "$target" 2>/dev/null || true
  find "$target" -type d -exec chmod 755 {} + 2>/dev/null || true
  find "$target" -type f -name '*.sh' -exec chmod 755 {} + 2>/dev/null || true
  find "$target" -type f -name '*.py' -exec chmod 644 {} + 2>/dev/null || true
}

if ! command -v git >/dev/null; then echo "git required" >&2; exit 1; fi

if [[ -d "$TARGET_DIR/.git" ]]; then
  echo "[prep] Updating existing repo $TARGET_DIR";
  git -C "$TARGET_DIR" fetch --depth 1 origin "$BRANCH";
  git -C "$TARGET_DIR" reset --hard origin/"$BRANCH";
else
  echo "[prep] Cloning $REPO_URL -> $TARGET_DIR";
  git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$TARGET_DIR";
fi
cd "$TARGET_DIR"
normalize_perms "$TARGET_DIR"

echo "[prep] Installing system prerequisites (sudo)"
export DEBIAN_FRONTEND=noninteractive
sudo apt update -qq
sudo apt install -y -qq \
  python3-venv python3-pip python3-gi \
  gstreamer1.0-tools gstreamer1.0-libav \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
  gir1.2-gst-plugins-base-1.0 gir1.2-gst-rtsp-server-1.0 \
  ffmpeg jq sqlite3 curl

mkdir -p "$BASE_DIR/data/frames" "$BASE_DIR/logs" models

MODEL_PATH=${MODEL_PATH:-models/yolov8n.tflite}
if [[ ! -f "$MODEL_PATH" ]]; then
  if [[ -n "${MODEL_URL:-}" ]]; then
    echo "[prep] Downloading TFLite model from $MODEL_URL"
    if curl -L --fail --retry 3 -o "$MODEL_PATH" "$MODEL_URL"; then
      echo "[prep] Model saved to $MODEL_PATH"
    else
      echo "[prep] Model download failed; detect will wait for file." >&2
    fi
  else
    echo "[prep] No TFLite model present ($MODEL_PATH). Detection will wait until file appears." >&2
  fi
fi

# Ensure install.sh uses same BASE_DIR
export BASE_DIR MODEL_PATH
bash scripts/install.sh

normalize_perms "$BASE_DIR"

echo "[prep] Enabling services"
sudo systemctl enable pld_probe pld_detect pld_restream pld_api || true

echo "[prep] Starting services"
sudo systemctl start pld_probe pld_detect pld_restream pld_api || true

echo "[prep] Done. If detect waits, place model at $MODEL_PATH then: sudo systemctl restart pld_detect"
echo "[prep] Using BASE_DIR=$BASE_DIR (repository). Set BASE_DIR env before running to choose a different deployment directory."
