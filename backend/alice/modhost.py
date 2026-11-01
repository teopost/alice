"""Client del protocollo testuale di mod-host (https://github.com/moddevices/mod-host)."""
import logging
import socket
import threading
import time

log = logging.getLogger("alice.modhost")


class ModHostError(RuntimeError):
    pass


class ModHost:
    """Connessione a mod-host.

    mod-host serve un client alla volta e, se avviato con -f, dopo aver accettato
    il socket comandi resta in attesa sul socket di feedback: vanno aperti
    entrambi, in quest'ordine. Il feedback va letto di continuo, altrimenti
    mod-host si blocca quando il buffer si riempie.
    """

    def __init__(self, host="127.0.0.1", port=5555, feedback_port=5556):
        self.addr = (host, port)
        self.fb_addr = (host, feedback_port)
        self.lock = threading.Lock()
        self.sock = None
        self.fb = None
        self.on_feedback = None  # callback(str)

    def connect(self, timeout=30.0):
        deadline = time.monotonic() + timeout
        while True:
            try:
                self.sock = socket.create_connection(self.addr, timeout=10)
                self.fb = socket.create_connection(self.fb_addr, timeout=10)
                break
            except OSError:
                for s in (self.sock, self.fb):
                    if s:
                        s.close()
                self.sock = self.fb = None
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.5)
        threading.Thread(target=self._drain_feedback, daemon=True).start()
        log.info("connesso a mod-host %s:%s", *self.addr)

    def _drain_feedback(self):
        self.fb.settimeout(None)
        buf = b""
        while True:
            try:
                chunk = self.fb.recv(4096)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            *msgs, buf = buf.split(b"\0")
            for m in msgs:
                if m and self.on_feedback:
                    self.on_feedback(m.decode(errors="replace"))

    def cmd(self, line, check=True):
        with self.lock:
            log.debug(">> %s", line)
            self.sock.sendall(line.encode() + b"\0")
            data = b""
            while not data.endswith(b"\0"):
                chunk = self.sock.recv(4096)
                if not chunk:
                    raise ModHostError("connessione con mod-host chiusa")
                data += chunk
        resp = data.rstrip(b"\0").decode()
        log.debug("<< %s", resp)
        parts = resp.split()
        code = int(parts[1]) if len(parts) > 1 and parts[0] == "resp" else -1
        if check and code < 0:
            raise ModHostError(f"'{line}' -> {resp}")
        return resp

    # --- comandi ---------------------------------------------------------
    def add(self, uri, instance):
        self.cmd(f"add {uri} {instance}")

    def remove(self, instance):
        self.cmd(f"remove {instance}", check=False)

    def remove_all(self):
        self.cmd("remove -1", check=False)

    def connect_ports(self, src, dst):
        self.cmd(f"connect {src} {dst}", check=False)

    def disconnect_ports(self, src, dst):
        self.cmd(f"disconnect {src} {dst}", check=False)

    def param_set(self, instance, symbol, value):
        self.cmd(f"param_set {instance} {symbol} {float(value)}")

    def patch_set(self, instance, prop, path):
        escaped = path.replace("\\", "\\\\").replace('"', '\\"')
        self.cmd(f'patch_set {instance} {prop} "{escaped}"')

    def bypass(self, instance, bypassed):
        self.cmd(f"bypass {instance} {1 if bypassed else 0}")
