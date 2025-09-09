# Pi Live Detect RTSP with Hailo8L

Modular Python system for Raspberry Pi 5 on Raspberry Pi OS Lite (64-bit). Ingest RTSP streams, run object detection on Hailo8L (YOLOv8s via HailoRT), track with DeepSORT, cache results in Redis, and expose a FastAPI dashboard and API. All components run as systemd services.

## Features
- RTSP ingestor(s) -> pipelines (Hailo+DeepSORT)
- Redis RAM-only cache with TTL per entry
- FastAPI with HTTP Basic Auth, simple dashboard
- systemd services + install/uninstall scripts
- Syslog logging and SSH-friendly

## Defaults
- One default stream: `rtsp://192.168.100.4:8554/stream` (MJPEG). Set `RTSP_URL_1` to override. To add a 2nd stream, set `RTSP_URL_2`.
- API Basic Auth: admin/changeme (set via `API_USER`/`API_PASS`).

## Hardware/OS
- Raspberry Pi 5, Raspberry Pi OS Lite 64-bit
- Hailo-8L M.2 with official HailoRT SDK installed

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
  - TCP: `ffprobe -hide_banner -loglevel error -rtsp_transport tcp -select_streams v:0 -show_streams -show_format "$RTSP_URL"`
  - UDP: `ffprobe -hide_banner -loglevel error -rtsp_transport udp -select_streams v:0 -show_streams -show_format "$RTSP_URL"`
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
- `pi-live-pipeline@<name>.service`: Hailo + DeepSORT + annotate (per stream)

Use `journalctl -u pi-live-*.service -f` to tail logs.

## Hailo
`app/infer/hailo_infer.py` loads HailoRT dynamically; implement your SDK-specific pre/post/inference for YOLOv8s.

## Troubleshooting
- If ffprobe (tcp) fails but (udp) works, your RTSP server may be MJPEG over UDP only; ingestion still works via OpenCV/FFmpeg.
- If no frames in dashboard, check `pi-live-ingest@<name>.service` logs.
- If Redis missing, rerun installer; it installs and configures RAM-only Redis.
- Hailo not installed yet: pipeline runs with empty detections until SDK is present.

## Development
Run everything in one process for quick testing:
```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export RTSP_URL_1="rtsp://192.168.100.4:8554/stream"
python -m app.main
```

