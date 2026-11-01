#!/usr/bin/env python3
"""Genera modelli NAM WaveNet con pesi casuali (solo per test di caricamento e carico CPU).

Non suonano come un ampli: servono a misurare le prestazioni senza installare PyTorch.
Uso: python3 make_test_nam.py OUT_DIR
"""
import json
import random
import sys
from pathlib import Path

DIL = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]
ARCHS = {  # (canali layer1, canali layer2) come nel trainer ufficiale
    "standard": (16, 8),
    "lite": (12, 6),
    "feather": (8, 4),
}


def layer_cfg(inp, ch, head, head_bias):
    return {"input_size": inp, "condition_size": 1, "head_size": head, "channels": ch,
            "kernel_size": 3, "dilations": DIL, "activation": "Tanh", "gated": False,
            "head_bias": head_bias}


def n_weights(l):
    ch, k, cond = l["channels"], l["kernel_size"], l["condition_size"]
    n = ch * l["input_size"]                      # rechannel
    n += len(l["dilations"]) * (ch * ch * k + ch  # conv dilatata + bias
                                + ch * cond       # input mixin
                                + ch * ch + ch)   # 1x1 + bias
    n += l["head_size"] * ch + (l["head_size"] if l["head_bias"] else 0)  # head rechannel
    return n


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(42)
    for name, (c1, c2) in ARCHS.items():
        layers = [layer_cfg(1, c1, c2, False), layer_cfg(c1, c2, 1, True)]
        total = sum(n_weights(l) for l in layers) + 1  # + head_scale
        weights = [rnd.gauss(0, 0.05) for _ in range(total - 1)] + [0.02]
        model = {"version": "0.5.4", "architecture": "WaveNet",
                 "config": {"layers": layers, "head": None, "head_scale": 0.02},
                 "metadata": {"name": f"alice-test-{name}", "modeled_by": "alice (random weights)"},
                 "weights": weights, "sample_rate": 48000}
        p = out / f"test-{name}.nam"
        p.write_text(json.dumps(model))
        print(p, total, "pesi")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
