"""SQLite storage: scripts (naskah), sessions, per-utterance events, user feedback, settings.
Only text is stored, never audio."""
import json
import os
import sqlite3
import threading
import time

DB_PATH = os.environ.get("NEX_DB", os.path.join(os.path.dirname(__file__), "..", "data", "nex.db"))
SCHEMA = """
CREATE TABLE IF NOT EXISTS scripts(id INTEGER PRIMARY KEY, title TEXT NOT NULL, platform TEXT,
  slides TEXT NOT NULL DEFAULT '[]', vocab TEXT NOT NULL DEFAULT '', updated REAL);
CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY, title TEXT, script_id INTEGER,
  started REAL, ended REAL, model TEXT, language TEXT, chunk_s REAL, slides_total INTEGER);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, session_id INTEGER, t REAL, type TEXT,
  text TEXT, action TEXT, slide INTEGER, source TEXT, latency REAL, audio_s REAL, infer_s REAL);
CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY, code TEXT NOT NULL, role TEXT,
  ease INTEGER, responsiveness INTEGER, quality INTEGER, satisfaction INTEGER,
  useful TEXT, confusing TEXT, missing TEXT, session_id INTEGER, created REAL);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""
# tiny by default: on an i7-8700 CPU, small took ~4.6 s per command (RTF > 1); pick per laptop via eval
DEFAULT_SETTINGS = {"model": "tiny", "language": "id", "chunk_s": 1.0, "silence_s": 0.6,
                    "jump_mode": "number", "device": None}


class DB:
    def __init__(self, path=DB_PATH):
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.con = sqlite3.connect(path, check_same_thread=False)  # shared by API + engine thread
        self.con.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.con.executescript(SCHEMA)

    def q(self, sql, args=()):
        with self.lock:
            cur = self.con.execute(sql, args)
            self.con.commit()
            return cur

    def rows(self, sql, args=()):
        return [dict(r) for r in self.q(sql, args).fetchall()]

    # scripts ------------------------------------------------------------
    def scripts(self):
        return [self._script(r) for r in self.rows("SELECT * FROM scripts ORDER BY updated DESC")]

    def script(self, sid):
        r = self.rows("SELECT * FROM scripts WHERE id=?", (sid,))
        return self._script(r[0]) if r else None

    def save_script(self, title, platform, slides, vocab, sid=None):
        args = (title, platform, json.dumps(slides), vocab, time.time())
        if sid is None:
            return self.q("INSERT INTO scripts(title,platform,slides,vocab,updated) VALUES(?,?,?,?,?)", args).lastrowid
        self.q("UPDATE scripts SET title=?,platform=?,slides=?,vocab=?,updated=? WHERE id=?", (*args, sid))
        return sid

    def delete_script(self, sid):
        return self.q("DELETE FROM scripts WHERE id=?", (sid,)).rowcount

    @staticmethod
    def _script(r):
        return {**r, "slides": json.loads(r["slides"])}

    # sessions -----------------------------------------------------------
    def start_session(self, title, script_id, model, language, chunk_s, slides_total):
        return self.q("INSERT INTO sessions(title,script_id,started,model,language,chunk_s,slides_total) "
                      "VALUES(?,?,?,?,?,?,?)",
                      (title, script_id, time.time(), model, language, chunk_s, slides_total)).lastrowid

    def end_session(self, sid):
        self.q("UPDATE sessions SET ended=? WHERE id=? AND ended IS NULL", (time.time(), sid))

    def log_event(self, session_id, ev):
        self.q("INSERT INTO events(session_id,t,type,text,action,slide,source,latency,audio_s,infer_s) "
               "VALUES(?,?,?,?,?,?,?,?,?,?)",
               (session_id, time.time(), ev["type"], ev.get("text"), ev.get("action"), ev.get("slide"),
                ev.get("source"), ev.get("latency"), ev.get("audio_s"), ev.get("infer_s")))

    def sessions(self):
        return [self.session_stats(r) for r in self.rows("SELECT * FROM sessions ORDER BY started DESC")]

    def session(self, sid):
        r = self.rows("SELECT * FROM sessions WHERE id=?", (sid,))
        if not r:
            return None
        s = self.session_stats(r[0])
        s["events"] = self.rows("SELECT * FROM events WHERE session_id=? ORDER BY t", (sid,))
        return s

    def session_stats(self, s):
        ev = self.rows("SELECT * FROM events WHERE session_id=?", (s["id"],))
        voice = [e for e in ev if e["type"] == "command" and e["source"] == "voice"]
        lat = sorted(e["latency"] for e in voice if e["latency"] is not None)
        finals = [e for e in ev if e["type"] == "final" and e["audio_s"]]
        audio = sum(e["audio_s"] for e in finals)
        return {**s,
                "duration_s": ((s["ended"] or time.time()) - s["started"]) if s["started"] else None,
                "voice_commands": len(voice),
                "manual_commands": sum(e["type"] == "command" and e["source"] == "manual" for e in ev),
                "latency_p50": _pct(lat, 50), "latency_p95": _pct(lat, 95),
                "rtf": (sum(e["infer_s"] for e in finals) / audio) if audio else None,
                "feedback": bool(self.rows("SELECT 1 FROM feedback WHERE session_id=?", (s["id"],)))}

    # feedback / settings --------------------------------------------------
    def add_feedback(self, f):
        cols = ["code", "role", "ease", "responsiveness", "quality", "satisfaction",
                "useful", "confusing", "missing", "session_id"]
        return self.q(f"INSERT INTO feedback({','.join(cols)},created) VALUES({','.join('?' * len(cols))},?)",
                      (*[f.get(c) for c in cols], time.time())).lastrowid

    def feedback(self):
        return self.rows("SELECT * FROM feedback ORDER BY created")

    def settings(self):
        stored = {r["key"]: json.loads(r["value"]) for r in self.rows("SELECT * FROM settings")}
        return {**DEFAULT_SETTINGS, **stored}

    def save_settings(self, values):
        for k, v in values.items():
            self.q("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, json.dumps(v)))
        return self.settings()


def _pct(xs, p):
    if not xs:
        return None
    return xs[min(len(xs) - 1, round(p / 100 * (len(xs) - 1)))]
