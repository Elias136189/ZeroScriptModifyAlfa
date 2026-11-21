#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Despierta a otra IA cuando tiene un mensaje nuevo en el buzon compartido.

Por defecto SOLO simula. Con ``--apply`` ejecuta el CLI del destino (metodo
recomendado) o, si se configura como fallback, enfoca su ventana y pega el
prompt restringido.

``--watch`` mantiene el bucle de vigilancia en primer plano; el bridge lo usa
desde un hilo demonio para arrancarlo y pararlo con el propio bridge.

Reglas anti-bucle (todas activas):
  1. Solo hilos nuevos: ``reply_to`` vacio y ``hops`` 0.
  2. Un mensaje con respuesta o ya procesado no vuelve a despertar.
  3. Los mensajes con asunto ``[auto]`` se ignoran.
  4. Presupuesto: 1 cada 60 s, 6 por hora y 20 por dia.
  5. Interruptor: si existe ``wake_off`` junto al script, no hace nada.
  6. Prompt fijo: el cuerpo del mensaje nunca se inyecta.
  7. Un mensaje por ejecucion/ciclo, el mas antiguo pendiente.
  8. Fallos con backoff y limite; el mensaje nunca se marca leido.
  9. Disparador: con ``trigger.require`` solo despierta si el asunto o el
     cuerpo del mensaje contiene algun token (por defecto ``@despertar``).

Ejemplos:
    py -3 despertar.py
    py -3 despertar.py claude
    py -3 despertar.py --apply
    py -3 despertar.py opencode --apply --method cli
    py -3 despertar.py --watch
    py -3 despertar.py --status
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mailbox_store  # noqa: E402

DEFAULT_STATE_FILE = HERE / "wake_state.json"
DEFAULT_CONFIG_FILE = HERE / "despertar_config.json"
OFF_SWITCH = HERE / "wake_off"
LOG_FILE = HERE / "logs" / "despertar.log"

DEFAULT_PROMPT = (
    "Lee el mensaje {id} de {from} en el buzon compartido. Responde una sola vez "
    "con msg_reply. Si msg_inbox responde 'Sin mensajes nuevos.', vuelve a leerlo "
    "con include_read=true: el aviso pudo marcarlo como leido. No envies mensajes "
    "nuevos. No uses pc_shell, pc_write ni despertar.py. Si ya respondiste o el "
    "mensaje es automatico, no hagas nada."
)

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "default_targets": ["claude", "opencode"],
    "min_seconds_between": 60,
    "max_per_hour": 6,
    "max_per_day": 20,
    "max_age_hours": 24,
    "max_attempts": 5,
    "retry_base_seconds": 30,
    "require_reply": True,
    "allowed_senders": [],
    "trigger": {
        "require": False,
        "tokens": ["@despertar", "[despertar]"],
    },
    "watch": {
        "enabled": True,
        "interval_seconds": 2.5,
        "targets": ["claude", "opencode"],
    },
    "prompt": DEFAULT_PROMPT,
    "targets": {
        "claude": {
            "method": "cli",
            "fallback": [],
            "process": ["claude", "Claude"],
            "title": "Claude",
            "command": ["claude", "-p", "{prompt}"],
            "cli_timeout_seconds": 240,
        },
        "opencode": {
            "method": "cli",
            "fallback": [],
            "process": ["OpenCode Dev", "OpenCode"],
            "title": "OpenCode",
            "command": ["opencode", "run", "{prompt}"],
            "cli_timeout_seconds": 240,
        },
    },
}

# PowerShell de ventana: ASCII puro a proposito. El prompt viaja por variable
# de entorno (UTF-16) para no depender de la codificacion de la consola.
WINDOW_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$names = $env:ZS_WAKE_PROCESS | ConvertFrom-Json
$title = $env:ZS_WAKE_TITLE
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class ZWake {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, IntPtr extra);
  public static void KeyTap(byte vk) {
    keybd_event(vk, 0, 0, IntPtr.Zero);
    keybd_event(vk, 0, 2, IntPtr.Zero);
  }
}
"@ | Out-Null
$found = @()
foreach ($n in $names) {
  foreach ($p in @(Get-Process -Name $n -ErrorAction SilentlyContinue)) {
    if ($p.MainWindowHandle -eq 0) { continue }
    if ($title -and ($p.MainWindowTitle -notmatch $title)) { continue }
    $found += $p
  }
}
if ($found.Count -eq 0) {
  @{ ok = $false; error = 'no-window' } | ConvertTo-Json -Compress
  exit 0
}
$p = $found[0]
[ZWake]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
Start-Sleep -Milliseconds 300
# Windows bloquea SetForegroundWindow si otra app tiene el foco; un toque de
# ALT simula entrada del usuario y libera el bloqueo.
[ZWake]::KeyTap(0x12)
Start-Sleep -Milliseconds 200
$shell = New-Object -ComObject WScript.Shell
$got = $false
for ($i = 0; $i -lt 6; $i++) {
  [ZWake]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
  Start-Sleep -Milliseconds 250
  if ([ZWake]::GetForegroundWindow() -eq $p.MainWindowHandle) { $got = $true; break }
  $null = $shell.AppActivate($p.Id)
  Start-Sleep -Milliseconds 250
  if ([ZWake]::GetForegroundWindow() -eq $p.MainWindowHandle) { $got = $true; break }
}
if (-not $got) {
  [ZWake]::ShowWindow($p.MainWindowHandle, 6) | Out-Null
  Start-Sleep -Milliseconds 300
  [ZWake]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
  Start-Sleep -Milliseconds 400
  [ZWake]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
  Start-Sleep -Milliseconds 400
  if ([ZWake]::GetForegroundWindow() -eq $p.MainWindowHandle) { $got = $true }
}
if (-not $got) {
  @{ ok = $false; error = 'no-foreground'; pid = $p.Id; process = $p.ProcessName } |
    ConvertTo-Json -Compress
  exit 0
}
Set-Clipboard -Value $env:ZS_WAKE_PROMPT
Start-Sleep -Milliseconds 200
[System.Windows.Forms.SendKeys]::SendWait('^v')
Start-Sleep -Milliseconds 250
[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
@{ ok = $true; pid = $p.Id; process = $p.ProcessName; title = $p.MainWindowTitle } |
  ConvertTo-Json -Compress
"""

# CLI hijos vivos, para poder terminarlos al cerrar el bridge.
_ACTIVE_LOCK = threading.Lock()
_ACTIVE_PROCS: set[subprocess.Popen] = set()


def terminate_active() -> None:
    """Termina los CLI que sigan vivos (cierre del bridge / Ctrl+C)."""
    with _ACTIVE_LOCK:
        procs = list(_ACTIVE_PROCS)
    for proc in procs:
        try:
            if proc.poll() is None:
                proc.terminate()
        except OSError:
            pass
    deadline = time.monotonic() + 2.0
    for proc in procs:
        try:
            remaining = max(0.0, deadline - time.monotonic())
            proc.wait(timeout=remaining)
        except Exception:
            try:
                proc.kill()
            except OSError:
                pass


def safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))


def log(message: str, *, quiet: bool = False) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{stamp} {message}"
    if not quiet:
        safe_print(f"[despertar] {message}")
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def read_json(path: Path, default: Any) -> Any:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return default
    except Exception as exc:
        log(f"no se pudo leer {path.name}: {exc}; uso valores por defecto")
        return default
    return data if isinstance(data, type(default)) else default


def write_json(path: Path, payload: dict[str, Any]) -> None:
    mailbox_store.atomic_write_json(path, payload)


def load_config(path: Path) -> dict[str, Any]:
    effective = path
    if not effective.is_file() and effective.suffix.lower() == ".json":
        example = effective.with_name(f"{effective.stem}.example.json")
        if example.is_file():
            effective = example
    raw = read_json(effective, {})
    config = copy.deepcopy(DEFAULT_CONFIG)
    for key, value in raw.items():
        if key in ("targets", "watch"):
            continue
        config[key] = value
    watch = raw.get("watch")
    if isinstance(watch, dict):
        config["watch"].update(watch)
    targets = config["targets"]
    for name, cfg in (raw.get("targets") or {}).items():
        if isinstance(cfg, dict):
            targets[name] = {**targets.get(name, {}), **cfg}
    return config


def load_state(path: Path) -> dict[str, Any]:
    raw = read_json(path, {})
    state = {
        "version": 1,
        "wakes": raw.get("wakes") if isinstance(raw.get("wakes"), list) else [],
        "processed": raw.get("processed") if isinstance(raw.get("processed"), dict) else {},
        "failures": raw.get("failures") if isinstance(raw.get("failures"), dict) else {},
    }
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    state["version"] = 1
    state["wakes"] = [w for w in state.get("wakes", []) if isinstance(w, dict)][-500:]
    processed = state.get("processed") or {}
    state["processed"] = {
        str(name): [str(i) for i in ids][-200:]
        for name, ids in processed.items()
        if isinstance(ids, list)
    }
    failures = state.get("failures") or {}
    state["failures"] = dict(
        sorted(
            (
                (str(key), value)
                for key, value in failures.items()
                if isinstance(value, dict)
            ),
            key=lambda item: float(item[1].get("last_epoch") or 0),
        )[-200:]
    )
    write_json(path, state)


def parsed_epoch(message: dict[str, Any], path: Path) -> float:
    return mailbox_store.message_timestamp(path, message)


def fmt_age(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)} s"
    if seconds < 3600:
        return f"{int(seconds // 60)} min"
    if seconds < 86400:
        return f"{seconds / 3600:.1f} h"
    return f"{seconds / 86400:.1f} d"


def short_id(value: Any) -> str:
    text = str(value or "")
    return text[:8] if len(text) > 8 else text


def message_subject(message: dict[str, Any]) -> str:
    return str(message.get("subject") or "").strip()


def failure_key(target: str, message_id: Any) -> str:
    return f"{target.casefold()}:{message_id}"


def trigger_settings(config: dict[str, Any]) -> tuple[bool, list[str]]:
    """Devuelve (obligatorio, tokens) de la seccion ``trigger``."""
    trigger = config.get("trigger") or {}
    require = bool(trigger.get("require", False))
    tokens = trigger.get("tokens") or []
    if isinstance(tokens, str):
        tokens = [tokens]
    clean = [str(token).strip() for token in tokens if str(token).strip()]
    return require, clean


def message_has_trigger(message: dict[str, Any], tokens: list[str]) -> bool:
    """True si el asunto o el cuerpo contienen algun token (sin distinguir mayusculas)."""
    haystack = f"{message_subject(message)}\n{message.get('body') or ''}".casefold()
    return any(token.casefold() in haystack for token in tokens)


def prompt_for(template: str, message: dict[str, Any]) -> str:
    try:
        return template.format(
            id=message.get("id", ""),
            from_=message.get("from", ""),
            **{"from": message.get("from", "")},
            to=message.get("to", ""),
            subject=message_subject(message),
        )
    except Exception:
        return DEFAULT_PROMPT.format(
            id=message.get("id", ""),
            **{"from": message.get("from", "")},
        )


def collect_messages(
    root: Path,
    target: str,
    *,
    include_read: bool,
    max_age_hours: float,
    processed: list[str],
    failures: dict[str, Any] | None = None,
    max_attempts: int = 5,
    ignore_retry: bool = False,
    allowed_senders: list[str] | None = None,
    trigger_tokens: list[str] | None = None,
    log_fn: Any = None,
) -> list[dict[str, Any]]:
    """Mensajes dirigidos a ``target`` con el motivo para aceptar o descartar."""
    wanted = target.casefold()
    allowed = {
        str(name).strip().casefold()
        for name in (allowed_senders or [])
        if str(name).strip()
    }
    now = time.time()
    entries = mailbox_store.iter_messages(root, log=log_fn)
    answered = {
        str(message.get("reply_to"))
        for _path, message in entries
        if str(message.get("reply_to") or "").strip()
    }
    rows: list[dict[str, Any]] = []
    for path, message in entries:
        if str(message.get("to") or "").strip().casefold() != wanted:
            continue
        message_id = str(message.get("id") or "")
        fail = (failures or {}).get(failure_key(target, message_id)) or {}
        try:
            fail_count = int(fail.get("count") or 0)
        except Exception:
            fail_count = 0
        try:
            retry_at = float(fail.get("next_epoch") or 0)
        except Exception:
            retry_at = 0.0

        reason = ""
        if str(message.get("from") or "").strip().casefold() == wanted:
            reason = "lo envio el propio destino"
        elif allowed and str(message.get("from") or "").strip().casefold() not in allowed:
            reason = "remitente no permitido"
        elif str(message.get("reply_to") or "").strip():
            reason = f"es respuesta (reply_to={short_id(message.get('reply_to'))})"
        elif int(message.get("hops") or 0) != 0:
            reason = f"hops={message.get('hops')}"
        elif message_subject(message).lower().startswith("[auto]"):
            reason = "asunto [auto]"
        elif message_id in answered:
            reason = "ya tiene respuesta"
        elif message_id in processed:
            reason = "ya despertado antes"
        elif fail_count >= max_attempts:
            reason = f"fallos agotados ({fail_count}/{max_attempts})"
        elif retry_at > now and not ignore_retry:
            reason = f"reintento en {int(retry_at - now)} s"
        elif bool(message.get("read", False)) and not include_read:
            reason = "ya leido"
        elif trigger_tokens and not message_has_trigger(message, trigger_tokens):
            reason = f"falta el disparador {trigger_tokens[0]}"

        age = max(0.0, now - parsed_epoch(message, path))
        if not reason and max_age_hours > 0 and age > max_age_hours * 3600:
            reason = f"mas de {max_age_hours:g} h"
        rows.append({
            "path": path,
            "message": message,
            "reason": reason,
            "age": age,
        })
    rows.sort(key=lambda row: parsed_epoch(row["message"], row["path"]))
    return rows


def message_has_reply(root: Path, message_id: Any, log_fn: Any = None) -> bool:
    """True si ya existe un mensaje con ``reply_to`` igual a ``message_id``."""
    wanted = str(message_id or "")
    if not wanted:
        return False
    for _path, message in mailbox_store.iter_messages(root, log=log_fn):
        if str(message.get("reply_to") or "").strip() == wanted:
            return True
    return False


def budget_status(config: dict[str, Any], state: dict[str, Any], now: float) -> tuple[list[str], dict[str, int]]:
    wakes = [
        w for w in state.get("wakes", [])
        if isinstance(w, dict) and str(w.get("result")) == "ok"
    ]
    epochs = []
    for wake in wakes:
        try:
            epochs.append(float(wake.get("epoch") or 0))
        except Exception:
            continue
    epochs.sort()
    last = epochs[-1] if epochs else 0.0
    in_hour = sum(1 for value in epochs if now - value <= 3600)
    in_day = sum(1 for value in epochs if now - value <= 86400)
    problems: list[str] = []
    raw_cooldown = config.get("min_seconds_between")
    cooldown = 60 if raw_cooldown is None else int(raw_cooldown)
    raw_hour = config.get("max_per_hour")
    max_hour = 6 if raw_hour is None else int(raw_hour)
    raw_day = config.get("max_per_day")
    max_day = 20 if raw_day is None else int(raw_day)
    if last and now - last < cooldown:
        problems.append(f"espera {int(cooldown - (now - last))} s (minimo {cooldown} s entre despertares)")
    if max_hour > 0 and in_hour >= max_hour:
        problems.append(f"limite por hora alcanzado ({in_hour}/{max_hour})")
    if max_day > 0 and in_day >= max_day:
        problems.append(f"limite diario alcanzado ({in_day}/{max_day})")
    return problems, {"hour": in_hour, "day": in_day, "last": last}


def target_config(config: dict[str, Any], target: str) -> dict[str, Any] | None:
    for name, cfg in config.get("targets", {}).items():
        if str(name).casefold() == target.casefold():
            return cfg
    return None


def acquire_lock(path: Path) -> bool:
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="ascii") as handle:
                handle.write(f"{os.getpid()} {time.time()}")
            return True
        except FileExistsError:
            try:
                age = time.time() - path.stat().st_mtime
            except OSError:
                age = 9999
            if age <= 180:
                return False
            try:
                path.unlink()
            except OSError:
                return False
        except OSError:
            return False
    return False


def release_lock(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _run_command(argv: list[str], timeout: float, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Ejecuta un CLI sin consola, sin stdin y con registro para poder matarlo."""
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "creationflags": creationflags,
    }
    if env is not None:
        kwargs["env"] = env
    if os.name != "nt":
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(argv, **kwargs)  # noqa: S603 - argv viene de config local
    with _ACTIVE_LOCK:
        _ACTIVE_PROCS.add(proc)
    try:
        try:
            out, err = proc.communicate(timeout=timeout)
            return proc.returncode or 0, out or "", err or ""
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
            return -1, out or "", f"tiempo agotado ({timeout:g} s)"
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_PROCS.discard(proc)


def wake_window(cfg: dict[str, Any], prompt: str, timeout: float) -> tuple[bool, str]:
    processes = cfg.get("process") or []
    if isinstance(processes, str):
        processes = [processes]
    if not processes:
        return False, "falta 'process' en la configuracion del destino"
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        return False, "no se encontro PowerShell"
    env = os.environ.copy()
    env["ZS_WAKE_PROCESS"] = json.dumps(processes)
    env["ZS_WAKE_TITLE"] = str(cfg.get("title") or "")
    env["ZS_WAKE_PROMPT"] = prompt
    # -Command - con stdin redirigido no ejecuta el script en Windows
    # PowerShell; un archivo temporal con -File si es fiable.
    fd, script_name = tempfile.mkstemp(prefix="zs-wake-", suffix=".ps1")
    os.close(fd)
    try:
        Path(script_name).write_text(WINDOW_SCRIPT, encoding="ascii")
        proc = subprocess.run(
            [exe, "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", script_name],
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, f"PowerShell no respondio en {timeout:g} s"
    except OSError as exc:
        return False, f"no se pudo ejecutar PowerShell: {exc}"
    finally:
        try:
            os.unlink(script_name)
        except OSError:
            pass
    lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    if not lines:
        detail = (proc.stderr or "").strip().splitlines()
        return False, detail[-1] if detail else "PowerShell no devolvio resultado"
    try:
        data = json.loads(lines[-1])
    except Exception:
        return False, f"respuesta inesperada de PowerShell: {lines[-1][:200]}"
    if data.get("ok"):
        return True, f"pid={data.get('pid')} ventana={data.get('title') or '(sin titulo)'}"
    error = str(data.get("error") or "desconocido")
    if error == "no-window":
        names = ", ".join(str(p) for p in processes)
        return False, f"no hay ventana abierta de: {names}"
    if error == "no-foreground":
        return False, "la ventana no paso a primer plano; haz clic en ella y reintenta"
    return False, f"error de ventana: {error}"


def wake_cli(cfg: dict[str, Any], prompt: str, timeout: float) -> tuple[bool, str]:
    command = cfg.get("command")
    if not command or not isinstance(command, list):
        return False, "falta 'command' (lista) en la configuracion del destino"
    argv = [str(part).replace("{prompt}", prompt) for part in command]
    argv[0] = os.path.expandvars(os.path.expanduser(argv[0]))
    # En Windows los CLI de npm son .cmd/.bat y CreateProcess no los ejecuta
    # directamente: hay que resolverlos y pasar por cmd.exe.
    resolved = shutil.which(argv[0])
    if not resolved and os.name == "nt" and Path(argv[0]).name.lower() in ("opencode", "opencode.exe"):
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            candidate = Path(local_app) / "Programs" / "ZeroScript" / "opencode.exe"
            if candidate.is_file():
                resolved = str(candidate)
    resolved = resolved or argv[0]
    if os.name == "nt" and resolved.lower().endswith((".cmd", ".bat")):
        argv = ["cmd.exe", "/d", "/c", resolved, *argv[1:]]
    else:
        argv[0] = resolved
    # Fail closed if the dedicated restricted profile is missing.
    env = os.environ.copy()
    restricted_config = Path(__file__).parent / "pc_agent_config.restricted.json"
    if not restricted_config.is_file():
        restricted_example = Path(__file__).parent / "pc_agent_config.restricted.example.json"
        if restricted_example.is_file():
            restricted_config = restricted_example
    if not restricted_config.is_file():
        return False, f"no existe el perfil restringido: {restricted_config}"
    wake_ws = Path(__file__).parent / "workspace_wake"
    try:
        wake_ws.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    env["ZS_PC_CONFIG"] = str(restricted_config)
    env.pop("ZS_PC_WORKSPACE", None)
    env["ZS_PC_ALLOW_OUTSIDE_WORKSPACE"] = "false"
    env["ZS_PC_ALLOW_SHELL"] = "false"
    env["ZS_PC_ALLOW_WRITE"] = "false"
    try:
        code, out, err = _run_command(argv, timeout, env=env)
    except FileNotFoundError:
        return False, (
            f"no se encontro el ejecutable '{argv[0]}'; instala el CLI o pon la ruta "
            "completa en 'command'"
        )
    except OSError as exc:
        return False, f"no se pudo ejecutar '{argv[0]}': {exc}"
    if code != 0:
        detail = (err or out or "").strip().splitlines()
        return False, f"el CLI salio con codigo {code}: {detail[-1][:200] if detail else ''}"
    return True, "CLI ejecutado"


def _wake_with(method: str, cfg: dict[str, Any], prompt: str) -> tuple[bool, str]:
    if method == "window":
        return wake_window(cfg, prompt, timeout=30)
    if method == "cli":
        timeout = float(cfg.get("cli_timeout_seconds") or 180)
        return wake_cli(cfg, prompt, timeout=timeout)
    return False, f"metodo desconocido: {method}"


def record_failure(
    state: dict[str, Any],
    config: dict[str, Any],
    target: str,
    message_id: Any,
    detail: str,
) -> dict[str, Any]:
    failures = state.setdefault("failures", {})
    key = failure_key(target, message_id)
    item = failures.get(key)
    if not isinstance(item, dict):
        item = {"count": 0}
    try:
        count = int(item.get("count") or 0) + 1
    except Exception:
        count = 1
    base = max(5.0, float(config.get("retry_base_seconds") or 30))
    delay = min(300.0, base * (2 ** min(count - 1, 5)))
    now = time.time()
    item.update({
        "count": count,
        "last_epoch": now,
        "next_epoch": now + delay,
        "detail": str(detail)[:400],
        "target": target,
        "message_id": str(message_id),
    })
    failures[key] = item
    return item


def process_target(
    root: Path,
    target: str,
    config: dict[str, Any],
    state: dict[str, Any],
    state_path: Path,
    *,
    apply: bool,
    method_override: str = "",
    include_read: bool = False,
    max_age_hours: float | None = None,
    quiet: bool = False,
    ignore_retry: bool = False,
    log_fn: Any = log,
) -> dict[str, Any]:
    """Evalua un destino y, con ``apply``, intenta despertarlo una vez."""
    cfg = target_config(config, target)
    method = method_override or str((cfg or {}).get("method") or "cli")
    state_key = target.casefold()
    processed = [str(i) for i in (state.get("processed") or {}).get(state_key, [])]
    max_age = config.get("max_age_hours")
    max_age = float(max_age) if max_age is not None else 24.0
    if max_age_hours is not None:
        max_age = max_age_hours
    require_trigger, trigger_tokens = trigger_settings(config)
    trigger_filter = trigger_tokens if require_trigger else None
    rows = collect_messages(
        root,
        target,
        include_read=include_read,
        max_age_hours=max_age,
        processed=processed,
        failures=state.get("failures") or {},
        max_attempts=int(config.get("max_attempts") or 5),
        ignore_retry=ignore_retry,
        allowed_senders=config.get("allowed_senders") or [],
        trigger_tokens=trigger_filter,
        log_fn=None if quiet else log_fn,
    )
    candidates = [row for row in rows if not row["reason"]]
    result: dict[str, Any] = {
        "target": target,
        "rows": rows,
        "candidates": candidates,
        "chosen": None,
        "prompt": "",
        "method": method,
        "status": "none",
        "detail": "",
    }
    if not candidates:
        return result

    chosen = candidates[0]
    message = chosen["message"]
    prompt = prompt_for(str(config.get("prompt") or DEFAULT_PROMPT), message)
    result.update({"chosen": chosen, "prompt": prompt})
    if not apply:
        result["status"] = "simulated"
        return result

    if not config.get("enabled", True):
        result.update({"status": "blocked", "detail": "'enabled' es false en la configuracion"})
        return result
    if OFF_SWITCH.exists():
        result.update({"status": "blocked", "detail": f"existe el interruptor {OFF_SWITCH.name}"})
        return result
    if cfg is None:
        result.update({"status": "error", "detail": f"no hay configuracion para '{target}'"})
        return result
    if method == "none":
        result.update({
            "status": "error",
            "detail": str(cfg.get("note") or "metodo 'none' no despierta nada"),
        })
        return result

    lock_path = state_path.with_suffix(".lock")
    if not acquire_lock(lock_path):
        result.update({"status": "blocked", "detail": "otra ejecucion de despertar esta en curso"})
        return result
    try:
        # Otra ejecucion pudo cambiar el estado mientras esperabamos el lock.
        fresh = load_state(state_path)
        state.clear()
        state.update(fresh)
        fresh_rows = collect_messages(
            root,
            target,
            include_read=include_read,
            max_age_hours=max_age,
            processed=[str(i) for i in (state.get("processed") or {}).get(state_key, [])],
            failures=state.get("failures") or {},
            max_attempts=int(config.get("max_attempts") or 5),
            ignore_retry=ignore_retry,
            allowed_senders=config.get("allowed_senders") or [],
            trigger_tokens=trigger_filter,
            log_fn=None,
        )
        still = [
            row for row in fresh_rows
            if str(row["message"].get("id")) == str(message.get("id")) and not row["reason"]
        ]
        if not still:
            result.update({"status": "blocked", "detail": "otra ejecucion ya proceso este mensaje"})
            return result

        problems, _stats = budget_status(config, state, time.time())
        if problems:
            result.update({"status": "blocked", "detail": "; ".join(problems)})
            return result

        chain = [method]
        for extra in cfg.get("fallback") or []:
            extra = str(extra)
            if extra and extra != method and extra not in chain:
                chain.append(extra)

        errors: list[str] = []
        used = ""
        detail = ""
        ok = False
        for candidate_method in chain:
            ok, detail = _wake_with(candidate_method, cfg, prompt)
            if ok:
                used = candidate_method
                break
            errors.append(f"{candidate_method}: {detail}")
            if not quiet:
                log_fn(f"destino={target} metodo={candidate_method} fallo: {detail}")

        # Un CLI puede salir con 0 sin haber hecho nada (por ejemplo, si su
        # perfil no tiene el MCP del buzon). En ese caso el mensaje NO se da por
        # despertado: se registra el fallo y se reintenta con backoff.
        if ok and used == "cli" and config.get("require_reply", True):
            if not message_has_reply(root, message.get("id")):
                detail = (
                    f"{used}: el CLI termino con codigo 0 pero no hay respuesta al "
                    "mensaje; revisa que ese CLI tenga el MCP del buzon configurado"
                )
                errors.append(detail)
                ok = False
                used = ""

        # La ventana puede pegar el aviso y pulsar Enter sin que el cliente
        # llegue a usar el buzón (permisos pendientes, ventana ocupada...). Se
        # espera la respuesta para no marcar como despertado algo que no lo fue.
        if ok and used == "window" and config.get("require_reply", True):
            timeout = float(cfg.get("window_reply_timeout_seconds") or 90)
            deadline = time.time() + timeout
            while True:
                if message_has_reply(root, message.get("id")):
                    break
                if time.time() >= deadline:
                    break
                time.sleep(2)
            if not message_has_reply(root, message.get("id")):
                detail = (
                    f"{used}: la ventana acepto el aviso pero no hay respuesta al "
                    f"mensaje tras {int(timeout)} s; revisa los permisos del cliente "
                    "(msg_inbox/msg_reply) y que la ventana siga disponible"
                )
                errors.append(detail)
                ok = False
                used = ""

        if not ok:
            joined = " | ".join(errors)
            item = record_failure(
                state, config, target, message.get("id"), joined,
            )
            save_state(state_path, state)
            count = int(item.get("count") or 0)
            attempts = int(config.get("max_attempts") or 5)
            suffix = " (sin mas reintentos automaticos)" if count >= attempts else ""
            result.update({
                "status": "failed",
                "detail": joined + suffix,
                "failures": item,
            })
            log_fn(
                f"destino={target} msg={short_id(message.get('id'))} FALLO "
                f"{count}/{attempts}: {joined}{suffix}"
            )
            return result

        stamped = datetime.now().astimezone()
        state.setdefault("wakes", []).append({
            "ts": stamped.isoformat(timespec="seconds"),
            "epoch": stamped.timestamp(),
            "target": target,
            "message_id": message.get("id"),
            "method": used,
            "result": "ok",
            "detail": detail,
        })
        processed_now = state.setdefault("processed", {}).setdefault(state_key, [])
        if str(message.get("id")) not in processed_now:
            processed_now.append(str(message.get("id")))
        state.setdefault("failures", {}).pop(failure_key(target, message.get("id")), None)
        save_state(state_path, state)
        result.update({"status": "woke", "method": used, "detail": detail})
        log_fn(f"destino={target} msg={short_id(message.get('id'))} metodo={used} OK: {detail}")
        return result
    finally:
        release_lock(lock_path)


def reset_failures(state_path: Path, target: str = "") -> int:
    state = load_state(state_path)
    failures = state.get("failures") or {}
    if not target:
        removed = len(failures)
        state["failures"] = {}
    else:
        prefix = f"{target.casefold()}:"
        keep = {k: v for k, v in failures.items() if not str(k).startswith(prefix)}
        removed = len(failures) - len(keep)
        state["failures"] = keep
    if removed:
        save_state(state_path, state)
    return removed


def watch_loop(
    stop_event: threading.Event,
    *,
    config_path: Path = DEFAULT_CONFIG_FILE,
    state_path: Path = DEFAULT_STATE_FILE,
    mailbox: str = "",
    interval: float | None = None,
    targets: list[str] | None = None,
    log_fn: Any = log,
) -> None:
    """Mensajero: vigila el buzon y despierta como maximo una IA por ciclo."""
    while not stop_event.is_set():
        try:
            config = load_config(config_path)
            state = load_state(state_path)
            watch = config.get("watch") or {}
            if not config.get("enabled", True) or not watch.get("enabled", True):
                stop_event.wait(5.0)
                continue
            cycle_targets = targets or watch.get("targets") or config.get("default_targets") or []
            if isinstance(cycle_targets, str):
                cycle_targets = [cycle_targets]
            wait = float(interval or watch.get("interval_seconds") or 2.5)
            raw_mailbox = mailbox or os.environ.get("ZS_PC_MAILBOX_DIR") or ""
            if not raw_mailbox:
                raw_mailbox = read_json(HERE / "pc_agent_config.json", {}).get("mailbox_dir") or ""
            root = mailbox_store.resolve_mailbox_dir(raw_mailbox, base_dir=HERE)
            woke = False
            for target in [str(t) for t in cycle_targets]:
                result = process_target(
                    root,
                    target,
                    config,
                    state,
                    state_path,
                    apply=True,
                    quiet=True,
                    log_fn=log_fn,
                )
                if result["status"] == "woke":
                    woke = True
                    break
                if result["status"] == "failed":
                    break
            if woke:
                continue
            stop_event.wait(wait)
        except Exception as exc:
            log_fn(f"mensajero: error inesperado: {type(exc).__name__}: {exc}")
            stop_event.wait(5.0)


def print_status(config: dict[str, Any], state: dict[str, Any], state_path: Path) -> None:
    now = time.time()
    problems, stats = budget_status(config, state, now)
    safe_print("")
    safe_print(f"Estado: {state_path}")
    wakes = [w for w in state.get("wakes", []) if isinstance(w, dict)]
    safe_print(f"Despertares registrados: {len(wakes)}")
    for wake in wakes[-5:]:
        safe_print(f"  {wake.get('ts', '?')}  {wake.get('target', '?')}  "
                   f"msg {short_id(wake.get('message_id'))}  {wake.get('result', '?')}")
    if not wakes:
        safe_print("  (ninguno todavia)")
    safe_print(f"Presupuesto: {stats['hour']}/{config.get('max_per_hour')} por hora, "
               f"{stats['day']}/{config.get('max_per_day')} por dia")
    if problems:
        for problem in problems:
            safe_print(f"  BLOQUEADO: {problem}")
    else:
        safe_print("  disponible")
    processed = state.get("processed") or {}
    if processed:
        counts = ", ".join(f"{name}: {len(ids)}" for name, ids in processed.items() if isinstance(ids, list))
        safe_print(f"Procesados por destino: {counts}")
    failures = state.get("failures") or {}
    if failures:
        safe_print(f"Fallos pendientes: {len(failures)}")
        for key, item in list(failures.items())[-5:]:
            safe_print(f"  {key}  intentos={item.get('count')}  "
                       f"{str(item.get('detail') or '')[:100]}")
    watch = config.get("watch") or {}
    watch_targets = watch.get("targets") or config.get("default_targets") or []
    if isinstance(watch_targets, str):
        watch_targets = [watch_targets]
    require_trigger, trigger_tokens = trigger_settings(config)
    if require_trigger:
        tokens = ", ".join(trigger_tokens) if trigger_tokens else "(sin token: nunca despierta)"
        safe_print(f"Disparador obligatorio: {tokens}")
    else:
        safe_print("Disparador: desactivado (cualquier mensaje nuevo despierta)")
    safe_print(f"Mensajero: {'activo' if watch.get('enabled', True) else 'desactivado'} "
               f"cada {watch.get('interval_seconds', 2.5)} s"
               + (f"; destinos: {', '.join(str(t) for t in watch_targets)}" if watch_targets else ""))
    manual = [
        str(name) for name, cfg in (config.get("targets") or {}).items()
        if str((cfg or {}).get("method") or "").lower() == "none"
    ]
    if manual:
        safe_print(f"Manual (sin despertar automatico): {', '.join(manual)}")
    safe_print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Despierta a otra IA cuando tiene un mensaje nuevo (simulacion por defecto). "
                     "Con 'trigger.require' solo despierta si el mensaje lleva el token "
                     "(@despertar o [despertar])."),
    )
    parser.add_argument("target", nargs="*", help="Destino(s) del buzon; por defecto los de la configuracion.")
    parser.add_argument("--apply", action="store_true", help="Despierta de verdad; sin esto solo simula.")
    parser.add_argument("--method", choices=["window", "cli", "none"], default="",
                        help="Fuerza el metodo; por defecto el de la configuracion (cli).")
    parser.add_argument("--include-read", action="store_true",
                        help="En simulacion, trata tambien los mensajes ya leidos como candidatos.")
    parser.add_argument("--max-age-hours", type=float, default=None,
                        help="Antiguedad maxima en horas (0 = sin limite).")
    parser.add_argument("--mailbox", default="", help="Carpeta del buzon.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_FILE), help="Archivo de configuracion.")
    parser.add_argument("--state", default=str(DEFAULT_STATE_FILE), help="Archivo de estado.")
    parser.add_argument("--watch", action="store_true", help="Vigila el buzon en primer plano.")
    parser.add_argument("--status", action="store_true", help="Muestra el estado y el presupuesto.")
    parser.add_argument("--reset-failures", action="store_true",
                        help="Borra los fallos registrados (todos o los del destino indicado).")
    parser.add_argument("--quiet", action="store_true", help="No imprime avisos del buzon.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config).expanduser()
    state_path = Path(args.state).expanduser()
    config = load_config(config_path)
    state = load_state(state_path)

    mailbox_raw = args.mailbox or os.environ.get("ZS_PC_MAILBOX_DIR") or ""
    if not mailbox_raw:
        mailbox_raw = read_json(HERE / "pc_agent_config.json", {}).get("mailbox_dir") or ""
    root = mailbox_store.resolve_mailbox_dir(mailbox_raw, base_dir=HERE)

    if args.status:
        print_status(config, state, state_path)
        return 0

    if args.reset_failures:
        target = args.target[0] if args.target else ""
        removed = reset_failures(state_path, target)
        safe_print(f"Fallos borrados: {removed}.")
        return 0

    if args.watch and not args.apply:
        safe_print("ERROR: --watch despierta de verdad; agrega --apply para confirmarlo.")
        return 1

    if args.watch:
        stop = threading.Event()

        def _stop(_signum, _frame):
            stop.set()

        try:
            signal.signal(signal.SIGINT, _stop)
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, _stop)
        except (ValueError, OSError):
            pass
        safe_print(f"Vigilando {root} cada {config.get('watch', {}).get('interval_seconds', 2.5)} s. Ctrl+C para salir.")
        try:
            watch_loop(
                stop,
                config_path=config_path,
                state_path=state_path,
                mailbox=mailbox_raw,
                targets=[str(t) for t in args.target] or None,
            )
        finally:
            terminate_active()
        return 0

    if args.method == "none" and args.apply:
        safe_print("ERROR: --method none solo sirve para simular; quita --apply.")
        return 1
    if args.include_read and args.apply:
        safe_print("ERROR: --include-read solo vale en simulacion; quita --apply.")
        return 1

    max_age = config.get("max_age_hours")
    max_age = float(max_age) if max_age is not None else 24.0
    if args.max_age_hours is not None:
        max_age = args.max_age_hours

    if args.target:
        targets = [str(t) for t in args.target]
    else:
        targets = [str(t) for t in (config.get("default_targets") or [])]

    if not args.apply:
        safe_print("")
        safe_print("MODO SIMULACION: no se despertara nada. Usa --apply para activar.")
        safe_print(f"Buzon: {root}")
        if OFF_SWITCH.exists():
            safe_print(f"AVISO: existe el interruptor {OFF_SWITCH.name}; con --apply no haria nada.")
        if not config.get("enabled", True):
            safe_print("AVISO: 'enabled' es false en la configuracion; con --apply no haria nada.")
        problems, stats = budget_status(config, state, time.time())
        safe_print(f"Presupuesto: {stats['hour']}/{config.get('max_per_hour')} por hora, "
                   f"{stats['day']}/{config.get('max_per_day')} por dia")
        for problem in problems:
            safe_print(f"  BLOQUEADO: {problem}")
        safe_print("")

    exit_code = 0
    woke_something = False
    had_error = False

    for target in targets:
        result = process_target(
            root,
            target,
            config,
            state,
            state_path,
            apply=bool(args.apply),
            method_override=args.method,
            include_read=bool(args.include_read),
            max_age_hours=max_age,
            ignore_retry=True,
        )
        cfg = target_config(config, target)
        method = result["method"]
        safe_print(f"== Destino: {target} ==")
        if cfg is None:
            safe_print("  (sin configuracion propia; solo se puede simular)")
        elif method == "none":
            safe_print("  metodo: none (manual; no se despierta)")
        else:
            processes = cfg.get("process") or []
            if isinstance(processes, str):
                processes = [processes]
            detail = f"proceso: {', '.join(str(p) for p in processes)}" if processes else "CLI"
            safe_print(f"  metodo: {method} ({detail})")

        if not result["rows"]:
            safe_print("  Sin mensajes para este destino.")
            safe_print("")
            continue

        for row in result["rows"]:
            message = row["message"]
            subject = message_subject(message)
            label = f"  {short_id(message.get('id'))}  hace {fmt_age(row['age']):>7}  " \
                    f"de {str(message.get('from'))[:12]:<12}  '{subject[:40]}'"
            if row["reason"]:
                safe_print(f"{label}  [descartado: {row['reason']}]")
            else:
                safe_print(f"{label}  [CANDIDATO]")

        if result["candidates"]:
            message = result["candidates"][0]["message"]
            safe_print("")
            safe_print(f"  Elegido: {message.get('id')} de {message.get('from')}")
            safe_print("  Prompt que se inyectaria:")
            for line in result["prompt"].splitlines() or [""]:
                safe_print(f"    {line}")
            safe_print("")

        status = result["status"]
        if status == "none":
            safe_print("  Nada que despertar.")
        elif status == "simulated":
            safe_print("  (simulacion: no se inyecto nada)")
        elif status == "woke":
            safe_print(f"  DESPERTADO ({result['method']}): {result['detail']}")
            woke_something = True
            exit_code = 0
        elif status == "blocked":
            if woke_something:
                safe_print("  Ya se despertó a otro destino en esta ejecucion; se omite.")
            else:
                safe_print(f"  BLOQUEADO: {result['detail']}")
                exit_code = 4
        elif status == "failed":
            safe_print(f"  FALLO: {result['detail']}")
            had_error = True
        else:
            safe_print(f"  ERROR: {result['detail']}")
            had_error = True
        safe_print("")

    if had_error:
        return 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
