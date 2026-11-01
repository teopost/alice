// Alice: negozio dei profili NAM e IR di TONE3000.
// Le chiamate passano dal motore (/api/t3k/...), che conserva l'accesso all'account
// e scarica i modelli direttamente tra i file di Alice.

const GEARS = [
  ["", "Tutti"], ["amp", "Ampli"], ["amp-cab", "Ampli + cassa"], ["pedal", "Pedali"],
  ["outboard", "Outboard"], ["cab", "Casse"],
];
const GEAR_LABEL = { amp: "Ampli", "amp-cab": "Ampli + cassa", pedal: "Pedale", outboard: "Outboard", cab: "Cassa",
                     space: "Ambiente", experimental: "Sperimentale" };
const TABS = [
  ["trending", "Di tendenza"], ["latest", "Novità"], ["favorited", "Preferiti"],
  ["downloaded", "Scaricati"], ["installed", "Installati"],
];
const SIZE_LABEL = { standard: "Standard", lite: "Lite", feather: "Feather", nano: "Nano", custom: "Custom" };

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const num = (n) => (n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : String(n ?? 0));

export function createStore({ api, toast, root, onUse, getTarget }) {
  const st = { status: null, tab: "trending", gear: "", page: 1, items: [], loading: false, detail: null };

  // ------------------------------------------------------------ struttura
  root.innerHTML = `
    <div class="store-head">
      <div class="store-brand">
        <span class="t3k-logo">TONE3000</span>
        <span class="store-sub">Profili NAM e IR della community</span>
      </div>
      <div class="store-account"></div>
    </div>
    <div class="store-body"></div>
    <div class="store-detail" hidden></div>`;
  const $ = (sel) => root.querySelector(sel);
  const body = $(".store-body");
  const detail = $(".store-detail");

  // ------------------------------------------------------------ accesso
  async function refreshStatus() {
    st.status = await api("GET", "/api/t3k/status");
    renderAccount();
    render();
  }

  function renderAccount() {
    const acc = $(".store-account");
    const s = st.status;
    if (!s?.configured) { acc.innerHTML = ""; return; }
    if (!s.connected) {
      acc.innerHTML = `<button class="btn primary" data-act="connect">Collega account TONE3000</button>`;
    } else {
      const u = s.user || {};
      const name = u.display_name || u.username || "account collegato";
      acc.innerHTML = `${u.avatar_url ? `<img class="avatar" src="${esc(u.avatar_url)}" alt="">` : '<span class="avatar"></span>'}
        <span class="acc-name">${esc(name)}</span>
        <button class="btn ghost" data-act="logout">Scollega</button>`;
    }
  }

  // il popup va aperto subito nel gestore del clic, altrimenti il browser lo blocca
  async function startFlow(prompt, extra = {}) {
    const w = 480, h = 720;
    const popup = window.open("about:blank", "alice_t3k",
      `width=${w},height=${h},left=${Math.round(screenX + (outerWidth - w) / 2)},top=${Math.round(screenY + (outerHeight - h) / 2)}`);
    try {
      const { url } = await api("POST", "/api/t3k/authorize", { origin: location.origin, prompt, ...extra });
      if (popup) popup.location.href = url;
      else location.href = url;   // popup bloccato: si va a TONE3000 nella stessa scheda
    } catch (e) {
      popup?.close();
      toast(e.message, true);
    }
  }

  async function onFlowResult(msg) {
    if (msg?.type !== "alice_t3k") return;
    if (!msg.ok) return toast(msg.error || "Accesso a TONE3000 non riuscito", true);
    await refreshStatus();
    if (msg.tone_id) openDetail(msg.tone_id);
    else if (!msg.canceled) toast("Account TONE3000 collegato");
  }
  window.addEventListener("message", (e) => { if (e.origin === location.origin) onFlowResult(e.data); });
  try { new BroadcastChannel("alice_t3k").onmessage = (e) => onFlowResult(e.data); } catch { /* browser vecchio */ }

  // ------------------------------------------------------------ contenuto
  function render() {
    const s = st.status;
    if (!s) { body.innerHTML = '<div class="store-empty">Caricamento…</div>'; return; }
    if (!s.configured) return renderKeyForm();
    if (!s.connected) {
      body.innerHTML = `<div class="store-empty">
        <div class="t3k-logo big">TONE3000</div>
        <p>Collega il tuo account TONE3000 per sfogliare e installare migliaia di profili NAM e IR.</p>
        <button class="btn primary" data-act="connect">Collega account</button>
        <p class="hint">Si apre una finestra di TONE3000: accedi e autorizza Alice.</p></div>`;
      return;
    }
    body.innerHTML = `
      <div class="store-browse">
        <button class="btn primary" data-act="browse">Sfoglia tutto il catalogo su TONE3000</button>
        <button class="btn" data-act="browse-ir">Sfoglia le IR</button>
        <span class="hint">Cerca sul sito, scegli un profilo e torni qui per installarlo.</span>
      </div>
      <div class="store-tabs">${TABS.map(([id, label]) =>
        `<button class="store-tab${st.tab === id ? " active" : ""}" data-tab="${id}">${label}</button>`).join("")}</div>
      ${st.tab === "installed" ? "" : `<div class="store-gears">${GEARS.map(([id, label]) =>
        `<button class="chip${st.gear === id ? " active" : ""}" data-gear="${id}">${label}</button>`).join("")}</div>`}
      <div class="store-grid"></div>
      <div class="store-more"></div>`;
    renderGrid();
  }

  function renderKeyForm() {
    body.innerHTML = `<div class="store-empty">
      <div class="t3k-logo big">TONE3000</div>
      <p>Per collegare Alice a TONE3000 serve la <b>chiave pubblica</b> della tua API (inizia con <code>t3k_pub_</code>).</p>
      <form class="key-form"><input type="text" name="key" placeholder="t3k_pub_…" spellcheck="false" autocomplete="off">
      <button class="btn primary">Salva</button></form>
      <p class="hint">La trovi su tone3000.com → Settings → API Keys. Non usare la chiave segreta (t3k_cs_…).</p></div>`;
    body.querySelector("form").onsubmit = async (e) => {
      e.preventDefault();
      try {
        st.status = await api("PUT", "/api/t3k/key", { key: e.target.key.value });
        renderAccount();
        render();
      } catch (err) { toast(err.message, true); }
    };
  }

  async function load(reset = true) {
    if (reset) { st.page = 1; st.items = []; }
    st.loading = true;
    renderGrid();
    try {
      if (st.tab === "installed") {
        st.items = await api("GET", "/api/t3k/library");
        st.totalPages = 1;
      } else {
        const q = new URLSearchParams({ gear: st.gear, page: st.page });
        const res = await api("GET", `/api/t3k/feed/${st.tab}?${q}`);
        st.items = reset ? res.data : st.items.concat(res.data);
        st.totalPages = res.total_pages || 1;
      }
    } catch (e) {
      toast(e.message, true);
      if (/collega|scaduta/i.test(e.message)) refreshStatus();
    } finally {
      st.loading = false;
      renderGrid();
    }
  }

  function renderGrid() {
    const grid = body.querySelector(".store-grid");
    if (!grid) return;
    if (st.loading && !st.items.length) {
      grid.innerHTML = Array.from({ length: 8 }, () => '<div class="tone-card skeleton"><div class="cover"></div><div class="tc-body"><span></span><span></span></div></div>').join("");
      return;
    }
    if (!st.items.length) {
      const empty = { favorited: "Non hai ancora preferiti su TONE3000.", downloaded: "Non hai ancora scaricato profili da TONE3000.",
                      installed: "Nessun profilo installato da TONE3000." }[st.tab] || "Nessun profilo trovato.";
      grid.innerHTML = `<div class="store-empty small">${empty}</div>`;
    } else if (st.tab === "installed") {
      grid.innerHTML = st.items.map(installedCard).join("");
    } else {
      grid.innerHTML = st.items.map(toneCard).join("");
    }
    const more = body.querySelector(".store-more");
    more.innerHTML = st.tab !== "installed" && st.page < st.totalPages
      ? `<button class="btn" data-act="more"${st.loading ? " disabled" : ""}>Carica altri</button>` : "";
  }

  const cover = (img, gear) => img
    ? `<div class="cover" style="background-image:url('${esc(img)}')"></div>`
    : `<div class="cover none"><span>${esc(GEAR_LABEL[gear] || "NAM")}</span></div>`;

  function toneCard(t) {
    const creator = t.user?.display_name || t.user?.username || "";
    return `<button class="tone-card" data-tone="${t.id}">
      ${cover(t.images?.[0], t.gear)}
      <span class="badge fmt">${t.format === "ir" ? "IR" : "NAM"}</span>
      <div class="tc-body">
        <span class="tc-title">${esc(t.title)}</span>
        <span class="tc-creator">${esc(creator)}${t.user?.is_verified ? ' <span class="verified" title="Creatore verificato">✓</span>' : ""}</span>
        <span class="tc-meta"><span class="gear">${esc(GEAR_LABEL[t.gear] || t.gear || "")}</span>
          <span title="Download">⬇ ${num(t.downloads_count)}</span><span title="Preferiti">♥ ${num(t.favorites_count)}</span></span>
      </div></button>`;
  }

  function installedCard(f) {
    return `<div class="tone-card installed">
      ${cover(f.image, f.gear)}
      <span class="badge fmt">${f.kind === "ir" ? "IR" : "NAM"}</span>
      <div class="tc-body">
        <span class="tc-title">${esc(f.title)}</span>
        <span class="tc-creator">${esc(f.model)}${f.creator ? " · " + esc(f.creator) : ""}</span>
        <span class="tc-actions"><button class="btn primary" data-use="${esc(f.name)}" data-kind="${f.kind}">${useLabel(f.kind)}</button>
          ${f.tone_id ? `<button class="btn ghost" data-tone="${f.tone_id}">Dettagli</button>` : ""}</span>
      </div></div>`;
  }

  const useLabel = (kind) => (getTarget(kind) ? "Usa nel blocco" : "Aggiungi alla catena");

  // ------------------------------------------------------------ scheda di un profilo
  async function openDetail(toneId) {
    detail.hidden = false;
    detail.innerHTML = '<div class="sd-panel"><div class="store-empty">Caricamento…</div></div>';
    try {
      st.detail = await api("GET", `/api/t3k/tones/${toneId}`);
      renderDetail();
    } catch (e) {
      detail.hidden = true;
      toast(e.message, true);
    }
  }

  function renderDetail() {
    const { tone: t, models } = st.detail;
    const creator = t.user?.display_name || t.user?.username || "";
    const supported = t.format === "nam" || t.format === "ir";
    detail.innerHTML = `<div class="sd-panel" role="dialog" aria-label="${esc(t.title)}">
      <button class="sd-close icon-btn" data-act="close" title="Chiudi" aria-label="Chiudi"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
      <div class="sd-top">
        ${cover(t.images?.[0], t.gear)}
        <div class="sd-info">
          <span class="badge fmt inline">${t.format === "ir" ? "IR" : "NAM"}</span>
          <h2>${esc(t.title)}</h2>
          <div class="sd-creator">di <a href="${esc(t.user?.url)}" target="_blank" rel="noopener">${esc(creator)}</a></div>
          <div class="tc-meta"><span class="gear">${esc(GEAR_LABEL[t.gear] || t.gear || "")}</span>
            <span>⬇ ${num(t.downloads_count)}</span><span>♥ ${num(t.favorites_count)}</span>
            ${t.license ? `<span title="Licenza">${esc(t.license.toUpperCase())}</span>` : ""}</div>
          ${t.makes?.length ? `<div class="sd-tags">${t.makes.map((m) => `<span class="chip static">${esc(m.name)}</span>`).join("")}</div>` : ""}
          <a class="sd-link" href="${esc(t.url)}" target="_blank" rel="noopener">Apri su TONE3000 ↗</a>
        </div>
      </div>
      ${t.description ? `<p class="sd-desc">${esc(t.description)}</p>` : ""}
      <h3>Modelli <small>${models.length}</small></h3>
      ${supported ? "" : `<p class="hint">Formato "${esc(t.format)}" non supportato da Alice.</p>`}
      <div class="sd-models">${models.map((m) => `
        <div class="sd-model">
          <div class="sm-name">${esc(m.name)}</div>
          <div class="sm-meta">${esc(SIZE_LABEL[m.size] || m.size || "")}${m.architecture_version ? ` · A${esc(m.architecture_version)}`.replace("Acustom", "Custom") : ""}</div>
          ${m.installed
            ? `<button class="btn" data-use="${esc(m.installed)}" data-kind="${t.format === "ir" ? "ir" : "nam"}">✓ ${useLabel(t.format === "ir" ? "ir" : "nam")}</button>`
            : `<button class="btn primary" data-install="${m.id}"${supported ? "" : " disabled"}>Installa</button>`}
        </div>`).join("")}</div>
    </div>`;
  }

  async function install(modelId, btn) {
    const { tone } = st.detail;
    btn.disabled = true;
    btn.textContent = "Download…";
    try {
      const res = await api("POST", "/api/t3k/install", { tone_id: tone.id, model_id: Number(modelId) });
      const m = st.detail.models.find((x) => x.id === Number(modelId));
      if (m) m.installed = res.name;
      toast(`Installato: ${res.name}`);
      renderDetail();
      await onUse(res.kind, res.name, { installOnly: true });
    } catch (e) {
      toast(e.message, true);
      btn.disabled = false;
      btn.textContent = "Installa";
    }
  }

  // ------------------------------------------------------------ eventi
  root.addEventListener("click", (e) => {
    const el = e.target.closest("[data-act],[data-tab],[data-gear],[data-tone],[data-install],[data-use]");
    if (!el) {
      if (e.target === detail) detail.hidden = true;   // clic fuori dal pannello
      return;
    }
    const d = el.dataset;
    if (d.act === "connect") startFlow(null);
    else if (d.act === "logout") api("POST", "/api/t3k/logout").then(refreshStatus);
    else if (d.act === "browse") startFlow("select_tone");
    else if (d.act === "browse-ir") startFlow("select_tone", { format: "ir" });
    else if (d.act === "more") { st.page += 1; load(false); }
    else if (d.act === "close") detail.hidden = true;
    else if (d.tab) { st.tab = d.tab; render(); load(); }
    else if (d.gear !== undefined) { st.gear = d.gear; render(); load(); }
    else if (d.install) install(d.install, el);
    else if (d.use) { detail.hidden = true; onUse(d.kind, d.use); }
    else if (d.tone) openDetail(d.tone);
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !detail.hidden) detail.hidden = true; });

  return {
    async show() {
      if (!st.status) await refreshStatus().catch((e) => toast(e.message, true));
      if (st.status?.connected && !st.items.length && !st.loading) load();
      else render();
    },
    refreshStatus,
  };
}
