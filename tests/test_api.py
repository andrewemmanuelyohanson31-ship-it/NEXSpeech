import queue
import time

import numpy as np
from fastapi.testclient import TestClient

from nex.app import app
from test_recognizer import loud, quiet


class FakeTranscriber:
    """Stands in for faster-whisper: says whatever the test scripted, one final per utterance."""

    def __init__(self, model_size="small", language="id", **kw):
        self.model_size, self.language, self.prompt = model_size, language, ""
        self.script = ["lanjut", "slide 4", "balik", "the next topic is speech recognition"]

    def __call__(self, audio):
        return self.script[0]


class FakeMic:
    def __init__(self, blocks):
        self.blocks = list(blocks)

    def __call__(self, device=None):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def read(self, timeout=0.5):
        if not self.blocks:
            time.sleep(0.01)
            raise queue.Empty
        return self.blocks.pop(0)


def wait_for(fn, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if fn():
            return True
        time.sleep(0.02)
    return False


def utterances(n):
    return quiet(8) + sum((loud(2) + quiet(4) for _ in range(n)), [])


def test_scripts_crud_and_validation():
    c = TestClient(app)
    s = c.post("/api/scripts", json={"title": "Pengantar SR", "platform": "PowerPoint",
                                     "slides": ["a", "b", "c"], "vocab": "gradient descent"}).json()
    assert s["slides"] == ["a", "b", "c"]
    assert c.get(f"/api/scripts/{s['id']}").json()["title"] == "Pengantar SR"
    assert c.put(f"/api/scripts/{s['id']}", json={"title": "X", "slides": []}).json()["title"] == "X"
    assert c.post("/api/scripts", json={"title": ""}).status_code == 422
    assert c.delete(f"/api/scripts/{s['id']}").status_code == 204
    assert c.get(f"/api/scripts/{s['id']}").status_code == 404


def test_feedback_and_settings_validation():
    c = TestClient(app)
    ok = {"code": "U1", "ease": 4, "responsiveness": 4, "quality": 3, "satisfaction": 5}
    assert c.post("/api/feedback", json=ok).status_code == 201
    assert c.post("/api/feedback", json={**ok, "ease": 9}).status_code == 422
    assert c.put("/api/settings", json={"model": "gpt"}).status_code == 422
    assert c.put("/api/settings", json={"chunk_s": 0.5}).json()["chunk_s"] == 0.5
    c.put("/api/settings", json={"chunk_s": 1.0})


def test_voice_session_end_to_end():
    """fake mic -> recognizer -> speech-to-action -> slide moves -> stats in Riwayat."""
    fake = FakeTranscriber()
    app.state.transcriber_factory = lambda **kw: fake
    app.state.transcriber = None
    app.state.mic_factory = FakeMic(utterances(1))
    with TestClient(app) as c:
        with c.websocket_connect("/ws") as ws:
            assert ws.receive_json()["type"] == "state"
            r = c.post("/api/session/start", json={"title": "demo", "slides_total": 5})
            assert r.status_code == 201
            assert c.post("/api/session/start", json={}).status_code == 409  # one session at a time

            seen = []
            while not any(e["type"] == "command" for e in seen):
                seen.append(ws.receive_json())
            cmd = next(e for e in seen if e["type"] == "command")
            assert (cmd["action"], cmd["slide"], cmd["source"]) == ("next", 2, "voice")
            assert cmd["latency"] is not None and cmd["latency"] >= 0
            assert any(e["type"] == "final" and e["text"] == "lanjut" for e in seen)

        assert c.post("/api/session/action", json={"action": "goto", "slide": 5}).json()["slide"] == 5
        assert c.post("/api/session/action", json={"action": "next"}).json()["type"] == "rejected"  # past last slide
        assert c.post("/api/session/action", json={"action": "goto"}).status_code == 422
        assert c.post("/api/session/pause").json()["state"] == "paused"
        assert c.post("/api/session/resume").json()["state"] == "listening"
        summary = c.post("/api/session/stop").json()
        assert summary["voice_commands"] == 1 and summary["manual_commands"] == 1
        assert summary["ended"] is not None
        assert c.post("/api/session/pause").status_code == 409
        assert c.get(f"/api/sessions/{summary['id']}").json()["events"]


def test_long_sentence_does_not_move_slide():
    fake = FakeTranscriber()
    fake.script = ["the next topic is speech recognition"]
    app.state.transcriber_factory = lambda **kw: fake
    app.state.transcriber = None
    app.state.mic_factory = FakeMic(utterances(1))
    with TestClient(app) as c:
        c.post("/api/session/start", json={"title": "talk"})
        sid = app.state.engine.session_id
        assert wait_for(lambda: any(e["type"] == "final" for e in c.get(f"/api/sessions/{sid}").json()["events"]))
        assert app.state.engine.slide == 1
        assert c.post("/api/session/stop").json()["voice_commands"] == 0
