#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vigilante de cambios en el sistema de archivos.

Uso:
  python vigilante_cambios.py run          Corre en primer plano (tarea programada)
  python vigilante_cambios.py start        Arranca en segundo plano (sin ventana)
  python vigilante_cambios.py ensure       Si es nueva PC (no esta en Inicio), lo instala y arranca
  python vigilante_cambios.py stop         Detiene la instancia en segundo plano
  python vigilante_cambios.py status       Estado y ruta del log actual
  python vigilante_cambios.py ver [N]      Ultimas N lineas del log de esta semana
  python vigilante_cambios.py contexto [N] Resumen compacto con diffs de los ultimos N cambios

Vigila la carpeta del proyecto y subcarpetas. Ignora __pycache__, .git, logs,
backups, assets, runtime y workspace_wake. Registra CREATED, MODIFIED, DELETED y
MOVED tanto de archivos como de carpetas (ignorando lecturas y guardados sin
cambio real de contenido) con un diff compacto en:
  - logs/registro_cambios/cambios_YYYY-WWW.log    (registro semanal legible)
  - logs/registro_cambios/cambios_recientes.jsonl (resumen estructurado para IAs)

Cuando un cambio llega desde pc_agent_mcp.py (pc_write / pc_edit), el autor se
etiqueta como mcp:<agente> (ej. mcp:claude, mcp:opencode, mcp:antigravity); en
caso contrario usa el usuario de Windows.
"""

from __future__ import annotations

import difflib
import getpass
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    _HAS_WATCHDOG = True
except ImportError:
    Observer = None  # type: ignore[assignment]
    FileSystemEventHandler = object  # type: ignore[assignment,misc]
    FileSystemEvent = Any  # type: ignore[assignment,misc]
    _HAS_WATCHDOG = False

# ─── CONFIG ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
REGISTRY_DIR = LOG_DIR / "registro_cambios"
PID_FILE = LOG_DIR / "vigilante_cambios.pid"
RECENT_JSONL = REGISTRY_DIR / "cambios_recientes.jsonl"
MCP_ACTIONS_JSONL = REGISTRY_DIR / "ultimas_acciones_mcp.jsonl"
ATTRIBUTION_JSONL = REGISTRY_DIR / ".atribucion_mcp.jsonl"

# Vida maxima de los archivos temporales de contexto para IAs (48 horas).
CONTEXT_TTL_HOURS = 48
CONTEXT_TTL_SECONDS = CONTEXT_TTL_HOURS * 3600
MCP_ACTIONS_MAX_ENTRIES = 40

IGNORE_DIRS = {"__pycache__", ".git", "logs", "backups", "assets", "workspace_wake", "runtime"}
IGNORE_NAMES = {"desktop.ini", "Thumbs.db"}
IGNORE_PREFIXES = ("~$", ".#")
IGNORE_SUFFIXES = (".swp", ".swx", "~", ".zs.lock")

DEBOUNCE_SECONDS = 0.5
ATTRIBUTION_WINDOW_SECONDS = 5.0
PENDING_DELETE_DELAY_SECONDS = 0.12
RECENT_DELETE_WINDOW_SECONDS = 3.0

MAX_DIFF_BYTES = 256 * 1024       # Archivos de texto <= 256 KB generan diff
MAX_CACHE_BYTES = 16 * 1024 * 1024  # Tope de RAM para snapshots de texto
MAX_DIFF_LINES = 18
MAX_DIFF_CHARS = 1200
MAX_CREATED_PREVIEW_LINES = 6
MAX_LINE_LEN = 160

RECENT_MAX_ENTRIES = 200
RECENT_TRIM_THRESHOLD = 300
ATTRIBUTION_MAX_ENTRIES = 60
ATTRIBUTION_TRIM_THRESHOLD = 200

try:
    AUTHOR = os.environ.get("USERNAME") or getpass.getuser() or "desconocido"
except Exception:
    AUTHOR = "desconocido"
# ─────────────────────────────────────────────────────────────────────────

_IO_LOCK = threading.Lock()


def weekly_log_path() -> Path:
    """logs/registro_cambios/cambios_YYYY-WWW.log usando la semana y el año ISO."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    iso = datetime.now().isocalendar()
    return REGISTRY_DIR / f"cambios_{iso.year}-W{iso.week:02d}.log"


def should_ignore(path: str | Path) -> bool:
    p = Path(path)
    name = p.name
    if (
        name in IGNORE_NAMES
        or name.startswith(IGNORE_PREFIXES)
        or name.endswith(IGNORE_SUFFIXES)
        or (".zs-" in name and name.endswith(".tmp"))
    ):
        return True
    try:
        rel = p.resolve().relative_to(PROJECT_ROOT)
    except Exception:
        return True
    return any(part in IGNORE_DIRS for part in rel.parts)


def rel_path(path: str | Path) -> str:
    try:
        return Path(path).resolve().relative_to(PROJECT_ROOT).as_posix()
    except Exception:
        return str(path)


def _clip_line(line: str, limit: int = MAX_LINE_LEN) -> str:
    if len(line) <= limit:
        return line
    return line[: limit - 3] + "..."


def read_text_snapshot(path: str | Path) -> str | None:
    """Lee un archivo de texto pequeno para calcular diffs; None si es binario o grande."""
    p = Path(path)
    try:
        st = p.stat()
        if st.st_size > MAX_DIFF_BYTES:
            return None
        data = p.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:8192]:
        return None
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def build_compact_diff(
    old_text: str | None,
    new_text: str | None,
    *,
    event: str = "modified",
) -> tuple[str, str]:
    """Devuelve (stats, diff_compacto) para un cambio de archivo de texto."""
    ev = event.lower()
    if ev in ("modified", "created") and old_text is not None and new_text is not None:
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        raw = list(difflib.unified_diff(old_lines, new_lines, n=1, lineterm=""))
        body: list[str] = []
        added = 0
        removed = 0
        for line in raw:
            if line.startswith("---") or line.startswith("+++"):
                continue
            if line.startswith("+"):
                added += 1
            elif line.startswith("-"):
                removed += 1
            body.append(line)
        if added == 0 and removed == 0:
            return "sin cambios", ""
        parts = []
        if added:
            parts.append(f"+{added}")
        if removed:
            parts.append(f"-{removed}")
        stats = " ".join(parts)

        out_lines: list[str] = []
        total_chars = 0
        omitted = 0
        for idx, line in enumerate(body):
            clipped = _clip_line(line)
            if len(out_lines) >= MAX_DIFF_LINES or total_chars + len(clipped) + 1 > MAX_DIFF_CHARS:
                omitted = len(body) - idx
                break
            out_lines.append(clipped)
            total_chars += len(clipped) + 1
        if omitted > 0:
            out_lines.append(f"... (+{omitted} lineas mas en el diff)")
        return stats, "\n".join(out_lines)

    if ev == "created" and new_text is not None:
        new_lines = new_text.splitlines()
        stats = f"+{len(new_lines)}" if new_lines else "+0"
        preview: list[str] = []
        total_chars = 0
        for line in new_lines:
            if not line.strip():
                continue
            clipped = "+ " + _clip_line(line)
            if len(preview) >= MAX_CREATED_PREVIEW_LINES or total_chars + len(clipped) + 1 > 500:
                break
            preview.append(clipped)
            total_chars += len(clipped) + 1
        if len(new_lines) > len(preview) and preview:
            preview.append(f"... ({len(new_lines)} lineas en total)")
        return stats, "\n".join(preview)

    if ev == "deleted" and old_text is not None:
        old_lines = old_text.splitlines()
        return (f"-{len(old_lines)}" if old_lines else "-0"), ""

    return "", ""


def _entry_epoch(item: dict[str, Any]) -> float:
    """Devuelve el timestamp epoch de un registro JSONL (desde 'epoch' o parseando 'ts')."""
    raw_epoch = item.get("epoch")
    if isinstance(raw_epoch, (int, float)) and raw_epoch > 0:
        return float(raw_epoch)
    ts_str = str(item.get("ts") or "").strip()
    if ts_str:
        try:
            return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError:
            pass
    return 0.0


def _atomic_write_lines(path: Path, lines: list[str]) -> None:
    """Reescribe `path` de forma atomica, o lo borra si `lines` esta vacia."""
    if not lines:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return
    content = "\n".join(lines) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".ttl-", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
    except OSError:
        try:
            path.write_text(content, encoding="utf-8")
        except OSError:
            pass


def _load_and_prune_ttl_jsonl(
    path: Path,
    *,
    ttl_seconds: float = CONTEXT_TTL_SECONDS,
    max_entries: int = RECENT_MAX_ENTRIES,
    now: float | None = None,
) -> list[dict[str, Any]]:
    """Lee un JSONL temporal, purga registros con mas de 48h y borra el archivo si queda vacio."""
    if not path.is_file():
        return []
    now_ts = time.time() if now is None else now
    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    kept_objs: list[dict[str, Any]] = []
    kept_lines: list[str] = []
    changed = False
    for raw in raw_lines:
        stripped = raw.strip()
        if not stripped:
            changed = True
            continue
        try:
            obj = json.loads(stripped)
        except Exception:
            changed = True
            continue
        if not isinstance(obj, dict):
            changed = True
            continue
        ep = _entry_epoch(obj)
        if ep <= 0 or (now_ts - ep) > ttl_seconds:
            changed = True
            continue
        kept_objs.append(obj)
        kept_lines.append(stripped)

    if len(kept_objs) > max_entries:
        kept_objs = kept_objs[-max_entries:]
        kept_lines = kept_lines[-max_entries:]
        changed = True

    if changed:
        _atomic_write_lines(path, kept_lines)
    return kept_objs


def _trim_jsonl_if_needed(path: Path, threshold: int, keep: int) -> None:
    """Recorta un archivo JSONL a sus ultimas `keep` lineas de forma atomica."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    if len(lines) <= threshold:
        return
    _atomic_write_lines(path, lines[-keep:])


def record_mcp_attribution(path: str | Path, agent: str, tool: str = "") -> None:
    """Anota que agente MCP esta escribiendo `path` para que el vigilante lo atribuya."""
    if should_ignore(path):
        return
    rel = rel_path(path)
    clean_agent = str(agent or "").strip() or "zeroscript"
    entry = {
        "ts": time.time(),
        "agent": clean_agent,
        "tool": str(tool or "").strip(),
        "path": rel,
    }
    try:
        REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        with _IO_LOCK:
            with ATTRIBUTION_JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            _trim_jsonl_if_needed(
                ATTRIBUTION_JSONL,
                ATTRIBUTION_TRIM_THRESHOLD,
                ATTRIBUTION_MAX_ENTRIES,
            )
    except OSError:
        pass


def resolve_author(
    path_rel: str,
    *,
    now: float | None = None,
    consumed: dict[str, float] | None = None,
) -> tuple[str, str]:
    """Devuelve (autor, tool). Si un agente MCP edito recientemente esa ruta, devuelve mcp:<agente>."""
    if not ATTRIBUTION_JSONL.is_file():
        return AUTHOR, ""
    now_ts = time.time() if now is None else now
    try:
        lines = ATTRIBUTION_JSONL.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return AUTHOR, ""
    target = path_rel.replace("\\", "/")
    consumed_until = consumed.get(target, 0.0) if consumed is not None else 0.0
    for raw in reversed(lines[-80:]):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except Exception:
            continue
        if not isinstance(item, dict):
            continue
        ts = float(item.get("ts") or 0.0)
        if now_ts - ts > ATTRIBUTION_WINDOW_SECONDS:
            break
        if now_ts - ts < -2.0:
            continue
        if str(item.get("path") or "").replace("\\", "/") == target:
            if ts <= consumed_until:
                continue
            agent = str(item.get("agent") or "").strip()
            tool = str(item.get("tool") or "").strip()
            if agent:
                if consumed is not None:
                    consumed[target] = ts
                    if len(consumed) > 200:
                        cutoff = now_ts - ATTRIBUTION_WINDOW_SECONDS - 5.0
                        for k in [k for k, v in consumed.items() if v < cutoff]:
                            consumed.pop(k, None)
                return f"mcp:{agent}", tool
    return AUTHOR, ""


def append_change_record(
    event: str,
    kind: str,
    path_rel: str,
    *,
    author: str | None = None,
    dest_rel: str = "",
    stats: str = "",
    diff: str = "",
    tool: str = "",
    ts: str | None = None,
) -> dict[str, Any]:
    """Escribe el cambio en el log semanal legible y en cambios_recientes.jsonl."""
    now_epoch = time.time()
    ts_str = ts or datetime.fromtimestamp(now_epoch).strftime("%Y-%m-%d %H:%M:%S")
    who = author or AUTHOR
    ev_upper = event.upper()
    if ev_upper == "MOVED" and dest_rel:
        path_col = f"{path_rel} -> {dest_rel}"
    else:
        path_col = path_rel
    header = f"{ts_str} | {who} | {ev_upper:8s} | {kind} | {path_col}"
    if stats:
        header += f" | {stats}"

    record: dict[str, Any] = {
        "ts": ts_str,
        "epoch": round(now_epoch, 3),
        "author": who,
        "event": ev_upper,
        "kind": kind,
        "path": path_rel,
    }
    if dest_rel:
        record["dest"] = dest_rel
    if stats:
        record["stats"] = stats
    if tool:
        record["tool"] = tool
    if diff:
        record["diff"] = diff

    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    with _IO_LOCK:
        try:
            with weekly_log_path().open("a", encoding="utf-8") as fh:
                fh.write(header + "\n")
                if diff:
                    for dline in diff.splitlines():
                        fh.write("    " + dline + "\n")
        except Exception as exc:
            print(f"[vigilante] Error escribiendo log: {exc}", file=sys.stderr)

        try:
            with RECENT_JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            _load_and_prune_ttl_jsonl(
                RECENT_JSONL,
                ttl_seconds=CONTEXT_TTL_SECONDS,
                max_entries=RECENT_MAX_ENTRIES,
                now=now_epoch,
            )
        except Exception as exc:
            print(f"[vigilante] Error escribiendo jsonl: {exc}", file=sys.stderr)

    return record


def record_mcp_change(
    path: str | Path,
    *,
    agent: str,
    tool: str,
    old_text: str | None,
    new_text: str | None,
    existed_before: bool,
) -> None:
    """Registra un cambio desde pc_agent_mcp.py cuando el vigilante en segundo plano no corre."""
    if should_ignore(path):
        return
    if old_text is not None and new_text is not None and old_text == new_text:
        return
    ev = "modified" if existed_before else "created"
    stats, diff = build_compact_diff(old_text, new_text, event=ev)
    if ev == "modified" and stats == "sin cambios":
        return
    clean_agent = str(agent or "").strip() or "zeroscript"
    append_change_record(
        ev,
        "FILE",
        rel_path(path),
        author=f"mcp:{clean_agent}",
        stats=stats,
        diff=diff,
        tool=tool,
    )


def _parse_legacy_log_tail(limit: int, *, ttl_seconds: float = CONTEXT_TTL_SECONDS) -> list[dict[str, Any]]:
    """Fallback si aun no existe cambios_recientes.jsonl: lee el log semanal mas nuevo (<48h)."""
    if not REGISTRY_DIR.is_dir():
        return []
    logs = sorted(REGISTRY_DIR.glob("cambios_*.log"))
    if not logs:
        return []
    try:
        lines = logs[-1].read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    now_ts = time.time()
    records: list[dict[str, Any]] = []
    for line in lines:
        if not line or line.startswith("    "):
            if records and line.startswith("    "):
                prev_diff = records[-1].get("diff", "")
                records[-1]["diff"] = (prev_diff + "\n" if prev_diff else "") + line[4:]
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 5:
            rec: dict[str, Any] = {
                "ts": parts[0],
                "author": parts[1],
                "event": parts[2],
                "kind": parts[3],
                "path": parts[4],
            }
            if len(parts) >= 6 and parts[5]:
                rec["stats"] = parts[5]
            ep = _entry_epoch(rec)
            if ep > 0 and (now_ts - ep) <= ttl_seconds:
                records.append(rec)
    return records[-max(1, limit):]


def read_recent_changes(limit: int = 15) -> list[dict[str, Any]]:
    """Lee los ultimos `limit` cambios registrados en las ultimas 48h (mas antiguo -> mas reciente)."""
    with _IO_LOCK:
        items = _load_and_prune_ttl_jsonl(
            RECENT_JSONL,
            ttl_seconds=CONTEXT_TTL_SECONDS,
            max_entries=RECENT_MAX_ENTRIES,
        )
    if items:
        return items[-max(1, limit):]
    return _parse_legacy_log_tail(limit, ttl_seconds=CONTEXT_TTL_SECONDS)


def _summarize_mcp_args(tool: str, args: dict[str, Any]) -> str:
    a = args or {}
    if tool == "pc_read":
        p = str(a.get("path") or ".")
        off = a.get("offset")
        lim = a.get("limit")
        extra = []
        if off:
            extra.append(f"offset={off}")
        if lim:
            extra.append(f"limit={lim}")
        return f"{p} ({', '.join(extra)})" if extra else p
    if tool in ("pc_write", "pc_edit", "pc_list"):
        return str(a.get("path") or ".")
    if tool == "pc_glob":
        return f"pattern={a.get('pattern')!r} path={a.get('path') or '.'}"
    if tool == "pc_grep":
        inc = f" include={a.get('include')}" if a.get("include") else ""
        return f"pattern={a.get('pattern')!r} path={a.get('path') or '.'}{inc}"
    if tool == "pc_shell":
        cmd = _clip_line(str(a.get("command") or "").replace("\n", " ").strip(), 100)
        cwd = f" (cwd={a.get('cwd')})" if a.get("cwd") else ""
        return f"{cmd}{cwd}"
    if tool == "msg_send":
        return f"to={a.get('to')} subject={_clip_line(str(a.get('subject') or ''), 40)!r}"
    if tool == "msg_reply":
        return f"id={a.get('id')}"
    if tool in ("msg_inbox", "msg_wait"):
        return f"as={a.get('as')}" if a.get("as") else ""
    return _clip_line(json.dumps(a, ensure_ascii=False), 80)


def _summarize_mcp_outcome(tool: str, result_text: str) -> str:
    txt = str(result_text or "").strip()
    if not txt:
        return ""
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    if not lines:
        return ""
    if tool == "pc_shell":
        exit_ln = next((ln for ln in lines if ln.startswith("Exit code:")), "")
        body_ln = next(
            (
                ln for ln in lines
                if not ln.startswith(("Command:", "Directory:", "Exit code:", "Elapsed:", "--- stdout ---", "--- stderr ---"))
            ),
            "",
        )
        combined = f"{exit_ln} | {body_ln}" if (exit_ln and body_ln) else (exit_ln or body_ln or lines[0])
        return _clip_line(combined, 110)
    return _clip_line(lines[0], 110)


def record_mcp_action(
    agent: str,
    tool: str,
    args: dict[str, Any],
    result_text: str,
    is_error: bool = False,
) -> None:
    """Bitacora temporal (48h) de pasos MCP ('caja negra' ante cortes de cuota)."""
    now_epoch = time.time()
    if tool == "pc_system_info":
        # Solo purgar entradas caducadas (>48h), sin ensuciar la bitacora con consultas de estado.
        with _IO_LOCK:
            _load_and_prune_ttl_jsonl(
                MCP_ACTIONS_JSONL,
                ttl_seconds=CONTEXT_TTL_SECONDS,
                max_entries=MCP_ACTIONS_MAX_ENTRIES,
                now=now_epoch,
            )
            _load_and_prune_ttl_jsonl(
                RECENT_JSONL,
                ttl_seconds=CONTEXT_TTL_SECONDS,
                max_entries=RECENT_MAX_ENTRIES,
                now=now_epoch,
            )
        return

    alias = str((args or {}).get("as") or "").strip()
    clean_agent = alias or str(agent or "").strip() or "zeroscript"
    record = {
        "ts": datetime.fromtimestamp(now_epoch).strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": round(now_epoch, 3),
        "author": f"mcp:{clean_agent}",
        "tool": tool,
        "target": _summarize_mcp_args(tool, args or {}),
        "status": "ERROR" if is_error else "OK",
        "outcome": _summarize_mcp_outcome(tool, result_text),
    }
    try:
        REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        with _IO_LOCK:
            with MCP_ACTIONS_JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            _load_and_prune_ttl_jsonl(
                MCP_ACTIONS_JSONL,
                ttl_seconds=CONTEXT_TTL_SECONDS,
                max_entries=MCP_ACTIONS_MAX_ENTRIES,
                now=now_epoch,
            )
    except OSError:
        pass


def read_recent_mcp_actions(limit: int = 15) -> list[dict[str, Any]]:
    """Lee las ultimas `limit` acciones MCP de las ultimas 48h (y borra las caducadas)."""
    with _IO_LOCK:
        items = _load_and_prune_ttl_jsonl(
            MCP_ACTIONS_JSONL,
            ttl_seconds=CONTEXT_TTL_SECONDS,
            max_entries=MCP_ACTIONS_MAX_ENTRIES,
        )
    return items[-max(1, limit):]


def format_recent_mcp_actions(limit: int = 15, max_chars: int = 2500) -> tuple[str, int, int]:
    """Formatea los ultimos pasos ejecutados por cualquier IA en las ultimas 48h."""
    items = read_recent_mcp_actions(limit=max(limit, MCP_ACTIONS_MAX_ENTRIES))
    total = len(items)
    if not items:
        return "(sin actividad MCP en las ultimas 48h)", 0, 0
    selected = items[-max(1, limit):]
    lines_rev: list[str] = []
    used = 0
    for rec in reversed(selected):
        ts = rec.get("ts", "")
        author = rec.get("author", "?")
        tool = rec.get("tool", "?")
        target = str(rec.get("target") or "").strip()
        status = rec.get("status", "OK")
        outcome = str(rec.get("outcome") or "").strip()
        target_part = f" | {target}" if target else ""
        outcome_part = f" ({outcome})" if outcome else ""
        line = f"- {ts} | {author} | {tool}{target_part} -> {status}{outcome_part}"
        if lines_rev and used + len(line) + 1 > max_chars:
            break
        lines_rev.append(line)
        used += len(line) + 1
    lines = list(reversed(lines_rev))
    return "\n".join(lines), len(lines), total


def _format_single_record(rec: dict[str, Any], *, include_diff: bool = True) -> str:
    ts = rec.get("ts", "")
    author = rec.get("author", "?")
    event = rec.get("event", "?")
    kind = rec.get("kind", "FILE")
    path = rec.get("path", "?")
    dest = rec.get("dest", "")
    stats = rec.get("stats", "")
    path_part = f"{path} -> {dest}" if event == "MOVED" and dest else path
    kind_prefix = "[DIR] " if kind == "DIR" else ""
    stats_part = f" ({stats})" if stats else ""
    header = f"- {ts} | {author} | {event} | {kind_prefix}{path_part}{stats_part}"
    diff = str(rec.get("diff") or "").strip() if include_diff else ""
    if not diff:
        return header
    indented = "\n".join("    " + ln for ln in diff.splitlines())
    return header + "\n" + indented


def format_recent_changes(limit: int = 12, max_chars: int = 6000) -> tuple[str, int, int]:
    """Devuelve (texto_resumen, mostrados, total_en_buffer) acotado a `max_chars`.

    Prioriza conservar el diff completo de los cambios mas recientes.
    """
    records = read_recent_changes(limit=max(limit, 30))
    total = len(records)
    if not records:
        return "(sin cambios recientes registrados)", 0, 0
    selected = records[-max(1, limit):]

    # Construir desde el mas reciente hacia atras para respetar max_chars sin cortar el ultimo cambio.
    blocks_rev: list[str] = []
    used = 0
    for rec in reversed(selected):
        block = _format_single_record(rec, include_diff=True)
        if blocks_rev and used + len(block) + 1 > max_chars:
            # Intentar incluir al menos la linea de cabecera sin diff
            compact = _format_single_record(rec, include_diff=False)
            if used + len(compact) + 1 > max_chars:
                break
            blocks_rev.append(compact)
            used += len(compact) + 1
            continue
        if not blocks_rev and len(block) > max_chars:
            block = block[: max(200, max_chars - 24)] + "\n    ... [truncado]"
        blocks_rev.append(block)
        used += len(block) + 1

    blocks = list(reversed(blocks_rev))
    return "\n".join(blocks), len(blocks), total


def _pid_alive(pid: int) -> bool:
    """Comprueba si un PID existe y sigue activo (sin enviarle ninguna senal)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return bool(ok) and code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def is_vigilante_running() -> bool:
    pid = _read_pid()
    return bool(pid and _pid_alive(pid))


def get_watcher_context(limit: int = 12, max_chars: int = 6000) -> tuple[dict[str, Any], str]:
    """Informacion estructurada + resumen legible (48h) para incrustar en pc_system_info."""
    act_budget = min(2200, max(800, max_chars // 3))
    chg_budget = max(1500, max_chars - act_budget)
    act_text, act_shown, act_total = format_recent_mcp_actions(limit=15, max_chars=act_budget)
    chg_text, chg_shown, chg_total = format_recent_changes(limit=limit, max_chars=chg_budget)
    meta = {
        "running": is_vigilante_running(),
        "ttl_hours": CONTEXT_TTL_HOURS,
        "log_file": rel_path(weekly_log_path()),
        "recent_file": rel_path(RECENT_JSONL),
        "actions_file": rel_path(MCP_ACTIONS_JSONL),
        "shown": chg_shown,
        "total_recent": chg_total,
        "mcp_actions_shown": act_shown,
        "mcp_actions_total": act_total,
    }
    combined = (
        f"Recent MCP activity (last {CONTEXT_TTL_HOURS}h, {act_shown}/{act_total} shown, newest last):\n"
        f"{act_text}\n\n"
        f"Recent project file changes (vigilante, last {CONTEXT_TTL_HOURS}h, {chg_shown}/{chg_total} shown, newest last):\n"
        f"{chg_text}"
    )
    return meta, combined


class ChangeHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._last: dict[str, tuple[str, float]] = {}
        # Cache de (mtime_ns, size) para detectar cambios reales de contenido
        self._file_state: dict[str, tuple[int, int]] = {}
        # Cache de texto previo para calcular diffs compactos sin bloquear
        self._file_text: dict[str, str] = {}
        self._cache_bytes = 0
        # Buffer breve para reconocer reemplazos delete+create (ej. os.replace / git checkout)
        self._recently_deleted: dict[str, tuple[float, str | None]] = {}
        self._pending_deletes: dict[str, threading.Timer] = {}
        # Evita atribuir un cambio manual posterior a una edicion MCP previa (ruta -> ultimo ts consumido)
        self._consumed_attributions: dict[str, float] = {}
        self._prime_state()

    def _cancel_pending_delete(self, path: str) -> bool:
        """Cancela un DELETED pendiente de un reemplazo atomico; True si existia."""
        timer = self._pending_deletes.pop(path, None)
        if timer is not None:
            timer.cancel()
            return True
        return False

    def _flush_pending_delete(self, path: str, stats: str) -> None:
        with self._lock:
            if path not in self._pending_deletes:
                return
            self._pending_deletes.pop(path, None)
            if os.path.exists(path):
                return
            self._emit("deleted", False, path, stats=stats)

    def _set_text_cache(self, path: str, text: str | None) -> None:
        old = self._file_text.pop(path, None)
        if old is not None:
            self._cache_bytes -= len(old)
        if text is None:
            return
        if self._cache_bytes + len(text) > MAX_CACHE_BYTES:
            return
        self._file_text[path] = text
        self._cache_bytes += len(text)

    def _pop_text_cache(self, path: str) -> str | None:
        old = self._file_text.pop(path, None)
        if old is not None:
            self._cache_bytes -= len(old)
        return old

    def _prune_deleted(self, now: float) -> None:
        expired = [k for k, (ts, _) in self._recently_deleted.items() if now - ts > RECENT_DELETE_WINDOW_SECONDS]
        for k in expired:
            self._recently_deleted.pop(k, None)

    def _prime_state(self) -> None:
        """Precarga (st_mtime_ns, st_size) y texto de los archivos actuales al iniciar."""
        for root, dirs, files in os.walk(PROJECT_ROOT):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for name in files:
                if (
                    name in IGNORE_NAMES
                    or name.startswith(IGNORE_PREFIXES)
                    or name.endswith(IGNORE_SUFFIXES)
                    or (".zs-" in name and name.endswith(".tmp"))
                ):
                    continue
                full = os.path.join(root, name)
                st = self._get_file_state(full)
                if st is not None:
                    self._file_state[full] = st
                    if st[1] <= MAX_DIFF_BYTES:
                        self._set_text_cache(full, read_text_snapshot(full))

    def _get_file_state(self, path: str) -> tuple[int, int] | None:
        """Devuelve (st_mtime_ns, st_size) o None si no existe/no accesible."""
        try:
            st = os.stat(path)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def _has_real_change(self, path: str) -> tuple[bool, int, int]:
        """Devuelve (cambio_real, prev_size, cur_size)."""
        current = self._get_file_state(path)
        if current is None:
            self._file_state.pop(path, None)
            return False, -1, -1
        prev = self._file_state.get(path)
        if prev is None:
            self._file_state[path] = current
            return True, -1, current[1]
        if prev != current:
            self._file_state[path] = current
            return True, prev[1], current[1]
        return False, prev[1], current[1]

    def _debounced(self, path: str, event_type: str, *, allow_created_fill: bool = False) -> bool:
        """Evita rafagas: mismo tipo en <DEBOUNCE_SECONDS, o MODIFIED vacio justo tras CREATED."""
        now = time.monotonic()
        prev = self._last.get(path)
        self._last[path] = (event_type, now)
        if prev is None:
            return False
        prev_type, prev_ts = prev
        if now - prev_ts > DEBOUNCE_SECONDS:
            return False
        if prev_type == event_type:
            return True
        if event_type == "modified" and prev_type == "created":
            return not allow_created_fill
        return False

    def _emit(
        self,
        event_type: str,
        is_directory: bool,
        src_path: str,
        *,
        dest_path: str = "",
        stats: str = "",
        diff: str = "",
    ) -> None:
        kind = "DIR" if is_directory else "FILE"
        src_rel = rel_path(src_path)
        dest_rel = rel_path(dest_path) if dest_path else ""
        lookup_rel = dest_rel if (event_type == "moved" and dest_rel) else src_rel
        # pc_agent_mcp solo tiene pc_write/pc_edit (no pc_delete), asi que DELETED nunca se atribuye a MCP
        if event_type == "deleted":
            author, tool = AUTHOR, ""
        else:
            author, tool = resolve_author(lookup_rel, consumed=self._consumed_attributions)
        append_change_record(
            event_type,
            kind,
            src_rel,
            author=author,
            dest_rel=dest_rel,
            stats=stats,
            diff=diff,
            tool=tool,
        )

    def _handle_file_write(self, path: str, event_type: str) -> None:
        """Procesa una creacion o modificacion real de archivo y genera su diff compacto."""
        replaced_atomically = self._cancel_pending_delete(path)
        prev_text = self._file_text.get(path)
        effective_event = event_type
        if prev_text is None:
            self._prune_deleted(time.monotonic())
            recent = self._recently_deleted.pop(path, None)
            if recent is not None:
                prev_text = recent[1]
                effective_event = "modified"
            elif replaced_atomically:
                effective_event = "modified"
        elif replaced_atomically and event_type == "created":
            effective_event = "modified"

        new_text = read_text_snapshot(path)
        if effective_event == "modified" and prev_text is not None and new_text is not None:
            if new_text == prev_text:
                self._set_text_cache(path, new_text)
                return

        stats, diff = build_compact_diff(prev_text, new_text, event=effective_event)
        if effective_event == "modified" and stats == "sin cambios":
            if new_text is not None:
                self._set_text_cache(path, new_text)
            return

        if new_text is not None:
            self._set_text_cache(path, new_text)
        else:
            self._pop_text_cache(path)

        self._emit(effective_event, False, path, stats=stats, diff=diff)

    def on_created(self, event):
        if should_ignore(event.src_path):
            return
        with self._lock:
            if event.is_directory:
                if not self._debounced(event.src_path, "created"):
                    self._emit("created", True, event.src_path)
                return
            st = self._get_file_state(event.src_path)
            if st is not None:
                self._file_state[event.src_path] = st
            if self._debounced(event.src_path, "created"):
                return
            self._handle_file_write(event.src_path, "created")

    def on_modified(self, event):
        if event.is_directory or should_ignore(event.src_path):
            return
        with self._lock:
            changed, prev_size, cur_size = self._has_real_change(event.src_path)
            if not changed:
                return
            allow_fill = prev_size == 0 and cur_size > 0
            if self._debounced(event.src_path, "modified", allow_created_fill=allow_fill):
                return
            self._handle_file_write(event.src_path, "modified")

    def on_deleted(self, event):
        if should_ignore(event.src_path):
            return
        with self._lock:
            self._file_state.pop(event.src_path, None)
            self._last.pop(event.src_path, None)
            if event.is_directory:
                self._emit("deleted", True, event.src_path)
                return
            prev_text = self._pop_text_cache(event.src_path)
            now = time.monotonic()
            self._prune_deleted(now)
            self._recently_deleted[event.src_path] = (now, prev_text)
            stats = ""
            if prev_text is not None:
                stats, _ = build_compact_diff(prev_text, None, event="deleted")
            # Esperar brevemente por si es un os.replace (DELETED + CREATED en milisegundos)
            self._cancel_pending_delete(event.src_path)
            timer = threading.Timer(
                PENDING_DELETE_DELAY_SECONDS,
                self._flush_pending_delete,
                args=(event.src_path, stats),
            )
            timer.daemon = True
            self._pending_deletes[event.src_path] = timer
            timer.start()

    def on_moved(self, event):
        src_ignored = should_ignore(event.src_path)
        dest_ignored = should_ignore(event.dest_path)
        if src_ignored and dest_ignored:
            return
        with self._lock:
            # Escritura atomica (temp ignorado -> archivo real): registrar como MODIFIED/CREATED con diff
            if src_ignored and not dest_ignored:
                if event.is_directory:
                    self._emit("created", True, event.dest_path)
                    return
                existed = (
                    event.dest_path in self._file_state
                    or event.dest_path in self._pending_deletes
                    or event.dest_path in self._recently_deleted
                )
                st = self._get_file_state(event.dest_path)
                if st is not None:
                    self._file_state[event.dest_path] = st
                ev_type = "modified" if existed else "created"
                if not self._debounced(event.dest_path, ev_type):
                    self._handle_file_write(event.dest_path, ev_type)
                return

            # Archivo real movido hacia un destino ignorado: tratar como DELETED
            if not src_ignored and dest_ignored:
                self._file_state.pop(event.src_path, None)
                self._last.pop(event.src_path, None)
                stats = ""
                if not event.is_directory:
                    prev_text = self._pop_text_cache(event.src_path)
                    if prev_text is not None:
                        stats, _ = build_compact_diff(prev_text, None, event="deleted")
                self._emit("deleted", event.is_directory, event.src_path, stats=stats)
                return

            self._file_state.pop(event.src_path, None)
            self._last.pop(event.src_path, None)
            if not event.is_directory:
                st = self._get_file_state(event.dest_path)
                if st is not None:
                    self._file_state[event.dest_path] = st
                moved_text = self._pop_text_cache(event.src_path)
                if moved_text is not None:
                    self._set_text_cache(event.dest_path, moved_text)
                else:
                    self._set_text_cache(event.dest_path, read_text_snapshot(event.dest_path))
            self._emit("moved", event.is_directory, event.src_path, dest_path=event.dest_path)


def _write_pid() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _remove_pid() -> None:
    try:
        PID_FILE.unlink()
    except Exception:
        pass


def _pythonw() -> str:
    """pythonw.exe junto al python actual, para no abrir consola."""
    candidate = Path(sys.executable).with_name("pythonw.exe")
    return str(candidate) if candidate.exists() else sys.executable


STARTUP_VBS_NAME = "ZeroScript_Vigilante_Cambios.vbs"


def _startup_vbs_path() -> Path | None:
    override = os.environ.get("ZS_VIGILANTE_STARTUP_DIR", "").strip()
    if override:
        return Path(override) / STARTUP_VBS_NAME
    if os.name != "nt":
        return None
    appdata = os.environ.get("APPDATA", "").strip()
    if not appdata:
        return None
    return (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / STARTUP_VBS_NAME
    )


def cmd_ensure() -> int:
    """Si es una PC nueva (sin lanzador en Inicio), lo instala y lo arranca.
    Si la PC ya lo tiene instalado en Inicio, no reinstala ni modifica nada."""
    vbs = _startup_vbs_path()
    if vbs is not None and vbs.exists():
        print(f"[vigilante] PC ya cuenta con el vigilante instalado ({vbs.name}); no se reinstala.")
        return 0
    if vbs is not None:
        try:
            vbs.parent.mkdir(parents=True, exist_ok=True)
            pyw = _pythonw()
            script = str(Path(__file__).resolve())
            content = (
                'Set sh = CreateObject("WScript.Shell")\r\n'
                f'sh.Run """{pyw}"" ""{script}"" run", 0, False\r\n'
            )
            vbs.write_text(content, encoding="utf-8")
            print(f"[vigilante] Nueva PC detectada: autoarranque instalado en {vbs}")
        except Exception as exc:
            print(f"[vigilante] Aviso: no se pudo registrar en Inicio: {exc}", file=sys.stderr)
    return cmd_start()


def cmd_start() -> int:
    if not _HAS_WATCHDOG:
        print("ERROR: watchdog no instalado. Ejecuta: pip install watchdog", file=sys.stderr)
        return 1
    pid = _read_pid()
    if pid and _pid_alive(pid):
        print(f"[vigilante] Ya esta corriendo (PID {pid}).")
        return 0
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
    proc = subprocess.Popen(
        [_pythonw(), str(Path(__file__).resolve()), "run"],
        cwd=str(PROJECT_ROOT),
        creationflags=creationflags,
        close_fds=True,
    )
    time.sleep(0.5)
    print(f"[vigilante] Iniciado en segundo plano (PID {proc.pid}). Log: {weekly_log_path()}")
    return 0


def cmd_stop() -> int:
    pid = _read_pid()
    if not pid:
        print("[vigilante] No hay PID registrado; no esta corriendo.")
        return 0
    if not _pid_alive(pid):
        _remove_pid()
        print("[vigilante] El proceso ya no existia; PID limpiado.")
        return 0
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, signal.SIGTERM)
        print(f"[vigilante] Detenido (PID {pid}).")
    except Exception as exc:
        print(f"[vigilante] No se pudo detener: {exc}", file=sys.stderr)
        return 1
    _remove_pid()
    return 0


def cmd_status() -> int:
    pid = _read_pid()
    running = bool(pid and _pid_alive(pid))
    print(f"[vigilante] Estado: {'CORRIENDO' if running else 'DETENIDO'}")
    if pid:
        print(f"[vigilante] PID: {pid}")
    print(f"[vigilante] Proyecto: {PROJECT_ROOT}")
    print(f"[vigilante] Log actual: {weekly_log_path()}")
    print(f"[vigilante] Resumen IA: {RECENT_JSONL}")
    print(f"[vigilante] Ignorando: {', '.join(sorted(IGNORE_DIRS))}")
    return 0 if running else 1


def cmd_ver(count: int = 30) -> int:
    path = weekly_log_path()
    if not path.exists():
        print(f"[vigilante] Aun no hay log esta semana: {path}")
        return 0
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-max(1, count):]:
        print(line)
    return 0


def cmd_contexto(count: int = 15) -> int:
    act_text, act_shown, act_total = format_recent_mcp_actions(limit=max(1, count), max_chars=5000)
    chg_text, chg_shown, chg_total = format_recent_changes(limit=max(1, count), max_chars=12000)
    print(f"[vigilante] Actividad MCP reciente - ventana {CONTEXT_TTL_HOURS}h ({act_shown}/{act_total}):")
    print(act_text)
    print(f"\n[vigilante] Cambios en archivos - ventana {CONTEXT_TTL_HOURS}h ({chg_shown}/{chg_total}):")
    print(chg_text)
    return 0


def run_foreground() -> int:
    if not _HAS_WATCHDOG:
        print("ERROR: watchdog no instalado. Ejecuta: pip install watchdog", file=sys.stderr)
        return 1
    pid = _read_pid()
    if pid and pid != os.getpid() and _pid_alive(pid):
        print(f"[vigilante] Ya hay otra instancia (PID {pid}). Saliendo.", file=sys.stderr)
        return 1
    _write_pid()
    print(f"[vigilante] Iniciando... Proyecto: {PROJECT_ROOT}")
    print(f"[vigilante] Log semanal: {weekly_log_path()}")
    print(f"[vigilante] Resumen IA: {RECENT_JSONL}")
    print(f"[vigilante] Ignorando: {', '.join(sorted(IGNORE_DIRS))}")
    handler = ChangeHandler()
    observer = Observer(timeout=0.3)
    observer.schedule(handler, str(PROJECT_ROOT), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        _remove_pid()
        print("[vigilante] Detenido.")
    return 0


def main(argv: list[str]) -> int:
    cmd = (argv[1] if len(argv) > 1 else "run").lower()
    if cmd in ("run", ""):
        return run_foreground()
    if cmd == "start":
        return cmd_start()
    if cmd == "ensure":
        return cmd_ensure()
    if cmd == "stop":
        return cmd_stop()
    if cmd == "status":
        return cmd_status()
    if cmd == "ver":
        count = 30
        if len(argv) > 2:
            try:
                count = int(argv[2])
            except ValueError:
                pass
        return cmd_ver(count)
    if cmd in ("contexto", "resumen"):
        count = 15
        if len(argv) > 2:
            try:
                count = int(argv[2])
            except ValueError:
                pass
        return cmd_contexto(count)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
