import cv2, threading, queue, time
from typing import Optional
from loguru import logger

class RTSPClient:
    def __init__(self, url: str, max_queue: int = 4, name: Optional[str] = None):
        self.url = url
        self.name = name or url.rsplit("/", 1)[-1]
        self.cap = None
        self.q: queue.Queue = queue.Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.fps = 0.0

    def start(self):
        if self.thread and self.thread.is_alive():
            return self
        self.cap = cv2.VideoCapture(self.url)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open RTSP stream: {self.url}")
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()
        logger.info(f"RTSP client started for {self.url}")
        return self

    def _reader(self):
        last = time.time(); frames = 0
        while not self._stop.is_set():
            ok, frame = self.cap.read()
            if not ok:
                logger.warning(f"Stream read failed for {self.url}; retrying in 2s")
                time.sleep(2)
                continue
            frames += 1
            now = time.time()
            if now - last >= 2:
                self.fps = frames / (now - last)
                frames = 0; last = now
            if not self.q.full():
                self.q.put(frame)
            else:
                try:
                    _ = self.q.get_nowait()
                except Exception:
                    pass
                self.q.put(frame)
        logger.info(f"RTSP client stopped: {self.url}")

    def read(self):
        try:
            return self.q.get(timeout=1)
        except queue.Empty:
            return None

    def stop(self):
        self._stop.set()
        if self.thread:
            self.thread.join(timeout=2)
        if self.cap:
            self.cap.release()

    def snapshot(self):
        frame = self.read()
        if frame is None:
            raise RuntimeError("No frame available")
        return frame
