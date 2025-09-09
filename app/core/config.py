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


class HailoConfig(BaseModel):
    enabled: bool = True
    yolov8_hef_path: str = "/opt/hailo/models/yolov8s.hef"  # Placeholder default
    device_id: Optional[int] = None  # None = auto-select
    score_threshold: float = 0.3
    nms_iou_threshold: float = 0.45


class RedisConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ttl_seconds: int = 30  # rolling window per entry


class APIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    username: str = Field(default="admin")
    password: str = Field(default="changeme")


class AppConfig(BaseModel):
    rtsp_streams: List[RTSPConfig] = Field(
        default=[
            RTSPConfig(name="cam1", url=os.getenv("RTSP_URL_1", "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mov")),
            RTSPConfig(name="cam2", url=os.getenv("RTSP_URL_2", "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mov")),
        ]
    )
    hailo: HailoConfig = HailoConfig()
    redis: RedisConfig = RedisConfig()
    api: APIConfig = APIConfig()


CONFIG = AppConfig()
