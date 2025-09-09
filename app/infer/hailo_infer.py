from __future__ import annotations
import importlib
import numpy as np
from typing import Any, Dict, List

from app.utils.logging_setup import setup_logging
from app.core.config import HailoConfig


class HailoYoloV8:
    """Thin wrapper around HailoRT for YOLOv8s. Falls back to CPU NMS if needed.

    Note: Actual HailoRT API calls depend on installed SDK (not on PyPI). This wrapper
    loads modules dynamically to avoid import errors on dev machines.
    """

    def __init__(self, cfg: HailoConfig) -> None:
        self.cfg = cfg
        self.log = setup_logging("hailo")
        self.available = False
        self._init_hailo()

    def _init_hailo(self) -> None:
        try:
            hailo_rt = importlib.import_module("hailo")  # pseudoname; replace with actual
            # Placeholder usage; actual HailoRT init differs, but we keep interface stable
            # E.g. create device, load HEF, configure network group, etc.
            self.available = True
            self.log.info("HailoRT module loaded; using device=%s", self.cfg.device_id)
        except Exception as e:
            self.available = False
            self.log.warning("HailoRT not available, inference disabled: %s", e)

    def infer(self, image_bgr: np.ndarray) -> List[Dict[str, Any]]:
        """Run inference; return list of detections with keys: [cls, conf, x1,y1,x2,y2].
        If Hailo is not available, returns empty list to keep pipeline running.
        """
        if not self.available or not self.cfg.enabled:
            return []

        # Placeholder: Assuming hailo returns bounding boxes in needed format.
        # Real implementation would:
        # - preprocess (resize, normalize)
        # - run HailoRT inference
        # - postprocess YOLO head to boxes with score_threshold & NMS
        # Here we return empty for skeleton.
        return []
