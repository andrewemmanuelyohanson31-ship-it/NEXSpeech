import csv
import os
import re
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nex.asr import SR  # noqa: E402
from nex.commands import NUM  # noqa: E402

FIELDS = ["file", "reference", "expected", "condition", "speaker"]


def load_wav(path):
    """16-bit PCM WAV -> float32 mono at 16 kHz (downmix + linear resample if needed)."""
    with wave.open(path) as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"{path}: need 16-bit PCM WAV")
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        x = np.interp(np.arange(0, len(x), sr / SR), np.arange(len(x)), x).astype(np.float32)
    return x


def save_wav(path, x):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def read_manifest(path):
    with open(path, newline="", encoding="utf-8-sig") as f:  # -sig: Excel/PowerShell add a BOM
        return list(csv.DictReader(f))


def write_manifest(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def norm(text):
    """Lowercase, drop punctuation, number words -> digits, so "slide two" == "slide 2" for WER."""
    return " ".join(str(NUM.get(w, w)) for w in re.findall(r"[a-z0-9]+", text.lower()))
