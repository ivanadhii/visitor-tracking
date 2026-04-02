import asyncio
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.stream_manager import StreamManager
from core.auth import AuthManager

app = FastAPI(title="VisionTrack API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = StreamManager()
auth = AuthManager()


# ──────────────────────────────────────────────────────────────────── schemas

class StreamCreate(BaseModel):
    url: str
    name: str

class StreamUpdate(BaseModel):
    detection: bool

class DetectionAll(BaseModel):
    detection: bool

class LoginBody(BaseModel):
    username: str
    password: str


# ──────────────────────────────────────────────────────────────────── auth dep

def require_auth(authorization: Optional[str] = Header(default=None)):
    if not auth.auth_required:
        return "anonymous"
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.removeprefix("Bearer ")
    username = auth.verify(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return username


# ──────────────────────────────────────────────────────────────────── auth API

@app.post("/api/auth/login")
def login(body: LoginBody):
    token = auth.login(body.username, body.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": token, "username": body.username}


@app.post("/api/auth/logout")
def logout():
    # JWT is stateless — actual logout is handled client-side by clearing the token
    return {"ok": True}


@app.get("/api/auth/me")
def me(username: str = require_auth):  # type: ignore[assignment]
    return {"username": username, "auth_required": auth.auth_required}


# ──────────────────────────────────────────────────────────────────── REST API

@app.get("/api/streams")
def list_streams(username: str = require_auth):  # type: ignore[assignment]
    return manager.list_streams()


@app.post("/api/streams", status_code=201)
def create_stream(body: StreamCreate, username: str = require_auth):  # type: ignore[assignment]
    sid = manager.add(body.url, body.name)
    return {"id": sid}


@app.patch("/api/streams")
def update_all_streams(body: DetectionAll, username: str = require_auth):  # type: ignore[assignment]
    manager.set_detection_all(body.detection)
    return {"ok": True}


@app.patch("/api/streams/{stream_id}")
def update_stream(stream_id: str, body: StreamUpdate, username: str = require_auth):  # type: ignore[assignment]
    ok = manager.set_detection(stream_id, body.detection)
    return {"ok": ok}


@app.delete("/api/streams/{stream_id}")
def delete_stream(stream_id: str, username: str = require_auth):  # type: ignore[assignment]
    ok = manager.remove(stream_id)
    return {"ok": ok}


# ──────────────────────────────────────────────────────────────────── WebSocket

@app.websocket("/ws/stream/{stream_id}")
async def stream_ws(
    ws: WebSocket,
    stream_id: str,
    token: Optional[str] = Query(default=None),
):
    # Auth check for WebSocket
    if auth.auth_required:
        username = auth.verify(token or "")
        if not username:
            await ws.close(code=4001)
            return

    pipeline = manager.get_pipeline(stream_id)
    if not pipeline:
        await ws.close(code=4004)
        return

    await ws.accept()
    last = None

    try:
        while pipeline.running:
            data = pipeline.get_latest()
            if data is not None and data is not last:
                await ws.send_json(data)
                last = data
            await asyncio.sleep(1 / 20)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
