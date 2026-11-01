"""Ponte audio browser <-> JACK, in un processo separato.

Il browser cattura la chitarra con la scheda audio del PC e la invia qui via
WebSocket (blocchi float32 mono little-endian); il suono in uscita dalla catena
torna indietro sulla stessa connessione.

Sta in un processo a sé perché la callback di JACK, scritta in Python, deve
rispondere ogni pochi millisecondi: nello stesso processo del server web
competerebbe per il GIL con le richieste HTTP e arriverebbe in ritardo (xrun).

Avvio: python3 -m alice.bridge   (porta ALICE_BRIDGE_PORT, default 8091)
Porte JACK: alice-bridge:src (verso la catena), alice-bridge:monitor (dalla catena).
L'Engine del backend le collega all'inizio e alla fine della catena.
"""
import asyncio
import json
import logging
import os
import threading
import time

import jack
import numpy as np
import websockets

from .dsp import Bridge

CLIENT_NAME = "alice-bridge"
SRC = f"{CLIENT_NAME}:src"
MONITOR = f"{CLIENT_NAME}:monitor"

log = logging.getLogger("alice.bridge")


class JackSide:
    def __init__(self):
        self.client = jack.Client(CLIENT_NAME, no_start_server=True)
        self.src = self.client.outports.register("src")
        self.mon = self.client.inports.register("monitor")
        self.bridge = Bridge(self.client.samplerate)
        self.frames = 0
        self.client.set_process_callback(self._process)
        self.client.activate()
        threading.Thread(target=self._measure_rate, daemon=True).start()

    def _process(self, frames):
        self.frames += frames
        self.bridge.jack_cycle(self.src.get_array(), self.mon.get_array())

    def _measure_rate(self):
        """Stima la velocità reale di JACK (campioni al secondo di orologio)."""
        last_t, last_f = time.monotonic(), self.frames
        while True:
            time.sleep(1.0)
            t, f = time.monotonic(), self.frames
            if f > last_f:
                b = self.bridge
                b.rate = 0.7 * b.rate + 0.3 * (f - last_f) / (t - last_t)
            last_t, last_f = t, f


async def serve(js: JackSide, port: int):
    bridge = js.bridge

    async def handler(ws):
        owner = object()
        bridge.start(owner)  # una nuova connessione sostituisce la precedente
        await ws.send(json.dumps({"type": "hello", "samplerate": js.client.samplerate}))
        log.info("browser collegato")
        try:
            async for msg in ws:
                if bridge.owner is not owner:
                    break
                if isinstance(msg, str):
                    d = json.loads(msg)
                    d.update(server_underruns=bridge.underruns, jack_rate=round(bridge.rate),
                             server_in=bridge.inp.available(), server_pending=len(bridge.pending))
                    log.info("stato: %s", json.dumps(d))
                    continue
                out = bridge.exchange(np.frombuffer(msg, dtype="<f4"))
                if len(out):
                    await ws.send(out.astype("<f4").tobytes())
        except websockets.ConnectionClosed:
            pass
        finally:
            bridge.stop(owner)
            log.info("browser scollegato")

    async with websockets.serve(handler, "0.0.0.0", port, max_size=2**20, compression=None):
        log.info("ponte audio in ascolto sulla porta %d", port)
        await asyncio.Future()


def main():
    logging.basicConfig(level=os.environ.get("ALICE_LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    js = JackSide()
    asyncio.run(serve(js, int(os.environ.get("ALICE_BRIDGE_PORT", 8091))))


if __name__ == "__main__":
    main()
