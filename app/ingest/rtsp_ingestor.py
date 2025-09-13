import cv2
import os
import time
import threading
from typing import Optional, Tuple

from app.utils.logging_setup import setup_logging
from app.core.config import RTSPConfig
from app.core.redis_client import RedisCache


class RTSPIngestor(threading.Thread):
    """Reads frames from an RTSP source and publishes them to Redis."""

    def __init__(self, cfg: RTSPConfig, cache: RedisCache) -> None:
        super().__init__(daemon=True)
        self.cfg = cfg
        self.cache = cache
        self.log = setup_logging(f"ingest.{cfg.name}")
        self.stop_event = threading.Event()
        self.cap: Optional[cv2.VideoCapture] = None
        self.transport: str = "udp"  # prefer UDP; fallback to TCP on repeated failures
        self.reopen_tries: int = 0

    def open(self) -> bool:
        # Force transport to TCP for reliability
        self.transport = "tcp"
        desired_transport = self.transport
        opts = [
            f"rtsp_transport;{self.transport}",
            "max_delay;5000000",
            "stimeout;10000000",
            "reorder_queue_size;0",
            "buffer_size;2048",
        ]
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "|".join(opts)
        self.cap = cv2.VideoCapture(self.cfg.url, cv2.CAP_FFMPEG)
        if not (self.cap and self.cap.isOpened()):
            self.log.error("Failed to open RTSP (%s): %s", self.transport, self.cfg.url)
            return False
        # Lower internal buffering
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        # Optional timeouts if supported
        for prop, val in (
            (getattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC", None), 5000),
            (getattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC", None), 5000),
        ):
            if prop is not None:
                try:
                    self.cap.set(prop, val)
                except Exception:
                    pass
        # Try to configure FPS and size if supported
        self.cap.set(cv2.CAP_PROP_FPS, self.cfg.fps)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.height)
        return True

    def _reopen(self) -> None:
        try:
            if self.cap:
                self.cap.release()
        except Exception:
            pass
        # After a couple of failed reopen attempts on UDP, switch to TCP
        self.reopen_tries += 1
        if self.transport == "udp" and self.reopen_tries >= 2:
            self.transport = "tcp"
            self.log.info("Switching RTSP transport to TCP due to repeated failures")
        time.sleep(1.0)
        self.open()

    def run(self) -> None:
        if not self.open():
            self.cache.publish_probe(self.cfg.name, "error", {"reason": "open_failed"})
            return
        self.cache.publish_probe(self.cfg.name, "ok", {"event": "start"})
        frame_interval = 1.0 / max(self.cfg.fps, 1)
        last = 0.0
        fail_count = 0
        while not self.stop_event.is_set():
            if not self.cap:
                break
            ok, frame = self.cap.read()
            if not ok or frame is None:
                fail_count += 1
                if fail_count % 10 == 0:
                    self.log.warning("Read failed x%d, retrying...", fail_count)
                # Reopen after sustained failures
                if fail_count >= 12:
                    self.log.info("Reopening RTSP due to repeated read failures")
                    self._reopen()
                    fail_count = 0
                time.sleep(0.25)
                continue
            if fail_count:
                self.log.info("Read recovered after %d failures", fail_count)
            fail_count = 0
            now = time.time()
            if now - last < frame_interval:
                # throttle to desired fps
                time.sleep(max(0.0, frame_interval - (now - last)))
            last = time.time()

            self.log.info(f"RTSP frame captured: shape={frame.shape}, dtype={frame.dtype}, min={frame.min()}, max={frame.max()}")
            # Encode frame as JPEG for caching and dashboard
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if ok:
                self.log.info(f"RTSP frame encoded: size={len(buf.tobytes())} bytes, first 4 bytes={buf.tobytes()[:4]}")
                # Write primary frame key and one alias (not duplicate alias of alias)
                self.cache.push_frame(self.cfg.name, buf.tobytes())
                self.cache.push_frame(f"frame:{self.cfg.name}", buf.tobytes())
                self.log.info(f"RTSP frame pushed to Redis: key={self.cfg.name}, bytes={len(buf.tobytes())}")
                self.cache.set_json(f"last_frame_meta:{self.cfg.name}", {
                    "ts": int(last),
                    "w": frame.shape[1],
                    "h": frame.shape[0],
                })
        self.cache.publish_probe(self.cfg.name, "stopped", {"event": "stop"})

    def stop(self) -> None:
        self.stop_event.set()
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
