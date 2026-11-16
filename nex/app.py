"""NEX backend API. Run: python -m nex  (serves on http://127.0.0.1:8000, docs at /docs)

Binds to localhost only: this server can press keys on the machine, so it must not be reachable
from the network.
"""
import asyncio
import os
import threading
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .db import DB
from .engine import Engine

@asynccontextmanager
async def lifespan(app):
    app.state.loop = asyncio.get_running_loop()  # engine thread posts WebSocket events onto this loop
    yield
    if app.state.engine:
        app.state.engine.stop()


app = FastAPI(title="NEX backend", version="0.1.0", lifespan=lifespan)
app.state.db = DB()
app.state.engine = None
app.state.transcriber = None
app.state.transcriber_factory = None  # tests inject a fake; default loads faster-whisper
app.state.mic_factory = None
app.state.loading = False
clients: set[WebSocket] = set()
_model_lock = threading.Lock()


# --- schemas ---------------------------------------------------------------
class ScriptIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    platform: Optional[str] = Field(None, max_length=50)
    slides: list[str] = Field(default_factory=list, max_length=500)  # script text per slide
    vocab: str = Field("", max_length=2000)  # extra words appended to the Whisper prompt


class SettingsIn(BaseModel):
    model: Optional[Literal["tiny", "base", "small", "medium"]] = None
    language: Optional[Literal["id", "en", ""]] = None  # "" = auto-detect
    chunk_s: Optional[float] = Field(None, ge=0.25, le=3)
    silence_s: Optional[float] = Field(None, ge=0.25, le=2)
    jump_mode: Optional[Literal["number", "arrows"]] = None
    device: Optional[int] = None


class StartIn(BaseModel):
    title: str = Field("Sesi tanpa judul", max_length=200)
    script_id: Optional[int] = None
    slides_total: Optional[int] = Field(None, ge=1, le=500)


class ActionIn(BaseModel):
    action: Literal["next", "prev", "goto"]
    slide: Optional[int] = Field(None, ge=1, le=500)


class FeedbackIn(BaseModel):
    code: str = Field(min_length=1, max_length=20)  # participant code (U1..U5), never a name
    role: Optional[str] = Field(None, max_length=100)
    ease: int = Field(ge=1, le=5)
    responsiveness: int = Field(ge=1, le=5)
    quality: int = Field(ge=1, le=5)
    satisfaction: int = Field(ge=1, le=5)
    useful: Optional[str] = Field(None, max_length=2000)
    confusing: Optional[str] = Field(None, max_length=2000)
    missing: Optional[str] = Field(None, max_length=2000)
    session_id: Optional[int] = None


# --- live events -------------------------------------------------------------
def emit(ev):
    """Called from the engine thread; hands the event to the asyncio loop for all browsers."""
    loop = getattr(app.state, "loop", None)
    if loop and clients:
        asyncio.run_coroutine_threadsafe(_broadcast(ev), loop)


async def _broadcast(ev):
    for ws in list(clients):
        try:
            await ws.send_json(ev)
        except Exception:
            clients.discard(ws)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    eng = app.state.engine
    await ws.send_json({"type": "state", **(eng.info() if eng else {"state": "idle"})})
    try:
        while True:
            await ws.receive_text()  # keep-alive; the UI sends actions over REST
    except WebSocketDisconnect:
        clients.discard(ws)


# --- model -------------------------------------------------------------------
def _get_transcriber(settings, vocab=""):
    from .asr import PROMPT, Transcriber

    with _model_lock:
        t = app.state.transcriber
        if t is None or (t.model_size, t.language) != (settings["model"], settings["language"]):
            app.state.loading = True
            try:
                factory = app.state.transcriber_factory or Transcriber
                t = app.state.transcriber = factory(model_size=settings["model"], language=settings["language"])
            finally:
                app.state.loading = False
        t.prompt = PROMPT + (", " + vocab if vocab else "")
        return t


@app.post("/api/model/load")
def load_model():
    t = _get_transcriber(app.state.db.settings())
    return {"model": t.model_size, "language": t.language, "loaded": True}


@app.get("/api/status")
def status():
    t, eng = app.state.transcriber, app.state.engine
    try:
        from .audio import list_devices

        mics = list_devices()
    except Exception as e:
        mics, mic_error = [], str(e)
    else:
        mic_error = None
    return {"model": {"loaded": t is not None, "loading": app.state.loading,
                      "name": getattr(t, "model_size", None)},
            "microphones": mics, "mic_error": mic_error,
            "session": eng.info() if eng else {"state": "idle"},
            "settings": app.state.db.settings()}


# --- scripts (Naskah) ----------------------------------------------------------
@app.get("/api/scripts")
def list_scripts():
    return app.state.db.scripts()


@app.post("/api/scripts", status_code=201)
def create_script(s: ScriptIn):
    return app.state.db.script(app.state.db.save_script(s.title, s.platform, s.slides, s.vocab))


@app.get("/api/scripts/{sid}")
def get_script(sid: int):
    return app.state.db.script(sid) or _404("script")


@app.put("/api/scripts/{sid}")
def update_script(sid: int, s: ScriptIn):
    get_script(sid)
    return app.state.db.script(app.state.db.save_script(s.title, s.platform, s.slides, s.vocab, sid))


@app.delete("/api/scripts/{sid}", status_code=204)
def delete_script(sid: int):
    if not app.state.db.delete_script(sid):
        _404("script")


# --- live session --------------------------------------------------------------
@app.post("/api/session/start", status_code=201)
def start_session(body: StartIn):
    db = app.state.db
    if app.state.engine and app.state.engine.state != "stopped":
        raise HTTPException(409, "A session is already running")
    script = get_script(body.script_id) if body.script_id else None
    total = body.slides_total or (len(script["slides"]) if script and script["slides"] else None)
    settings = db.settings()
    transcriber = _get_transcriber(settings, script["vocab"] if script else "")
    sid = db.start_session(body.title, body.script_id, settings["model"], settings["language"],
                           settings["chunk_s"], total)
    eng = app.state.engine = Engine(transcriber, db, emit, settings, sid, total, app.state.mic_factory)
    eng.start()
    return eng.info()


def _engine():
    eng = app.state.engine
    if not eng or eng.state == "stopped":
        raise HTTPException(409, "No running session")
    return eng


@app.post("/api/session/pause")
def pause():
    _engine().pause()
    return app.state.engine.info()


@app.post("/api/session/resume")
def resume():
    _engine().resume()
    return app.state.engine.info()


@app.post("/api/session/stop")
def stop():
    eng = _engine()
    eng.stop()
    return app.state.db.session(eng.session_id)


@app.post("/api/session/action")
def manual_action(body: ActionIn):
    if body.action == "goto" and not body.slide:
        raise HTTPException(422, "goto needs a slide number")
    return _engine().act((body.action, body.slide), "manual")


# --- history (Riwayat), feedback (Review), settings (Pengaturan) -----------------
@app.get("/api/sessions")
def list_sessions():
    return app.state.db.sessions()


@app.get("/api/sessions/{sid}")
def get_session(sid: int):
    return app.state.db.session(sid) or _404("session")


@app.get("/api/feedback")
def list_feedback():
    return app.state.db.feedback()


@app.post("/api/feedback", status_code=201)
def add_feedback(f: FeedbackIn):
    return {"id": app.state.db.add_feedback(f.model_dump())}


@app.get("/api/settings")
def get_settings():
    return app.state.db.settings()


@app.put("/api/settings")
def put_settings(s: SettingsIn):
    if app.state.engine and app.state.engine.state != "stopped":
        raise HTTPException(409, "Stop the session before changing settings")
    return app.state.db.save_settings(s.model_dump(exclude_none=True))


def _404(what):
    raise HTTPException(404, f"{what} not found")


_frontend = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_frontend):  # the web UI (Figma screens) goes here later
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")
