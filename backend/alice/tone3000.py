"""Client TONE3000 (https://www.tone3000.com/api) lato motore.

Il motore fa da intermediario: conserva chiave e token in data/state/tone3000.json,
così l'account resta collegato tra un riavvio e l'altro e da qualunque dispositivo
apra l'interfaccia, e scarica i modelli direttamente nella cartella dei file.

Login con OAuth 2.0 + PKCE (S256). Il piano gratuito dell'API permette solo i flussi
OAuth (select_tone, load_tone) e le liste limitate: created, favorited, downloaded,
trending e latest. La ricerca libera richiede un accordo commerciale.
"""
import base64
import hashlib
import json
import logging
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger("alice.tone3000")

API = "https://www.tone3000.com"
FEEDS = ("trending", "latest", "favorited", "downloaded", "created")
GEARS = ("amp", "amp-cab", "pedal", "outboard", "cab", "space", "experimental")
USER_AGENT = "Alice/1.0 (+https://github.com/teopost/alice)"


class T3KError(RuntimeError):
    def __init__(self, message, status=500):
        super().__init__(message)
        self.status = status


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class Tone3000:
    def __init__(self, state_file: Path, client_id: str | None = None):
        self.state_file = state_file
        self.lock = threading.RLock()
        self.pending = {}  # state -> {"verifier", "redirect_uri", "created"}
        self.data = {}
        if state_file.is_file():
            try:
                self.data = json.loads(state_file.read_text())
            except ValueError:
                log.warning("stato TONE3000 illeggibile, lo ignoro")
        if client_id:
            self.data["client_id"] = client_id

    # --- stato ---------------------------------------------------------------
    def _save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2))
        tmp.chmod(0o600)
        tmp.replace(self.state_file)

    @property
    def client_id(self):
        return self.data.get("client_id")

    def set_client_id(self, key: str):
        key = key.strip()
        if not key.startswith("t3k_pub_"):
            raise T3KError("serve la chiave pubblica (inizia con t3k_pub_), non quella segreta", 400)
        with self.lock:
            if key != self.data.get("client_id"):
                self.data = {"client_id": key}  # chiave nuova: i vecchi token non valgono più
            self._save()

    def status(self):
        tokens = self.data.get("tokens")
        return {"configured": bool(self.client_id), "connected": bool(tokens),
                "user": self.data.get("user")}

    def logout(self):
        with self.lock:
            self.data.pop("tokens", None)
            self.data.pop("user", None)
            self._save()

    # --- OAuth -----------------------------------------------------------------
    def authorize_url(self, redirect_uri: str, prompt: str | None = None, extra: dict | None = None):
        if not self.client_id:
            raise T3KError("chiave TONE3000 non configurata", 400)
        verifier = _b64url(secrets.token_bytes(32))
        state = _b64url(secrets.token_bytes(16))
        challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
        now = time.time()
        with self.lock:
            # i flussi abbandonati scadono dopo 30 minuti
            self.pending = {k: v for k, v in self.pending.items() if now - v["created"] < 1800}
            self.pending[state] = {"verifier": verifier, "redirect_uri": redirect_uri, "created": now}
        params = {"client_id": self.client_id, "redirect_uri": redirect_uri, "response_type": "code",
                  "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
                  "menubar": "true", **(extra or {})}
        if prompt:
            params["prompt"] = prompt
        return f"{API}/api/v1/oauth/authorize?{urllib.parse.urlencode(params)}"

    def complete(self, state: str, code: str | None):
        """Verifica lo state e scambia il codice con i token."""
        with self.lock:
            flow = self.pending.pop(state or "", None)
        if flow is None:
            raise T3KError("richiesta di accesso scaduta o non valida: riprova", 400)
        if not code:
            raise T3KError("accesso annullato", 400)
        tokens = self._token_request({"grant_type": "authorization_code", "code": code,
                                      "code_verifier": flow["verifier"], "redirect_uri": flow["redirect_uri"],
                                      "client_id": self.client_id})
        with self.lock:
            self.data["tokens"] = tokens
            self._save()
        try:
            user = self.get("/api/v1/user")
            with self.lock:
                self.data["user"] = {k: user.get(k) for k in ("id", "username", "display_name", "avatar_url", "url")}
                self._save()
        except T3KError as e:
            log.warning("profilo TONE3000 non letto: %s", e)

    def _token_request(self, form):
        body = urllib.parse.urlencode(form).encode()
        req = urllib.request.Request(f"{API}/api/v1/oauth/token", data=body, method="POST",
                                     headers={"Content-Type": "application/x-www-form-urlencoded",
                                              "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise T3KError(f"TONE3000 ha rifiutato l'accesso ({e.code})", e.code)
        except urllib.error.URLError as e:
            raise T3KError(f"TONE3000 non raggiungibile: {e.reason}", 502)
        return {"access_token": d["access_token"], "refresh_token": d.get("refresh_token"),
                "expires_at": time.time() + float(d.get("expires_in", 3600))}

    def _access_token(self, force_refresh=False):
        with self.lock:
            tokens = self.data.get("tokens")
            if not tokens:
                raise T3KError("account TONE3000 non collegato", 401)
            # rinnovo un minuto prima della scadenza, uno alla volta (c'è il lock)
            if force_refresh or time.time() > tokens["expires_at"] - 60:
                try:
                    new = self._token_request({"grant_type": "refresh_token", "client_id": self.client_id,
                                               "refresh_token": tokens.get("refresh_token") or ""})
                except T3KError as e:
                    if e.status in (400, 401):
                        # sessione finita: serve un nuovo accesso
                        self.data.pop("tokens", None)
                        self._save()
                        raise T3KError("sessione TONE3000 scaduta: ricollega l'account", 401)
                    raise
                if not new.get("refresh_token"):
                    new["refresh_token"] = tokens.get("refresh_token")
                self.data["tokens"] = tokens = new
                self._save()
            return tokens["access_token"]

    # --- richieste autenticate ----------------------------------------------------
    def _request(self, path_or_url, raw=False, max_bytes=None):
        url = path_or_url if path_or_url.startswith("http") else API + path_or_url
        if not url.startswith(API + "/"):
            raise T3KError("indirizzo non consentito", 400)  # il token va solo a TONE3000
        for attempt in (0, 1):
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self._access_token(attempt == 1)}",
                                                       "User-Agent": USER_AGENT, "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    dep = r.headers.get("X-Tone3000-Deprecations")
                    if dep:
                        log.warning("TONE3000: parametri deprecati su %s: %s", url, dep)
                    data = r.read(max_bytes + 1 if max_bytes else -1)
                    if max_bytes and len(data) > max_bytes:
                        raise T3KError("file troppo grande", 413)
                    return data if raw else json.loads(data)
            except urllib.error.HTTPError as e:
                if e.code == 401 and attempt == 0:
                    continue  # token scaduto nel frattempo: rinnova e riprova una volta
                if e.code == 429:
                    raise T3KError("troppe richieste a TONE3000: riprova tra un minuto", 429)
                if e.code == 403:
                    raise T3KError("TONE3000 non consente questa operazione con la chiave gratuita", 403)
                if e.code == 404:
                    raise T3KError("non trovato su TONE3000 (forse è privato o è stato rimosso)", 404)
                raise T3KError(f"errore da TONE3000 ({e.code})", e.code)
            except urllib.error.URLError as e:
                raise T3KError(f"TONE3000 non raggiungibile: {e.reason}", 502)
        raise T3KError("accesso a TONE3000 non riuscito", 401)

    def get(self, path, params=None):
        if params:
            path += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
        return self._request(path)

    def download(self, url, max_bytes=200 * 1024 * 1024):
        return self._request(url, raw=True, max_bytes=max_bytes)

    # --- funzioni di alto livello ---------------------------------------------------
    def feed(self, kind, gear=None, page=None, query=None):
        if kind not in FEEDS:
            raise T3KError(f"lista sconosciuta: {kind}", 404)
        if gear and gear not in GEARS:
            raise T3KError(f"tipo sconosciuto: {gear}", 400)
        params = {"gear": gear}
        if kind not in ("trending", "latest"):
            params.update(page=page, page_size=24, query=query)
        return self.get(f"/api/v1/tones/{kind}", params)

    def tone(self, tone_id):
        tone = self.get(f"/api/v1/tones/{int(tone_id)}")
        models = []
        # senza "architecture" l'API restituisce solo A1 + Custom: si chiedono anche gli A2
        for arch in (None, "2"):
            page = 1
            while True:
                res = self.get("/api/v1/models", {"tone_id": int(tone_id), "architecture": arch,
                                                  "page": page, "page_size": 100})
                models += res.get("data", [])
                if page >= res.get("total_pages", 1):
                    break
                page += 1
        seen, unique = set(), []
        for m in models:
            if m["id"] not in seen:
                seen.add(m["id"])
                unique.append(m)
        return {"tone": tone, "models": unique}
