from __future__ import annotations
import importlib
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.utils.logging_setup import setup_logging
from app.core.config import HailoConfig


# Prefer user-writable cache path by default; can be overridden via YOLO_ONNX_PATH
YOLO_ONNX_DEFAULT_URL = os.getenv(
    "YOLO_ONNX_URL",
    # Updated to valid Ultralytics ONNX asset
    "https://github.com/ultralytics/yolov5/releases/download/v6.2/yolov5n.onnx",
)
YOLO_ONNX_LOCAL = Path(
    os.getenv("YOLO_ONNX_PATH", os.path.join(os.path.expanduser("~"), ".cache", "pi-live-detect-rstp", "yolov8n.onnx"))
)
YOLO_ONNX_IMG_SIZE = int(os.getenv("YOLO_ONNX_IMG", "640"))
CPU_FALLBACK = os.getenv("CPU_FALLBACK", "1") == "1"


class HailoYoloV8:
    """Thin wrapper around HailoRT for YOLOv8s with CPU ONNX fallback using OpenCV DNN.

    - Tries to initialize HailoRT (when SDK is installed on the Pi).
    - If unavailable (or cfg.enabled is False), falls back to ONNX model with OpenCV DNN.
    - ONNX model is auto-downloaded once to YOLO_ONNX_LOCAL if missing.
    """

    def __init__(self, cfg: HailoConfig) -> None:
        self.cfg = cfg
        self.log = setup_logging("hailo")
        self.available = False
        self._hailo = None  # legacy reference imports
        self._dnn_net: Optional[cv2.dnn_Net] = None
        # Hailo runtime members
        self._hp = None
        self._device = None
        self._hef = None
        self._configured = False
        self._input_vstreams = None
        self._output_vstreams = None
        self._hailo_input_shape: Optional[Tuple[int, int]] = None  # (H, W)
        self._logged_shapes = False
        self._init_hailo_or_cpu()

    # ---------------------------- Hailo path ----------------------------
    def _init_hailo_or_cpu(self) -> None:
        if self.cfg.enabled:
            try:
                self._hp = importlib.import_module("hailo_platform")
                hp = self._hp
                hef_path = self.cfg.yolov8_hef_path
                if not hef_path or not os.path.isfile(hef_path):
                    raise FileNotFoundError(f"HEF not found at {hef_path}")
                self._hef = hp.HEF(hef_path)
                self._device = hp.Device()
                net_groups = self._hef.get_network_groups_infos()
                if not net_groups:
                    raise RuntimeError("No network groups in HEF")
                group = net_groups[0]
                # SDK 4.20.0: configure with just the HEF
                self._device.configure(self._hef)
                input_infos = self._hef.get_input_vstream_infos(group)
                output_infos = self._hef.get_output_vstream_infos(group)
                self._input_vstreams = hp.InferVStreams(self._device, input_infos, True)
                self._output_vstreams = hp.InferVStreams(self._device, output_infos, False)
                if input_infos:
                    info0 = list(input_infos)[0]
                    shape = getattr(info0, 'shape', None)
                    if shape and len(shape) >= 2:
                        self._hailo_input_shape = (shape[0], shape[1])
                if not self._hailo_input_shape:
                    self._hailo_input_shape = (640, 640)
                self.available = True
                self._configured = True
                self.log.info(
                    "HailoRT configured (hef=%s, input=%s)",
                    hef_path,
                    self._hailo_input_shape,
                )
                return
            except Exception as e:
                self.log.warning("HailoRT init failed: %s", e)
        # Hailo disabled or failed -> CPU fallback (only if allowed)
        if CPU_FALLBACK:
            self._ensure_onnx()
            self._init_cpu_net()
        else:
            self.log.info("No fallback enabled; detections will be empty.")

    # ---------------------------- CPU ONNX path ----------------------------
    def _ensure_onnx(self) -> None:
        try:
            if YOLO_ONNX_LOCAL.exists() and YOLO_ONNX_LOCAL.stat().st_size > 1024 * 1024:
                return
        except Exception:
            pass
        # Create parent dir
        try:
            YOLO_ONNX_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        # Download to temp then move
        self.log.info("Downloading YOLOv8n ONNX model -> %s", YOLO_ONNX_LOCAL)
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                urllib.request.urlretrieve(YOLO_ONNX_DEFAULT_URL, tmp.name)
                tmp_path = Path(tmp.name)
            YOLO_ONNX_LOCAL.write_bytes(tmp_path.read_bytes())
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
        except Exception as e:
            self.log.error("Failed to download ONNX model: %s", e)

    def _init_cpu_net(self) -> None:
        try:
            net = cv2.dnn.readNetFromONNX(str(YOLO_ONNX_LOCAL))
            # Prefer OpenVINO or CPU; on Pi CPU is typical
            backend = int(os.getenv("OPENCV_DNN_BACKEND", str(cv2.dnn.DNN_BACKEND_OPENCV)))
            target = int(os.getenv("OPENCV_DNN_TARGET", str(cv2.dnn.DNN_TARGET_CPU)))
            net.setPreferableBackend(backend)
            net.setPreferableTarget(target)
            self._dnn_net = net
            self.log.info("CPU ONNX fallback initialized (%s)", YOLO_ONNX_LOCAL)
        except Exception as e:
            self._dnn_net = None
            self.log.error("Failed to initialize OpenCV DNN ONNX: %s", e)

    # ---------------------------- Inference ----------------------------
    def infer(self, image_bgr: np.ndarray) -> List[Dict[str, Any]]:
        """Run inference; return list of detections with keys: [cls, conf, x1,y1,x2,y2].
        - If Hailo is not available or disabled, uses CPU ONNX fallback.
        - Returns empty list if neither path is available.
        """
        if self.cfg.enabled and self.available and self._configured:
            return self._infer_hailo(image_bgr)
        if CPU_FALLBACK and self._dnn_net is not None:
            return self._infer_onnx(image_bgr)
        return []

    # ---------------------------- Hailo inference ----------------------------
    def _letterbox(self, img: np.ndarray, new_shape: Tuple[int, int]) -> Tuple[np.ndarray, float, float, Tuple[int, int]]:
        h, w = img.shape[:2]
        new_h, new_w = new_shape
        scale = min(new_w / w, new_h / h)
        resized = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR)
        canvas = np.zeros((new_h, new_w, 3), dtype=np.uint8)
        top = (new_h - resized.shape[0]) // 2
        left = (new_w - resized.shape[1]) // 2
        canvas[top:top + resized.shape[0], left:left + resized.shape[1]] = resized
        return canvas, scale, left, top

    def _infer_hailo(self, image_bgr: np.ndarray) -> List[Dict[str, Any]]:
        try:
            if not self._configured or self._input_vstreams is None or self._output_vstreams is None:
                return []
            target_shape = self._hailo_input_shape or (640, 640)
            hb, wb = target_shape
            pre_img, scale, pad_left, pad_top = self._letterbox(image_bgr, (hb, wb))
            inp = pre_img.astype(np.uint8)
            for _, vs in self._input_vstreams.items():  # type: ignore[attr-defined]
                vs.write(inp)
            outputs: Dict[str, Any] = {}
            for name, vs in self._output_vstreams.items():  # type: ignore[attr-defined]
                outputs[name] = vs.read()
            if not self._logged_shapes:
                shape_map = {k: (v.shape if hasattr(v, 'shape') else type(v)) for k, v in outputs.items()}
                self.log.info("Hailo outputs shapes: %s", shape_map)
                self._logged_shapes = True
            det_arrays = []
            for arr in outputs.values():
                if not hasattr(arr, 'shape'):
                    continue
                a = np.array(arr)
                # Normalize to (N, C)
                if a.ndim == 3:  # (1, N, C) or (1, C, N)
                    if a.shape[0] == 1:
                        a = a[0]
                if a.ndim == 2:
                    if a.shape[1] in (84, 85):
                        det_arrays.append(a[:, :84])  # trim 85 -> 84 if needed
                    elif a.shape[0] in (84, 85):
                        det_arrays.append(a[:84, :].T)
                elif a.ndim == 1 and a.size % 84 == 0:
                    det_arrays.append(a.reshape(-1, 84))
            if not det_arrays:
                return []
            det_mat = np.concatenate(det_arrays, axis=0)
            if det_mat.shape[1] < 6:
                return []
            boxes_xywh = det_mat[:, :4]
            scores = det_mat[:, 4:]
            class_ids = np.argmax(scores, axis=1)
            confidences = np.max(scores, axis=1)
            mask = confidences >= float(self.cfg.score_threshold)
            if not np.any(mask):
                return []
            boxes_xywh = boxes_xywh[mask]
            confidences = confidences[mask]
            class_ids = class_ids[mask]
            # Reverse letterbox scaling: boxes are in letterboxed space (640x640)
            # YOLOv8 format cx,cy,w,h relative to letterbox dims
            cx = boxes_xywh[:, 0]
            cy = boxes_xywh[:, 1]
            bw = boxes_xywh[:, 2]
            bh = boxes_xywh[:, 3]
            # Convert to top-left in letterbox image
            x1_l = cx - bw / 2
            y1_l = cy - bh / 2
            x2_l = cx + bw / 2
            y2_l = cy + bh / 2
            # Remove padding and divide by scale to map back to original image
            x1 = (x1_l - pad_left) / scale
            y1 = (y1_l - pad_top) / scale
            x2 = (x2_l - pad_left) / scale
            y2 = (y2_l - pad_top) / scale
            H, W = image_bgr.shape[:2]
            def clamp(v, lo, hi):
                return np.maximum(lo, np.minimum(hi, v))
            x1p = clamp(x1, 0, W - 1)
            y1p = clamp(y1, 0, H - 1)
            x2p = clamp(x2, 0, W - 1)
            y2p = clamp(y2, 0, H - 1)
            widths = np.maximum(1.0, x2p - x1p)
            heights = np.maximum(1.0, y2p - y1p)
            boxes_for_nms = np.stack([x1p, y1p, widths, heights], axis=1).astype(np.float32)
            confidences_f32 = confidences.astype(np.float32).tolist()
            idxs = cv2.dnn.NMSBoxes(boxes_for_nms.tolist(), confidences_f32, float(self.cfg.score_threshold), float(self.cfg.nms_iou_threshold))
            if isinstance(idxs, (list, tuple, np.ndarray)):
                try:
                    flat = np.array(idxs).reshape(-1).tolist()
                except Exception:
                    flat = [int(i[0]) if isinstance(i, (list, tuple, np.ndarray)) else int(i) for i in idxs]
            else:
                flat = [int(idxs)] if idxs is not None else []
            dets: List[Dict[str, Any]] = []
            for i in flat[:200]:
                if i < 0 or i >= len(boxes_for_nms):
                    continue
                x, y, w, h = boxes_for_nms[i]
                dets.append({
                    "cls": int(class_ids[i]),
                    "conf": float(confidences[i]),
                    "x1": float(x),
                    "y1": float(y),
                    "x2": float(x + w),
                    "y2": float(y + h),
                })
            if os.getenv("HAILO_DEBUG", "0") == "1":
                self.log.info("Hailo raw dets (pre-NMS=%d, post=%d)", det_mat.shape[0], len(dets))
            return dets
        except Exception as e:
            self.log.error("Hailo inference/postprocess error: %s", e)
            return []

    # ---------------------------- CPU ONNX postprocess helpers ----------------------------
    def _preprocess(self, img: np.ndarray, size: int) -> Tuple[np.ndarray, float, float]:
        h, w = img.shape[:2]
        blob = cv2.dnn.blobFromImage(img, scalefactor=1/255.0, size=(size, size), mean=(0, 0, 0), swapRB=True, crop=False)
        return blob, w / float(size), h / float(size)

    def _infer_onnx(self, image_bgr: np.ndarray) -> List[Dict[str, Any]]:
        net = self._dnn_net
        if net is None:
            return []
        size = YOLO_ONNX_IMG_SIZE
        blob, scale_w, scale_h = self._preprocess(image_bgr, size)
        net.setInput(blob)
        out = net.forward()
        # Normalize output shape to (N, C)
        if out.ndim == 3:
            # (1, C, N) or (1, N, C)
            if out.shape[1] < out.shape[2]:
                # (1, C, N) -> (N, C)
                out = np.transpose(out, (0, 2, 1))
            out = out[0]
        elif out.ndim != 2:
            # Unknown format
            return []
        if out.shape[1] < 6:
            return []
        boxes_xywh = out[:, :4]
        scores = out[:, 4:]
        class_ids = np.argmax(scores, axis=1)
        confidences = np.max(scores, axis=1)

        # Threshold
        mask = confidences >= float(self.cfg.score_threshold)
        boxes_xywh = boxes_xywh[mask]
        confidences = confidences[mask]
        class_ids = class_ids[mask]
        if boxes_xywh.size == 0:
            return []

        # Convert to original image coordinates
        cx = boxes_xywh[:, 0]
        cy = boxes_xywh[:, 1]
        bw = boxes_xywh[:, 2]
        bh = boxes_xywh[:, 3]
        x1 = (cx - bw / 2) * scale_w
        y1 = (cy - bh / 2) * scale_h
        x2 = (cx + bw / 2) * scale_w
        y2 = (cy + bh / 2) * scale_h

        H, W = image_bgr.shape[:2]
        def clamp(v, lo, hi):
            return np.maximum(lo, np.minimum(hi, v))
        x1p = clamp(x1, 0, W - 1)
        y1p = clamp(y1, 0, H - 1)
        x2p = clamp(x2, 0, W - 1)
        y2p = clamp(y2, 0, H - 1)
        widths = np.maximum(1.0, x2p - x1p)
        heights = np.maximum(1.0, y2p - y1p)
        boxes_for_nms = np.stack([x1p, y1p, widths, heights], axis=1).astype(np.float32)
        confidences_f32 = confidences.astype(np.float32).tolist()
        idxs = cv2.dnn.NMSBoxes(boxes_for_nms.tolist(), confidences_f32, float(self.cfg.score_threshold), float(self.cfg.nms_iou_threshold))
        dets: List[Dict[str, Any]] = []
        # Normalize indices to a flat list of ints
        if isinstance(idxs, (list, tuple, np.ndarray)):
            try:
                flat = np.array(idxs).reshape(-1).tolist()
            except Exception:
                flat = [int(i[0]) if isinstance(i, (list, tuple, np.ndarray)) else int(i) for i in idxs]
        else:
            flat = [int(idxs)] if idxs is not None else []
        for i in flat:
            if i < 0 or i >= len(boxes_for_nms):
                continue
            x, y, w, h = boxes_for_nms[i]
            dets.append({
                "cls": int(class_ids[i]),
                "conf": float(confidences[i]),
                "x1": float(x),
                "y1": float(y),
                "x2": float(x + w),
                "y2": float(y + h),
            })
        return dets
