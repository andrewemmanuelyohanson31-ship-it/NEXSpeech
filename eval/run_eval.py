"""Technical evaluation: run every clip through the SAME streaming pipeline as the live app.

  python eval/run_eval.py eval/data/manifest.csv --model small
Reports per condition: WER (S, D, I, N), command accuracy, false triggers, latency P50/P95, RTF.
Writes eval/results/<model>_clips.csv (per clip, use it for the error-analysis table).
"""
import argparse
import csv
import os
import time
from collections import defaultdict

import jiwer
import numpy as np

from common import load_wav, norm, read_manifest
from nex.asr import BLOCK_S, NOISE_FLOOR, SR, StreamingRecognizer, Transcriber, rms
from nex.commands import parse


def action_str(a):
    return "none" if a is None else (a[0] if a[0] != "goto" else f"goto:{a[1]}")


def run_clip(transcriber, audio, silence_s=0.6, chunk_s=1.0):
    n = int(SR * BLOCK_S)
    blocks = [audio[i:i + n] for i in range(0, len(audio) - n + 1, n)]
    levels = [rms(b) for b in blocks]
    # clips have no 2 s lead-in, so estimate the noise level from the quietest blocks instead
    thr = max(3 * float(np.percentile(levels, 10)), NOISE_FLOOR) if levels else NOISE_FLOOR
    rec = StreamingRecognizer(transcriber, chunk_s=chunk_s, silence_s=silence_s, threshold=thr)
    tail = [np.zeros(n, dtype=np.float32)] * int(np.ceil(silence_s / BLOCK_S) + 1)  # let the last word finish
    # Replay on a simulated live clock: block i arrives at (i+1)*BLOCK_S, and the single-threaded loop
    # can't take the next block until it finishes processing. Latency therefore includes the backlog
    # that partial transcriptions cause, exactly as in the live app.
    finals, partials, fired, clock, proc = [], 0, [], 0.0, 0.0
    for i, b in enumerate(blocks + tail):
        arrive = (i + 1) * BLOCK_S
        clock = max(clock, arrive)
        t0 = time.perf_counter()
        events = rec.feed(b, now=arrive)
        dt = time.perf_counter() - t0
        clock, proc = clock + dt, proc + dt
        for ev in events:
            if ev["type"] == "partial":
                partials += 1
                continue
            finals.append(ev)
            a = None if ev["after_cut"] else parse(ev["text"])  # same rule as the live engine
            if a:
                fired.append((a, clock - ev["speech_end_t"]))
    audio_s = len(blocks + tail) * BLOCK_S
    return {"hyp": " ".join(f["text"] for f in finals), "partials": partials,
            "actions": [action_str(a) for a, _ in fired],
            "latency": fired[0][1] if fired else None,  # end of speech -> action ready
            "infer_s": proc, "audio_s": audio_s}


def pct(xs, p):
    return float(np.percentile(xs, p)) if xs else float("nan")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("manifest")
    p.add_argument("--model", default="small")
    p.add_argument("--language", default="id")
    p.add_argument("--chunk-s", type=float, default=1.0)
    p.add_argument("--silence-s", type=float, default=0.6)
    a = p.parse_args()

    base = os.path.dirname(a.manifest)
    t = Transcriber(a.model, language=a.language or None)
    by_cond = defaultdict(list)
    out_rows = []
    for r in read_manifest(a.manifest):
        res = run_clip(t, load_wav(os.path.join(base, r["file"])), a.silence_s, a.chunk_s)
        exp = r["expected"] or "none"
        got = res["actions"][0] if res["actions"] else "none"
        clip = jiwer.process_words(norm(r["reference"]) or "-", norm(res["hyp"]))
        row = {**r, **res, "got": got, "correct": got == exp, "actions": " ".join(res["actions"]),
               # per-clip error counts for the error-analysis table (brief section 14)
               "wer": round(clip.wer, 3), "S": clip.substitutions, "D": clip.deletions, "I": clip.insertions}
        by_cond[r["condition"]].append(row)
        out_rows.append(row)
        print(f"{r['condition']:<12} {exp:<8} -> {got:<8} | {r['reference'][:40]!r} => {res['hyp'][:40]!r}")

    print(f"\nmodel={a.model} language={a.language or 'auto'} chunk={a.chunk_s}s silence={a.silence_s}s")
    print(f"{'condition':<12}{'WER':>7}{'S':>5}{'D':>5}{'I':>5}{'N':>6}{'cmd acc':>9}"
          f"{'false/10m':>10}{'lat P50':>9}{'lat P95':>9}{'RTF':>7}")
    for cond, rows in sorted(by_cond.items()):
        refs = [norm(x["reference"]) or "-" for x in rows]
        hyps = [norm(x["hyp"]) for x in rows]
        m = jiwer.process_words(refs, hyps)
        n = m.hits + m.substitutions + m.deletions
        cmds = [x for x in rows if x["expected"] not in ("", "none")]
        talk = [x for x in rows if x["expected"] in ("", "none")]
        false = sum(len(x["actions"].split()) for x in talk)
        talk_min = sum(x["audio_s"] for x in talk) / 60
        lat = [x["latency"] for x in cmds if x["latency"] is not None]
        rtf = sum(x["infer_s"] for x in rows) / sum(x["audio_s"] for x in rows)
        acc = f"{sum(x['correct'] for x in cmds) / len(cmds):.0%}" if cmds else "-"
        fpm = f"{false / talk_min * 10:.1f}" if talk_min else "-"
        print(f"{cond:<12}{m.wer:>7.1%}{m.substitutions:>5}{m.deletions:>5}{m.insertions:>5}{n:>6}"
              f"{acc:>9}{fpm:>10}{pct(lat, 50):>8.2f}s{pct(lat, 95):>8.2f}s{rtf:>7.2f}")

    os.makedirs(os.path.join(os.path.dirname(__file__), "results"), exist_ok=True)
    out = os.path.join(os.path.dirname(__file__), "results", f"{a.model}_clips.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(out_rows[0].keys()), extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)
    print(f"\nper-clip results -> {out}")
