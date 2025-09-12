from __future__ import annotations
import time
from typing import Any, Dict, List, Optional

import numpy as np

from app.utils.logging_setup import setup_logging


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    # a,b: [x1,y1,x2,y2]
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    iw = max(0.0, inter_x2 - inter_x1)
    ih = max(0.0, inter_y2 - inter_y1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return float(inter / denom) if denom > 0 else 0.0


class _Track:
    def __init__(self, tid: int, bbox: np.ndarray, cls: int, conf: float) -> None:
        self.id = tid
        self.bbox = bbox.astype(float)  # [x1,y1,x2,y2]
        self.cls = int(cls)
        self.conf = float(conf)
        self.missed = 0
        self.last_ts = time.time()

    def update(self, bbox: np.ndarray, cls: int, conf: float):
        self.bbox = bbox.astype(float)
        self.cls = int(cls)
        self.conf = float(conf)
        self.missed = 0
        self.last_ts = time.time()


class MultiObjectTracker:
    """Lightweight IOU-based tracker for object tracking.

    - No external dependencies (no torch, no deep-sort-realtime).
    - Greedy IoU matching; tracks expire after `max_age` missed updates.
    """

    def __init__(self, max_age: int = 30, iou_thresh: float = 0.3) -> None:
        self.log = setup_logging("tracker")
        self.max_age = max(1, int(max_age))
        self.iou_thresh = float(iou_thresh)
        self.tracks: list[_Track] = []
        self.next_tid: int = 1
        # Preserve stable class_uid mapping like previous implementation
        self.id_map: dict[int, int] = {}
        self.next_uid: int = 1

    def _new_track(self, bbox: np.ndarray, cls: int, conf: float) -> _Track:
        t = _Track(self.next_tid, bbox, cls, conf)
        self.next_tid += 1
        self.tracks.append(t)
        return t

    def update(self, detections: List[Dict[str, Any]], frame_bgr: Optional[np.ndarray] = None) -> List[Dict[str, Any]]:
        # Convert detections into numpy bboxes
        det_bboxes: list[np.ndarray] = []
        det_meta: list[tuple[int, float]] = []  # (cls, conf)
        for d in detections or []:
            x1, y1, x2, y2 = float(d["x1"]), float(d["y1"]), float(d["x2"]), float(d["y2"])
            det_bboxes.append(np.array([x1, y1, x2, y2], dtype=float))
            det_meta.append((int(d.get("cls", -1)), float(d.get("conf", 1.0))))

        # Age existing tracks
        for t in self.tracks:
            t.missed += 1

        # Match detections to tracks greedily by IoU
        unmatched_det_idxs = set(range(len(det_bboxes)))
        for t in self.tracks:
            # pick best det by IoU
            best_iou = 0.0
            best_j = None
            for j in list(unmatched_det_idxs):
                iou = _iou(t.bbox, det_bboxes[j])
                if iou > best_iou:
                    best_iou = iou
                    best_j = j
            if best_j is not None and best_iou >= self.iou_thresh:
                cls, conf = det_meta[best_j]
                t.update(det_bboxes[best_j], cls, conf)
                if best_j in unmatched_det_idxs:
                    unmatched_det_idxs.remove(best_j)

        # Create new tracks for unmatched detections
        for j in sorted(unmatched_det_idxs):
            cls, conf = det_meta[j] if j < len(det_meta) else (-1, 1.0)
            self._new_track(det_bboxes[j], cls, conf)

        # Drop stale tracks
        self.tracks = [t for t in self.tracks if t.missed <= self.max_age]

        # Build output in pipeline-expected schema
        out: List[Dict[str, Any]] = []
        for t in self.tracks:
            tid = int(t.id)
            if tid not in self.id_map:
                self.id_map[tid] = self.next_uid
                self.next_uid += 1
            uid = self.id_map[tid]
            x1, y1, x2, y2 = t.bbox.tolist()
            out.append({
                "track_id": tid,
                "class_uid": uid,
                "x1": float(x1),
                "y1": float(y1),
                "x2": float(x2),
                "y2": float(y2),
                "cls": int(t.cls),
                "conf": float(t.conf),
            })
        return out
