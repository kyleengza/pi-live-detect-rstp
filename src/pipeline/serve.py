from __future__ import annotations
import cv2, io, time, asyncio, json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, Query
from fastapi.responses import StreamingResponse, JSONResponse
from loguru import logger
from typing import Dict, List
from .config import settings
from .rtsp_client import RTSPClient
from .infer_engine import HailoInference
from .postprocess import filter_boxes
import numpy as np
import os

app = FastAPI(title="Pi Live Detect RTSP")

STREAMS: Dict[str, RTSPClient] = {}
INFER = HailoInference()

@app.on_event("startup")
def startup():
    logger.info("Starting streams")
    for idx, url in enumerate(settings.rtsp_urls):
        name = f"cam{idx}"
        STREAMS[name] = RTSPClient(url, settings.max_queue, name).start()
    INFER.load()

@app.on_event("shutdown")
def shutdown():
    for c in STREAMS.values():
        c.stop()

@app.get("/health")
def health():
    return {"status": "ok", "streams": list(STREAMS.keys())}

@app.get("/streams")
def list_streams():
    return {k: {"fps": v.fps} for k,v in STREAMS.items()}

@app.get("/snapshot/{stream_id}")
def snapshot(stream_id: str, save: bool = Query(False, description="Persist snapshot to disk")):
    client = STREAMS.get(stream_id)
    if not client:
        return JSONResponse({"error": "not found"}, status_code=404)
    frame = client.snapshot()
    ok, buf = cv2.imencode('.jpg', frame)
    if not ok:
        return JSONResponse({"error": "encode failed"}, status_code=500)
    if save:
        ts = int(time.time()*1000)
        os.makedirs(settings.snapshot_dir, exist_ok=True)
        path = os.path.join(settings.snapshot_dir, f"{stream_id}_{ts}.jpg")
        with open(path, 'wb') as f:
            f.write(buf.tobytes())
        logger.info(f"Saved snapshot {path}")
        return Response(content=buf.tobytes(), headers={"X-Snapshot-Path": path}, media_type='image/jpeg')
    return Response(content=buf.tobytes(), media_type='image/jpeg')

@app.get("/mjpeg/{stream_id}")
def mjpeg(stream_id: str):
    client = STREAMS.get(stream_id)
    if not client:
        return JSONResponse({"error": "not found"}, status_code=404)

    def gen():
        while True:
            frame = client.read()
            if frame is None:
                time.sleep(0.05); continue
            boxes, scores = INFER.infer(frame)
            boxes, scores = filter_boxes(boxes, scores, settings.conf_threshold, settings.iou_threshold)
            for b,s in zip(boxes, scores):
                x1,y1,x2,y2 = b.astype(int)
                cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,0),2)
                cv2.putText(frame,f"{s:.2f}",(x1,y1-4),cv2.FONT_HERSHEY_SIMPLEX,0.4,(0,255,0),1)
            ok, jpg = cv2.imencode('.jpg', frame)
            if not ok:
                continue
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n")
    return StreamingResponse(gen(), media_type='multipart/x-mixed-replace; boundary=frame')

WS_CONNECTIONS: List[WebSocket] = []

@app.websocket("/ws/detections")
async def ws(ws: WebSocket):
    await ws.accept()
    WS_CONNECTIONS.append(ws)
    try:
        while True:
            await asyncio.sleep(1)
            payload = []
            for name, client in STREAMS.items():
                frame = client.read()
                if frame is None:
                    continue
                boxes, scores = INFER.infer(frame)
                boxes, scores = filter_boxes(boxes, scores, settings.conf_threshold, settings.iou_threshold)
                for b,s in zip(boxes, scores):
                    payload.append({
                        "stream": name,
                        "box": b.tolist(),
                        "score": float(s)
                    })
            await ws.send_text(json.dumps({"detections": payload, "ts": time.time()}))
    except WebSocketDisconnect:
        pass
    finally:
        if ws in WS_CONNECTIONS:
            WS_CONNECTIONS.remove(ws)

if __name__ == "__main__":
    import argparse, uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("src.pipeline.serve:app", host=args.host, port=args.port, reload=False)

# Added explicit main entrypoint for console script

def main():  # pragma: no cover
    import argparse, uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("src.pipeline.serve:app", host=args.host, port=args.port, reload=False)
