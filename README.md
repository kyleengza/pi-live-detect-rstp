# Pi Live Detect RTSP with Hailo8L

Modular Python system for Raspberry Pi 5 on Raspberry Pi OS Lite (64-bit). Ingest RTSP streams, run object detection on Hailo8L (YOLOv8s via HailoRT), or fallback to CPU ONNX (OpenCV DNN) automatically, track with a lightweight IOU tracker (no PyTorch), cache results in Redis, and expose a FastAPI dashboard and API. All components run as systemd services.

## Features
- RTSP ingestor(s) -> pipelines (Hailo + tracking)
- Automatic CPU fallback: downloads YOLOv8n.onnx and runs OpenCV DNN if HailoRT not present
- Redis RAM-only cache with TTL per entry
- FastAPI with HTTP Basic Auth, simple dashboard
- systemd services + install/uninstall scripts
- Syslog logging and SSH-friendly
- Auto-reconnect on RTSP failures with UDP->TCP fallback

## Defaults
- One default stream: `rtsp://192.168.100.4:8554/stream` (MJPEG). Set `RTSP_URL_1` to override. To add a 2nd stream, set `RTSP_URL_2`.
- API Basic Auth: admin/changeme (set via `API_USER`/`API_PASS`).

## Hardware/OS
- Raspberry Pi 5, Raspberry Pi OS Lite 64-bit
- Hailo-8L M.2 with official HailoRT SDK installed (optional initially)

## Quick start on Pi
```sh
# On the Pi
sudo apt-get update && sudo apt-get install -y git
cd ~ && git clone https://github.com/kyleengza/pi-live-detect-rstp.git
cd pi-live-detect-rstp
# Optional overrides
export RTSP_URL_1="rtsp://192.168.100.4:8554/stream"
# export RTSP_URL_2="rtsp://..."   # only if you have a 2nd stream
sh scripts/install.sh
```

Open http://<pi-ip>:8000 and login with admin/changeme.

## RTSP notes
- The default stream is MJPEG. ffprobe examples:
  - TCP: `ffprobe -hide_banner -loglevel error -rtsp_transport tcp -select_streams v:0 -show_streams "$RTSP_URL"`
  - UDP: `ffprobe -hide_banner -loglevel error -rtsp_transport udp -select_streams v:0 -show_streams "$RTSP_URL"`
- For GStreamer MJPEG testing: `gst-launch-1.0 rtspsrc location="$RTSP_URL" protocols=tcp latency=200 ! rtpjpegdepay ! jpegdec ! fakesink`

## API endpoints (Basic Auth)
- GET `/config`
- GET `/cache/keys`, GET `/cache/get?key=...`
- GET `/streams/{name}/frame.jpg`, `/streams/{name}/annotated.jpg`
- GET `/logs/{logger}`
- GET `/probes`

## Services
- `pi-live-api.service`: serves FastAPI
- `pi-live-ingest@<name>.service`: read RTSP (per stream)
- `pi-live-pipeline@<name>.service`: Hailo/CPU detect + tracking + annotate (per stream)

Use `journalctl -u pi-live-*.service -f` to tail logs.

## Hailo and CPU fallback
- `app/infer/hailo_infer.py` tries HailoRT first. If unavailable, it will:
  - Auto-download YOLOv8n.onnx to `~/.cache/pi-live-detect-rstp/` (override via `YOLO_ONNX_PATH`).
  - Run inference via OpenCV DNN backend on CPU. Configure with envs:
    - `CPU_FALLBACK=0|1` (default 1)
    - `YOLO_ONNX_URL` (custom model URL)
    - `YOLO_ONNX_IMG` (input size, default 640)

## Troubleshooting
- If ffprobe returns 503, the camera/server is down; ingestor will auto-retry and fall back to TCP.
- If no frames in dashboard, check `pi-live-ingest@<name>.service` logs.
- If Redis missing, rerun installer; it installs and configures RAM-only Redis.
- If Hailo not installed, CPU fallback should still produce boxes after first ONNX download.

## Operations Manual
See `docs/OPERATIONS.md` for detailed architecture, configuration, install, monitoring, and troubleshooting guidance.

