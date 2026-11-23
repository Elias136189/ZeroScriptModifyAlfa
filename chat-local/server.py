#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Chat local: muestra el buzon compartido de las IAs (ZeroScript) en una pagina web.

Lee los mensajes JSON del mismo buzon que usan msg_send / msg_inbox / msg_reply
y deja escribir mensajes nuevos como "usuario". Solo escucha en 127.0.0.1.

La deteccion de agentes conectados es perezosa: solo se ejecuta cuando la
pagina pide /api/messages, como maximo cada SCAN_EVERY_S segundos (15 s por
defecto). Asi no queda un PowerShell corriendo para siempre cuando nadie mira
el chat.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mailbox_store  # noqa: E402

APP_VERSION = "2.4.0"
CONFIG_PATH = ROOT / "pc_agent_config.json"
USER_NAME = "usuario"
UNSIGNED_NAME = "sin-firma"
DEFAULT_PORT = 8765
MAX_CONTENT_LENGTH = 1_000_000
MAX_BODY_CHARS = 20_000
MAX_SUBJECT_CHARS = 200
MAX_HOPS = 6
SCAN_EVERY_S = max(5, int(os.environ.get("CHAT_LOCAL_SCAN_SECONDS", "15") or "15"))

PORT = int(os.environ.get("CHAT_LOCAL_PORT", str(DEFAULT_PORT)) or DEFAULT_PORT)
MAILBOX = mailbox_store.resolve_mailbox_dir(None, base_dir=ROOT)

# ── Deteccion de agentes conectados ─────────────────────────────────────────
MAX_DEPTH = 8
STOP_AT = {"explorer.exe", "services.exe", "svchost.exe", "wininit.exe", "winlogon.exe", "system"}
RULES = [
    ("antigravity", ("antigravity",)),
    ("opencode", ("opencode",)),
    ("codex", ("codex",)),
    ("kimi", ("kimi",)),
]
CONNECTED: list[str] | None = None
_connected_lock = threading.Lock()
_scan_lock = threading.Lock()
_last_scan = 0.0
_scanning = False

PS_LIST = (
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
    "Get-CimInstance Win32_Process | "
    "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
)


def log(message: str) -> None:
    print(f"[chat-local] {message}", file=sys.stderr, flush=True)


def list_processes():
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    out = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_LIST],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=20, **kwargs,
    )
    if out.returncode != 0:
        detail = (out.stderr or "").strip().splitlines()
        msg = detail[0] if detail else f"exit code {out.returncode}"
        raise RuntimeError(f"powershell Win32_Process fallo: {msg}")
    raw = (out.stdout or "").strip()
    if not raw:
        return []
    data = json.loads(raw)
    return data if isinstance(data, list) else [data]


_AGENT_FLAG_RE = re.compile(r"(?:^|\s)--agent(?:=|\s+)\"?([A-Za-z0-9_.-]+)\"?")


def detect_connected() -> list[str]:
    rows = list_processes()
    by_pid = {row.get("ProcessId"): row for row in rows}
    found: dict[str, str] = {}
    for row in rows:
        raw_cmd = str(row.get("CommandLine") or "")
        cmd = raw_cmd.lower()
        name = (row.get("Name") or "").lower()
        if "pc_agent_mcp" not in cmd or not name.startswith("python"):
            continue
        m = _AGENT_FLAG_RE.search(raw_cmd)
        if m:
            ag = mailbox_store.clean_agent_name(m.group(1), "")
            if ag and ag.casefold() != "zeroscript":
                found[ag.casefold()] = ag
                continue
        current = by_pid.get(row.get("ParentProcessId"))
        for _ in range(MAX_DEPTH):
            if not current:
                break
            name = (current.get("Name") or "").lower()
            if name in STOP_AT:
                break
            if name == "claude.exe":
                found["claude"] = "claude"
                break
            text = name + " " + (current.get("CommandLine") or "").lower()
            hit = next((key for key, patterns in RULES if any(p in text for p in patterns)), None)
            if hit:
                found[hit.casefold()] = hit
                break
            current = by_pid.get(current.get("ParentProcessId"))
    return [found[k] for k in sorted(found)]


def _scan_once() -> None:
    global CONNECTED, _last_scan, _scanning
    try:
        result = detect_connected()
    except Exception as exc:
        log(f"no se pudo detectar agentes conectados: {exc}")
        result = None
    if result is not None:
        with _connected_lock:
            CONNECTED = result
    with _scan_lock:
        _last_scan = time.monotonic()
        _scanning = False


def request_scan() -> None:
    """Lanza una deteccion en segundo plano, como mucho cada SCAN_EVERY_S s."""
    global _scanning
    with _scan_lock:
        if _scanning or (time.monotonic() - _last_scan) < SCAN_EVERY_S:
            return
        _scanning = True
    threading.Thread(target=_scan_once, daemon=True).start()


def get_connected() -> list[str] | None:
    with _connected_lock:
        return None if CONNECTED is None else list(CONNECTED)


# ── Buzon ───────────────────────────────────────────────────────────────────
_cache_lock = threading.Lock()
_cache_signature: tuple[tuple[str, int, int], ...] | None = None
_cache_messages: list[dict[str, Any]] = []


def _mailbox_signature() -> tuple[tuple[str, int, int], ...]:
    entries: list[tuple[str, int, int]] = []
    try:
        with os.scandir(MAILBOX) as iterator:
            for entry in iterator:
                if entry.name.startswith(".") or not entry.name.lower().endswith(".json"):
                    continue
                try:
                    if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                        continue
                    stat = entry.stat(follow_symlinks=False)
                    entries.append((entry.name, stat.st_mtime_ns, stat.st_size))
                except OSError:
                    continue
    except OSError:
        return ()
    return tuple(sorted(entries))


def load_messages() -> list[dict[str, Any]]:
    """Devuelve los mensajes; solo vuelve a leer si cambio el directorio."""
    global _cache_signature, _cache_messages
    signature = _mailbox_signature()
    with _cache_lock:
        if signature == _cache_signature:
            return list(_cache_messages)
    items = mailbox_store.iter_messages(MAILBOX, log=log)
    messages = [message for _path, message in items]
    with _cache_lock:
        _cache_signature = signature
        _cache_messages = messages
    return list(messages)


def invalidate_cache() -> None:
    global _cache_signature
    with _cache_lock:
        _cache_signature = None


def read_config() -> dict[str, Any]:
    candidates = [CONFIG_PATH, ROOT / "pc_agent_config.example.json"]
    for cfg_path in candidates:
        try:
            if cfg_path.is_file():
                data = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict):
                    return data
        except Exception as exc:
            log(f"no se pudo leer {cfg_path}: {exc}")
    return {}


def config_int(config: dict[str, Any], key: str, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(config.get(key) or default)))
    except Exception:
        return default


def resolve_mailbox(cli_value: str = "") -> Path:
    config = read_config()
    raw = cli_value or os.environ.get("ZS_PC_MAILBOX_DIR") or config.get("mailbox_dir")
    return mailbox_store.resolve_mailbox_dir(raw, base_dir=ROOT)


def write_message(sender: str, to: str, body: str, subject: str = "", reply_to: str | None = None,
                  hops: int = 0) -> dict[str, Any]:
    _message_id, _path, message = mailbox_store.create_message(
        MAILBOX,
        sender=sender,
        to=to,
        body=body,
        subject=subject,
        reply_to=reply_to,
        hops=hops,
        max_body=MAX_BODY_CHARS,
    )
    invalidate_cache()
    return message


BROADCAST_DEFAULT = ["claude", "opencode"]


def broadcast_recipients() -> list[str]:
    """Agentes a los que llega un mensaje para 'todos': los conectados; si aun
    no se sabe cuales son, claude y opencode."""
    connected = get_connected()
    names = [name for name in (connected or []) if name]
    return names or list(BROADCAST_DEFAULT)


class Handler(BaseHTTPRequestHandler):
    server_version = f"ChatLocal/{APP_VERSION}"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code: int, body: Any, ctype: str = "application/json; charset=utf-8") -> None:
        data = body if isinstance(body, bytes) else str(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; connect-src 'self'; "
            "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        self.end_headers()
        if code != 204:
            self.wfile.write(data)

    def _allowed_origins(self) -> set[str]:
        return {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}

    def _same_origin(self) -> bool:
        origin = (self.headers.get("Origin") or "").strip().lower()
        if origin and origin in self._allowed_origins():
            return True
        # Algunos navegadores omiten Origin en POST del mismo origen; en ese
        # caso la cabecera Fetch Metadata sigue distinguiendo la pagina local.
        return (self.headers.get("Sec-Fetch-Site") or "").strip().lower() == "same-origin"

    def _local_only(self) -> bool:
        """Solo 127.0.0.1/localhost y, si hay Origin, el de esta pagina."""
        host = (self.headers.get("Host") or "").strip().lower()
        host = host.rsplit(":", 1)[0]
        if host not in ("127.0.0.1", "localhost"):
            return False
        origin = (self.headers.get("Origin") or "").strip().lower()
        return not origin or origin in self._allowed_origins()

    def do_GET(self) -> None:
        if not self._local_only():
            self._send(403, json.dumps({"error": "forbidden"}))
            return
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            page = HERE / "chat.html"
            if not page.is_file():
                self._send(500, "chat.html no existe en chat-local", "text/plain; charset=utf-8")
                return
            self._send(200, page.read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/messages":
            request_scan()
            self._send(200, json.dumps({
                "user": USER_NAME,
                "connected": get_connected(),
                "messages": load_messages(),
                "version": APP_VERSION,
                "mailbox": str(MAILBOX),
            }, ensure_ascii=False))
        elif path == "/api/health":
            self._send(200, json.dumps({
                "ok": True,
                "app": "chat-local",
                "version": APP_VERSION,
                "port": PORT,
                "mailbox": str(MAILBOX),
                "messages": len(load_messages()),
            }, ensure_ascii=False))
        elif path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self) -> None:
        if not self._local_only():
            self._send(403, json.dumps({"error": "forbidden"}))
            return
        if self.path.split("?", 1)[0] != "/api/send":
            self._send(404, json.dumps({"error": "not found"}))
            return
        try:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise ValueError("Content-Length requerido")
            length = int(raw_length)
            if length <= 0 or length > MAX_CONTENT_LENGTH:
                raise ValueError("tamano de peticion no valido")
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("el cuerpo debe ser un objeto JSON")

            to = mailbox_store.clean_agent_name(data.get("to"), "")
            if not to:
                raise ValueError("falta 'to' o no es un nombre de agente valido")
            body = data.get("body")
            if not isinstance(body, str) or not body.strip():
                raise ValueError("falta 'body' o esta vacio")
            if len(body) > MAX_BODY_CHARS:
                raise ValueError(f"'body' supera el maximo de {MAX_BODY_CHARS} caracteres")
            subject = str(data.get("subject") or "").strip()[:MAX_SUBJECT_CHARS]

            raw_from = str(data.get("from") or "").strip()
            sender = mailbox_store.clean_agent_name(raw_from, "") if raw_from else ""
            if raw_from and not sender:
                raise ValueError("'from' no es un nombre de agente valido")
            if sender == USER_NAME:
                if not self._same_origin():
                    self._send(403, json.dumps({"error": "usuario solo desde la pagina local"}))
                    return
            elif not sender:
                sender = UNSIGNED_NAME

            if to.casefold() == "todos":
                # Difusion: un mensaje por agente. Solo desde la pagina local
                # (sender == usuario ya paso la comprobacion de mismo origen).
                if sender != USER_NAME:
                    raise ValueError("'todos' solo se puede usar desde la pagina local")
                recipients = broadcast_recipients()
                sent = [write_message(sender, name, body, subject, None, 0) for name in recipients]
                self._send(200, json.dumps(
                    {"ok": True, "message": sent[0], "sent_to": recipients}, ensure_ascii=False))
                return

            reply_to = str(data.get("reply_to") or "").strip() or None
            hops = 0
            if reply_to:
                found = mailbox_store.find_message(MAILBOX, reply_to, log=log)
                if found is None:
                    raise ValueError(f"reply_to no existe en el buzon: {reply_to}")
                original_path, original = found
                try:
                    previous = int(original.get("hops") or 0)
                except Exception:
                    previous = 0
                hops = previous + 1
                if hops > MAX_HOPS:
                    raise ValueError(f"cadena de respuestas demasiado larga (maximo {MAX_HOPS} saltos)")
                try:
                    mailbox_store.mark_read(original_path, original)
                except Exception as exc:
                    log(f"no se pudo marcar leido {original_path.name}: {exc}")

            message = write_message(sender, to, body, subject, reply_to, hops)
            self._send(200, json.dumps({"ok": True, "message": message}, ensure_ascii=False))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        except Exception as exc:
            log(f"error en /api/send: {exc}")
            self._send(500, json.dumps({"ok": False, "error": "error interno"}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chat local del buzon de IAs")
    parser.add_argument("--port", type=int, default=int(os.environ.get("CHAT_LOCAL_PORT", str(DEFAULT_PORT)) or DEFAULT_PORT))
    parser.add_argument("--mailbox", default="", help="Carpeta del buzon (por defecto pc_agent_config.json)")
    parser.add_argument("--version", action="version", version=f"Chat local {APP_VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    global PORT, MAILBOX, MAX_BODY_CHARS, MAX_HOPS
    args = build_parser().parse_args(argv)
    PORT = max(1, min(65535, int(args.port)))
    config = read_config()
    MAILBOX = resolve_mailbox(args.mailbox)
    MAX_BODY_CHARS = config_int(config, "max_message_chars", 20_000, 1000, 2_000_000)
    MAX_HOPS = config_int(config, "max_hops", 6, 1, 100)
    mailbox_store.ensure_dir(MAILBOX)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    print(f"Chat local {APP_VERSION} en http://127.0.0.1:{PORT}  (buzon: {MAILBOX})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Detenido.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
