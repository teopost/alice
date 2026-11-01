// Alice: interfaccia web a blocchi (JavaScript puro, nessuna dipendenza esterna:
// deve funzionare anche offline sulla pedaliera).

const MIN_SLOTS = 8;
const clientId = Math.random().toString(36).slice(2);
const $ = (sel) => document.querySelector(sel);

const S = {
  catalog: null,
  models: {},
  cats: {},
  board: { name: "", chain: [] },
  selected: null,          // {type: "block", id} | {type: "slot", index}
  pickerCat: "drive",
  files: { nam: [], ir: [], di: [] },
  presets: [],
  draggingKnob: false,
};

// ---------------------------------------------------------------- icone
const ICONS = {
  dynamics: '<path d="M3 12h3l2-6 3 12 3-9 2 3h5" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>',
  wah: '<path d="M5 18l3-11h8l3 11z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M8 13h8" stroke="currentColor" stroke-width="2"/>',
  drive: '<path d="M13 2L5 14h6l-1 8 8-12h-6z" fill="currentColor"/>',
  amp: '<rect x="3" y="6" width="18" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="8" cy="12" r="1.6" fill="currentColor"/><circle cx="12" cy="12" r="1.6" fill="currentColor"/><circle cx="16" cy="12" r="1.6" fill="currentColor"/>',
  cab: '<rect x="4" y="3" width="16" height="18" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="4.5" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="1.3" fill="currentColor"/>',
  eq: '<path d="M6 4v16M12 4v16M18 4v16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><rect x="4" y="13" width="4" height="3" rx="1" fill="currentColor"/><rect x="10" y="7" width="4" height="3" rx="1" fill="currentColor"/><rect x="16" y="11" width="4" height="3" rx="1" fill="currentColor"/>',
  modulation: '<path d="M2 12c2.5-6 5-6 7.5 0s5 6 7.5 0 3.5-4 5-2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  delay: '<circle cx="5" cy="12" r="3" fill="currentColor"/><circle cx="12.5" cy="12" r="2.3" fill="currentColor" opacity=".7"/><circle cx="19" cy="12" r="1.6" fill="currentColor" opacity=".45"/>',
  reverb: '<path d="M4 18a8 8 0 0 1 16 0M7.5 18a4.5 4.5 0 0 1 9 0" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="18" r="1.4" fill="currentColor"/>',
};
const icon = (cat) => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[cat] || ""}</svg>`;

// ---------------------------------------------------------------- API
async function api(method, path, body, raw = false) {
  const opts = { method, headers: { "X-Client-Id": clientId } };
  if (body instanceof Blob) {
    opts.body = body;
  } else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch { /* risposta non JSON */ }
    throw new Error(msg);
  }
  return raw ? res : res.json();
}

function toast(msg, isError = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show" + (isError ? " error" : "");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.className = "toast"), isError ? 5000 : 2200);
}

async function guarded(fn) {
  try { return await fn(); } catch (e) { toast(e.message, true); }
}

// ---------------------------------------------------------------- modello dati
const newId = (prefix = "b") => prefix + Math.random().toString(36).slice(2, 8);

function findBlock(id, chain = S.board.chain) {
  for (const el of chain) {
    if (el.kind === "split") {
      for (const lane of el.lanes) {
        const b = findBlock(id, lane);
        if (b) return b;
      }
    } else if (el.id === id) {
      return el;
    }
  }
  return null;
}

async function putBoard(board) {
  S.board = await api("PUT", "/api/board", board);
  render();
}

function cloneBoard() {
  return JSON.parse(JSON.stringify(S.board));
}

// ---------------------------------------------------------------- valori dei parametri
const log10 = Math.log10;

function dbRange(p) {
  const lo = p.min > 0 ? 20 * log10(p.min) : (p.min_db ?? -60);
  return [lo, 20 * log10(p.max)];
}

// scala logaritmica anche quando il minimo è 0 (es. tempi di attacco/rilascio)
const logLo = (p) => (p.min > 0 ? p.min : p.max / 1000);

function toNorm(p, v) {
  let n;
  if (p.display === "db") {
    const [lo, hi] = dbRange(p);
    const db = v > 0 ? 20 * log10(v) : lo;
    n = (db - lo) / (hi - lo);
  } else if (p.log && p.max > 0) {
    const lo = logLo(p);
    n = v <= lo ? 0 : (log10(v) - log10(lo)) / (log10(p.max) - log10(lo));
  } else {
    n = (v - p.min) / (p.max - p.min);
  }
  return Math.min(1, Math.max(0, n));
}

function fromNorm(p, n) {
  n = Math.min(1, Math.max(0, n));
  let v;
  if (p.display === "db") {
    const [lo, hi] = dbRange(p);
    const db = lo + n * (hi - lo);
    v = n === 0 && p.min <= 0 ? 0 : Math.pow(10, db / 20);
  } else if (p.log && p.max > 0) {
    const lo = logLo(p);
    v = n === 0 ? p.min : Math.pow(10, log10(lo) + n * (log10(p.max) - log10(lo)));
  } else {
    v = p.min + n * (p.max - p.min);
  }
  if (p.integer) v = Math.round(v);
  return Math.min(p.max, Math.max(p.min, v));
}

function formatValue(p, v) {
  if (p.options) {
    const o = p.options.find((o) => o.value === v);
    if (o) return o.label;
  }
  if (p.display === "db") return v <= 0 ? "-∞ dB" : `${(20 * log10(v)).toFixed(1)} dB`;
  if (p.display === "pct") return `${Math.round(((v - p.min) / (p.max - p.min)) * 100)}%`;
  if (p.integer) return String(Math.round(v));
  const a = Math.abs(v);
  return v.toFixed(a >= 100 ? 0 : a >= 10 ? 1 : 2);
}

// invio dei parametri raggruppato (un PATCH ogni ~40 ms durante il trascinamento)
const pending = new Map();
function sendParam(blockId, symbol, value) {
  const b = findBlock(blockId);
  if (b) b.params[symbol] = value;
  if (!pending.has(blockId)) {
    pending.set(blockId, {});
    setTimeout(() => {
      const params = pending.get(blockId);
      pending.delete(blockId);
      guarded(() => api("PATCH", `/api/blocks/${blockId}`, { params }));
    }, 40);
  }
  pending.get(blockId)[symbol] = value;
}

// ---------------------------------------------------------------- percorso del segnale
function render() {
  // la selezione potrebbe riferirsi a un blocco che non esiste più
  if (S.selected?.type === "block" && !findBlock(S.selected.id) &&
      !S.board.chain.some((e) => e.id === S.selected.id)) {
    S.selected = null;
  }
  $("#presetName").value = S.board.name;
  renderPath();
  renderEditor();
}

function renderPath() {
  const path = $("#path");
  path.innerHTML = "";
  const chain = S.board.chain;
  const n = Math.max(MIN_SLOTS, chain.length + 1);

  const io = (label) => Object.assign(document.createElement("div"), { className: "io", textContent: label });
  const wire = () => Object.assign(document.createElement("div"), { className: "wire" });

  path.append(io("IN"), wire());
  for (let i = 0; i < n; i++) {
    const el = chain[i];
    const slot = document.createElement("div");
    slot.className = "slot";
    slot.dataset.index = String(Math.min(i, chain.length));
    const tile = document.createElement("div");
    tile.className = "tile";
    const name = document.createElement("div");
    name.className = "name";
    slot.append(tile, name);

    if (!el) {
      slot.classList.add("empty");
      if (S.selected?.type === "slot" && i === chain.length) slot.classList.add("selected");
      tile.title = "Aggiungi un blocco";
      tile.onclick = () => select({ type: "slot", index: chain.length });
    } else if (el.kind === "split") {
      slot.classList.add("split");
      tile.textContent = `${el.lanes.length} rami`;
      name.textContent = "Parallelo";
      if (S.selected?.id === el.id) slot.classList.add("selected");
      tile.onclick = () => select({ type: "block", id: el.id });
    } else {
      const m = S.models[el.model];
      const cat = S.cats[m.category];
      slot.classList.add("block");
      slot.style.setProperty("--c", cat.color);
      if (!el.enabled) slot.classList.add("bypassed");
      if (S.selected?.id === el.id) slot.classList.add("selected");
      tile.innerHTML = icon(m.category) + '<span class="led"></span>' +
        (m.file && !el.file ? '<span class="file-warn" title="Nessun file caricato">!</span>' : "");
      tile.title = `${m.name} - clic: modifica, doppio clic: on/off`;
      name.textContent = el.file ? el.file.replace(/\.(nam|wav)$/i, "") : m.name;
      tile.onclick = () => select({ type: "block", id: el.id });
      tile.ondblclick = () => toggleBlock(el.id);
      makeDraggable(slot, tile, el.id);
    }
    makeDropTarget(slot);
    path.append(slot, wire());
  }
  path.append(io("OUT"));
}

function select(sel) {
  S.selected = sel;
  render();
}

// trascinamento dei blocchi per riordinarli
let dragId = null;
function makeDraggable(slot, tile, id) {
  tile.draggable = true;
  tile.addEventListener("dragstart", (e) => {
    dragId = id;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", id);
    requestAnimationFrame(() => slot.classList.add("dragging"));
  });
  tile.addEventListener("dragend", () => {
    dragId = null;
    slot.classList.remove("dragging");
  });
}

function makeDropTarget(slot) {
  slot.addEventListener("dragover", (e) => {
    if (!dragId) return;
    e.preventDefault();
    slot.classList.add("drop-target");
  });
  slot.addEventListener("dragleave", () => slot.classList.remove("drop-target"));
  slot.addEventListener("drop", (e) => {
    e.preventDefault();
    slot.classList.remove("drop-target");
    if (dragId) moveBlock(dragId, Number(slot.dataset.index));
  });
}

function moveBlock(id, target) {
  const b = cloneBoard();
  const from = b.chain.findIndex((e) => e.id === id);
  if (from < 0) return;
  const [el] = b.chain.splice(from, 1);
  if (target > from) target -= 1;
  target = Math.max(0, Math.min(b.chain.length, target));
  if (target === from) return;
  b.chain.splice(target, 0, el);
  guarded(() => putBoard(b));
}

function addBlock(modelId, index) {
  const b = cloneBoard();
  const block = { id: newId(), kind: "block", model: modelId, enabled: true, params: {} };
  const m = S.models[modelId];
  if (m.file && S.files[m.file.kind].length) block.file = S.files[m.file.kind][0].name;
  b.chain.splice(index, 0, block);
  S.selected = { type: "block", id: block.id };
  guarded(() => putBoard(b));
}

function deleteBlock(id) {
  const b = cloneBoard();
  const i = b.chain.findIndex((e) => e.id === id);
  if (i < 0) return;
  b.chain.splice(i, 1);
  S.selected = { type: "slot", index: Math.min(i, b.chain.length) };
  guarded(() => putBoard(b));
}

function changeModel(id, modelId) {
  const b = cloneBoard();
  const i = b.chain.findIndex((e) => e.id === id);
  const m = S.models[modelId];
  b.chain[i] = { id, kind: "block", model: modelId, enabled: b.chain[i].enabled, params: {},
                 file: m.file && S.files[m.file.kind].length ? S.files[m.file.kind][0].name : null };
  guarded(() => putBoard(b));
}

async function toggleBlock(id) {
  const b = findBlock(id);
  if (!b) return;
  b.enabled = !b.enabled;
  render();
  await guarded(() => api("PATCH", `/api/blocks/${id}`, { enabled: b.enabled }));
}

// ---------------------------------------------------------------- pannello editor
function renderEditor() {
  const ed = $("#editor");
  ed.innerHTML = "";
  ed.style.removeProperty("--c");
  const sel = S.selected;
  if (!sel) {
    ed.innerHTML = '<div class="empty-hint">Seleziona un blocco per modificarlo, oppure uno slot vuoto per aggiungerne uno.</div>';
    return;
  }
  if (sel.type === "slot") return renderPicker(ed, sel.index);
  const split = S.board.chain.find((e) => e.id === sel.id && e.kind === "split");
  if (split) {
    ed.innerHTML = '<div class="empty-hint">Blocchi in parallelo: la modifica dall\'interfaccia arriverà presto.</div>';
    return;
  }
  renderBlockEditor(ed, findBlock(sel.id));
}

function renderPicker(ed, index) {
  const wrap = document.createElement("div");
  wrap.className = "picker";
  const cats = document.createElement("div");
  cats.className = "cats";
  for (const c of S.catalog.categories) {
    if (!S.catalog.models.some((m) => m.category === c.id)) continue;
    const b = document.createElement("button");
    b.className = "cat" + (c.id === S.pickerCat ? " active" : "");
    b.style.setProperty("--c", c.color);
    b.innerHTML = `<span class="dot"></span>${c.name}`;
    b.onclick = () => { S.pickerCat = c.id; renderEditor(); };
    cats.append(b);
  }
  const models = document.createElement("div");
  models.className = "models";
  const cat = S.cats[S.pickerCat];
  for (const m of S.catalog.models.filter((m) => m.category === S.pickerCat)) {
    const b = document.createElement("button");
    b.className = "model";
    b.style.setProperty("--c", cat.color);
    b.innerHTML = `<span class="mi">${icon(m.category)}</span><span>${m.name}</span>`;
    b.onclick = () => addBlock(m.id, index);
    models.append(b);
  }
  wrap.append(cats, models);
  ed.append(wrap);
}

function renderBlockEditor(ed, block) {
  const m = S.models[block.model];
  const cat = S.cats[m.category];
  ed.style.setProperty("--c", cat.color);

  const head = document.createElement("div");
  head.className = "editor-head";
  const modelSel = document.createElement("select");
  modelSel.title = "Cambia modello";
  for (const mm of S.catalog.models.filter((x) => x.category === m.category)) {
    modelSel.add(new Option(mm.name, mm.id, false, mm.id === m.id));
  }
  modelSel.onchange = () => changeModel(block.id, modelSel.value);

  const onBtn = button(block.enabled ? "ON" : "OFF", "btn " + (block.enabled ? "on" : "off"), () => toggleBlock(block.id));
  onBtn.title = "Attiva / bypass";
  const idx = S.board.chain.findIndex((e) => e.id === block.id);
  const left = button("◀", "btn ghost", () => moveBlock(block.id, idx - 1));
  const right = button("▶", "btn ghost", () => moveBlock(block.id, idx + 2));
  left.title = "Sposta a sinistra";
  right.title = "Sposta a destra";
  left.disabled = idx <= 0;
  right.disabled = idx >= S.board.chain.length - 1;
  const del = button("Elimina", "btn ghost danger", () => deleteBlock(block.id));

  head.innerHTML = `<span class="swatch"></span><h2>${cat.name}</h2>`;
  head.append(modelSel, onBtn, Object.assign(document.createElement("span"), { className: "spacer" }), left, right, del);
  ed.append(head);

  if (m.file) ed.append(fileRow(block, m));

  const params = document.createElement("div");
  params.className = "params";
  for (const p of m.params) params.append(paramControl(block, p));
  ed.append(params);
}

function button(text, cls, onclick) {
  const b = document.createElement("button");
  b.className = cls;
  b.textContent = text;
  b.onclick = onclick;
  return b;
}

function fileRow(block, m) {
  const row = document.createElement("div");
  row.className = "filerow";
  const kind = m.file.kind;
  row.innerHTML = `<span class="label">${m.file.label}</span>`;
  const sel = document.createElement("select");
  sel.add(new Option("— nessuno —", ""));
  for (const f of S.files[kind]) sel.add(new Option(f.name, f.name, false, f.name === block.file));
  sel.onchange = () => setBlockFile(block.id, sel.value);
  const up = document.createElement("label");
  up.className = "btn ghost";
  up.textContent = "Carica file…";
  const input = Object.assign(document.createElement("input"), { type: "file", hidden: true, accept: kind === "nam" ? ".nam" : ".wav" });
  input.onchange = async () => {
    const f = input.files[0];
    if (!f) return;
    const res = await guarded(() => api("PUT", `/api/files/${kind}/${encodeURIComponent(f.name)}`, f));
    if (res) {
      toast(`Caricato ${res.name}`);
      await loadFiles(kind);
      await setBlockFile(block.id, res.name);
    }
  };
  up.append(input);
  row.append(sel, up);
  if (kind === "nam") {
    const hint = document.createElement("span");
    hint.className = "hint";
    hint.innerHTML = 'Profili gratuiti su <a href="https://www.tone3000.com" target="_blank" rel="noopener" style="color:inherit">tone3000.com</a>';
    row.append(hint);
  }
  return row;
}

async function setBlockFile(id, name) {
  const b = findBlock(id);
  b.file = name || null;
  render();
  await guarded(() => api("PATCH", `/api/blocks/${id}`, { file: name || "" }));
}

function paramControl(block, p) {
  const wrap = document.createElement("div");
  wrap.className = "param";
  const label = Object.assign(document.createElement("div"), { className: "plabel", textContent: p.label, title: p.label });
  const value = Object.assign(document.createElement("div"), { className: "pvalue" });
  const v = block.params[p.symbol] ?? p.default;

  if (p.options && p.options.length) {
    const sel = document.createElement("select");
    for (const o of p.options) sel.add(new Option(o.label, o.value, false, o.value === v));
    sel.onchange = () => sendParam(block.id, p.symbol, Number(sel.value));
    wrap.append(label, sel);
    return wrap;
  }
  if (p.toggled) {
    const sw = document.createElement("button");
    sw.className = "switch" + (v > 0 ? " on" : "");
    sw.onclick = () => {
      const nv = block.params[p.symbol] > 0 ? p.min : p.max;
      sw.classList.toggle("on", nv > 0);
      sendParam(block.id, p.symbol, nv);
    };
    wrap.append(label, sw);
    return wrap;
  }
  const knob = makeKnob(p, v, (nv) => {
    value.textContent = formatValue(p, nv);
    sendParam(block.id, p.symbol, nv);
  });
  value.textContent = formatValue(p, v);
  wrap.append(knob, label, value);
  return wrap;
}

// manopola SVG: trascina in verticale (Shift = fine), rotella, doppio clic = default
function makeKnob(p, initial, onChange) {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 64 64");
  svg.classList.add("knob");
  const START = 135, SWEEP = 270, R = 26;
  const pt = (deg, r) => {
    const a = (deg * Math.PI) / 180;
    return [32 + r * Math.cos(a), 32 + r * Math.sin(a)];
  };
  const arc = (from, to) => {
    const [x1, y1] = pt(from, R), [x2, y2] = pt(to, R);
    return `M${x1} ${y1} A${R} ${R} 0 ${to - from > 180 ? 1 : 0} 1 ${x2} ${y2}`;
  };
  const mk = (tag, attrs) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    svg.append(e);
    return e;
  };
  mk("path", { d: arc(START, START + SWEEP), class: "track", "stroke-width": 5, fill: "none", "stroke-linecap": "round" });
  const fill = mk("path", { class: "fill", "stroke-width": 5, fill: "none", "stroke-linecap": "round" });
  mk("circle", { cx: 32, cy: 32, r: 17, class: "cap", "stroke-width": 2 });
  const pointer = mk("line", { class: "pointer", "stroke-width": 3, "stroke-linecap": "round" });

  let norm = toNorm(p, initial);
  const draw = () => {
    const deg = START + norm * SWEEP;
    fill.setAttribute("d", norm > 0.001 ? arc(START, deg) : "");
    const [x1, y1] = pt(deg, 6), [x2, y2] = pt(deg, 15);
    pointer.setAttribute("x1", x1); pointer.setAttribute("y1", y1);
    pointer.setAttribute("x2", x2); pointer.setAttribute("y2", y2);
  };
  const set = (n) => {
    const v = fromNorm(p, n);
    norm = p.integer ? toNorm(p, v) : Math.min(1, Math.max(0, n));
    draw();
    onChange(v);
  };
  draw();

  let startY = 0, startN = 0;
  svg.addEventListener("pointerdown", (e) => {
    svg.setPointerCapture(e.pointerId);
    startY = e.clientY;
    startN = norm;
    S.draggingKnob = true;
  });
  svg.addEventListener("pointermove", (e) => {
    if (!svg.hasPointerCapture(e.pointerId)) return;
    const dy = startY - e.clientY;
    set(startN + dy / (e.shiftKey ? 800 : 180));
  });
  const end = (e) => {
    if (svg.hasPointerCapture(e.pointerId)) svg.releasePointerCapture(e.pointerId);
    S.draggingKnob = false;
  };
  svg.addEventListener("pointerup", end);
  svg.addEventListener("pointercancel", end);
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const step = p.integer ? 1 / Math.max(1, p.max - p.min) : e.shiftKey ? 0.002 : 0.02;
    set(norm + (e.deltaY < 0 ? step : -step));
  }, { passive: false });
  svg.addEventListener("dblclick", () => set(toNorm(p, p.default)));
  return svg;
}

// ---------------------------------------------------------------- preset
async function loadPresets() {
  S.presets = await api("GET", "/api/presets");
  const sel = $("#presetSelect");
  sel.innerHTML = "";
  sel.add(new Option("Preset…", ""));
  for (const p of S.presets) sel.add(new Option(p.name, p.name, false, p.name === S.board.name));
}

function setupPresets() {
  $("#presetSelect").onchange = (e) => {
    const name = e.target.value;
    if (!name) return;
    guarded(async () => {
      S.board = await api("POST", `/api/presets/${encodeURIComponent(name)}/load`);
      S.selected = null;
      render();
      toast(`Preset "${name}" caricato`);
    });
  };
  $("#savePreset").onclick = () => guarded(async () => {
    const name = $("#presetName").value.trim();
    if (!name) throw new Error("Dai un nome al preset");
    S.board = await api("PUT", `/api/presets/${encodeURIComponent(name)}`);
    render();
    await loadPresets();
    toast(`Preset "${name}" salvato`);
  });
  $("#newPreset").onclick = () => {
    if (!confirm("Creare un preset vuoto? Le modifiche non salvate andranno perse.")) return;
    S.selected = { type: "slot", index: 0 };
    guarded(() => putBoard({ name: "Nuovo preset", chain: [] }));
  };
  $("#deletePreset").onclick = () => {
    const name = $("#presetSelect").value || S.board.name;
    if (!S.presets.some((p) => p.name === name)) return toast("Seleziona un preset salvato", true);
    if (!confirm(`Eliminare il preset "${name}"?`)) return;
    guarded(async () => {
      await api("DELETE", `/api/presets/${encodeURIComponent(name)}`);
      await loadPresets();
      toast(`Preset "${name}" eliminato`);
    });
  };
}

// ---------------------------------------------------------------- file e prova suono
async function loadFiles(kind) {
  S.files[kind] = await api("GET", `/api/files/${kind}`);
  if (kind === "di") {
    const sel = $("#diSelect");
    const cur = sel.value;
    sel.innerHTML = "";
    if (!S.files.di.length) sel.add(new Option("nessun file DI", ""));
    for (const f of S.files.di) sel.add(new Option(f.name, f.name, false, f.name === cur));
  }
}

function setupTestbar() {
  $("#diUpload").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const res = await guarded(() => api("PUT", `/api/files/di/${encodeURIComponent(f.name)}`, f));
    if (res) {
      await loadFiles("di");
      $("#diSelect").value = res.name;
      toast(`Caricato ${res.name}`);
    }
    e.target.value = "";
  };
  $("#renderBtn").onclick = async () => {
    const di = $("#diSelect").value;
    if (!di) return toast("Carica prima un file DI (.wav)", true);
    const btn = $("#renderBtn");
    btn.disabled = true;
    $("#renderInfo").textContent = "Elaborazione in tempo reale…";
    try {
      const res = await api("POST", `/api/render?di=${encodeURIComponent(di)}`, undefined, true);
      const url = URL.createObjectURL(await res.blob());
      const player = $("#player");
      if (player.dataset.url) URL.revokeObjectURL(player.dataset.url);
      player.dataset.url = url;
      player.src = url;
      player.play().catch(() => {});
      $("#renderInfo").textContent = "";
    } catch (e) {
      $("#renderInfo").textContent = "";
      toast(e.message, true);
    } finally {
      btn.disabled = false;
    }
  };
}

// ---------------------------------------------------------------- WebSocket
function connectWs() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => $("#conn").classList.add("ok");
  ws.onclose = () => {
    $("#conn").classList.remove("ok");
    setTimeout(connectWs, 1500);
  };
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "status") return showStatus(msg);
    if (msg.origin === clientId) return;
    if (msg.type === "board") {
      S.board = msg.board;
      render();
    } else if (msg.type === "block") {
      const b = findBlock(msg.block.id);
      if (!b) return;
      Object.assign(b, msg.block);
      if (S.draggingKnob) return;
      render();
    }
  };
}

function showStatus(s) {
  const dsp = Math.min(100, s.dsp);
  const fill = $("#dspFill");
  fill.style.width = `${dsp}%`;
  fill.style.background = dsp > 85 ? "var(--accent)" : dsp > 65 ? "var(--warn)" : "var(--ok)";
  $("#dspValue").textContent = `${dsp.toFixed(0)}%`;
  const ms = ((s.buffer / s.samplerate) * 1000).toFixed(1);
  $("#engineInfo").textContent = `${s.samplerate / 1000} kHz · ${s.buffer} (${ms} ms) · xrun ${s.xruns}`;
}

// ---------------------------------------------------------------- tastiera
document.addEventListener("keydown", (e) => {
  if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
  const sel = S.selected;
  if (sel?.type === "block" && (e.key === "Delete" || e.key === "Backspace")) {
    e.preventDefault();
    deleteBlock(sel.id);
  } else if (sel?.type === "block" && e.key === " ") {
    e.preventDefault();
    toggleBlock(sel.id);
  } else if (e.key === "Escape") {
    select(null);
  }
});

// ---------------------------------------------------------------- avvio
async function init() {
  S.catalog = await api("GET", "/api/catalog");
  for (const m of S.catalog.models) S.models[m.id] = m;
  for (const c of S.catalog.categories) S.cats[c.id] = c;
  await Promise.all(["nam", "ir", "di"].map(loadFiles));
  S.board = await api("GET", "/api/board");
  await loadPresets();
  setupPresets();
  setupTestbar();
  render();
  connectWs();
}

init().catch((e) => toast(`Impossibile avviare l'interfaccia: ${e.message}`, true));
