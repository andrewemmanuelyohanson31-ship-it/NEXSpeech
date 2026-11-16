"""Record a test set from a prompt file.

prompts.txt lines are  expected|text , e.g.  next|lanjut   goto:3|slide tiga   none|<2-minute talk text>
  python eval/record.py eval/prompts.txt --speaker U1 --condition baseline --seconds 3
Appends to eval/data/manifest.csv. Record with consent; clips are evaluation data only.
"""
import argparse
import os
import time

import sounddevice as sd

from common import FIELDS, SR, read_manifest, save_wav, write_manifest

p = argparse.ArgumentParser()
p.add_argument("prompts")
p.add_argument("--speaker", required=True)
p.add_argument("--condition", default="baseline")
p.add_argument("--seconds", type=float, default=3.0, help="per prompt; use ~130 for the no-command talk")
p.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "data"))
a = p.parse_args()

manifest = os.path.join(a.out, "manifest.csv")
rows = read_manifest(manifest) if os.path.exists(manifest) else []
prompts = [line.strip().split("|", 1) for line in open(a.prompts, encoding="utf-8") if "|" in line]
for i, (expected, text) in enumerate(prompts, 1):
    input(f"\n[{i}/{len(prompts)}] Say: \"{text}\"   (Enter to start, {a.seconds:.0f} s)")
    audio = sd.rec(int(a.seconds * SR), samplerate=SR, channels=1, dtype="float32")
    sd.wait()
    name = f"{a.condition}/{a.speaker}_{i:03d}_{int(time.time())}.wav"
    save_wav(os.path.join(a.out, name), audio[:, 0])
    rows.append(dict(zip(FIELDS, [name, text, expected, a.condition, a.speaker])))
    write_manifest(manifest, rows)  # save after each clip so a crash loses nothing
print(f"\nSaved {len(prompts)} clips -> {manifest}")
