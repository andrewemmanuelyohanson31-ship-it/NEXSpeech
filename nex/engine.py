"""A live NEX session: mic -> StreamingRecognizer -> speech-to-action -> key press -> events."""
import queue
import threading
import time

from . import keys
from .asr import StreamingRecognizer, rms
from .commands import parse

COOLDOWN_S = 1.0  # ignore a second voice command this soon after one (echo / repeated word)


class Engine:
    def __init__(self, transcriber, db, emit, settings, session_id, slides_total=None, mic_factory=None):
        self.db, self.emit, self.session_id = db, emit, session_id
        self.jump_mode = settings.get("jump_mode", "number")
        self.slides_total = slides_total
        self.slide = 1
        self.rec = StreamingRecognizer(transcriber, chunk_s=settings["chunk_s"], silence_s=settings["silence_s"])
        self.mic_factory = mic_factory
        self.device = settings.get("device")
        self.state = "starting"
        self.last_voice_action = 0.0
        self._stop = threading.Event()
        self._lock = threading.Lock()  # voice thread and API buttons both move the slide
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        try:
            if self.mic_factory is None:
                from .audio import Mic

                self.mic_factory = Mic
            with self.mic_factory(self.device) as mic:
                self._set_state("calibrating")
                n = 0
                while not self._stop.is_set():
                    try:
                        block = mic.read()
                    except queue.Empty:
                        continue
                    n += 1
                    if n % 2 == 0:
                        self.emit({"type": "level", "rms": rms(block)})
                    if self.state == "paused":
                        continue
                    for ev in self.rec.feed(block):
                        self._handle(ev)
                    if self.state == "calibrating" and self.rec.calibrated():
                        self._set_state("listening")
                for ev in self.rec.flush():
                    self._handle(ev)
        except Exception as e:  # mic unplugged, permission denied: tell the UI instead of dying silently
            self.emit({"type": "error", "message": str(e)})
        finally:
            self._set_state("stopped")
            self.db.end_session(self.session_id)

    def _handle(self, ev):
        speech_end_t = ev.pop("speech_end_t", None)
        self.emit(ev)
        if ev["type"] == "partial":
            return
        self.db.log_event(self.session_id, ev)
        # finals only (one "next" can't fire twice), and never the tail of a forced 8 s cut
        action = None if ev.get("after_cut") else parse(ev["text"])
        if action and time.perf_counter() - self.last_voice_action >= COOLDOWN_S:
            self.last_voice_action = time.perf_counter()
            self.act(action, "voice", speech_end_t, ev["text"])

    def act(self, action, source, speech_end_t=None, text=None):
        with self._lock:
            kind, n = action
            target = {"next": self.slide + 1, "prev": self.slide - 1, "goto": n}[kind]
            if target < 1 or (self.slides_total and target > self.slides_total):
                ev = {"type": "rejected", "action": kind, "slide": target, "text": text, "source": source}
                self.emit(ev)
                self.db.log_event(self.session_id, ev)
                return ev
            keys.send(action, current=self.slide, jump_mode=self.jump_mode)
            self.slide = target
            latency = (time.perf_counter() - speech_end_t) if speech_end_t else None
            ev = {"type": "command", "action": kind, "slide": target, "slides_total": self.slides_total,
                  "text": text, "source": source, "latency": latency}
            self.emit(ev)
            self.db.log_event(self.session_id, ev)
            return ev

    def pause(self):
        if self.state != "stopped":
            self.rec.reset()
            self._set_state("paused")

    def resume(self):
        if self.state == "paused":
            self._set_state("listening")

    def stop(self):
        self._stop.set()
        if self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=5)

    def _set_state(self, s):
        self.state = s
        self.emit({"type": "state", "state": s, "slide": self.slide, "slides_total": self.slides_total,
                   "session_id": self.session_id})

    def info(self):
        return {"state": self.state, "slide": self.slide, "slides_total": self.slides_total,
                "session_id": self.session_id}
