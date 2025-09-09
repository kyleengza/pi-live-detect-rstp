from __future__ import annotations
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import JSONResponse, Response, HTMLResponse
import base64

from app.core.config import CONFIG
from app.core.redis_client import RedisCache

security = HTTPBasic()
app = FastAPI(title="Pi Live Detect")
cache = RedisCache()


def check_auth(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = credentials.username == CONFIG.api.username
    correct_password = credentials.password == CONFIG.api.password
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True


@app.get("/config", response_class=JSONResponse)
async def get_config(_: bool = Depends(check_auth)):
    return CONFIG.model_dump()


@app.get("/cache/keys")
async def list_cache_keys(_: bool = Depends(check_auth)):
    return {"keys": cache.list_keys("*")}


@app.get("/cache/get")
async def cache_get(key: str, _: bool = Depends(check_auth)):
    data = cache.get_json(key)
    if data is not None:
        return data
    # maybe it's a frame
    raw = cache.get_frame(key)
    if raw:
        return Response(content=raw, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="not found")


@app.get("/streams/{name}/frame.jpg")
async def get_stream_frame(name: str, _: bool = Depends(check_auth)):
    raw = cache.get_frame(f"frame:{name}") or cache.get_frame(name)
    if raw:
        return Response(content=raw, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="no frame")


@app.get("/streams/{name}/annotated.jpg")
async def get_stream_ann(name: str, _: bool = Depends(check_auth)):
    raw = cache.get_frame(f"frame:annotated:{name}") or cache.get_frame(f"annotated:{name}")
    if raw:
        return Response(content=raw, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="no annotated frame")


@app.get("/logs/{logger}")
async def get_logs(logger: str, n: int = 100, _: bool = Depends(check_auth)):
    return {"logs": cache.read_logs(f"logs:{logger}")[:n]}


@app.get("/probes")
async def get_probes(_: bool = Depends(check_auth)):
    keys = cache.list_keys("probe:*")
    return cache.get_many(keys)


@app.get("/")
async def dashboard(_: bool = Depends(check_auth)):
    with open("app/web/dashboard.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())
