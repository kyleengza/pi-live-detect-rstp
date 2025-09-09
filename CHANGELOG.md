# Changelog

## 0.2.1 - 2025-09-09
- Default to single MJPEG RTSP stream (192.168.100.4:8554) with optional second stream via RTSP_URL_2.
- Sudo-aware scripts: install.sh, uninstall.sh, dev_run_all.sh; no hardcoded /home/pi.
- End-to-end modular pipeline: RTSP ingest, Redis TTL cache, FastAPI API, dashboard, DeepSORT tracking, systemd units.
- HailoRT wrapper scaffolding with graceful no-op when SDK absent.
- RAM-only Redis config (disable RDB/AOF) in installer.
- Basic Auth for API, syslog + Redis logging.
