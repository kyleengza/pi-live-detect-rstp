# Pi Live Detect RTSP with Hailo8L

Modular Python system for Raspberry Pi 5 on Raspberry Pi OS Lite (64-bit). Ingest two RTSP streams, run object detection on Hailo8L (YOLOv8s via HailoRT), track with DeepSORT, cache results in Redis, and expose a FastAPI dashboard and API. All components run as systemd services.

## Features
- Two parallel RTSP ingestors -> pipelines (Hailo+DeepSORT)
- Redis RAM-only cache with TTL per entry
- FastAPI with HTTP Basic Auth, simple dashboard
- systemd services + install/uninstall scripts
- Syslog logging and SSH-friendly

## Hardware/OS
- Raspberry Pi 5, Raspberry Pi OS Lite 64-bit
- Hailo-8L M.2 with official HailoRT SDK installed

## Quick start on Pi
```sh
# On the Pi (as user pi)
sudo apt-get update
sudo apt-get install -y git
cd ~
git clone https://github.com/<your-org>/pi-live-detect-rstp.git
cd pi-live-detect-rstp
sh scripts/install.sh
```

Then open http://<pi-ip>:8000 and login with admin/changeme (change in `app/core/config.py`).

## Configuration
Edit defaults in `app/core/config.py` or set env vars RTSP_URL_1 / RTSP_URL_2 before running. Update `yolov8_hef_path` to the actual .hef path from Hailo.

## Services
- `pi-live-api.service`: serves FastAPI
- `pi-live-ingest@cam1.service` and `@cam2`: read RTSP
- `pi-live-pipeline@cam1.service` and `@cam2`: Hailo + DeepSORT + annotate

Use `journalctl -u pi-live-*.service -f` to tail logs.

## Notes on Hailo
This repo loads HailoRT dynamically. Implement actual pre/post/infer steps in `app/infer/hailo_infer.py` with your SDK environment.

## Development
Run everything in one process for quick testing:
```sh
python -m app.main
```

