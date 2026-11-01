"""Client JACK del backend: carico DSP, xrun e render di prova.

Le porte "alice:test_src" (inizio catena) e "alice:monitor" (fine catena) sono
sempre collegate dall'Engine. Il render fa passare un file DI nella catena e
registra l'uscita: serve per ascoltare il suono quando non c'è una scheda audio
(sviluppo su PC/WSL2 con driver dummy).
"""
import threading

import jack
import numpy as np

CLIENT_NAME = "alice"
TEST_SRC = f"{CLIENT_NAME}:test_src"
MONITOR = f"{CLIENT_NAME}:monitor"


class Audio:
    def __init__(self):
        self.client = jack.Client(CLIENT_NAME, no_start_server=True)
        self.src = self.client.outports.register("test_src")
        self.mon = self.client.inports.register("monitor")
        self.xruns = 0
        self._render = None
        self._render_lock = threading.Lock()
        self.client.set_process_callback(self._process)
        self.client.set_xrun_callback(self._xrun)
        self.client.activate()

    @property
    def samplerate(self):
        return self.client.samplerate

    @property
    def blocksize(self):
        return self.client.blocksize

    def cpu_load(self):
        return self.client.cpu_load()

    def _xrun(self, delay):
        self.xruns += 1

    def _process(self, frames):
        r = self._render
        out = self.src.get_array()
        if r is None:
            out.fill(0.0)
            return
        mon = self.mon.get_array()
        pos = r["pos"]
        chunk = r["di"][pos:pos + frames]
        out[:len(chunk)] = chunk
        out[len(chunk):] = 0.0
        n = min(frames, len(r["rec"]) - pos)
        if n > 0:
            r["rec"][pos:pos + n] = mon[:n]
        r["pos"] = pos + frames
        if r["pos"] >= len(r["rec"]):
            self._render = None
            r["done"].set()

    def render(self, di, tail_seconds=2.0):
        """Fa passare `di` (mono float32, alla samplerate di JACK) nella catena."""
        with self._render_lock:
            total = len(di) + int(tail_seconds * self.samplerate)
            r = {"di": di.astype("float32"), "rec": np.zeros(total, dtype="float32"),
                 "pos": 0, "done": threading.Event()}
            self._render = r
            if not r["done"].wait(timeout=total / self.samplerate * 3 + 5):
                self._render = None
                raise TimeoutError("render non completato")
            return r["rec"]
