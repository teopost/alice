"""Strutture audio senza dipendenze da JACK: buffer circolare, ricampionatore, ponte."""
import threading
import time

import numpy as np


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
        return out[:self.read_into(out)]

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
    vera i due orologi non coincidono mai. Il ponte ricampiona in entrata e in
    uscita con un rapporto pari alla velocità misurata di JACK, corretto da un
    regolatore che mantiene i buffer al livello obiettivo. Al browser vengono
    restituiti tanti campioni quanti ne ha inviati: se una volta mancano, il
    debito viene recuperato con i blocchi successivi.

    Thread: `exchange` gira nel loop del server WebSocket, `jack_cycle` nella
    callback di JACK; comunicano solo attraverso i due Ring.
    """
    IN_TARGET = 768   # livello obiettivo iniziale del buffer verso JACK (adattivo)
    IN_TARGET_MAX = 9600  # 200 ms: oltre non ha senso suonare
    OUT_TARGET = 512  # livello obiettivo del buffer verso il browser
    MAX_FILL = 4096   # oltre questa soglia (oltre l'obiettivo) si scarta l'eccesso

    def __init__(self, samplerate):
        self.sr = samplerate
        self.rate = float(samplerate)  # velocità reale di JACK (campioni/s), aggiornata da fuori
        self.inp = Ring(samplerate)    # browser -> JACK
        self.out = Ring(samplerate)    # JACK -> browser
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
        self.owed = 0
        self.in_target = self.IN_TARGET
        self.last_underruns = 0
        self.stable_since = time.monotonic()
        self.primed = False
        self.underruns = 0
        self.owner = owner
        self.active = True

    def stop(self, owner):
        if self.owner is owner:
            self.active = False
            self.owner = None

    # --- lato browser (loop asyncio) ---------------------------------------
    def exchange(self, x):
        """Riceve un blocco dal browser, restituisce il blocco da rimandare."""
        rho = self.rate / self.sr  # campioni JACK per campione del browser
        self._adapt()
        fill = self.inp.available()
        corr = _clamp(1 + 0.02 * (fill - self.in_target) / self.in_target, 0.98, 1.02)
        self.inp.write(self.rs_in.process(x, corr / rho))

        y = self.out.read_all()
        pend = len(self.pending)
        corr = _clamp(1 + 0.02 * (pend - self.OUT_TARGET) / self.OUT_TARGET, 0.98, 1.02)
        self.pending = np.concatenate((self.pending, self.rs_out.process(y, rho * corr)))
        if len(self.pending) > self.MAX_FILL:
            self.pending = self.pending[-self.OUT_TARGET:]
        self.owed = min(self.owed + len(x), self.MAX_FILL)
        # invia quanto dovuto; il regolatore sopra tiene una riserva di circa OUT_TARGET
        k = min(self.owed, len(self.pending))
        send, self.pending = self.pending[:k], self.pending[k:]
        self.owed -= k
        return send

    def _adapt(self):
        """Buffer adattivo: si allarga dopo un'interruzione, si restringe se stabile.

        Serve quando i pacchetti arrivano a raffiche (es. rete Windows <-> WSL2).
        """
        now = time.monotonic()
        if self.underruns != self.last_underruns:
            self.last_underruns = self.underruns
            self.in_target = min(int(self.in_target * 1.5), self.IN_TARGET_MAX)
            self.stable_since = now
        elif now - self.stable_since > 5 and self.in_target > self.IN_TARGET:
            self.in_target = max(self.IN_TARGET, int(self.in_target * 0.9))
            self.stable_since = now

    # --- lato JACK (callback in tempo reale) --------------------------------
    def jack_cycle(self, src_out, monitor_in):
        frames = len(src_out)
        if not self.active:
            src_out.fill(0.0)
            return
        if not self.primed and self.inp.available() >= self.in_target:
            self.primed = True
        if self.primed:
            if self.inp.available() > self.in_target + self.MAX_FILL:
                self.inp.skip_to(self.in_target)
            n = self.inp.read_into(src_out)
            if n < frames:
                src_out[n:] = 0.0
                self.underruns += 1
                self.primed = False
        else:
            src_out.fill(0.0)
        self.out.write(monitor_in.copy())
