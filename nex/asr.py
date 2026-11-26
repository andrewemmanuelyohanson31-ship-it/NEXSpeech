"""Local ASR (faster-whisper) + streaming segmenter that emits partial and final text."""
import os
import time

import numpy as np

SR = 16000
BLOCK_S = 0.25
PROMPT = ("next, lanjut, back, balik, previous, sebelumnya, slide dua, slide 3, "
          "slide pertama, slide terakhir, first slide, last slide, stop, berhenti, mulai")
NOISE_FLOOR = 0.003  # minimum RMS threshold so a dead-silent room doesn't make every click "speech"


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0


class Transcriber:
    """Wraps a local faster-whisper model. Model files are downloaded once, then run offline."""

    def __init__(self, model_size="small", language="id", device="cpu", compute_type="int8", prompt=PROMPT):
        from faster_whisper import WhisperModel  # heavy import, keep it out of tests that use a fake

        self.model_size, self.language, self.prompt = model_size, language, prompt
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type,
                                  cpu_threads=os.cpu_count() or 4)
        self(np.zeros(SR, dtype=np.float32))  # warm-up: first real call would otherwise be slow

    def __call__(self, audio):
        segments, _ = self.model.transcribe(
            audio, language=self.language or None, beam_size=1, initial_prompt=self.prompt,
            condition_on_previous_text=False, without_timestamps=True)
        # no_speech_prob filter drops Whisper's classic silence hallucinations ("Terima kasih.")
        return " ".join(s.text.strip() for s in segments if s.no_speech_prob < 0.6).strip()


class StreamingRecognizer:
    """Feed 0.25 s float32 blocks; get partial text every `chunk_s` of speech and a final text
    after `silence_s` of silence. Commands should only be acted on from finals."""

    def __init__(self, transcribe, chunk_s=1.0, silence_s=0.6, max_utt_s=8.0, min_utt_s=0.25, threshold=None):
        self.transcribe = transcribe
        self.chunk_s, self.silence_s, self.max_utt_s, self.min_utt_s = chunk_s, silence_s, max_utt_s, min_utt_s
        self.threshold = threshold
        self.partial_every = chunk_s
        self._calib = []
        self.reset()

    def reset(self):
        self.buf, self.prev = [], None
        self.silent = self.speech_s = self.since_partial = 0.0
        self.last_speech_t = None
        self.after_cut = False  # True while the current utterance began right after a forced max_utt_s cut

    def calibrated(self):
        return self.threshold is not None

    def feed(self, block, now=None):
        now = time.perf_counter() if now is None else now
        level = rms(block)
        if self.threshold is None:  # first 2 s: learn the room's noise level
            self._calib.append(level)
            if len(self._calib) >= int(2 / BLOCK_S):
                self.threshold = max(3 * float(np.median(self._calib)), NOISE_FLOOR)
            return []

        speaking = level > self.threshold
        if speaking:
            if not self.buf and self.prev is not None:
                self.buf.append(self.prev)  # pre-roll so the first phoneme isn't clipped
            self.speech_s += BLOCK_S
            self.silent = 0.0
            self.last_speech_t = now
        elif self.buf:
            self.silent += BLOCK_S
        else:
            self.after_cut = False  # a real pause happened, so the next utterance is a fresh one
        if self.buf or speaking:
            self.buf.append(block)
            self.since_partial += BLOCK_S
        self.prev = block

        if not self.buf:
            return []
        dur = len(self.buf) * BLOCK_S
        if self.silent >= self.silence_s or dur >= self.max_utt_s:
            return self._finish(forced=self.silent < self.silence_s)
        if self.since_partial >= self.partial_every:
            self.since_partial = 0.0
            t0 = time.perf_counter()
            text = self.transcribe(np.concatenate(self.buf))
            # adaptive throttle: on a slow CPU, space partials so they use <= ~50% of real time,
            # otherwise the audio queue backs up and every command gets later and later
            self.partial_every = max(self.chunk_s, 2 * (time.perf_counter() - t0))
            return [{"type": "partial", "text": text}] if text else []
        return []

    def flush(self):
        return self._finish() if self.buf else []

    def _finish(self, forced=False):
        audio, speech_s, last_speech_t = np.concatenate(self.buf), self.speech_s, self.last_speech_t
        after_cut = self.after_cut
        self.reset()
        # Commands come after a real pause. The piece that continues a forced cut ("...berikutnya.")
        # is the tail of a long sentence, so it gets flagged and never triggers an action.
        self.after_cut = forced
        if speech_s < self.min_utt_s:  # a cough or click: skip, Whisper would hallucinate on it
            return []
        t0 = time.perf_counter()
        text = self.transcribe(audio)
        infer_s = time.perf_counter() - t0
        if not text:
            return []
        return [{"type": "final", "text": text, "audio_s": len(audio) / SR, "infer_s": infer_s,
                 "rtf": infer_s / (len(audio) / SR), "speech_end_t": last_speech_t, "after_cut": after_cut}]
