"""Experiment E1: mix recorded background noise into every clip at given SNRs.
  python eval/add_noise.py eval/data/manifest.csv classroom_noise.wav --snr 20 10 5
Writes eval/data/E1_snr<N>/... and adds those rows to the manifest.
"""
import argparse
import os

import numpy as np

from common import load_wav, read_manifest, save_wav, write_manifest


def mix(speech, noise, snr_db):
    noise = np.resize(noise, len(speech))  # loop the noise if it is shorter than the speech
    p_s, p_n = np.mean(speech ** 2), np.mean(noise ** 2)
    return speech + noise * np.sqrt(p_s / (p_n * 10 ** (snr_db / 10)))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("manifest")
    p.add_argument("noise")
    p.add_argument("--snr", type=float, nargs="+", default=[20, 10, 5])
    p.add_argument("--from-condition", default="baseline")
    a = p.parse_args()

    base = os.path.dirname(a.manifest)
    rows = read_manifest(a.manifest)
    noise = load_wav(a.noise)
    new = []
    for snr in a.snr:
        cond = f"E1_snr{snr:g}"
        for r in rows:
            if r["condition"] != a.from_condition:
                continue
            name = os.path.join(cond, os.path.basename(r["file"]))
            save_wav(os.path.join(base, name), mix(load_wav(os.path.join(base, r["file"])), noise, snr))
            new.append({**r, "file": name, "condition": cond})
    write_manifest(a.manifest, [r for r in rows if not r["condition"].startswith("E1_")] + new)
    print(f"added {len(new)} noisy clips")
