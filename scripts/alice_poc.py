#!/usr/bin/env python3
"""Proof of concept di Alice.

Carica un profilo NAM in mod-host, fa passare un file DI attraverso la catena
via JACK, salva il risultato e riporta il carico DSP medio/massimo.

Uso (dentro il container engine):
    python3 /opt/alice/scripts/alice_poc.py --model /data/models/x.nam \
        --di /data/di/test.wav --out /data/renders/out.wav
"""
import argparse
import socket
import sys
import threading
import time

import jack
import numpy as np
import soundfile as sf

NAM_URI = "http://github.com/mikeoliphant/neural-amp-modeler-lv2"
NAM_MODEL_PROP = NAM_URI + "#model"


class ModHost:
    """Client minimale del protocollo testuale di mod-host."""

    def __init__(self, host="127.0.0.1", port=5555, feedback_port=5556):
        # mod-host serve un client alla volta e, se avviato con -f, dopo aver
        # accettato il socket comandi resta in attesa sul socket di feedback:
        # vanno aperti entrambi, in quest'ordine.
        self.sock = socket.create_connection((host, port), timeout=10)
        self.fb = socket.create_connection((host, feedback_port), timeout=10)
        self.feedback = []
        threading.Thread(target=self._drain_feedback, daemon=True).start()

    def _drain_feedback(self):
        """Legge i messaggi di feedback (param_set, output_set...) senza bloccare mod-host."""
        self.fb.settimeout(None)
        buf = b""
        while True:
            chunk = self.fb.recv(4096)
            if not chunk:
                return
            buf += chunk
            *msgs, buf = buf.split(b"\0")
            self.feedback.extend(m.decode(errors="replace") for m in msgs if m)

    def cmd(self, line):
        self.sock.sendall(line.encode() + b"\0")
        data = b""
        while not data.endswith(b"\0"):
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            data += chunk
        resp = data.rstrip(b"\0").decode()
        # risposta: "resp <codice> [valore]"; codice < 0 = errore
        code = int(resp.split()[1]) if resp.startswith("resp") else -1
        if code < 0:
            raise RuntimeError(f"mod-host: '{line}' -> {resp}")
        return resp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="file .nam")
    ap.add_argument("--di", required=True, help="file WAV mono del segnale DI")
    ap.add_argument("--out", required=True, help="file WAV di uscita")
    ap.add_argument("--instance", type=int, default=0)
    args = ap.parse_args()

    di, sr = sf.read(args.di, dtype="float32", always_2d=True)
    di = di[:, 0]

    host = ModHost()
    inst = args.instance
    try:
        host.cmd(f"remove {inst}")
    except RuntimeError:
        pass
    host.cmd(f"add {NAM_URI} {inst}")
    host.cmd(f'patch_set {inst} {NAM_MODEL_PROP} "{args.model}"')
    time.sleep(1.0)  # il modello viene caricato in modo asincrono (LV2 worker)

    client = jack.Client("alice-poc", no_start_server=True)
    if client.samplerate != sr:
        sys.exit(f"Sample rate DI {sr} != JACK {client.samplerate}: converti il file")
    out_port = client.outports.register("to_chain")
    in_port = client.inports.register("from_chain")

    recorded = np.zeros(len(di) + client.samplerate, dtype="float32")  # +1s di coda
    pos = {"play": 0, "rec": 0}
    done = threading.Event()

    @client.set_process_callback
    def process(frames):
        p = pos["play"]
        chunk = di[p:p + frames]
        buf = out_port.get_array()
        buf[:len(chunk)] = chunk
        buf[len(chunk):] = 0.0
        pos["play"] = p + frames

        r = pos["rec"]
        n = min(frames, len(recorded) - r)
        if n > 0:
            recorded[r:r + n] = in_port.get_array()[:n]
            pos["rec"] = r + n
        else:
            done.set()

    loads = []
    blocksize = client.blocksize
    with client:
        client.connect(out_port, f"effect_{inst}:input")
        client.connect(f"effect_{inst}:output", in_port)
        while not done.wait(0.1):
            loads.append(client.cpu_load())

    sf.write(args.out, recorded, sr)
    host.cmd(f"remove {inst}")

    peak = float(np.max(np.abs(recorded)))
    print(f"buffer JACK      : {blocksize} campioni @ {sr} Hz "
          f"({1000 * blocksize / sr:.2f} ms)")
    print(f"carico DSP medio : {np.mean(loads):.1f} %")
    print(f"carico DSP max   : {np.max(loads):.1f} %")
    print(f"picco uscita     : {peak:.3f}" + ("  <-- SILENZIO: modello non caricato?" if peak < 1e-4 else ""))
    print(f"salvato          : {args.out}")


if __name__ == "__main__":
    main()
