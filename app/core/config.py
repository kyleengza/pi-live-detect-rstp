import os
from pydantic import BaseModel, Field
from typing import List, Optional


class RTSPConfig(BaseModel):
    name: str
    url: str
    fps: int = 15
    width: int = 1280
    height: int = 720
    infer_every_n_frames: int = 1
    transport: Optional[str] = Field(default=None, description="udp or tcp; None = auto (start udp then fallback)")


class HailoConfig(BaseModel):
    enabled: bool = Field(default=(os.getenv("HAILO_ENABLED", "1") == "1"))
    yolov8_hef_path: str = Field(default=os.getenv("YOLOV8_HEF", "/opt/hailo/models/yolov8s.hef"))
    device_id: Optional[int] = None  # None = auto-select
    score_threshold: float = float(os.getenv("HAILO_SCORE_THRESH", 0.3))
    nms_iou_threshold: float = float(os.getenv("HAILO_NMS_IOU", 0.45))


class RedisConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ttl_seconds: int = 30  # rolling window per entry


class APIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    username: str = Field(default=os.getenv("API_USER", "admin"))
    password: str = Field(default=os.getenv("API_PASS", "changeme"))


def _default_streams() -> List[RTSPConfig]:
    # Default to a single MJPEG RTSP stream known to work on the LAN.
    url1 = os.getenv("RTSP_URL_1", "rtsp://192.168.100.4:8554/stream")
    t1 = os.getenv("RTSP_TRANSPORT_1")
    streams: List[RTSPConfig] = [RTSPConfig(name="cam1", url=url1, transport=t1)]
    url2 = os.getenv("RTSP_URL_2")
    if url2:
        t2 = os.getenv("RTSP_TRANSPORT_2")
        streams.append(RTSPConfig(name="cam2", url=url2, transport=t2))
    return streams


class AppConfig(BaseModel):
    rtsp_streams: List[RTSPConfig] = Field(default_factory=_default_streams)
    hailo: HailoConfig = HailoConfig()
    redis: RedisConfig = RedisConfig()
    api: APIConfig = APIConfig()


CONFIG = AppConfig()
