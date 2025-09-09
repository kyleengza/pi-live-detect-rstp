from __future__ import annotations
import cv2
import time
import threading
import numpy as np
from typing import Dict, Any, List

from app.utils.logging_setup import setup_logging
from app.core.config import RTSPConfig, CONFIG
from app.core.redis_client import RedisCache
from app.infer.hailo_infer import HailoYoloV8
from app.track.tracker import MultiObjectTracker


class DetectionPipeline(threading.Thread):
    """End-to-end pipeline for one stream: ingest from Redis, infer on Hailo, track, annotate, republish."""

    def __init__(self, cfg: RTSPConfig, cache: RedisCache, hailo: HailoYoloV8) -> None:
        super().__init__(daemon=True)
        self.cfg = cfg
        self.cache = cache
        self.hailo = hailo
        self.log = setup_logging(f"pipeline.{cfg.name}")
        self.stop_event = threading.Event()
        self.tracker = MultiObjectTracker()
        self.frame_count = 0

    def run(self) -> None:
        self.log.info("Starting pipeline for %s", self.cfg.name)
        while not self.stop_event.is_set():
            raw = self.cache.get_frame(self.cfg.name)
            if not raw:
                time.sleep(0.05)
                continue
            frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                time.sleep(0.01)
                continue
            self.frame_count += 1

            dets: List[Dict[str, Any]] = []
            if (self.frame_count % max(1, self.cfg.infer_every_n_frames)) == 0:
                dets = self.hailo.infer(frame)

            tracks = self.tracker.update(dets, frame)
            annotated = self._draw(frame.copy(), tracks)

            # Store outputs in Redis with TTL
            ok, buf = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ok:
                self.cache.push_frame(f"annotated:{self.cfg.name}", buf.tobytes())
                self.cache.push_frame(f"frame:annotated:{self.cfg.name}", buf.tobytes())
            self.cache.set_json(f"tracks:{self.cfg.name}", {"ts": int(time.time()), "tracks": tracks})
            self.cache.publish_probe(self.cfg.name, "ok", {"event": "tick", "frames": self.frame_count})

        self.log.info("Stopping pipeline for %s", self.cfg.name)

    def _draw(self, img, tracks: List[Dict[str, Any]]):
        for t in tracks:
            x1, y1, x2, y2 = map(int, (t["x1"], t["y1"], t["x2"], t["y2"]))
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"id:{t['class_uid']} cls:{t['cls']} conf:{t['conf']:.2f}"
            cv2.putText(img, label, (x1, max(0, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1, cv2.LINE_AA)
        return img
