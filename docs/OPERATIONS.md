# Pi Live Detect RTSP — Operations Manual

This manual describes the architecture, preparation, configuration, installation, operation, monitoring, and troubleshooting of the Pi Live Detect system on a Raspberry Pi 5.

## 1. Architecture Overview

- RTSP Ingestor (per stream)
  - Reads frames from an RTSP source using OpenCV/FFmpeg.
  - Publishes latest JPEG frame to Redis (binary) under keys:
    - `pi-live:frame:<name>` and alias `pi-live:frame:frame:<name>` (alias is deprecated; kept for compatibility).
  - Publishes last frame metadata JSON to `pi-live:last_frame_meta:<name>`.
  - Publishes health probe JSON to `pi-live:probe:<name>`.
  - Auto-reconnects on failure and falls back to TCP when UDP fails.

- Detection Pipeline (per stream)
  - Reads latest frame from Redis.
  - Runs Hailo inference via `app/infer/hailo_infer.py` (stub when HailoRT SDK is unavailable).
  - Tracks objects with a lightweight IOU tracker (no PyTorch required).
  - Draws annotations and publishes JPEG to `pi-live:frame:annotated:<name>`.
  - Publishes tracks JSON to `pi-live:tracks:<name>`.

- FastAPI Server
  - Serves REST API and a simple dashboard (HTTP Basic Auth).
  - Reads frames/JSON from Redis.

- Redis (RAM-only)
  - Key namespace prefix: `pi-live:*`.
  - Frames stored as binary bytes with TTL.

- systemd Services
  - `pi-live-api.service`: HTTP server.
  - `pi-live-ingest@<name>.service`: Ingestor per stream.
  - `pi-live-pipeline@<name>.service`: Pipeline per stream.

## 2. Prerequisites

- Raspberry Pi 5, Raspberry Pi OS Lite (64-bit).
- Internet access and SSH.
- Hailo-8L module (optional at first). Install HailoRT SDK later when ready.
- RTSP source URLs (MJPEG or H264; MJPEG preferred on constrained devices).

## 3. Configuration

Environment variables (can be set before running installer or added to `/etc/systemd/system/pi-live-*.service` Environment= entries):

- Stream URLs
  - `RTSP_URL_1` (default `rtsp://192.168.100.4:8554/stream`)
  - `RTSP_URL_2` (optional; enable second stream)
- Per-stream options (optional via code or config envs)
  - `RTSP_NAME_1` (default `cam1`), `RTSP_NAME_2` (default `cam2`)
  - `RTSP_FPS_1`, `RTSP_WIDTH_1`, `RTSP_HEIGHT_1` (defaults 15, 640, 480)
- API auth
  - `API_USER` (default `admin`), `API_PASS` (default `changeme`)
- Redis
  - `REDIS_HOST` (default `127.0.0.1`), `REDIS_PORT` (default `6379`)
  - `REDIS_DB` (default `0`), `REDIS_TTL` (default `30` seconds)

Transport/FFmpeg tuning (already coded; typically no need to set):
- The ingestor prefers UDP, auto-falls back to TCP after repeated failures.
- FFmpeg options via `OPENCV_FFMPEG_CAPTURE_OPTIONS` are applied internally.

## 4. Installation

On the Pi:

```sh
sudo apt-get update && sudo apt-get install -y git
cd ~ && git clone https://github.com/kyleengza/pi-live-detect-rstp.git
cd pi-live-detect-rstp
# Optional: override defaults
export RTSP_URL_1="rtsp://<camera-ip>:8554/stream"
# export RTSP_URL_2="rtsp://.../stream2"
# export API_USER=admin API_PASS=changeme
sh scripts/install.sh
```

What install.sh does:
- Creates Python venv and installs requirements.
- Ensures Redis is installed and configured.
- Installs systemd units, sets ExecStart to venv binaries.
- Enables and starts: API, ingest@cam1, pipeline@cam1.

Uninstall:
```sh
sh scripts/uninstall.sh
```

## 5. Running and Monitoring

- Check service status:
```sh
systemctl is-active pi-live-api.service
systemctl is-active pi-live-ingest@cam1.service
systemctl is-active pi-live-pipeline@cam1.service
```

- Tail logs:
```sh
journalctl -u pi-live-api.service -f
journalctl -u pi-live-ingest@cam1.service -f
journalctl -u pi-live-pipeline@cam1.service -f
```

- API and Dashboard:
  - http://<pi-ip>:8000 (Basic Auth)
  - Endpoints:
    - /streams/cam1/frame.jpg, /streams/cam1/annotated.jpg
    - /config, /cache/keys, /cache/get?key=pi-live:tracks:cam1
    - /probes, /logs/ingest.cam1

- Redis quick checks:
```sh
redis-cli --raw KEYS 'pi-live:*' | sort
redis-cli --raw GET pi-live:last_frame_meta:cam1
redis-cli --raw GET pi-live:frame:cam1 > /tmp/cam1.jpg
```

## 6. Troubleshooting

- RTSP 503 or intermittent availability
  - Ingestor will reconnect and switch to TCP automatically after repeated failures.
  - Verify stream with ffprobe:
    - UDP: `ffprobe -hide_banner -v error -rtsp_transport udp -select_streams v:0 -show_streams rtsp://<ip>:8554/stream`
    - TCP: `ffprobe -hide_banner -v error -rtsp_transport tcp -select_streams v:0 -show_streams rtsp://<ip>:8554/stream`
- No frames in API
  - Check `journalctl -u pi-live-ingest@cam1.service` for read errors.
  - Ensure network reachability to the camera.
- Pipeline not drawing boxes
  - HailoRT SDK not installed; inference returns no detections.
  - Tracker is IOU-based and requires detections to emit tracks.
- Torch import error
  - Resolved: DeepSORT replaced with IOU tracker; no PyTorch needed on Pi.

## 7. Hailo Integration TODO

- Implement YOLOv8s preprocessing/postprocessing in `app/infer/hailo_infer.py`.
- Add model assets (.hef) and load via HailoRT.
- Gate detection frequency via `infer_every_n_frames` in config for performance.

## 8. Development Tips

- Run API locally:
```sh
. .venv/bin/activate
uvicorn app.api.server:app --reload --host 0.0.0.0 --port 8000
```
- Run a single ingestor without systemd:
```sh
python -m app.entrypoints.rtsp_ingestor_service cam1
```
- Run pipeline without systemd:
```sh
python -m app.entrypoints.pipeline_service cam1
```

## 9. Key Paths

- Code: `app/`
- Services: `systemd/`
- Scripts: `scripts/`
- Docs: `docs/`
