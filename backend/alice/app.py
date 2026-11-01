"""API HTTP/WebSocket di Alice e server dell'interfaccia web."""
import asyncio
import io
import json
import logging
import os
import re
import subprocess
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path

import soundfile as sf
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .audio import MONITOR, TEST_SRC, Audio
from .bridge import MONITOR as BRIDGE_MONITOR
from .bridge import SRC as BRIDGE_SRC
from .catalog import FILE_KINDS, load_catalog
from .engine import BoardError, Engine
from .modhost import ModHost, ModHostError
from .tone3000 import T3KError, Tone3000

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
T3K_LIBRARY = DATA / "state" / "tone3000-library.json"   # file installati da TONE3000
t3k = Tone3000(DATA / "state" / "tone3000.json", os.environ.get("ALICE_T3K_KEY"))


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
    engine = Engine(mh, catalog, DATA, INPUTS + [TEST_SRC, BRIDGE_SRC], OUTPUTS + [MONITOR, BRIDGE_MONITOR])
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


@app.exception_handler(T3KError)
async def t3k_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=exc.status if 400 <= exc.status < 600 else 500)


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


# --- TONE3000 -------------------------------------------------------------------
def t3k_library():
    try:
        return json.loads(T3K_LIBRARY.read_text())
    except (OSError, ValueError):
        return {}


def safe_filename(text, ext):
    """Nome di file accettato da check_name, ricavato da titolo e nome del modello."""
    name = re.sub(r"[^\w\-. ()&+]+", " ", text, flags=re.UNICODE)
    name = re.sub(r"\s+", " ", name).strip(" .-")[: 100 - len(ext)] or "modello"
    return name + ext


@app.get("/api/t3k/status")
def t3k_status():
    return t3k.status()


@app.put("/api/t3k/key")
async def t3k_set_key(request: Request):
    t3k.set_client_id((await request.json()).get("key", ""))
    return t3k.status()


@app.post("/api/t3k/authorize")
async def t3k_authorize(request: Request):
    """URL di accesso a TONE3000. Il ritorno arriva a /t3k/callback sullo stesso indirizzo
    da cui è aperta l'interfaccia (localhost è sempre accettato da TONE3000; un indirizzo
    di rete va registrato sulla chiave)."""
    body = await request.json()
    origin = str(body.get("origin") or "").rstrip("/")
    if not re.match(r"^https?://[\w.\-\[\]:]+$", origin):
        raise HTTPException(400, "origine non valida")
    extra = {}
    if body.get("prompt") == "select_tone":
        extra = {"gears": body.get("gears") or "amp_amp-cab_pedal_outboard_cab", "format": "nam", "preview": "true"}
        if body.get("format") == "ir":
            extra = {"format": "ir", "preview": "true"}
    url = await run_in_threadpool(t3k.authorize_url, origin + "/t3k/callback", body.get("prompt"), extra)
    return {"url": url}


CALLBACK_PAGE = """<!doctype html><html lang="it"><meta charset="utf-8"><title>TONE3000 · Alice</title>
<style>body{background:#0b0c0e;color:#eceef1;font:15px system-ui,sans-serif;display:grid;place-items:center;height:100vh;margin:0}
div{text-align:center;max-width:420px;padding:20px}a{color:#7cf0b6}</style>
<div><h2>%s</h2><p>%s</p><p><a href="/">Torna ad Alice</a></p></div>
<script>
const msg = %s;
try { new BroadcastChannel("alice_t3k").postMessage(msg); } catch (e) {}
if (window.opener) { try { window.opener.postMessage(msg, location.origin); } catch (e) {} setTimeout(() => window.close(), 400); }
else { setTimeout(() => location.replace("/#store"), 1200); }
</script></html>"""


@app.get("/t3k/callback", response_class=HTMLResponse)
async def t3k_callback(state: str = "", code: str = "", error: str = "", tone_id: str = "", canceled: str = ""):
    import html
    msg = {"type": "alice_t3k", "ok": False, "tone_id": tone_id or None}
    try:
        if error and not code:
            raise T3KError(f"TONE3000 ha restituito un errore: {error}", 400)
        await run_in_threadpool(t3k.complete, state, code)
        msg["ok"] = True
        msg["canceled"] = canceled == "true"
        title, text = "Account collegato", "Puoi chiudere questa finestra e tornare ad Alice."
    except T3KError as e:
        msg["error"] = str(e)
        title, text = "Accesso non riuscito", html.escape(str(e))
    return CALLBACK_PAGE % (title, text, json.dumps(msg))


@app.post("/api/t3k/logout")
def t3k_logout():
    t3k.logout()
    return t3k.status()


@app.get("/api/t3k/feed/{kind}")
async def t3k_feed(kind: str, gear: str = "", page: int = 1, query: str = ""):
    return await run_in_threadpool(t3k.feed, kind, gear or None, page, query or None)


@app.get("/api/t3k/tones/{tone_id}")
async def t3k_tone(tone_id: int):
    res = await run_in_threadpool(t3k.tone, tone_id)
    lib = t3k_library()
    installed = {v["model_id"]: k for k, v in lib.items()}
    for m in res["models"]:
        m["installed"] = installed.get(m["id"])
    return res


@app.post("/api/t3k/install")
async def t3k_install(request: Request):
    """Scarica un modello di TONE3000 tra i file di Alice (NAM in models/, IR in irs/)."""
    body = await request.json()
    tone_id, model_id = int(body["tone_id"]), int(body["model_id"])
    tone = await run_in_threadpool(t3k.get, f"/api/v1/tones/{tone_id}")
    model = await run_in_threadpool(t3k.get, f"/api/v1/models/{model_id}")
    if model.get("tone_id") != tone_id:
        raise HTTPException(400, "il modello non appartiene a questo tone")
    is_ir = tone.get("format") == "ir"
    if tone.get("format") not in ("nam", "ir"):
        raise HTTPException(400, f"formato non supportato da Alice: {tone.get('format')}")
    kind = "ir" if is_ir else "nam"
    title = tone.get("title") or f"tone {tone_id}"
    mname = model.get("name") or str(model_id)
    label = title if mname.lower() in title.lower() else f"{title} - {mname}"
    name = safe_filename(label, ".wav" if is_ir else ".nam")
    d = kind_dir(kind)
    if (d / name).exists() and t3k_library().get(name, {}).get("model_id") != model_id:
        name = safe_filename(f"{label} {model_id}", ".wav" if is_ir else ".nam")
    data = await run_in_threadpool(t3k.download, model["model_url"])
    if is_ir:
        sr = state["audio"].samplerate
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            tmp.write(data)
            tmp.flush()
            r = subprocess.run(["sox", tmp.name, "-c", "1", "-r", str(sr), "-b", "24", str(d / name)],
                               capture_output=True, text=True)
        if r.returncode != 0:
            raise HTTPException(400, f"IR non valida: {r.stderr.strip()}")
    else:
        try:
            nam = json.loads(data)
            assert "architecture" in nam and "weights" in nam
        except Exception:
            raise HTTPException(400, "il file scaricato non è un modello NAM valido")
        (d / name).write_bytes(data)
    lib = t3k_library()
    user = tone.get("user") or {}
    lib[name] = {"kind": kind, "tone_id": tone_id, "model_id": model_id, "title": title, "model": mname,
                 "creator": user.get("display_name") or user.get("username"), "url": tone.get("url"),
                 "image": (tone.get("images") or [None])[0], "gear": tone.get("gear"),
                 "license": tone.get("license"), "size": model.get("size"),
                 "architecture": model.get("architecture_version"), "installed_at": time.time()}
    T3K_LIBRARY.parent.mkdir(parents=True, exist_ok=True)
    T3K_LIBRARY.write_text(json.dumps(lib, indent=2))
    log.info("TONE3000: installato %s (%s)", name, kind)
    return {"name": name, "kind": kind}


@app.get("/api/t3k/library")
def t3k_library_list():
    """File installati da TONE3000 ancora presenti su disco."""
    lib = t3k_library()
    return [dict(v, name=k) for k, v in lib.items()
            if (kind_dir(v["kind"]) / k).is_file()]


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
