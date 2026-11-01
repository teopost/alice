"""Stato della pedaliera e traduzione in comandi per mod-host.

Formato della pedaliera (JSON):

    {"name": "Clean", "chain": [ELEMENTO, ...]}

ELEMENTO è un blocco oppure un gruppo di rami in parallelo:

    {"id": "b1", "kind": "block", "model": "ts9", "enabled": true,
     "params": {"fslider2_": 0.6}, "file": null}

    {"id": "s1", "kind": "split", "lanes": [[ELEMENTO, ...], [ELEMENTO, ...]]}

Il routing è ricorsivo: lo split collega le stesse sorgenti all'inizio di ogni
ramo, e le uscite di tutti i rami vanno al blocco successivo. JACK somma i
segnali collegati alla stessa porta di ingresso, quindi il merge non richiede
un plugin. Un ramo vuoto lascia passare il segnale pulito, e un blocco spento
viene scavalcato nei collegamenti.
"""
import copy
import logging
import threading
from pathlib import Path

from .modhost import ModHost

log = logging.getLogger("alice.engine")


class BoardError(ValueError):
    pass


def iter_blocks(chain):
    for el in chain:
        if el.get("kind") == "split":
            for lane in el.get("lanes", []):
                yield from iter_blocks(lane)
        else:
            yield el


def find_block(chain, block_id):
    for b in iter_blocks(chain):
        if b["id"] == block_id:
            return b
    return None


class Engine:
    def __init__(self, modhost: ModHost, catalog, data_dir: Path, inputs, outputs):
        self.mh = modhost
        self.models = {m["id"]: m for m in catalog["models"]}
        self.file_kinds = None  # impostato da app
        self.data_dir = data_dir
        self.inputs = list(inputs)
        self.outputs = list(outputs)
        self.lock = threading.RLock()
        self.board = {"name": "Nuovo preset", "chain": []}
        self.applied = {}        # block_id -> {"inst", "model", "params", "enabled", "file"}
        self.connections = set()  # (src, dst)
        self._next_inst = 0

    # --- validazione ------------------------------------------------------
    def normalize(self, board):
        if not isinstance(board, dict) or not isinstance(board.get("chain"), list):
            raise BoardError("pedaliera non valida: serve un oggetto con 'chain'")
        seen = set()

        def norm_chain(chain, depth):
            out = []
            for el in chain:
                if not isinstance(el, dict) or not el.get("id"):
                    raise BoardError("ogni elemento deve avere un 'id'")
                if el["id"] in seen:
                    raise BoardError(f"id duplicato: {el['id']}")
                seen.add(el["id"])
                if el.get("kind") == "split":
                    if depth > 0:
                        raise BoardError("split annidati non supportati")
                    lanes = el.get("lanes")
                    if not isinstance(lanes, list) or len(lanes) < 2:
                        raise BoardError("uno split deve avere almeno due rami")
                    out.append({"id": el["id"], "kind": "split",
                                "lanes": [norm_chain(l, depth + 1) for l in lanes]})
                    continue
                model = self.models.get(el.get("model"))
                if model is None:
                    raise BoardError(f"modello sconosciuto: {el.get('model')}")
                params = {p["symbol"]: p["default"] for p in model["params"]}
                for k, v in (el.get("params") or {}).items():
                    if k in params:
                        params[k] = self._clamp(model, k, v)
                out.append({"id": el["id"], "kind": "block", "model": model["id"],
                            "enabled": bool(el.get("enabled", True)), "params": params,
                            "file": el.get("file") if model.get("file") else None})
            return out

        return {"name": str(board.get("name") or "Senza nome"), "chain": norm_chain(board["chain"], 0)}

    def _clamp(self, model, symbol, value):
        p = next(p for p in model["params"] if p["symbol"] == symbol)
        v = float(value)
        if p["min"] is not None:
            v = max(p["min"], v)
        if p["max"] is not None:
            v = min(p["max"], v)
        return v

    # --- routing ----------------------------------------------------------
    def _route(self, chain, sources, conns):
        for el in chain:
            if el["kind"] == "split":
                merged = []
                for lane in el["lanes"]:
                    merged += self._route(lane, sources, conns)
                sources = list(dict.fromkeys(merged))
            elif not el["enabled"]:
                # blocco spento: scavalcato nei collegamenti. Non ci si affida al bypass
                # dei plugin (con LSP Impulse Responses mod-host restituisce silenzio)
                continue
            else:
                inst = self.applied[el["id"]]["inst"]
                model = self.models[el["model"]]
                for s in sources:
                    for i in model["inputs"]:  # ingresso mono su tutte le porte (es. riverberi stereo)
                        conns.add((s, f"effect_{inst}:{i}"))
                sources = [f"effect_{inst}:{model['outputs'][0]}"]
        return sources

    def _compute_connections(self, chain):
        conns = set()
        tail = self._route(chain, self.inputs, conns)
        for s in tail:
            for o in self.outputs:
                conns.add((s, o))
        return conns

    def _rewire(self, chain):
        """Applica solo le differenze di collegamento rispetto allo stato attuale."""
        new_conns = self._compute_connections(chain)
        for c in new_conns - self.connections:
            self.mh.connect_ports(*c)
        for c in self.connections - new_conns:
            self.mh.disconnect_ports(*c)
        self.connections = new_conns

    # --- applicazione -----------------------------------------------------
    def file_path(self, model, name):
        if not name:
            return None
        kind = model["file"]["kind"]
        return self.data_dir / self.file_kinds[kind]["dir"] / name

    def _sync_block(self, block):
        """Porta l'istanza mod-host allo stato del blocco (la crea se serve)."""
        model = self.models[block["model"]]
        cur = self.applied.get(block["id"])
        if cur and cur["model"] != block["model"]:
            self.mh.remove(cur["inst"])
            cur = None
        if cur is None:
            inst = self._next_inst
            self._next_inst += 1
            self.mh.add(model["uri"], inst)
            cur = {"inst": inst, "model": model["id"], "params": {}, "enabled": True, "file": None}
            self.applied[block["id"]] = cur
        for sym, val in block["params"].items():
            if cur["params"].get(sym) != val:
                self.mh.param_set(cur["inst"], sym, val)
                cur["params"][sym] = val
        if cur["enabled"] != block["enabled"]:
            self.mh.bypass(cur["inst"], not block["enabled"])
            cur["enabled"] = block["enabled"]
        if model.get("file") and cur["file"] != block["file"]:
            path = self.file_path(model, block["file"])
            if path is not None and path.is_file():
                self.mh.patch_set(cur["inst"], model["file"]["property"], str(path))
            elif path is not None:
                log.warning("file non trovato: %s", path)
            cur["file"] = block["file"]

    def apply(self, board):
        board = self.normalize(board)
        with self.lock:
            wanted = {b["id"] for b in iter_blocks(board["chain"])}
            # prima stacca i blocchi rimossi, poi rimuovi le istanze
            for bid in [b for b in self.applied if b not in wanted]:
                inst = self.applied.pop(bid)["inst"]
                self.connections = {c for c in self.connections
                                    if not (c[0].startswith(f"effect_{inst}:") or c[1].startswith(f"effect_{inst}:"))}
                self.mh.remove(inst)
            for b in iter_blocks(board["chain"]):
                self._sync_block(b)
            self._rewire(board["chain"])
            self.board = board
            return copy.deepcopy(board)

    def update_block(self, block_id, params=None, enabled=None, file=None):
        with self.lock:
            block = find_block(self.board["chain"], block_id)
            if block is None:
                raise BoardError(f"blocco inesistente: {block_id}")
            model = self.models[block["model"]]
            for k, v in (params or {}).items():
                if k in block["params"]:
                    block["params"][k] = self._clamp(model, k, v)
            if enabled is not None:
                block["enabled"] = bool(enabled)
            if file is not None and model.get("file"):
                block["file"] = file or None
            self._sync_block(block)
            if enabled is not None:
                self._rewire(self.board["chain"])
            return copy.deepcopy(block)

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.board)

    def reset(self):
        with self.lock:
            self.mh.remove_all()
            self.applied.clear()
            self.connections.clear()
