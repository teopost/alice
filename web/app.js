// Alice: interfaccia web a blocchi (JavaScript puro, nessuna dipendenza esterna:
// deve funzionare anche offline sulla pedaliera).

import { createStore } from "./store.js";

const MIN_COLS = 12;   // colonne minime della griglia, come Fractal
const clientId = Math.random().toString(36).slice(2);
const $ = (sel) => document.querySelector(sel);

const S = {
  catalog: null,
  models: {},
  cats: {},
  board: { name: "", chain: [] },
  selected: null,          // {type: "block", id} | {type: "slot", index}
  pickerCat: "drive",
  pickerQuery: "",
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
  pitch: '<path d="M9 18V6l10-2v12" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><circle cx="6.5" cy="18" r="2.5" fill="currentColor"/><circle cx="16.5" cy="16" r="2.5" fill="currentColor"/>',
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

function findBlock(id, chain = [...S.board.chain, ...(S.board.chain2 || [])]) {
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
      !findSplit(S.board, S.selected.id)) {
    S.selected = null;
  }
  $("#presetName").value = S.board.name;
  renderPath();
  renderEditor();
}

// Posizione degli elementi. Un "contenitore" è la catena principale ({split: null})
// oppure un ramo di uno split ({split: id, lane: n}); gli split non si annidano.
// Ogni elemento ha "gap": le caselle vuote della griglia che lo precedono, così
// spostare o togliere un blocco lascia gli altri al loro posto (come su Fractal).
const TOP = { split: null, lane: null, row: 0 };
const rowRef = (row) => (row ? { split: null, lane: null, row: 1 } : TOP);
// le due righe della griglia: per l'audio la seconda prosegue la prima
const rowsOf = (b) => [b.chain, (b.chain2 ||= [])];

function findSplit(b, id) {
  for (const [row, arr] of rowsOf(b).entries()) {
    const index = arr.findIndex((e) => e.id === id && e.kind === "split");
    if (index >= 0) return { arr, index, split: arr[index], row };
  }
  return null;
}
const MAX_LANES = 6;
const gapOf = (el) => el.gap || 0;

function locate(b, id) {
  for (const [row, arr] of rowsOf(b).entries()) {
    const i = arr.findIndex((e) => e.id === id);
    if (i >= 0) return { arr, index: i, ref: rowRef(row) };
    for (const el of arr) {
      if (el.kind !== "split") continue;
      for (let l = 0; l < el.lanes.length; l++) {
        const j = el.lanes[l].findIndex((e) => e.id === id);
        if (j >= 0) return { arr: el.lanes[l], index: j, ref: { split: el.id, lane: l, row } };
      }
    }
  }
  return null;
}

function containerOf(b, ref) {
  if (!ref.split) return rowsOf(b)[ref.row || 0];
  return findSplit(b, ref.split)?.split.lanes[ref.lane] ?? null;
}

const sameRef = (a, b) => (a?.split ?? null) === (b?.split ?? null) && (a?.lane ?? null) === (b?.lane ?? null) &&
  (a?.split ? true : (a?.row || 0) === (b?.row || 0));
// un nodo di parallelo si aggancia alla sua riga o al ramo 1 del suo parallelo
const nodeTargetOk = (node, ref) => node && (ref.split ? ref.split === node.split && ref.lane === 0 : (ref.row || 0) === node.row);

// toglie l'elemento i lasciando vuota la sua casella
function removeAt(arr, i) {
  const [el] = arr.splice(i, 1);
  if (i < arr.length) arr[i].gap = gapOf(arr[i]) + gapOf(el) + 1;
  return el;
}

// mette l'elemento nella casella vuota k (0 = la prima) che precede arr[index]
// (oppure, con index = arr.length, nelle caselle libere dopo l'ultimo elemento)
function placeAt(arr, index, k, el) {
  if (index < arr.length) {
    const next = arr[index];
    k = Math.min(k, gapOf(next));
    el.gap = k;
    next.gap = Math.max(0, gapOf(next) - k - 1);
  } else {
    el.gap = k;
  }
  arr.splice(index, 0, el);
}

// larghezza in colonne di un contenitore e di uno split
const laneCols = (lane) => lane.reduce((n, e) => n + gapOf(e) + 1, 0);
const splitCols = (s) => Math.max(...s.lanes.map(laneCols)) + 2;
// Colonna interna del nodo di fine scelta dall'utente ("span"): mai prima della fine del
// ramo 1. Gli altri rami possono essere più lunghi: sporgono sotto la linea principale e
// il loro filo torna indietro sopra gli effetti. null = nodo in fondo al ramo più lungo.
function effSpan(s) {
  if (s.span == null) return null;
  const sp = Math.max(s.span, laneCols(s.lanes[0]));
  return sp + 2 < splitCols(s) ? sp : null;
}
const elCols = (e) => (e.kind === "split" ? splitCols(e) : 1);

function renderPath() {
  const path = $("#path");
  path.innerHTML = "";
  const io = (label, cls = "", title = "") =>
    Object.assign(document.createElement("div"), { className: "io " + cls, textContent: label, title });
  const two = hasRow2(S.board);
  if (two) {
    path.append(
      renderRow(S.board.chain, 0, io("IN"), io("↓", "link", "Fine della riga 1: prosegue nella riga 2")),
      renderRow(S.board.chain2 || [], 1, io("↳", "link", "Inizio della riga 2: arriva dalla riga 1"), io("OUT")),
    );
    requestAnimationFrame(drawRowLink);
  } else {
    path.append(renderRow(S.board.chain, 0, io("IN"), io("OUT")));
  }
  requestAnimationFrame(drawSpans);
  const btn = $("#rowsBtn");
  btn.textContent = two ? "Rimuovi riga 2" : "+ Riga 2";
  btn.title = two ? "Torna a una sola riga (i blocchi della riga 2 passano in fondo alla riga 1)"
                  : "Prosegui la catena su una seconda riga, come il secondo percorso dell'Helix";
}

const hasRow2 = (b) => b.rows === 2 || (b.chain2 || []).length > 0;

// attiva o toglie la seconda riga; togliendola, i suoi blocchi passano in fondo alla riga 1
function toggleRow2() {
  const b = cloneBoard();
  if (hasRow2(b)) {
    b.chain.push(...(b.chain2 || []));
    b.chain2 = [];
    b.rows = 1;
  } else {
    b.rows = 2;
  }
  guarded(() => putBoard(b));
}

function renderRow(chain, row, startEl, endEl) {
  const ref = rowRef(row);
  const el = document.createElement("div");
  el.className = "path-row";
  el.dataset.row = row + 1;
  el.append(startEl, wire(ref, 0));
  let cols = 0, extent = 0;
  chain.forEach((e, i) => {
    for (let k = 0; k < gapOf(e); k++) el.append(emptySlot(ref, i, k), wire(ref, i, false, k + 1));
    cols += gapOf(e);
    if (e.kind === "split") {
      // inizio e fine del parallelo sono essi stessi i nodi di quel punto della catena:
      // niente ancoraggi doppi sui fili accanto
      el.lastElementChild.querySelector(".anchor")?.remove();
      const after = wire(ref, i + 1);
      after.querySelector(".anchor").remove();
      let sp = effSpan(e);
      if (sp != null) {
        // i rami che sporgono non devono finire sotto un altro parallelo
        const overEnd = cols + splitCols(e);
        let c = cols + sp + 2;
        for (const n of chain.slice(i + 1)) {
          c += gapOf(n);
          if (c >= overEnd) break;
          if (n.kind === "split") { sp = null; break; }
          c += 1;
        }
      }
      el.append(renderSplit(e, i, row, sp), after);
      extent = Math.max(extent, cols + splitCols(e));
      cols += sp != null ? sp + 2 : splitCols(e);
    } else {
      el.append(blockSlot(e, ref, i), wire(ref, i + 1));
      cols += 1;
    }
    extent = Math.max(extent, cols);
  });
  // caselle libere fino a riempire la griglia (sempre almeno una per aggiungere, e
  // abbastanza da coprire i rami che sporgono)
  const free = Math.max(1, MIN_COLS - cols, extent - cols + 1);
  for (let k = 0; k < free; k++) el.append(emptySlot(ref, chain.length, k), wire(ref, chain.length, false, k + 1));
  el.append(endEl);
  return el;
}

// Paralleli con il nodo di fine prima della fine dei rami: la barra di unione e, per i rami
// che sporgono, il filo che dopo l'ultimo effetto risale e torna indietro sopra di essi.
function drawSpans() {
  const NS = "http://www.w3.org/2000/svg";
  const gap = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--lane-gap")) || 6;
  const block = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--block")) || 76;
  for (const group of document.querySelectorAll(".split-group.spanned")) {
    group.querySelector(".span-svg")?.remove();
    const g = group.getBoundingClientRect();
    const lanesBox = group.querySelector(".lanes").getBoundingClientRect();
    const bus = lanesBox.right - g.left;
    let d = "", bottom = 0;
    for (const lane of group.querySelectorAll(".lanes > .lane")) {
      const r = lane.getBoundingClientRect();
      const y = r.top - g.top + block / 2;
      const end = lane.lastElementChild.getBoundingClientRect().right - g.left;
      if (end <= bus + 1) {
        bottom = Math.max(bottom, y);          // ramo che arriva al nodo: si unisce alla barra
      } else {
        const back = r.top - g.top - gap / 2;  // sopra gli effetti del ramo
        d += ` M${end} ${y} V${back} H${bus}`;
        bottom = Math.max(bottom, back);
      }
    }
    const top = group.querySelector(".lanes > .lane").getBoundingClientRect().top - g.top + block / 2;
    d = `M${bus} ${top} V${bottom}` + d;
    const svg = document.createElementNS(NS, "svg");
    svg.classList.add("span-svg");
    svg.setAttribute("width", group.scrollWidth + 400);
    svg.setAttribute("height", g.height);
    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", d);
    svg.append(path);
    group.append(svg);
  }
}
window.addEventListener("resize", () => requestAnimationFrame(drawSpans));

// filo che scende dalla fine della riga 1 all'inizio della riga 2, come sull'Helix
function drawRowLink() {
  const path = $("#path");
  const [r1, r2] = path.querySelectorAll(".path-row");
  if (!r1 || !r2) return;
  path.querySelector(".row-link")?.remove();
  const from = r1.lastElementChild.getBoundingClientRect(), to = r2.firstElementChild.getBoundingClientRect();
  const box = path.getBoundingClientRect();
  const x1 = from.left + from.width / 2 - box.left, y1 = from.bottom - box.top;
  const x2 = to.left + to.width / 2 - box.left, y2 = to.top - box.top;
  const ym = r2.getBoundingClientRect().top - box.top - 10;
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.classList.add("row-link");
  svg.setAttribute("width", path.scrollWidth);
  svg.setAttribute("height", path.scrollHeight);
  const line = document.createElementNS(NS, "path");
  line.setAttribute("d", `M${x1} ${y1} V${ym} H${x2} V${y2}`);
  svg.append(line);
  path.prepend(svg);
}
window.addEventListener("resize", () => requestAnimationFrame(drawRowLink));

function wire(ref, index, grow = false, at = 0) {
  const w = Object.assign(document.createElement("div"), { className: "wire" + (grow ? " grow" : "") });
  const a = Object.assign(document.createElement("span"), { className: "anchor" });
  // i nodi di un parallelo si agganciano solo alla catena principale o al ramo 1
  const nodeOk = () => nodeTargetOk(dragNode, ref);
  if (!ref.split || ref.lane === 0) a.classList.add("node-ok");
  a.drop = { ref, index };
  a.addEventListener("dragover", (e) => {
    if (!dragId && !nodeOk()) return;
    e.preventDefault();
    e.stopPropagation();
    a.classList.add("hot");
  });
  a.addEventListener("dragleave", () => a.classList.remove("hot"));
  a.addEventListener("drop", (e) => {
    e.preventDefault();
    e.stopPropagation();
    a.classList.remove("hot");
    if (dragId) moveTo(dragId, ref, index, { at });
    else if (nodeOk()) moveNode(dragNode, ref, index);
  });
  w.append(a);
  return w;
}

function slotShell() {
  const slot = document.createElement("div");
  slot.className = "slot";
  const tile = Object.assign(document.createElement("div"), { className: "tile" });
  const name = Object.assign(document.createElement("div"), { className: "name" });
  slot.append(tile, name);
  return { slot, tile, name };
}

function emptySlot(ref, index, k) {
  const { slot, tile } = slotShell();
  slot.classList.add("empty");
  const sel = S.selected;
  if (sel?.type === "slot" && sameRef(sel.ref, ref) && sel.index === index && (sel.k ?? 0) === k) slot.classList.add("selected");
  tile.title = "Aggiungi un blocco";
  tile.onclick = () => select({ type: "slot", ref, index, k });
  makeDropTarget(slot, ref, index, k);
  return slot;
}

function blockSlot(el, ref, index) {
  const { slot, tile, name } = slotShell();
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
  name.title = name.textContent;
  slot.append(Object.assign(document.createElement("div"), { className: "sub", textContent: el.file ? m.name : cat.name }));
  tile.onclick = () => select({ type: "block", id: el.id });
  tile.ondblclick = () => toggleBlock(el.id);
  makeDraggable(slot, tile, el.id);
  makeDropTarget(slot, ref, index, null);
  return slot;
}

// gruppo parallelo: nodo di divisione, un ramo per riga, nodo di unione
function renderSplit(el, si, row, span = null) {
  const group = document.createElement("div");
  group.className = "split-group" + (S.selected?.id === el.id ? " selected" : "");
  const node = (end, title) => {
    const n = document.createElement("button");
    n.className = "split-node " + end;
    n.title = title;
    makeNodeDraggable(n, { split: el.id, end, row }, () => select({ type: "block", id: el.id }));
    // un blocco rilasciato sul nodo va subito prima (inizio) o subito dopo (fine) il parallelo
    n.addEventListener("dragover", (e) => {
      if (!dragId) return;
      e.preventDefault();
      n.classList.add("hot");
    });
    n.addEventListener("dragleave", () => n.classList.remove("hot"));
    n.addEventListener("drop", (e) => {
      e.preventDefault();
      n.classList.remove("hot");
      if (dragId) moveTo(dragId, rowRef(row), end === "fork" ? si : si + 1, { at: end === "fork" ? gapOf(el) : 0 });
    });
    return n;
  };
  const lanes = document.createElement("div");
  lanes.className = "lanes";
  el.lanes.forEach((lane, l) => {
    const ref = { split: el.id, lane: l };
    const row = document.createElement("div");
    row.className = "lane" + (lane.length ? "" : " empty-lane");
    const rm = document.createElement("button");
    rm.className = "lane-remove";
    rm.textContent = "×";
    rm.title = el.lanes.length <= 2 ? "Rimuovi questo ramo (elimina il parallelo)" : "Rimuovi questo ramo";
    rm.onclick = () => removeLane(el.id, l);
    const lead = wire(ref, 0);
    lead.classList.add("lead");   // primo filo del ramo: la × ci sta sopra senza interrompere la linea
    row.append(lead, rm);
    lane.forEach((b, j) => {
      for (let k = 0; k < gapOf(b); k++) row.append(emptySlot(ref, j, k), wire(ref, j, false, k + 1));
      row.append(blockSlot(b, ref, j), wire(ref, j + 1));
    });
    if (span == null || laneCols(lane) + 1 <= span) {
      // il filo finale del ramo arriva dritto al nodo di fine: niente ancoraggio, che si
      // sovrapporrebbe al nodo (in fondo al ramo si aggiunge con la casella vuota)
      const end = wire(ref, lane.length, true, 1);
      end.querySelector(".anchor").remove();
      row.append(emptySlot(ref, lane.length, 0), end);
    } else if (laneCols(lane) === span) {
      // ramo che finisce proprio al nodo: niente casella vuota e niente ancoraggio doppio
      row.lastElementChild.querySelector(".anchor")?.remove();
    }
    // (un ramo più lungo del nodo finisce col suo ultimo effetto: il filo torna indietro)
    lanes.append(row);
  });
  const add = document.createElement("button");
  add.className = "add-lane";
  add.textContent = "+ Ramo";
  add.title = "Aggiungi un ramo parallelo";
  add.disabled = el.lanes.length >= MAX_LANES;
  add.onclick = () => addLane(el.id);
  lanes.append(add);
  if (span != null) {
    // nodo di fine alla colonna scelta: i rami più lunghi sporgono oltre il riquadro
    group.classList.add("spanned");
    lanes.style.width = `calc(56px + ${span} * (var(--block) + 22px))`;
  }
  group.append(node("fork", "Inizio del parallelo: clic per le opzioni, trascina per spostarlo"), lanes,
               node("merge", "Fine del parallelo: clic per le opzioni, trascina per spostarla"));
  return group;
}

function select(sel) {
  S.selected = sel;
  render();
}

// trascinamento dei blocchi: in qualunque casella della catena principale o dei rami
let dragId = null;
function makeDraggable(slot, tile, id) {
  tile.draggable = true;
  tile.addEventListener("dragstart", (e) => {
    dragId = id;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", id);
    requestAnimationFrame(() => slot.classList.add("dragging"));
    document.body.classList.add("dragging-block");
  });
  tile.addEventListener("dragend", () => {
    dragId = null;
    slot.classList.remove("dragging");
    document.body.classList.remove("dragging-block");
  });
}

// k = casella vuota di destinazione; null = sopra un blocco (lo si spinge a destra)
function makeDropTarget(slot, ref, index, k) {
  slot.addEventListener("dragover", (e) => {
    if (!dragId && !dragNode) return;
    e.preventDefault();
    e.stopPropagation();
    slot.classList.add("drop-target");
  });
  slot.addEventListener("dragleave", () => slot.classList.remove("drop-target"));
  slot.addEventListener("drop", (e) => {
    e.preventDefault();
    e.stopPropagation();
    slot.classList.remove("drop-target");
    if (dragId) moveTo(dragId, ref, index, k);
    else if (dragNode) moveNode(dragNode, ref, index);
  });
}

// Trascinamento dei nodi di un parallelo, gestito con gli eventi del puntatore invece del
// drag and drop del browser (che Chrome annulla se la pagina cambia mentre parte, e che
// sui tablet non esiste). Un clic senza movimento apre le opzioni del parallelo.
function makeNodeDraggable(n, info, onClick) {
  let start = null, active = false, hot = null;
  const anchorAt = (x, y) => {
    const a = document.elementFromPoint(x, y)?.closest(".anchor");
    if (!a?.drop) return null;
    return nodeTargetOk(info, a.drop.ref) ? a : null;
  };
  n.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    start = { x: e.clientX, y: e.clientY };
    n.setPointerCapture(e.pointerId);
  });
  n.addEventListener("pointermove", (e) => {
    if (!start) return;
    if (!active) {
      if (Math.hypot(e.clientX - start.x, e.clientY - start.y) < 8) return;
      active = true;
      dragNode = info;
      document.body.classList.add("dragging-node");
      cable.start(n, e);
    }
    const a = anchorAt(e.clientX, e.clientY);
    if (a !== hot) {
      hot?.classList.remove("hot");
      a?.classList.add("hot");
      hot = a;
    }
    // vicino a un ancoraggio il filo ci si aggancia
    const r = a?.getBoundingClientRect();
    cable.draw(r ? r.left + r.width / 2 : e.clientX);
  });
  const finish = (e, commit) => {
    if (!start) return;
    if (n.hasPointerCapture(e.pointerId)) n.releasePointerCapture(e.pointerId);
    const target = commit && active ? hot?.drop : null;
    const clicked = commit && !active;
    hot?.classList.remove("hot");
    cable.stop();
    document.body.classList.remove("dragging-node");
    start = null; active = false; hot = null; dragNode = null;
    if (target) moveNode(info, target.ref, target.index);
    else if (clicked) onClick();
  };
  n.addEventListener("pointerup", (e) => finish(e, true));
  n.addEventListener("pointercancel", (e) => finish(e, false));
}

// Durante il trascinamento di un nodo il collegamento originale si allunga fino al
// puntatore: il nodo resta sulla linea principale, la barra verticale che unisce i rami
// lo segue e i fili orizzontali di ogni ramo si allungano o si accorciano fino a lì.
const cable = {
  start(node, e) {
    const group = node.closest(".split-group");
    const lanes = group.querySelector(".lanes");
    const lr = lanes.getBoundingClientRect();
    const half = node.getBoundingClientRect().height / 2;
    this.fork = node.classList.contains("fork");
    this.edge = this.fork ? lr.left : lr.right;   // dove finiscono ora i fili dei rami
    const block = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--block")) || 76;
    this.rows = [...lanes.querySelectorAll(":scope > .lane")];
    this.ys = this.rows.map((r) => r.getBoundingClientRect().top + block / 2);
    this.tops = this.rows.map((r) => r.getBoundingClientRect().top);
    // dove finisce il contenuto di ogni ramo (la sua ultima casella)
    this.ends = this.rows.map((r) => [...r.querySelectorAll(":scope > .slot")].pop().getBoundingClientRect().right);
    this.gap = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--lane-gap")) || 6;
    this.half = half;
    this.group = group;
    group.classList.add(this.fork ? "moving-fork" : "moving-merge");
    const NS = "http://www.w3.org/2000/svg";
    this.svg = document.createElementNS(NS, "svg");
    this.svg.classList.add("cable");
    this.path = document.createElementNS(NS, "path");
    this.dot = document.createElementNS(NS, "circle");
    this.dot.setAttribute("r", 8);
    this.svg.append(this.path, this.dot);
    document.body.append(this.svg);
    this.draw(e.clientX);
  },
  draw(x) {
    const y0 = this.ys[0], yN = this.ys[this.ys.length - 1];
    if (this.fork) {
      // inizio: verso l'esterno i fili dei rami si allungano fino alla barra
      let d = `M${x} ${y0} L${x} ${yN}`;
      if (x < this.edge) for (const y of this.ys) d += ` M${this.edge} ${y} L${x} ${y}`;
      this.path.setAttribute("d", d);
    } else {
      // fine: ogni ramo raggiunge la barra; un ramo più lungo resta intero e il suo filo,
      // dopo l'ultimo effetto, risale e torna indietro sopra di essi (il ramo 1 invece
      // prosegue: i suoi blocchi oltre la barra usciranno in serie)
      let d = "", bottom = y0;
      this.ys.forEach((y, i) => {
        const end = this.ends[i];
        if (end <= x) {
          d += ` M${end} ${y} H${x}`;
          bottom = Math.max(bottom, y);
        } else if (i > 0) {
          const back = this.tops[i] - this.gap / 2;
          d += ` M${end} ${y} V${back} H${x}`;
          bottom = Math.max(bottom, back);
        }
      });
      this.path.setAttribute("d", `M${x} ${y0} V${bottom}` + d);
    }
    this.dot.setAttribute("cx", x);
    this.dot.setAttribute("cy", y0);
  },
  stop() {
    this.svg?.remove();
    this.group?.classList.remove("moving-fork", "moving-merge");
    this.svg = this.group = null;
  },
};

// Sposta l'inizio (fork) o la fine (merge) di un parallelo in un altro punto:
// i blocchi scavalcati entrano nel ramo 1 oppure ne escono tornando in serie.
let dragNode = null;
function moveNode({ split: splitId, end }, ref, index) {
  const b = cloneBoard();
  const found = findSplit(b, splitId);
  if (!found) return;
  const { arr: line, index: si, split, row } = found;
  const main = split.lanes[0];
  const fail = (msg) => toast(msg, true);

  if (!ref.split && (ref.row || 0) === row) {
    if (end === "fork") {
      if (index === si) return;
      if (index > si) return fail("L'inizio del parallelo va spostato prima della sua fine");
      const taken = line.slice(index, si);
      if (taken.some((e) => e.kind === "split")) return fail("Un parallelo non può contenerne un altro");
      line.splice(index, si - index);
      // le caselle vuote che precedevano il parallelo restano dentro il ramo 1
      const oldGap = gapOf(split);
      split.gap = gapOf(taken[0]);
      taken[0].gap = 0;
      if (main.length) main[0].gap = gapOf(main[0]) + oldGap;
      main.unshift(...taken);
    } else {
      if (index === si + 1) return;
      if (index <= si) return fail("La fine del parallelo va spostata dopo il suo inizio");
      const taken = line.slice(si + 1, index);
      if (!taken.length) return;
      if (taken.some((e) => e.kind === "split")) return fail("Un parallelo non può contenerne un altro");
      line.splice(si + 1, taken.length);
      main.push(...taken);
      split.span = laneCols(main);
    }
  } else if (ref.split === splitId && ref.lane === 0) {
    if (end === "fork") {
      // il parallelo si restringe: gli altri rami perdono le caselle vuote per starci dentro
      split.lanes.slice(1).forEach((lane) => lane.forEach((e) => (e.gap = 0)));
      // i primi blocchi del ramo 1 escono e vanno prima del parallelo
      const out = main.splice(0, index);
      if (!out.length) return;
      out[0].gap = gapOf(split) + gapOf(out[0]);
      split.gap = 0;
      line.splice(si, 0, ...out);
    } else {
      // gli ultimi blocchi del ramo 1 escono e vanno dopo il parallelo; gli altri rami
      // restano interi e, se più lunghi, sporgono con il filo che torna al nodo
      const out = main.splice(index);
      if (!out.length) return;
      out[0].gap = 0;
      line.splice(si + 1, 0, ...out);
      split.span = laneCols(main);
    }
  } else {
    return fail("Trascina il nodo su un punto della sua riga o del ramo 1");
  }
  if (split.span != null && split.span + 2 >= splitCols(split)) delete split.span;   // nodo in fondo: non serve
  if (split.lanes.every((l) => !l.length)) {
    removeAt(line, line.indexOf(split));
    S.selected = null;
    toast("Il parallelo era rimasto vuoto ed è stato tolto");
  } else {
    S.selected = { type: "block", id: splitId };
  }
  guarded(() => putBoard(b));
}

function moveTo(id, ref, index, k = 0) {
  const b = cloneBoard();
  const from = locate(b, id);
  const dest = containerOf(b, ref);
  if (!from || !dest) return;
  // sopra se stesso o sul blocco subito dopo: nulla da fare
  if (from.arr === dest) {
    const self = from.arr[from.index];
    const onBlock = k === null && (index === from.index || index === from.index + 1);
    // nodi subito prima o subito dopo il blocco stesso
    const onOwnAnchor = typeof k === "object" && k !== null &&
      ((index === from.index && k.at === gapOf(self)) || (index === from.index + 1 && k.at === 0));
    if (onBlock || onOwnAnchor) return;
  }
  const el = from.arr[from.index];
  if (el.kind === "split" && ref.split) return toast("Un parallelo non può stare dentro un altro", true);
  const removedGap = gapOf(el);
  removeAt(from.arr, from.index);
  if (from.arr === dest && index > from.index) {
    // la casella lasciata libera si somma al vuoto che precede l'elemento successivo
    if (index === from.index + 1 && typeof k === "number") k += removedGap + 1;
    if (index === from.index + 1 && k && typeof k === "object") k = { at: k.at + removedGap + 1 };
    index -= 1;
  }
  index = Math.max(0, Math.min(dest.length, index));
  if (k === null) {
    // sopra un blocco: prende la sua casella e lo spinge a destra di una
    const next = dest[index];
    el.gap = next ? gapOf(next) : 0;
    if (next) next.gap = 0;
    dest.splice(index, 0, el);
  } else if (typeof k === "object") {
    // su un nodo di ancoraggio dopo k.at caselle vuote: si inserisce lì, il resto scorre di una
    const next = dest[index];
    el.gap = next ? Math.min(k.at, gapOf(next)) : k.at;
    if (next) next.gap = gapOf(next) - el.gap;
    dest.splice(index, 0, el);
  } else {
    placeAt(dest, index, k, el);
  }
  guarded(() => putBoard(b));
}

// sposta di una casella a sinistra (-1) o a destra (+1) nel suo contenitore
function nudge(id, dir) {
  const b = cloneBoard();
  const { arr, index: i } = locate(b, id);
  const el = arr[i], next = arr[i + 1], prev = arr[i - 1];
  if (dir < 0) {
    if (gapOf(el) > 0) {
      el.gap -= 1;
      if (next) next.gap = gapOf(next) + 1;
    } else if (prev) {
      [arr[i - 1], arr[i]] = [el, prev];
      el.gap = gapOf(prev);
      prev.gap = 0;
    } else return;
  } else if (next && gapOf(next) > 0) {
    el.gap = gapOf(el) + 1;
    next.gap -= 1;
  } else if (next) {
    [arr[i], arr[i + 1]] = [next, el];
    next.gap = gapOf(el);
    el.gap = 0;
  } else {
    el.gap = gapOf(el) + 1;
  }
  guarded(() => putBoard(b));
}

function addBlock(modelId, ref, index, k = 0) {
  const b = cloneBoard();
  const dest = containerOf(b, ref);
  if (!dest) return;
  const block = { id: newId(), kind: "block", model: modelId, enabled: true, params: {} };
  const m = S.models[modelId];
  if (m.file && S.files[m.file.kind].length) block.file = S.files[m.file.kind][0].name;
  placeAt(dest, index, k, block);
  S.selected = { type: "block", id: block.id };
  guarded(() => putBoard(b));
}

function deleteBlock(id) {
  const b = cloneBoard();
  const loc = locate(b, id);
  if (!loc) return;
  const k = gapOf(loc.arr[loc.index]);
  removeAt(loc.arr, loc.index);
  // resta selezionata la casella appena liberata
  S.selected = { type: "slot", ref: loc.ref, index: loc.index, k };
  guarded(() => putBoard(b));
}

function changeModel(id, modelId) {
  const b = cloneBoard();
  const loc = locate(b, id);
  const m = S.models[modelId];
  const old = loc.arr[loc.index];
  loc.arr[loc.index] = { id, kind: "block", model: modelId, enabled: old.enabled, params: {}, gap: gapOf(old),
                         file: m.file && S.files[m.file.kind].length ? S.files[m.file.kind][0].name : null };
  guarded(() => putBoard(b));
}

// --- operazioni sui paralleli
function makeParallel(id) {
  const b = cloneBoard();
  const loc = locate(b, id);
  if (!loc || loc.ref.split) return;
  const block = loc.arr[loc.index];
  // il secondo ramo vuoto lascia passare il segnale pulito (come un mix dry/wet)
  const split = { id: newId("s"), kind: "split", gap: gapOf(block), lanes: [[{ ...block, gap: 0 }], []] };
  loc.arr[loc.index] = split;
  S.selected = { type: "slot", ref: { split: split.id, lane: 1, row: loc.ref.row }, index: 0, k: 0 };
  guarded(() => putBoard(b));
}

function addLane(splitId) {
  const b = cloneBoard();
  const s = findSplit(b, splitId)?.split;
  if (!s || s.lanes.length >= MAX_LANES) return;
  s.lanes.push([]);
  S.selected = { type: "slot", ref: { split: splitId, lane: s.lanes.length - 1 }, index: 0, k: 0 };
  guarded(() => putBoard(b));
}

function removeLane(splitId, lane) {
  const b = cloneBoard();
  const s = findSplit(b, splitId).split;
  if (s.lanes.length <= 2) return dissolveSplit(splitId, lane === 0 ? 1 : 0);
  s.lanes.splice(lane, 1);
  guarded(() => putBoard(b));
}

// elimina il parallelo tenendo in catena i blocchi di un ramo
function dissolveSplit(splitId, keep = 0) {
  const b = cloneBoard();
  const found = findSplit(b, splitId);
  if (!found) return;
  const { arr, index: i, split } = found;
  const kept = split.lanes[keep] || [];
  if (kept.length) {
    kept[0].gap = gapOf(split) + gapOf(kept[0]);
    arr.splice(i, 1, ...kept);
  } else {
    removeAt(arr, i);
  }
  S.selected = kept.length ? { type: "block", id: kept[0].id } : null;
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
    ed.innerHTML = `<div class="empty-state"><div>
      <svg viewBox="0 0 24 24"><rect x="3" y="7" width="7" height="10" rx="2"/><rect x="14" y="7" width="7" height="10" rx="2"/><path d="M10 12h4"/></svg>
      <strong>Nessun blocco selezionato</strong>
      Tocca un blocco della catena per regolarlo, oppure uno slot vuoto <b>+</b> per aggiungere un effetto.
    </div></div>`;
    return;
  }
  if (sel.type === "slot") return renderPicker(ed, sel.ref || TOP, sel.index, sel.k ?? 0);
  const split = findSplit(S.board, sel.id)?.split;
  if (split) return renderSplitEditor(ed, split);
  renderBlockEditor(ed, findBlock(sel.id));
}

const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function renderPicker(ed, ref, index, k = 0) {
  const wrap = document.createElement("div");
  wrap.className = "picker";

  const side = document.createElement("div");
  side.className = "picker-side";
  const search = Object.assign(document.createElement("input"), {
    type: "search", placeholder: "Cerca un effetto…", value: S.pickerQuery || "", spellcheck: false,
  });
  const cats = document.createElement("div");
  cats.className = "cats";
  for (const c of S.catalog.categories) {
    const count = S.catalog.models.filter((m) => m.category === c.id).length;
    if (!count) continue;
    const b = document.createElement("button");
    b.className = "cat" + (c.id === S.pickerCat && !S.pickerQuery ? " active" : "");
    b.dataset.cat = c.id;
    b.style.setProperty("--c", c.color);
    b.innerHTML = `${icon(c.id)}<span>${c.name}</span><span class="count">${count}</span>`;
    b.onclick = () => { S.pickerCat = c.id; S.pickerQuery = ""; renderEditor(); };
    cats.append(b);
  }
  side.append(search, cats);
  const lane = ref.split && containerOf(S.board, ref);
  if (lane && !lane.length) {
    // ramo appena creato e ancora vuoto: si può tornare indietro
    const rm = document.createElement("button");
    rm.className = "btn ghost danger";
    rm.textContent = "Rimuovi questo ramo";
    rm.title = "Toglie il ramo vuoto; con due rami il parallelo viene eliminato";
    rm.onclick = () => removeLane(ref.split, ref.lane);
    side.append(rm);
  }

  const main = document.createElement("div");
  main.className = "picker-main";
  const title = document.createElement("h3");
  const models = document.createElement("div");
  models.className = "models";
  main.append(title, models);

  const fill = () => {
    const q = (S.pickerQuery || "").trim().toLowerCase();
    const list = q
      ? S.catalog.models.filter((m) => `${m.name} ${m.desc || ""} ${S.cats[m.category].name}`.toLowerCase().includes(q))
      : S.catalog.models.filter((m) => m.category === S.pickerCat);
    title.innerHTML = q
      ? `Risultati <small>${list.length} effetti</small>`
      : `${escapeHtml(S.cats[S.pickerCat].name)} <small>${list.length} effetti</small>`;
    models.innerHTML = "";
    if (!list.length) models.innerHTML = '<div class="no-results">Nessun effetto trovato.</div>';
    for (const m of list) {
      const b = document.createElement("button");
      b.className = "model";
      b.style.setProperty("--c", S.cats[m.category].color);
      b.innerHTML = `<span class="mi">${icon(m.category)}</span><span class="mt">` +
        (q ? `<span class="mc">${escapeHtml(S.cats[m.category].name)}</span>` : "") +
        `<span class="mn">${escapeHtml(m.name)}</span><span class="md">${escapeHtml(m.desc || "")}</span></span>`;
      b.onclick = () => addBlock(m.id, ref, index, k);
      models.append(b);
    }
    cats.querySelectorAll(".cat").forEach((c) => c.classList.toggle("active", !q && c.dataset.cat === S.pickerCat));
  };
  search.oninput = () => { S.pickerQuery = search.value; fill(); };
  fill();

  wrap.append(side, main);
  ed.append(wrap);
  if (matchMedia("(pointer: fine)").matches) search.focus();
}

function renderSplitEditor(ed, split) {
  ed.style.setProperty("--c", "#9aa0a6");
  const head = document.createElement("div");
  head.className = "editor-head";
  head.innerHTML = `<span class="cat-chip"><svg viewBox="0 0 24 24"><path d="M3 12h4M7 12c3 0 3-6 6-6h4M7 12c3 0 3 6 6 6h4M17 6h4M17 18h4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>Parallelo</span>
    <span class="model-title">${split.lanes.length} rami</span>`;
  ed.append(head);
  ed.append(Object.assign(document.createElement("p"), {
    className: "editor-desc",
    textContent: "Il segnale entra in tutti i rami contemporaneamente e alla fine i rami vengono sommati. " +
      "Un ramo vuoto lascia passare il suono pulito. Più rami suonano, più il volume sale: abbassa il livello dei blocchi se serve.",
  }));
  const list = document.createElement("div");
  list.className = "lane-list";
  split.lanes.forEach((lane, l) => {
    const row = document.createElement("div");
    row.className = "lane-item";
    const names = lane.map((b) => S.models[b.model].name).join(" → ") || "vuoto (suono pulito)";
    row.innerHTML = `<span class="lane-n">${l + 1}</span><span class="lane-names">${escapeHtml(names)}</span>`;
    const addB = document.createElement("button");
    addB.className = "btn ghost";
    addB.textContent = "+ Blocco";
    addB.onclick = () => select({ type: "slot", ref: { split: split.id, lane: l }, index: lane.length, k: 0 });
    const rm = document.createElement("button");
    rm.className = "btn ghost danger";
    rm.textContent = "Rimuovi ramo";
    rm.title = split.lanes.length <= 2 ? "Con due rami, rimuoverne uno elimina il parallelo" : "Rimuovi questo ramo e i suoi blocchi";
    rm.onclick = () => removeLane(split.id, l);
    row.append(addB, rm);
    list.append(row);
  });
  ed.append(list);
  const actions = document.createElement("div");
  actions.className = "split-actions";
  const add = document.createElement("button");
  add.className = "btn";
  add.textContent = "+ Aggiungi ramo";
  add.disabled = split.lanes.length >= MAX_LANES;
  add.onclick = () => addLane(split.id);
  const dissolve = document.createElement("button");
  dissolve.className = "btn ghost danger";
  dissolve.textContent = "Elimina parallelo (tieni il ramo 1)";
  dissolve.onclick = () => dissolveSplit(split.id, 0);
  actions.append(add, dissolve);
  ed.append(actions);
}

function renderBlockEditor(ed, block) {
  const m = S.models[block.model];
  const cat = S.cats[m.category];
  ed.style.setProperty("--c", cat.color);

  const head = document.createElement("div");
  head.className = "editor-head";
  const chip = Object.assign(document.createElement("span"), { className: "cat-chip" });
  chip.innerHTML = `${icon(m.category)}${escapeHtml(cat.name)}`;

  const switchWrap = Object.assign(document.createElement("span"), { className: "model-switch" });
  const modelSel = document.createElement("select");
  modelSel.title = "Cambia modello";
  for (const mm of S.catalog.models.filter((x) => x.category === m.category)) {
    modelSel.add(new Option(mm.name, mm.id, false, mm.id === m.id));
  }
  modelSel.onchange = () => changeModel(block.id, modelSel.value);
  switchWrap.append(modelSel);

  const onBtn = document.createElement("button");
  onBtn.className = "footswitch " + (block.enabled ? "on" : "off");
  onBtn.innerHTML = `<span class="fs-cap"></span>${block.enabled ? "ON" : "BYPASS"}`;
  onBtn.title = "Attiva / bypass (barra spaziatrice)";
  onBtn.onclick = () => toggleBlock(block.id);

  const loc = locate(S.board, block.id);
  const idx = loc.index;
  const iconBtn = (path, title, onclick, disabled = false) => {
    const b = document.createElement("button");
    b.className = "icon-btn";
    b.title = title;
    b.setAttribute("aria-label", title);
    b.innerHTML = `<svg viewBox="0 0 24 24">${path}</svg>`;
    b.onclick = onclick;
    b.disabled = disabled;
    return b;
  };
  const left = iconBtn('<path d="M15 5l-7 7 7 7"/>', "Sposta a sinistra", () => nudge(block.id, -1), idx <= 0 && !gapOf(block));
  const right = iconBtn('<path d="M9 5l7 7-7 7"/>', "Sposta a destra", () => nudge(block.id, 1));
  const extra = [];
  if (!loc.ref.split) {
    const par = iconBtn('<path d="M3 12h4M7 12c3 0 3-6 6-6h4M7 12c3 0 3 6 6 6h4M17 6h4M17 18h4"/>',
                        "Metti in parallelo (crea un secondo ramo)", () => makeParallel(block.id));
    par.classList.add("labeled");
    par.insertAdjacentText("beforeend", "Parallelo");
    extra.push(par);
  } else {
    const nLanes = findSplit(S.board, loc.ref.split).split.lanes.length;
    const lane = loc.ref.lane;
    extra.push(
      iconBtn('<path d="M12 19V5M5 12l7-7 7 7"/>', "Sposta nel ramo sopra",
              () => moveTo(block.id, { split: loc.ref.split, lane: lane - 1 }, Infinity, 0), lane <= 0),
      iconBtn('<path d="M12 5v14M5 12l7 7 7-7"/>', "Sposta nel ramo sotto",
              () => moveTo(block.id, { split: loc.ref.split, lane: lane + 1 }, Infinity, 0), lane >= nLanes - 1),
    );
  }
  const del = iconBtn('<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>', "Elimina blocco (Canc)", () => deleteBlock(block.id));
  del.classList.add("danger");

  head.append(chip, switchWrap, onBtn, Object.assign(document.createElement("span"), { className: "spacer" }), ...extra, left, right, del);
  ed.append(head);
  if (m.desc) ed.append(Object.assign(document.createElement("p"), { className: "editor-desc", textContent: m.desc }));

  if (m.file) ed.append(fileRow(block, m));

  const params = document.createElement("div");
  params.className = "params";
  for (const p of m.params) params.append(paramControl(block, p));
  if (!m.params.length) params.innerHTML = '<div class="hint">Questo effetto non ha controlli: accendilo o spegnilo.</div>';
  ed.append(params);
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
  const browse = document.createElement("button");
  browse.className = "btn";
  browse.textContent = kind === "nam" ? "Sfoglia TONE3000…" : "IR da TONE3000…";
  browse.title = "Scegli e installa un profilo dal negozio TONE3000";
  browse.onclick = () => showView("store");
  row.append(browse);
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
    wrap.classList.add("wide");
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
  // tacche della scala, anello del valore, gonna scura e cappello metallico
  for (let i = 0; i <= 10; i++) {
    const deg = START + (i / 10) * SWEEP;
    const [x1, y1] = pt(deg, 29.5), [x2, y2] = pt(deg, i % 5 ? 31 : 32);
    mk("line", { x1, y1, x2, y2, class: "tick" });
  }
  mk("path", { d: arc(START, START + SWEEP), class: "track", "stroke-width": 4, fill: "none", "stroke-linecap": "round" });
  const fill = mk("path", { class: "fill", "stroke-width": 4, fill: "none", "stroke-linecap": "round" });
  mk("circle", { cx: 32, cy: 33, r: 20, class: "skirt", "stroke-width": 1 });
  mk("circle", { cx: 32, cy: 32, r: 16, class: "cap", "stroke-width": 1 });
  const pointer = mk("line", { class: "pointer", "stroke-width": 2.5, "stroke-linecap": "round" });

  let norm = toNorm(p, initial);
  const draw = () => {
    const deg = START + norm * SWEEP;
    fill.setAttribute("d", norm > 0.001 ? arc(START, deg) : "");
    const [x1, y1] = pt(deg, 8), [x2, y2] = pt(deg, 19);
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

function loadPreset(name) {
  return guarded(async () => {
    S.board = await api("POST", `/api/presets/${encodeURIComponent(name)}/load`);
    S.selected = null;
    render();
    $("#presetSelect").value = name;
    toast(`Preset "${name}" caricato`);
  });
}

function stepPreset(dir) {
  if (!S.presets.length) return toast("Nessun preset salvato", true);
  const i = S.presets.findIndex((p) => p.name === S.board.name);
  const next = i < 0 ? (dir > 0 ? 0 : S.presets.length - 1) : (i + dir + S.presets.length) % S.presets.length;
  loadPreset(S.presets[next].name);
}

function setupPresets() {
  $("#presetSelect").onchange = (e) => {
    if (e.target.value) loadPreset(e.target.value);
  };
  $("#prevPreset").onclick = () => stepPreset(-1);
  $("#nextPreset").onclick = () => stepPreset(1);
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

// ---------------------------------------------------------------- ponte audio dal vivo
// Il browser cattura la chitarra dalla scheda audio del PC e la manda al motore
// via WebSocket; il suono elaborato torna indietro e viene riprodotto.
const LS = (k, v) => {
  try {
    if (v === undefined) return localStorage.getItem("alice." + k);
    localStorage.setItem("alice." + k, v);
  } catch { return null; }
};

const live = { ctx: null, stream: null, node: null, ws: null, sr: 48000, stats: null };

async function listDevices() {
  const devs = await navigator.mediaDevices.enumerateDevices();
  const fill = (sel, kind, first) => {
    const cur = sel.value || LS(sel.id) || "";
    sel.innerHTML = "";
    sel.add(new Option(first, ""));
    devs.filter((d) => d.kind === kind && d.deviceId && !["default", "communications"].includes(d.deviceId))
      .forEach((d, i) => sel.add(new Option(d.label || `${kind} ${i + 1}`, d.deviceId, false, d.deviceId === cur)));
  };
  fill($("#liveInput"), "audioinput", "Ingresso predefinito");
  fill($("#liveOutput"), "audiooutput", "Uscita predefinita");
}

function setupLive() {
  const canSink = typeof AudioContext !== "undefined" && "setSinkId" in AudioContext.prototype;
  if (!canSink) $("#liveOutput").hidden = true;
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    $("#liveBtn").disabled = true;
    $("#liveInfo").textContent = "Il browser permette l'ingresso audio solo da http://localhost o in https.";
    return;
  }
  const gain = $("#liveGain");
  const showGain = () => ($("#liveGainValue").textContent = `+${gain.value} dB`);
  if (LS("liveGain") !== null) gain.value = LS("liveGain");
  showGain();
  gain.addEventListener("input", () => {
    showGain();
    LS("liveGain", gain.value);
    live.node?.port.postMessage({ type: "config", gain: liveGain() });
  });
  for (const id of ["liveInput", "liveOutput", "liveChannel", "liveBuffer"]) {
    const saved = LS(id);  // ingresso e uscita vengono ripristinati da listDevices()
    if (saved !== null && (id === "liveChannel" || id === "liveBuffer")) $("#" + id).value = saved;
    $("#" + id).addEventListener("change", (e) => {
      LS(id, e.target.value);
      if (id === "liveChannel" || id === "liveBuffer") {
        live.node?.port.postMessage({ type: "config", channel: Number($("#liveChannel").value),
                                      target: Number($("#liveBuffer").value) });
      } else if (live.ctx) {
        stopLive().then(startLive);   // cambio di dispositivo: riavvia
      }
    });
  }
  // le etichette dei dispositivi sono visibili solo dopo il permesso del microfono
  listDevices().catch(() => {});
  navigator.mediaDevices.addEventListener?.("devicechange", () => listDevices().catch(() => {}));
  $("#liveBtn").onclick = () => (live.ctx ? stopLive() : startLive());
}

const liveGain = () => Math.pow(10, Number($("#liveGain").value) / 20);

async function startLive() {
  const btn = $("#liveBtn");
  btn.disabled = true;
  try {
    const inputId = $("#liveInput").value;
    live.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        deviceId: inputId ? { exact: inputId } : undefined,
        echoCancellation: false, noiseSuppression: false, autoGainControl: false,
        channelCount: { ideal: 2 }, latency: 0,
      },
    });
    await listDevices();
    const ctx = new AudioContext({ sampleRate: live.sr, latencyHint: 0 });
    live.ctx = ctx;
    const outId = $("#liveOutput").value;
    if (outId && ctx.setSinkId) await ctx.setSinkId(outId);
    await ctx.audioWorklet.addModule("bridge-worklet.js");
    const node = new AudioWorkletNode(ctx, "alice-bridge", {
      numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [2],
      channelCount: 2, channelCountMode: "explicit", channelInterpretation: "discrete",
    });
    live.node = node;
    node.port.postMessage({ type: "config", channel: Number($("#liveChannel").value),
                            target: Number($("#liveBuffer").value), gain: liveGain() });
    ctx.createMediaStreamSource(live.stream).connect(node);
    node.connect(ctx.destination);

    // il ponte è un processo separato sulla porta 8091 (vedi backend/alice/bridge.py)
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.hostname}:8091/`);
    ws.binaryType = "arraybuffer";
    live.ws = ws;
    ws.onmessage = (e) => {
      if (typeof e.data === "string") return;
      const data = new Float32Array(e.data);
      node.port.postMessage(data, [data.buffer]);
    };
    ws.onclose = () => {
      if (live.ws === ws) {
        stopLive();
        toast("Ponte audio interrotto", true);
      }
    };
    node.port.onmessage = (e) => {
      const m = e.data;
      if (m instanceof Float32Array) {
        if (ws.readyState === WebSocket.OPEN) ws.send(m.buffer);
      } else if (m.type === "stats") {
        showLiveStats(m);
      }
    };
    await ctx.resume();
    btn.textContent = "■ Ferma";
    btn.classList.add("active");
    const track = live.stream.getAudioTracks()[0];
    const settings = track.getSettings();
    if ((settings.channelCount || 1) < 2) $("#liveChannel").value = "0";
    toast(`In ascolto da: ${track.label || "ingresso predefinito"}`);
  } catch (e) {
    await stopLive();
    toast(e.name === "NotAllowedError" ? "Permesso per l'ingresso audio negato" : `Ponte audio: ${e.message}`, true);
  } finally {
    btn.disabled = false;
  }
}

async function stopLive() {
  const { ws, stream, ctx } = live;
  live.ws = live.node = live.ctx = live.stream = null;
  ws?.close();
  stream?.getTracks().forEach((t) => t.stop());
  await ctx?.close().catch(() => {});
  const btn = $("#liveBtn");
  btn.textContent = "● Attiva";
  btn.classList.remove("active");
  $("#liveInfo").textContent = "";
  setVu("#vuIn", 0);
  setVu("#vuOut", 0);
}

function setVu(sel, peak) {
  const el = $(sel);
  const db = peak > 0 ? 20 * Math.log10(peak) : -60;
  el.style.width = `${Math.max(0, Math.min(100, ((db + 60) / 60) * 100))}%`;
  el.classList.toggle("clip", peak >= 0.99);
}

function showLiveStats(m) {
  // diagnostica: invia al server lo stato del ponte (visibile nei log del container)
  if (live.ws?.readyState === WebSocket.OPEN && (!live.lastDiag || performance.now() - live.lastDiag > 2000)) {
    live.lastDiag = performance.now();
    const outSel = $("#liveOutput");
    live.ws.send(JSON.stringify({
      type: "diag", ctx: live.ctx?.state, sr: live.ctx?.sampleRate,
      input: live.stream?.getAudioTracks()[0]?.label,
      inputChannels: live.stream?.getAudioTracks()[0]?.getSettings().channelCount,
      output: outSel.hidden ? "(scelta uscita non supportata dal browser)" : outSel.selectedOptions[0]?.text,
      sinkId: live.ctx?.sinkId, inPeak: +m.inPeak.toFixed(4), outPeak: +m.outPeak.toFixed(4),
      fill: m.fill, target: m.target, underruns: m.underruns, baseLatency: live.ctx?.baseLatency, outputLatency: live.ctx?.outputLatency,
    }));
  }
  setVu("#vuIn", m.inPeak);
  setVu("#vuOut", m.outPeak);
  const ctx = live.ctx;
  if (!ctx) return;
  // stima: buffer di uscita del browser + buffer anti-scatti + cattura e motore (~2 quanti + 2 cicli JACK)
  const sec = (ctx.baseLatency || 0) + (ctx.outputLatency || 0) + m.fill / ctx.sampleRate + 0.02;
  $("#liveInfo").textContent = `ritardo ≈ ${Math.round(sec * 1000)} ms` + (m.underruns ? ` · scatti ${m.underruns}` : "");
}

// ---------------------------------------------------------------- WebSocket
function connectWs() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => {
    $("#conn").classList.add("ok");
    // dopo una riconnessione (es. riavvio del motore) lo stato locale può essere vecchio:
    // lo si ricarica, altrimenti la prima modifica rimanderebbe al server una pedaliera superata
    if (connectWs.connectedOnce) refreshState().catch(() => {});
    connectWs.connectedOnce = true;
  };
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
  live.sr = s.samplerate;
  const dsp = Math.min(100, s.dsp);
  const fill = $("#dspFill");
  fill.style.width = `${dsp}%`;
  fill.style.background = dsp > 85 ? "var(--accent)" : dsp > 65 ? "var(--warn)" : "var(--ok)";
  $("#dspValue").textContent = `${dsp.toFixed(0)}%`;
  const ms = ((s.buffer / s.samplerate) * 1000).toFixed(1);
  $("#engineInfo").textContent = `${s.samplerate / 1000} kHz · ${s.buffer} (${ms} ms) · xrun ${s.xruns}`;
}

async function refreshState() {
  await Promise.all(["nam", "ir", "di"].map(loadFiles));
  S.board = await api("GET", "/api/board");
  await loadPresets();
  render();
}

// ---------------------------------------------------------------- tastiera
document.addEventListener("keydown", (e) => {
  if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
  if ($("#boardView").hidden) return;   // nel negozio i tasti non agiscono sulla pedaliera
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
// ---------------------------------------------------------------- viste: pedaliera / negozio
let store = null;

function showView(view) {
  $("#boardView").hidden = view !== "board";
  $("#storeView").hidden = view !== "store";
  document.querySelectorAll(".views button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  history.replaceState(null, "", view === "store" ? "#store" : location.pathname);
  if (view === "store") store.show();
}

// blocco selezionato che può ricevere un file di questo tipo (nam / ir)
function fileTarget(kind) {
  const b = S.selected?.type === "block" ? findBlock(S.selected.id) : null;
  return b && S.models[b.model]?.file?.kind === kind ? b : null;
}

// un profilo installato dal negozio: nel blocco selezionato oppure in un blocco nuovo
async function useFile(kind, name, { installOnly = false } = {}) {
  await loadFiles(kind);
  if (installOnly) return render();
  const target = fileTarget(kind);
  if (target) {
    await setBlockFile(target.id, name);
  } else {
    const modelId = S.catalog.models.find((m) => m.file?.kind === kind)?.id;
    const b = cloneBoard();
    const block = { id: newId(), kind: "block", model: modelId, enabled: true, params: {}, file: name };
    const line = (b.chain2 || []).length ? b.chain2 : b.chain;   // in fondo alla catena
    placeAt(line, line.length, 0, block);
    S.selected = { type: "block", id: block.id };
    await guarded(() => putBoard(b));
  }
  showView("board");
  toast(`"${name.replace(/\.(nam|wav)$/i, "")}" caricato nella catena`);
}

function setupViews() {
  store = createStore({ api, toast, root: $("#storeView"), onUse: useFile, getTarget: fileTarget });
  document.querySelectorAll(".views button").forEach((b) => (b.onclick = () => showView(b.dataset.view)));
  if (location.hash === "#store") showView("store");
}

// sfumature condivise dalle manopole SVG
function installSvgDefs() {
  document.body.insertAdjacentHTML("afterbegin", `<svg width="0" height="0" style="position:absolute" aria-hidden="true">
    <defs><radialGradient id="knobCap" cx="38%" cy="30%" r="80%">
      <stop offset="0" stop-color="#e3e6ea"/><stop offset=".45" stop-color="#8d949e"/><stop offset="1" stop-color="#2f333a"/>
    </radialGradient></defs></svg>`);
}

async function init() {
  installSvgDefs();
  S.catalog = await api("GET", "/api/catalog");
  for (const m of S.catalog.models) S.models[m.id] = m;
  for (const c of S.catalog.categories) S.cats[c.id] = c;
  await Promise.all(["nam", "ir", "di"].map(loadFiles));
  S.board = await api("GET", "/api/board");
  await loadPresets();
  setupPresets();
  setupTestbar();
  setupLive();
  setupViews();
  $("#rowsBtn").onclick = toggleRow2;
  render();
  connectWs();
}

init().catch((e) => toast(`Impossibile avviare l'interfaccia: ${e.message}`, true));
