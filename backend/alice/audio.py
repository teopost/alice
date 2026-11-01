"""Client JACK del backend: carico DSP, xrun, render di prova e ponte audio col browser.

Porte del client "alice", collegate dall'Engine:
  test_src   (uscita)   -> inizio catena: file DI del render di prova
  bridge_src (uscita)   -> inizio catena: audio in arrivo dal browser
  monitor    (ingresso) <- fine catena

Render: fa passare un file DI nella catena e registra l'uscita.
Ponte: il browser cattura la chitarra (getUserMedia, driver del sistema operativo
del PC) e la invia via WebSocket; il suono elaborato torna al browser. Serve
quando la scheda audio non è collegata al container (es. sviluppo su WSL2).
"""
import threading
import time

import jack
import numpy as np

CLIENT_NAME = "alice"
TEST_SRC = f"{CLIENT_NAME}:test_src"
BRIDGE_SRC = f"{CLIENT_NAME}:bridge_src"
MONITOR = f"{CLIENT_NAME}:monitor"


class Ring:
    """Buffer circolare mono float32; se si riempie scarta i campioni più vecchi."""

    def __init__(self, size):
        self.buf = np.zeros(size, dtype="float32")
        self.size = size
        self.r = 0  # contatori assoluti
        self.w = 0
        self.lock = threading.Lock()

    def available(self):
        return self.w - self.r

    def clear(self):
        with self.lock:
            self.r = self.w = 0

    def write(self, data):
        n = len(data)
        if n == 0:
            return
        with self.lock:
            if n > self.size:
                data = data[-self.size:]
                n = self.size
            i = self.w % self.size
            first = min(n, self.size - i)
            self.buf[i:i + first] = data[:first]
            self.buf[:n - first] = data[first:]
            self.w += n
            if self.w - self.r > self.size:
                self.r = self.w - self.size

    def read_into(self, out):
        """Riempie `out` con i campioni disponibili; restituisce quanti ne ha letti."""
        with self.lock:
            n = min(len(out), self.w - self.r)
            i = self.r % self.size
            first = min(n, self.size - i)
            out[:first] = self.buf[i:i + first]
            out[first:n] = self.buf[:n - first]
            self.r += n
            return n

    def read_all(self):
        with self.lock:
            n = self.w - self.r
        out = np.empty(n, dtype="float32")
        n = self.read_into(out)
        return out[:n]

    def skip_to(self, keep):
        """Scarta i campioni più vecchi lasciandone `keep` (limita la latenza)."""
        with self.lock:
            if self.w - self.r > keep:
                self.r = self.w - keep


class Resampler:
    """Ricampionatore lineare a flusso continuo (passo variabile tra un blocco e l'altro)."""

    def __init__(self):
        self.pos = 0.0
        self.prev = np.zeros(1, dtype="float32")

    def process(self, x, step):
        """`step` = campioni di ingresso per ogni campione di uscita."""
        if len(x) == 0:
            return np.zeros(0, dtype="float32")
        buf = np.concatenate((self.prev, x))
        last = len(buf) - 1
        n = max(0, int(np.ceil((last - self.pos) / step)))
        idx = self.pos + step * np.arange(n)
        i = idx.astype(np.int64)
        f = (idx - i).astype("float32")
        out = buf[i] * (1.0 - f) + buf[np.minimum(i + 1, last)] * f
        self.pos = self.pos + step * n - len(x)
        self.prev = buf[-1:].copy()
        return out.astype("float32")


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class Bridge:
    """Ponte audio browser <-> JACK.

    Browser e JACK hanno orologi diversi: il driver dummy di JACK su WSL2, per
    esempio, gira circa il 9% più veloce del tempo reale, e anche con una scheda
    vera i due orologi non coincidono mai. Il ponte quindi ricampiona in entrata
    e in uscita con un rapporto pari alla velocità misurata di JACK, corretto da
    un regolatore che mantiene i buffer al livello obiettivo. Il browser riceve
    esattamente tanti campioni quanti ne invia.
    """
    PRIME = 256       # campioni accumulati prima che JACK inizi a leggere
    IN_TARGET = 384   # livello obiettivo del buffer verso JACK
    OUT_TARGET = 256  # livello obiettivo del buffer verso il browser
    MAX_FILL = 2048   # oltre questa soglia si scarta l'eccesso (limita la latenza)

    def __init__(self, samplerate, rate_fn):
        self.sr = samplerate
        self.rate_fn = rate_fn        # velocità reale di JACK (campioni/s)
        self.inp = Ring(samplerate)   # browser -> JACK
        self.out = Ring(samplerate)   # JACK -> browser
        self.active = False
        self.primed = False
        self.underruns = 0
        self.owner = None

    def start(self, owner):
        self.inp.clear()
        self.out.clear()
        self.rs_in = Resampler()
        self.rs_out = Resampler()
        self.pending = np.zeros(0, dtype="float32")
        self.primed = False
        self.underruns = 0
        self.owner = owner
        self.active = True

    def stop(self, owner):
        if self.owner is owner:
            self.active = False
            self.owner = None

    def exchange(self, x):
        """Riceve un blocco dal browser, restituisce un blocco della stessa lunghezza."""
        rho = self.rate_fn() / self.sr  # campioni JACK per campione del browser
        fill = self.inp.available()
        corr = _clamp(1 + 0.02 * (fill - self.IN_TARGET) / self.IN_TARGET, 0.98, 1.02)
        self.inp.write(self.rs_in.process(x, corr / rho))

        y = self.out.read_all()
        pend = len(self.pending)
        corr = _clamp(1 + 0.02 * (pend - self.OUT_TARGET) / self.OUT_TARGET, 0.98, 1.02)
        self.pending = np.concatenate((self.pending, self.rs_out.process(y, rho * corr)))
        if len(self.pending) > self.MAX_FILL:
            self.pending = self.pending[-self.OUT_TARGET:]
        n = len(x)
        send, self.pending = self.pending[:n], self.pending[n:]
        return send


class Audio:
    def __init__(self):
        self.client = jack.Client(CLIENT_NAME, no_start_server=True)
        self.src = self.client.outports.register("test_src")
        self.bsrc = self.client.outports.register("bridge_src")
        self.mon = self.client.inports.register("monitor")
        self.xruns = 0
        self._render = None
        self._render_lock = threading.Lock()
        self.frames = 0
        self.rate = float(self.client.samplerate)
        self.bridge = Bridge(self.client.samplerate, lambda: self.rate)
        threading.Thread(target=self._measure_rate, daemon=True).start()
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

    def _measure_rate(self):
        """Stima la velocità reale di JACK (campioni al secondo di orologio)."""
        last_t, last_f = time.monotonic(), self.frames
        while True:
            time.sleep(1.0)
            t, f = time.monotonic(), self.frames
            if f > last_f:
                measured = (f - last_f) / (t - last_t)
                self.rate = 0.7 * self.rate + 0.3 * measured
            last_t, last_f = t, f

    def _process(self, frames):
        self.frames += frames
        self._process_bridge(frames)
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

    def _process_bridge(self, frames):
        b = self.bridge
        out = self.bsrc.get_array()
        if not b.active:
            out.fill(0.0)
            return
        if not b.primed:
            if b.inp.available() >= Bridge.PRIME:
                b.primed = True
            else:
                out.fill(0.0)
        if b.primed:
            if b.inp.available() > Bridge.MAX_FILL:
                b.inp.skip_to(Bridge.PRIME)
            n = b.inp.read_into(out)
            if n < frames:
                out[n:] = 0.0
                b.underruns += 1
                b.primed = False
        b.out.write(self.mon.get_array().copy())

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
