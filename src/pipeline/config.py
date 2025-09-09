from __future__ import annotations
from pydantic import BaseSettings, Field
from typing import List
import os, yaml

class Settings(BaseSettings):
    rtsp_urls: List[str] = Field(default_factory=list, alias="RTSP_URLS")
    frame_width: int = Field(640, alias="FRAME_WIDTH")
    frame_height: int = Field(384, alias="FRAME_HEIGHT")
    conf_threshold: float = Field(0.25, alias="CONF_THRESHOLD")
    iou_threshold: float = Field(0.45, alias="IOU_THRESHOLD")
    max_queue: int = Field(4, alias="MAX_QUEUE")
    snapshot_dir: str = Field("snapshots", alias="SNAPSHOT_DIR")

    def __init__(self, **values):
        super().__init__(**values)
        # If user provided nothing, set default primary stream
        if not self.rtsp_urls:
            self.rtsp_urls = ["rtsp://192.168.100.4:8554/stream"]

    class Config:
        case_sensitive = False
        env_file = ".env"

    @classmethod
    def load(cls, yaml_path: str = "config.yaml") -> "Settings":
        data = {}
        if os.path.isfile(yaml_path):
            with open(yaml_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            for k, v in raw.items():
                data[k.upper()] = v
        env_override = cls(**data)
        # Rebuild data from env override (env precedence)
        merged = {}
        for field in env_override.__fields__:
            env_name = env_override.__fields__[field].alias
            val = getattr(env_override, field)
            if val not in (None, [], ""):
                merged[env_name] = val
        if isinstance(merged.get("RTSP_URLS"), str):
            merged["RTSP_URLS"] = [s.strip() for s in merged["RTSP_URLS"].split(",") if s.strip()]
        settings = cls(**merged)
        os.makedirs(settings.snapshot_dir, exist_ok=True)
        return settings

settings = Settings.load()
