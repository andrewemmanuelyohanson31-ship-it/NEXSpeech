"""Try NEX in the terminal: talk, then see the text, the slide action, and how long it took.
No keys are pressed, so no slides are needed.

  python -m nex.try_mic                       # default microphone, tiny model
  python -m nex.try_mic --list                # list microphones
  python -m nex.try_mic --device 3 --model base --language ""   # "" = auto-detect language
  python -m nex.try_mic --wav clip.wav        # replay a 16 kHz mono WAV at real-time speed
"""
import argparse
import queue
import shutil
import time
import wave

import numpy as np

from .asr import BLOCK_S, SR, StreamingRecognizer, Transcriber
from .commands import parse

N = int(SR * BLOCK_S)


class WavSource:
    """Plays a WAV into the pipeline block by block, at the speed a microphone would deliver it."""

    def __init__(self, path):
        with wave.open(path) as w:
            if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (SR, 1, 2):
                raise SystemExit(f"{path}: need 16 kHz mono 16-bit WAV (eval/record.py makes these)")
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        lead = [np.zeros(N, np.float32)] * 8  # 2 s of silence first, for calibration
        tail = [np.zeros(N, np.float32)] * 6
        self.blocks = lead + [x[i:i + N] for i in range(0, len(x) - N + 1, N)] + tail

    def __enter__(self):
        self.t0, self.i = time.perf_counter(), 0
        return self

    def __exit__(self, *a):
        pass

    def read(self, timeout=0.5):
        if self.i >= len(self.blocks):
            raise StopIteration
        time.sleep(max(0.0, self.t0 + (self.i + 1) * BLOCK_S - time.perf_counter()))
        self.i += 1
        return self.blocks[self.i - 1]


def describe(ev):
    if ev.get("after_cut"):
        return "none (tail of a long sentence cut at 8 s, not after a real pause)"
    a = parse(ev["text"])
    if a:
        return {"next": "NEXT slide", "prev": "PREVIOUS slide", "last": "LAST slide (needs the slide count)",
                "pause": "PAUSE listening", "resume": "RESUME listening"}.get(a[0]) or f"GO TO slide {a[1]}"
    return "none (normal speech, not a command on its own)"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--list", action="store_true", help="list microphones and exit")
    p.add_argument("--device", type=int, default=None)
    p.add_argument("--model", default="tiny", choices=["tiny", "base", "small", "medium"])
    p.add_argument("--language", default="id", help='"id", "en", or "" for auto-detect')
    p.add_argument("--chunk-s", type=float, default=1.0)
    p.add_argument("--silence-s", type=float, default=0.6)
    p.add_argument("--wav", help="replay this file instead of the microphone")
    a = p.parse_args()

    if a.list:
        from .audio import list_devices

        for d in list_devices():
            print(f"{d['id']:>3}  {d['name']}{'   <- default' if d['default'] else ''}")
        return

    if a.wav:
        source = WavSource(a.wav)
    else:
        from .audio import Mic

        source = Mic(a.device)  # open the mic first so a bad --device fails before the slow model load
    print(f"Loading Whisper '{a.model}' (first time downloads it)...", flush=True)
    t0 = time.perf_counter()
    rec = StreamingRecognizer(Transcriber(a.model, language=a.language or None),
                              chunk_s=a.chunk_s, silence_s=a.silence_s)
    print(f"Loaded in {time.perf_counter() - t0:.1f} s.")
    print("Stay QUIET for 2 seconds while NEX measures the room noise...", flush=True)

    latencies = []
    width = max(20, shutil.get_terminal_size().columns - 8)  # a wrapped line can't be overwritten with \r

    def show(ev):
        if ev["type"] == "partial":
            print(f"\r  ... {ev['text'][-width:]:<{width}}", end="", flush=True)
            return
        total = time.perf_counter() - ev["speech_end_t"]
        latencies.append(total)
        print(f"\r{' ' * (width + 6)}\r", end="")
        print(f'  YOU SAID : "{ev["text"]}"')
        print(f"  ACTION   : {describe(ev)}")
        print(f"  TIME     : {total:.2f} s after you stopped talking "
              f"(= {total - ev['infer_s']:.2f} s waiting for silence + {ev['infer_s']:.2f} s recognition)"
              f"  | {ev['audio_s']:.1f} s of audio, RTF {ev['rtf']:.2f}\n", flush=True)

    try:
        with source:
            while True:
                try:
                    block = source.read()
                except queue.Empty:
                    continue
                except StopIteration:
                    break
                was = rec.calibrated()
                for ev in rec.feed(block):
                    show(ev)
                if not was and rec.calibrated():
                    print(f"Listening (noise threshold {rec.threshold:.4f}). Say \"lanjut\", \"balik\", "
                          "\"slide tiga\"... pause briefly after each. Ctrl+C to quit.\n", flush=True)
            for ev in rec.flush():
                show(ev)
    except KeyboardInterrupt:
        print()
    if latencies:
        print(f"{len(latencies)} utterances | latency avg {np.mean(latencies):.2f} s, "
              f"best {min(latencies):.2f} s, worst {max(latencies):.2f} s")


if __name__ == "__main__":
    main()
