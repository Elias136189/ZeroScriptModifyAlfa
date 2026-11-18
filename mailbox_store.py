#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Almacenamiento comun del buzon compartido de ZeroScript.

Lo usan ``pc_agent_mcp.py`` (herramientas msg_*) y ``chat-local/server.py``
(pagina web). Un mensaje es un JSON por archivo dentro de ``mailbox_dir``.
Este modulo concentra las reglas para que ambos caminos validen, lean y
escriban exactamente igual:

* nombres de agente simples y acotados;
* nada de enlaces simbolicos ni rutas fuera del buzon;
* escritura atomica (temporal + os.replace);
* JSON corrupto o demasiado grande se ignora y se registra;
* cuerpo y asunto con limite de tamano.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

MAX_BODY_CHARS = 20_000
MAX_SUBJECT_CHARS = 200
MAX_MESSAGE_BYTES = 2_000_000
NAME_MAX = 32
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def clean_agent_name(value: Any, fallback: str = "agent", max_len: int = NAME_MAX) -> str:
    """Devuelve un nombre seguro para usar como from/to."""
    text = NAME_RE.sub("", str(value or "")).strip("._-")
    return text[:max_len] or fallback


def safe_filename_part(value: Any, fallback: str = "agent", max_len: int = 24) -> str:
    """Parte de nombre de archivo: solo ASCII seguro, sin rutas."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._-")
    return cleaned[:max_len] or fallback


def resolve_mailbox_dir(
    raw: Any = None,
    *,
    base_dir: Path,
    default: Path | None = None,
) -> Path:
    """Resuelve mailbox_dir igual en el MCP y en el servidor del chat.

    Las rutas relativas se resuelven contra ``base_dir`` (la carpeta del
    proyecto), no contra el directorio actual del proceso.
    """
    text = str(raw or "").strip()
    if text:
        text = os.path.expandvars(os.path.expanduser(text))
        path = Path(text)
        if not path.is_absolute():
            path = Path(base_dir) / path
    else:
        path = default or (Path.home() / "Documents" / "AI-Shared" / "mailbox")
    try:
        return path.resolve()
    except Exception:
        return path.absolute()


def ensure_dir(root: Path) -> Path:
    """Crea el buzon si hace falta y devuelve su ruta resuelta."""
    root = Path(root)
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(f"cannot create mailbox directory {root}: {exc}")
    if not root.is_dir():
        raise NotADirectoryError(f"mailbox path is not a directory: {root}")
    try:
        return root.resolve()
    except Exception:
        return root.absolute()


def message_is_valid(message: Any) -> bool:
    """Campos minimos que ambos lados necesitan para mostrar un mensaje."""
    return (
        isinstance(message, dict)
        and isinstance(message.get("id"), str) and bool(message["id"])
        and isinstance(message.get("from"), str) and bool(message["from"])
        and isinstance(message.get("to"), str) and bool(message["to"])
        and isinstance(message.get("body"), str)
    )


def read_message(
    path: Path,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any] | None:
    """Lee un mensaje; devuelve None si es corrupto, enorme o un symlink."""
    path = Path(path)
    try:
        if path.is_symlink():
            if log:
                log(f"mailbox: skipped symlink {path.name}")
            return None
        if path.stat().st_size > MAX_MESSAGE_BYTES:
            if log:
                log(f"mailbox: skipped oversized {path.name}")
            return None
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        if log:
            log(f"mailbox: skipped unreadable {path.name}: {exc}")
        return None
    if not message_is_valid(data):
        if log:
            log(f"mailbox: skipped malformed {path.name}")
        return None
    return data


def _sort_key(item: tuple[Path, dict[str, Any]]) -> tuple[float, str]:
    path, message = item
    raw_ts = str(message.get("ts") or "")
    try:
        stamp = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        try:
            stamp = path.stat().st_mtime
        except OSError:
            stamp = 0.0
    return (stamp, path.name)


def iter_messages(
    root: Path,
    log: Callable[[str], None] | None = None,
) -> list[tuple[Path, dict[str, Any]]]:
    """Lista los mensajes validos, del mas antiguo al mas nuevo.

    Solo mira archivos *.json directamente dentro del buzon. Ignora enlaces
    simbolicos, temporales .msg-* y cualquier cosa fuera de la carpeta.
    """
    root = Path(root)
    if not root.is_dir():
        return []
    try:
        entries = list(os.scandir(root))
    except OSError as exc:
        raise OSError(f"cannot read mailbox directory {root}: {exc}")
    root_resolved = ensure_dir(root)
    items: list[tuple[Path, dict[str, Any]]] = []
    for entry in entries:
        try:
            if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                continue
            if not entry.name.lower().endswith(".json") or entry.name.startswith(".msg-"):
                continue
            path = Path(entry.path)
            if path.parent.resolve() != root_resolved:
                continue
        except (OSError, ValueError) as exc:
            if log:
                log(f"mailbox: skipped {entry.name}: {exc}")
            continue
        message = read_message(path, log=log)
        if message is not None:
            items.append((path, message))
    items.sort(key=_sort_key)
    return items


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Escribe JSON en un temporal del mismo directorio y lo reemplaza."""
    path = Path(path)
    root = ensure_dir(path.parent)
    fd, temp_name = tempfile.mkstemp(prefix=".msg-", suffix=".tmp", dir=str(root))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def create_message(
    root: Path,
    *,
    sender: Any,
    to: Any,
    body: Any,
    subject: Any = None,
    reply_to: Any = None,
    hops: int = 0,
    max_body: int = MAX_BODY_CHARS,
) -> tuple[str, Path, dict[str, Any]]:
    """Crea un mensaje nuevo y devuelve (id, ruta, payload)."""
    recipient = clean_agent_name(to, "")
    if not recipient:
        raise ValueError("'to' is required and must be a non-empty agent name")
    sender_name = clean_agent_name(sender, "")
    if not sender_name:
        raise ValueError("sender identity is empty")
    if not isinstance(body, str):
        raise ValueError("'body' must be a string")
    if not body.strip():
        raise ValueError("'body' must not be empty")
    if len(body) > max_body:
        raise ValueError(
            f"'body' is {len(body)} characters; maximum is {max_body}. "
            "Split it into smaller messages or attach a file path instead."
        )
    subject_text = str(subject).strip() if isinstance(subject, str) else ""
    if len(subject_text) > MAX_SUBJECT_CHARS:
        subject_text = subject_text[:MAX_SUBJECT_CHARS]
    reply_id = str(reply_to).strip() if isinstance(reply_to, str) and reply_to.strip() else None
    if reply_id is not None and not ID_RE.fullmatch(reply_id):
        raise ValueError("'reply_to' must be a message id (letters, digits, _ or -)")
    try:
        hop_count = max(0, int(hops))
    except Exception:
        hop_count = 0
    root = ensure_dir(root)
    for attempt in range(20):
        now = datetime.now().astimezone()
        ts_ms = int(now.timestamp() * 1000) + attempt
        message_id = uuid.uuid4().hex
        filename = (
            f"{ts_ms:013d}"
            f"{safe_filename_part(sender_name, 'agent', 24)}"
            f"{message_id[:8]}.json"
        )
        path = root / filename
        if not path.exists():
            break
    else:
        raise RuntimeError("could not allocate a unique mailbox filename")
    message = {
        "id": message_id,
        "from": sender_name,
        "to": recipient,
        "subject": subject_text,
        "body": body,
        "ts": now.isoformat(timespec="milliseconds"),
        "reply_to": reply_id,
        "hops": hop_count,
        "read": False,
    }
    atomic_write_json(path, message)
    return message_id, path, message


def mark_read(path: Path, message: dict[str, Any]) -> dict[str, Any]:
    """Marca un mensaje como leido de forma atomica."""
    updated = dict(message)
    updated["read"] = True
    atomic_write_json(path, updated)
    return updated


def find_message(
    root: Path,
    message_id: str,
    log: Callable[[str], None] | None = None,
) -> tuple[Path, dict[str, Any]] | None:
    wanted = str(message_id or "").strip()
    if not wanted:
        return None
    for path, message in iter_messages(root, log=log):
        if str(message.get("id") or "") == wanted:
            return path, message
    return None


def truncate_body(text: str, limit: int) -> tuple[str, bool]:
    """Recorta un cuerpo a ``limit`` caracteres e indica si lo hizo."""
    value = str(text or "")
    if limit <= 0:
        return "", bool(value)
    if len(value) <= limit:
        return value, False
    marker = f"\n... [truncado: {len(value) - limit} caracteres]"
    keep = max(0, limit - len(marker))
    return value[:keep] + marker, True


def message_timestamp(path: Path, message: dict[str, Any]) -> float:
    """Timestamp del mensaje, con la fecha del archivo como respaldo."""
    raw_ts = str(message.get("ts") or "")
    try:
        return datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0


def archive_messages(
    root: Path,
    *,
    days: int = 30,
    apply: bool = False,
    log: Callable[[str], None] | None = None,
) -> tuple[int, int]:
    """Mueve a ``root/archive/YYYY-MM`` los mensajes leidos mas antiguos.

    Devuelve (movidos, conservados). Con ``apply=False`` solo cuenta.
    """
    root = ensure_dir(root)
    cutoff = time.time() - max(1, int(days)) * 86_400
    moved = 0
    kept = 0
    for path, message in iter_messages(root, log=log):
        if not bool(message.get("read", False)):
            kept += 1
            continue
        stamp = message_timestamp(path, message)
        if stamp > cutoff:
            kept += 1
            continue
        if apply:
            folder = root / "archive" / datetime.fromtimestamp(stamp).strftime("%Y-%m")
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / path.name
            if target.exists():
                target = folder / f"{path.stem}-{uuid.uuid4().hex[:8]}.json"
            os.replace(path, target)
        moved += 1
    return moved, kept
