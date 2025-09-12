#!/bin/sh
set -e
RTSP_URL="${RTSP_URL_1:-rtsp://192.168.100.4:8554/stream}"
LABELS=config/classes.txt
CONFIG=config/model.yaml
PY=app/infer/hailo_infer.py
while true; do
  python "$PY" --config "$CONFIG" --labels "$LABELS" --source "$RTSP_URL" --annotate --publish
  sleep 1
done
