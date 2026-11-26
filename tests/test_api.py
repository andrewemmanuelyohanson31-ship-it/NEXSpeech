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


def test_live_page_is_served():
    r = TestClient(app).get("/")
    assert r.status_code == 200 and "Transkrip live" in r.text


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


class SequenceTranscriber(FakeTranscriber):
    """Returns the scripted texts in order, one per finished utterance."""

    def __init__(self, texts):
        super().__init__()
        self.texts = list(texts)

    def __call__(self, audio):
        return self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]


def voice_session(monkeypatch, texts, slides_total=None):
    """Speak `texts` one utterance each; return the finished session summary."""
    monkeypatch.setattr("nex.engine.COOLDOWN_S", 0)
    fake = SequenceTranscriber(texts)
    app.state.transcriber_factory = lambda **kw: fake
    app.state.transcriber = None
    app.state.mic_factory = FakeMic(utterances(len(texts)))
    with TestClient(app) as c:
        # no partials (chunk > utterance), so each utterance makes exactly one transcriber call
        c.put("/api/settings", json={"chunk_s": 3.0})
        try:
            c.post("/api/session/start", json={"title": "deck commands", "slides_total": slides_total})
            eng = app.state.engine
            assert wait_for(lambda: not app.state.mic_factory.blocks)  # all audio consumed
            time.sleep(0.2)
            slide, state = eng.slide, eng.state
            summary = c.post("/api/session/stop").json()
        finally:
            c.put("/api/settings", json={"chunk_s": 1.0})
    return slide, state, summary


def test_voice_stop_and_mulai(monkeypatch):
    # "stop" pauses; "lanjut" while paused is ignored; "mulai" resumes; then "lanjut" works
    slide, state, s = voice_session(monkeypatch, ["stop", "lanjut", "mulai", "lanjut"], slides_total=10)
    assert slide == 2 and state == "listening"
    assert s["voice_commands"] == 1
    types = [(e["type"], e["action"]) for e in s["events"] if e["type"] in ("control", "command")]
    assert types == [("control", "pause"), ("control", "resume"), ("command", "next")]
    finals = [e["text"] for e in s["events"] if e["type"] == "final"]
    assert "lanjut" in finals and finals.count("lanjut") == 1  # the paused "lanjut" was not stored


def test_voice_first_and_last_slide(monkeypatch):
    slide, _, _ = voice_session(monkeypatch, ["slide terakhir"], slides_total=12)
    assert slide == 12
    slide, _, _ = voice_session(monkeypatch, ["slide 5", "slide pertama"], slides_total=12)
    assert slide == 1


def test_last_slide_without_slide_count_is_rejected(monkeypatch):
    slide, _, s = voice_session(monkeypatch, ["slide terakhir"], slides_total=None)
    assert slide == 1
    assert any(e["type"] == "rejected" and e["action"] == "last" for e in s["events"])


def test_mulai_while_listening_does_nothing(monkeypatch):
    _, state, s = voice_session(monkeypatch, ["kita mulai"])
    assert state == "listening" and not any(e["type"] == "control" for e in s["events"])


def test_tail_of_forced_cut_does_not_move_slide(monkeypatch):
    """12 s of nonstop talk is cut at 8 s; even if the tail reads "berikutnya"-like "lanjut", no action."""
    monkeypatch.setattr("nex.engine.COOLDOWN_S", 0)  # so only the cut rule can block the 2nd action
    fake = FakeTranscriber()
    fake.script = ["lanjut"]
    app.state.transcriber_factory = lambda **kw: fake
    app.state.transcriber = None
    app.state.mic_factory = FakeMic(quiet(8) + loud(48) + quiet(4))
    with TestClient(app) as c:
        c.post("/api/session/start", json={"title": "long talk"})
        sid = app.state.engine.session_id
        assert wait_for(lambda: sum(e["type"] == "final"
                                    for e in c.get(f"/api/sessions/{sid}").json()["events"]) >= 2)
        assert c.post("/api/session/stop").json()["voice_commands"] == 1  # the first part only


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
