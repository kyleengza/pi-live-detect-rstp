from __future__ import annotations
import numpy as np
from typing import Any, Dict, List
from deep_sort_realtime.deepsort_tracker import DeepSort

from app.utils.logging_setup import setup_logging


class MultiObjectTracker:
    """Wrap DeepSort and map track_id to persistent class_uid."""

    def __init__(self, max_age: int = 30):
        self.log = setup_logging("tracker")
        self.tracker = DeepSort(max_age=max_age)
        self.id_map: dict[int, int] = {}
        self.next_uid: int = 1

    def update(self, detections: List[Dict[str, Any]], frame_bgr: np.ndarray) -> List[Dict[str, Any]]:
        # DeepSortRealtime expects: [[x1,y1,x2,y2, confidence, class], ...]
        ds_inputs = []
        for d in detections:
            ds_inputs.append([
                d["x1"], d["y1"], d["x2"], d["y2"], float(d.get("conf", 1.0)), int(d.get("cls", -1))
            ])
        tracks = self.tracker.update_tracks(ds_inputs, frame=frame_bgr)
        out = []
        for t in tracks:
            if not t.is_confirmed():
                continue
            tid = int(t.track_id)
            if tid not in self.id_map:
                self.id_map[tid] = self.next_uid
                self.next_uid += 1
            uid = self.id_map[tid]
            ltrb = t.to_ltrb()
            out.append({
                "track_id": tid,
                "class_uid": uid,
                "x1": float(ltrb[0]),
                "y1": float(ltrb[1]),
                "x2": float(ltrb[2]),
                "y2": float(ltrb[3]),
                "cls": int(getattr(t, "det_class", -1)),
                "conf": float(getattr(t, "det_conf", 1.0)),
            })
        return out
