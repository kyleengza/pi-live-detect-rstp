# Pi Live Detect RTSP (Hailo8L + YOLO Pipeline)

End-to-end Raspberry Pi 5 real-time object detection pipeline that:

- Pulls frames from one or more RTSP streams (IP cameras / ONVIF)
- Runs hardware‑accelerated inference on the Hailo8L (pre-compiled HEF)
- Performs NMS / decoding using supplied post-process library
- Overlays detections and serves MJPEG and/or WebRTC preview
- Exposes REST + WebSocket APIs for detections
- Supports snapshot export & retention

> This repository was re-initialized. Historical files were removed per reset request.

## High-Level Architecture

```
┌──────────┐   RTSP    ┌────────────┐   tensors   ┌──────────────┐  boxes  ┌────────────────┐
│ IP Cam 1 │──────────▶│ Frame Grab │────────────▶│ Hailo Runtime│──────▶  │ Postprocess/NMS│
└──────────┘           └────────────┘             └──────────────┘         └──────┬─────────┘
                                                                                  │
┌──────────┐   RTSP    ┌────────────┐                                          ┌──▼──────────┐
│ IP Cam N │──────────▶│ Frame Grab │──────────────────────────────────────────▶ Overlay + UI│
└──────────┘           └────────────┘                                          └──┬──────────┘
                                                                                  │
                                                                          ┌───────▼────────┐
                                                                          │ REST / WS API  │
                                                                          └────────────────┘
```

## Core Components
- `scripts/install.sh` — system + Python + Hailo dependency setup
- `models/` — place `yolov5s.hef`, `yolov5s_nms_config.json`, `libyolo_post.so`, `labels.txt`
- `src/pipeline/rtsp_client.py` — async frame reader
- `src/pipeline/infer_engine.py` — Hailo inference wrapper (placeholder until actual SDK binding)
- `src/pipeline/postprocess.py` — NMS + decoding integrating provided post library
- `src/pipeline/serve.py` — FastAPI app (REST + WebSocket + MJPEG)
- `src/pipeline/config.py` — Pydantic settings (env + YAML)

## Getting Started

```bash
# 1. Clone fresh
git clone https://github.com/kyleengza/pi-live-detect-rstp.git
cd pi-live-detect-rstp

# 2. (Optional) Hard reset remote history (DANGEROUS)
#   Only do this if you intend to wipe previous contents
#   git checkout --orphan temp_branch
#   git add .
#   git commit -m "Initial reset"
#   git push origin --force temp_branch:main

# 3. Run installer (installs hailo-all, venv, deps)
chmod +x scripts/install.sh
./scripts/install.sh install

# 4. Place model assets
mkdir -p models/
# Copy: yolov5s.hef, yolov5s_nms_config.json, libyolo_post.so, labels.txt

# 5. Launch API server
source .venv/bin/activate
python -m src.pipeline.serve --host 0.0.0.0 --port 8000
```

## Configuration
Environment variables / `.env` or a `config.yaml` file are supported.

If only one stream is desired the first slot is used and the second is left blank. Example default first stream:
`rtsp://192.168.100.4:8554/stream`

Create a `.env` file (second slot intentionally blank after the comma):
```
RTSP_URLS=rtsp://192.168.100.4:8554/stream,
CONF_THRESHOLD=0.30
IOU_THRESHOLD=0.50
FRAME_WIDTH=640
FRAME_HEIGHT=384
MAX_QUEUE=4
SNAPSHOT_DIR=snapshots
```
(Leaving the trailing comma enables an empty second slot; it will be ignored.)

| Variable | Description | Default |
|----------|-------------|---------|
| RTSP_URLS | Comma separated list of RTSP endpoints (second can be blank) | rtsp://192.168.100.4:8554/stream |
| FRAME_WIDTH | Resize width before inference | 640 |
| FRAME_HEIGHT | Resize height | 384 |
| CONF_THRESHOLD | Confidence threshold | 0.25 |
| IOU_THRESHOLD | IoU for NMS | 0.45 |
| MAX_QUEUE | Frame queue length | 4 |
| SNAPSHOT_DIR | Where snapshots are stored | snapshots/ |

## Snapshot Saving
Request a snapshot (no save):
```
curl -o snap.jpg http://HOST:8000/snapshot/cam0
```
Request and persist snapshot to disk (returns JPEG plus `X-Snapshot-Path` header):
```
curl -i "http://HOST:8000/snapshot/cam0?save=true"
```
Files are stored under `SNAPSHOT_DIR` as `<stream>_<epoch_ms>.jpg`.

## API Surface
- `GET /health` — liveness
- `GET /streams` — list active streams
- `GET /snapshot/{stream_id}` — capture + return JPEG
- `GET /mjpeg/{stream_id}` — multipart MJPEG preview
- `WS /ws/detections` — push detection events

## Roadmap
- WebRTC low latency preview
- ONVIF auto-discovery
- Persistence of detection events
- Hailo native postprocess integration (Ctypes binding)

## License
MIT (adjust as desired)
