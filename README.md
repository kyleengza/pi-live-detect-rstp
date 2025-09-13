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
- RTSP ingest now defaults to TCP transport for reliability. If you experience frame corruption or smudging, ensure your camera is streaming with sufficient bitrate and quality.
- JPEG encoding quality for frame capture is set to 95 for best clarity. You can adjust this in `app/ingest/rtsp_ingestor.py` if needed.

## API endpoints (Basic Auth)
- GET `/streams/{name}/frame.jpg` (raw frame)
- GET `/streams/{name}/annotated.jpg` (annotated frame)

Example:
```sh
curl -u admin:changeme -o raw_cam1_api.jpg http://<pi-ip>:8000/streams/cam1/frame.jpg
curl -u admin:changeme -o annotated_cam1_api.jpg http://<pi-ip>:8000/streams/cam1/annotated.jpg
```

## Services
- `pi-live-api.service`: serves FastAPI
- `pi-live-ingest@<name>.service`: read RTSP (per stream)
- `pi-live-pipeline@<name>.service`: Hailo/CPU detect + tracking + annotate (per stream)

Use `journalctl -u pi-live-*.service -f` to tail logs.

## Systemd units
All systemd unit files are patched automatically by the installer to use the correct user and home directory. If you change your username or move the project, rerun the installer.

## HailoRT SDK Installation
- The installer will install the HailoRT SDK and Python bindings if the packages are present in the `prereq/` folder.
- If you see `No module named 'hailo_platform'`, detection will run on CPU only.

## Uninstall
Run `sh scripts/uninstall.sh` to stop and remove all services and unit files.

## Troubleshooting
- If any service fails, check logs with `journalctl -u pi-live-*.service -f`.
- If you change your username or home directory, rerun the installer to patch all systemd units.

## Post-Install
- After install, verify services are running:
    - `systemctl status pi-live-api.service`
    - `systemctl status pi-live-ingest@<name>.service`
    - `systemctl status pi-live-pipeline@<name>.service`
- Test API at `http://<pi-ip>:8000` (admin/changeme).

## Operations Manual
See `docs/OPERATIONS.md` for detailed architecture, configuration, install, monitoring, and troubleshooting guidance.

## Model, Config, and Label Locations
- Models, configs, and labels are expected in:
  - `~/pi-live-detect-rstp/models/hailo/yolov5_custom.hef` (Hailo)
  - `~/pi-live-detect-rstp/models/custom/model.onnx` (CPU fallback)
  - `~/pi-live-detect-rstp/config/model.yaml`, `classes.txt` (labels/config)
- Paths are auto-detected; override with env vars if needed.

