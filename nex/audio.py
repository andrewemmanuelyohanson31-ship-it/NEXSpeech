"""Microphone capture as a stream of 0.25 s, 16 kHz mono float32 blocks."""
import queue

from .asr import BLOCK_S, SR


def list_devices():
    import sounddevice as sd

    return [{"id": i, "name": d["name"], "default": i == sd.default.device[0]}
            for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] > 0]


class Mic:
    def __init__(self, device=None):
        import sounddevice as sd

        self.q = queue.Queue()
        self.stream = sd.InputStream(samplerate=SR, channels=1, dtype="float32", device=device,
                                     blocksize=int(SR * BLOCK_S), callback=self._cb)

    def _cb(self, indata, frames, t, status):
        self.q.put(indata[:, 0].copy())

    def __enter__(self):
        self.stream.start()
        return self

    def __exit__(self, *exc):
        self.stream.stop()
        self.stream.close()

    def read(self, timeout=0.5):
        return self.q.get(timeout=timeout)
