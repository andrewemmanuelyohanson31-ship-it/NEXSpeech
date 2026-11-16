import numpy as np

from nex.asr import BLOCK_S, SR, StreamingRecognizer

N = int(SR * BLOCK_S)
rng = np.random.default_rng(0)


def quiet(n):
    return [rng.normal(0, 0.001, N).astype(np.float32) for _ in range(n)]


def loud(n):
    t = np.arange(N) / SR
    return [(0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32) for _ in range(n)]


class FakeASR:
    def __init__(self, text="lanjut"):
        self.text, self.calls = text, []

    def __call__(self, audio):
        self.calls.append(len(audio) / SR)
        return self.text


def run(blocks, **kw):
    rec = StreamingRecognizer(FakeASR(), **kw)
    events = [ev for b in blocks for ev in rec.feed(b)]
    return rec, events


def test_calibrates_then_finalizes_after_silence():
    rec, ev = run(quiet(8) + loud(2) + quiet(4))
    assert rec.calibrated()
    finals = [e for e in ev if e["type"] == "final"]
    assert len(finals) == 1 and finals[0]["text"] == "lanjut"
    assert finals[0]["audio_s"] >= 0.5  # includes pre-roll + speech + trailing silence
    assert finals[0]["rtf"] >= 0


def test_partials_while_speaking_long():
    rec, ev = run(quiet(8) + loud(12) + quiet(4), chunk_s=1.0)
    kinds = [e["type"] for e in ev]
    assert kinds.count("partial") >= 2  # text shows up before the speaker stops
    assert kinds[-1] == "final"


def test_max_utterance_forces_final():
    rec, ev = run(quiet(8) + loud(40), max_utt_s=4.0)
    assert sum(e["type"] == "final" for e in ev) >= 2


def test_tail_after_forced_cut_is_flagged():
    # 10 s nonstop: cut at 4 s, cut again at 8 s, then the 2 s tail ends with a real pause
    rec, ev = run(quiet(8) + loud(40) + quiet(4), max_utt_s=4.0)
    finals = [e for e in ev if e["type"] == "final"]
    assert [f["after_cut"] for f in finals] == [False, True, True]


def test_real_pause_clears_the_cut_flag():
    # cut at 4 s, then a pause, then a fresh short command: that one must count
    rec, ev = run(quiet(8) + loud(16) + quiet(4) + loud(2) + quiet(4), max_utt_s=4.0)
    finals = [e for e in ev if e["type"] == "final"]
    assert finals[-1]["after_cut"] is False


def test_silence_alone_never_transcribes():
    rec, ev = run(quiet(40))
    assert ev == [] and rec.transcribe.calls == []


def test_blip_shorter_than_min_is_dropped():
    rec, ev = run(quiet(8) + loud(1) + quiet(4), min_utt_s=0.5)
    assert not any(e["type"] == "final" for e in ev)
