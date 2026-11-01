"""API HTTP/WebSocket di Alice e server dell'interfaccia web."""
import asyncio
import io
import json
import logging
import os
import re
import subprocess
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import soundfile as sf
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .audio import MONITOR, TEST_SRC, Audio
from .catalog import FILE_KINDS, load_catalog
from .engine import BoardError, Engine
from .modhost import ModHost, ModHostError

logging.basicConfig(level=os.environ.get("ALICE_LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("alice")

DATA = Path(os.environ.get("ALICE_DATA", "/data"))
WEB = Path(os.environ.get("ALICE_WEB", Path(__file__).resolve().parents[2] / "web"))
INPUTS = [p for p in os.environ.get("ALICE_INPUTS", "system:capture_1").split(",") if p]
OUTPUTS = [p for p in os.environ.get("ALICE_OUTPUTS", "system:playback_1,system:playback_2").split(",") if p]
STATE_FILE = DATA / "state" / "current.json"
PRESETS = DATA / "presets"
SAFE_NAME = re.compile(r"^[\w\-. ()&+]{1,100}$")


class Hub:
    """Clienti WebSocket connessi (tablet, PC...) a cui inviare gli aggiornamenti."""

    def __init__(self):
        self.clients = set()

    async def send(self, msg):
        dead = []
        for ws in self.clients:
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)


hub = Hub()
state = {}


def default_board():
    def first(kind):
        files = list_files(kind)
        return files[0]["name"] if files else None

    return {"name": "Alice", "chain": [
        {"id": "gate1", "kind": "block", "model": "gate"},
        {"id": "drive1", "kind": "block", "model": "ts9", "enabled": False},
        {"id": "amp1", "kind": "block", "model": "nam", "file": first("nam")},
        {"id": "cab1", "kind": "block", "model": "ir", "file": first("ir")},
        {"id": "rev1", "kind": "block", "model": "room"},
    ]}


def save_state(board):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(board, indent=2))
    tmp.replace(STATE_FILE)


def kind_dir(kind):
    if kind not in FILE_KINDS:
        raise HTTPException(404, f"tipo di file sconosciuto: {kind}")
    d = DATA / FILE_KINDS[kind]["dir"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_files(kind):
    d = kind_dir(kind)
    exts = FILE_KINDS[kind]["ext"]
    return [{"name": f.name, "size": f.stat().st_size}
            for f in sorted(d.iterdir(), key=lambda f: f.name.lower())
            if f.is_file() and f.suffix.lower() in exts]


def check_name(name):
    if not SAFE_NAME.match(name) or name.startswith("."):
        raise HTTPException(400, f"nome non valido: {name!r}")
    return name


async def status_loop():
    audio: Audio = state["audio"]
    while True:
        await asyncio.sleep(0.5)
        if hub.clients:
            await hub.send({"type": "status", "dsp": round(audio.cpu_load(), 1), "xruns": audio.xruns,
                            "samplerate": audio.samplerate, "buffer": audio.blocksize})


@asynccontextmanager
async def lifespan(app):
    for d in ("state", "presets"):
        (DATA / d).mkdir(parents=True, exist_ok=True)
    catalog = await run_in_threadpool(load_catalog)
    mh = ModHost(port=int(os.environ.get("MOD_HOST_PORT", 5555)),
                 feedback_port=int(os.environ.get("MOD_HOST_FEEDBACK_PORT", 5556)))
    await run_in_threadpool(mh.connect)
    audio = Audio()
    engine = Engine(mh, catalog, DATA, INPUTS + [TEST_SRC], OUTPUTS + [MONITOR])
    engine.file_kinds = FILE_KINDS
    await run_in_threadpool(engine.reset)
    board = None
    if STATE_FILE.is_file():
        try:
            board = json.loads(STATE_FILE.read_text())
        except ValueError:
            log.warning("stato salvato illeggibile, uso la pedaliera di default")
    try:
        board = await run_in_threadpool(engine.apply, board or default_board())
    except (BoardError, ModHostError) as e:
        log.warning("stato salvato non applicabile (%s), uso la pedaliera di default", e)
        board = await run_in_threadpool(engine.apply, default_board())
    save_state(board)
    state.update(catalog=catalog, engine=engine, audio=audio)
    task = asyncio.create_task(status_loop())
    log.info("Alice pronta: %d Hz, buffer %d", audio.samplerate, audio.blocksize)
    yield
    task.cancel()


app = FastAPI(title="Alice", lifespan=lifespan)


@app.exception_handler(BoardError)
async def board_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(ModHostError)
async def modhost_error(request, exc):
    return JSONResponse({"detail": f"errore del motore audio: {exc}"}, status_code=500)


def origin(request: Request):
    return request.headers.get("x-client-id")


# --- catalogo e pedaliera ---------------------------------------------------
@app.get("/api/catalog")
def get_catalog():
    return state["catalog"]


@app.get("/api/board")
def get_board():
    return state["engine"].snapshot()


@app.put("/api/board")
async def put_board(request: Request):
    board = await run_in_threadpool(state["engine"].apply, await request.json())
    save_state(board)
    await hub.send({"type": "board", "board": board, "origin": origin(request)})
    return board


@app.patch("/api/blocks/{block_id}")
async def patch_block(block_id: str, request: Request):
    body = await request.json()
    engine = state["engine"]
    block = await run_in_threadpool(engine.update_block, block_id, body.get("params"),
                                    body.get("enabled"), body.get("file"))
    save_state(engine.snapshot())
    await hub.send({"type": "block", "block": block, "origin": origin(request)})
    return block


# --- file: modelli NAM, IR, DI ------------------------------------------------
@app.get("/api/files/{kind}")
def get_files(kind: str):
    return list_files(kind)


@app.put("/api/files/{kind}/{name}")
async def upload_file(kind: str, name: str, request: Request):
    """Carica un file: il corpo della richiesta è il contenuto del file."""
    d = kind_dir(kind)
    name = check_name(name)
    if Path(name).suffix.lower() not in FILE_KINDS[kind]["ext"]:
        raise HTTPException(400, f"estensione non ammessa per {kind}: {FILE_KINDS[kind]['ext']}")
    data = await request.body()
    if len(data) > 200 * 1024 * 1024:
        raise HTTPException(413, "file troppo grande")
    if kind == "nam":
        try:
            model = json.loads(data)
            assert "architecture" in model and "weights" in model
        except Exception:
            raise HTTPException(400, "il file non sembra un modello NAM valido")
        (d / name).write_bytes(data)
    else:
        # IR e DI: converte in WAV mono alla samplerate di JACK
        sr = state["audio"].samplerate
        with tempfile.NamedTemporaryFile(suffix=Path(name).suffix) as tmp:
            tmp.write(data)
            tmp.flush()
            r = subprocess.run(["sox", tmp.name, "-c", "1", "-r", str(sr), "-b", "24", str(d / name)],
                               capture_output=True, text=True)
        if r.returncode != 0:
            raise HTTPException(400, f"file audio non valido: {r.stderr.strip()}")
    return {"name": name}


@app.delete("/api/files/{kind}/{name}")
def delete_file(kind: str, name: str):
    p = kind_dir(kind) / check_name(name)
    if not p.is_file():
        raise HTTPException(404, "file inesistente")
    p.unlink()
    return {"ok": True}


# --- preset -----------------------------------------------------------------
@app.get("/api/presets")
def get_presets():
    return [{"name": p.stem} for p in sorted(PRESETS.glob("*.json"), key=lambda p: p.stem.lower())]


@app.put("/api/presets/{name}")
async def save_preset(name: str, request: Request):
    check_name(name)
    engine = state["engine"]
    board = engine.snapshot()
    board["name"] = name
    board = await run_in_threadpool(engine.apply, board)
    (PRESETS / f"{name}.json").write_text(json.dumps(board, indent=2))
    save_state(board)
    await hub.send({"type": "board", "board": board, "origin": origin(request)})
    return board


@app.post("/api/presets/{name}/load")
async def load_preset(name: str, request: Request):
    p = PRESETS / f"{check_name(name)}.json"
    if not p.is_file():
        raise HTTPException(404, "preset inesistente")
    board = await run_in_threadpool(state["engine"].apply, json.loads(p.read_text()))
    save_state(board)
    await hub.send({"type": "board", "board": board, "origin": origin(request)})
    return board


@app.delete("/api/presets/{name}")
def delete_preset(name: str):
    p = PRESETS / f"{check_name(name)}.json"
    if not p.is_file():
        raise HTTPException(404, "preset inesistente")
    p.unlink()
    return {"ok": True}


# --- render di prova ----------------------------------------------------------
@app.post("/api/render")
async def render(di: str):
    audio: Audio = state["audio"]
    path = kind_dir("di") / check_name(di)
    if not path.is_file():
        raise HTTPException(404, "file DI inesistente")
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    if sr != audio.samplerate:
        raise HTTPException(400, f"il DI è a {sr} Hz, JACK a {audio.samplerate} Hz: ricaricalo")
    out = await run_in_threadpool(audio.render, data[:, 0])
    buf = io.BytesIO()
    sf.write(buf, out, sr, format="WAV", subtype="PCM_16")
    return Response(buf.getvalue(), media_type="audio/wav")


# --- WebSocket ----------------------------------------------------------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    hub.clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # nessun comando dal client per ora
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(ws)


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB), name="web")
