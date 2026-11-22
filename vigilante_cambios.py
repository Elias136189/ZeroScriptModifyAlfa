#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vigilante de cambios en el sistema de archivos.

Uso:
  python vigilante_cambios.py run        Corre en primer plano (tarea programada)
  python vigilante_cambios.py start      Arranca en segundo plano (sin ventana)
  python vigilante_cambios.py ensure     Si es nueva PC (no esta en Inicio), lo instala y arranca
  python vigilante_cambios.py stop       Detiene la instancia en segundo plano
  python vigilante_cambios.py status     Estado y ruta del log actual
  python vigilante_cambios.py ver [N]    Ultimas N lineas del log de esta semana

Vigila la carpeta del proyecto y subcarpetas. Ignora __pycache__, .git, logs,
backups, assets y workspace_wake. Registra CREATED, MODIFIED, DELETED y MOVED
tanto de archivos como de carpetas, con el usuario de Windows que ejecuta el
vigilante como columna de autor, en logs/registro_cambios/cambios_YYYY-WWW.log
(una semana ISO por archivo). Formato de cada linea:
  fecha | autor | EVENTO | FILE|DIR | ruta
"""

import getpass
import os
import sys
import time
import signal
import subprocess
from datetime import datetime
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
except ImportError:
    print("ERROR: watchdog no instalado. Ejecuta: pip install watchdog", file=sys.stderr)
    sys.exit(1)

# ─── CONFIG ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
REGISTRY_DIR = LOG_DIR / "registro_cambios"
PID_FILE = LOG_DIR / "vigilante_cambios.pid"
IGNORE_DIRS = {"__pycache__", ".git", "logs", "backups", "assets", "workspace_wake", "runtime"}
IGNORE_NAMES = {"desktop.ini", "Thumbs.db"}
IGNORE_PREFIXES = ("~$",)
DEBOUNCE_SECONDS = 1.0
# Usuario de Windows que corre el vigilante. El sistema de archivos no dice
# que IA concreta escribio, asi que esto identifica la cuenta, no el proceso.
try:
    AUTHOR = os.environ.get("USERNAME") or getpass.getuser() or "desconocido"
except Exception:
    AUTHOR = "desconocido"
# ─────────────────────────────────────────────────────────────────────────


def weekly_log_path() -> Path:
    """logs/registro_cambios/cambios_YYYY-WWW.log usando la semana y el año ISO."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    iso = datetime.now().isocalendar()
    return REGISTRY_DIR / f"cambios_{iso.year}-W{iso.week:02d}.log"


def should_ignore(path: str) -> bool:
    p = Path(path)
    if p.name in IGNORE_NAMES or p.name.startswith(IGNORE_PREFIXES):
        return True
    try:
        rel = p.resolve().relative_to(PROJECT_ROOT)
    except Exception:
        return True
    return any(part in IGNORE_DIRS for part in rel.parts)


def rel_path(path: str) -> str:
    try:
        return Path(path).resolve().relative_to(PROJECT_ROOT).as_posix()
    except Exception:
        return path


class ChangeHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._last: dict[str, tuple[str, float]] = {}
        # Cache de (mtime_ns, size) para detectar cambios reales de contenido
        self._file_state: dict[str, tuple[int, int]] = {}
        self._prime_state()

    def _prime_state(self) -> None:
        """Precarga (st_mtime_ns, st_size) de los archivos actuales al iniciar."""
        for root, dirs, files in os.walk(PROJECT_ROOT):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for name in files:
                if name in IGNORE_NAMES or name.startswith(IGNORE_PREFIXES):
                    continue
                full = os.path.join(root, name)
                st = self._get_file_state(full)
                if st is not None:
                    self._file_state[full] = st

    def _get_file_state(self, path: str) -> tuple[int, int] | None:
        """Devuelve (st_mtime_ns, st_size) o None si no existe/no accesible."""
        try:
            st = os.stat(path)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def _has_real_change(self, path: str) -> bool:
        """True si mtime_ns o size han cambiado desde la ultima vez."""
        current = self._get_file_state(path)
        if current is None:
            self._file_state.pop(path, None)
            return False
        prev = self._file_state.get(path)
        if prev is None:
            self._file_state[path] = current
            return True
        if prev != current:
            self._file_state[path] = current
            return True
        # Mismo mtime_ns y size -> sin cambio real de contenido
        return False

    def _debounced(self, event: FileSystemEvent) -> bool:
        """Evita rafagas: mismo tipo en <1 s, o MODIFIED justo tras CREATED."""
        key = event.src_path
        now = time.monotonic()
        prev = self._last.get(key)
        self._last[key] = (event.event_type, now)
        if prev is None:
            return False
        prev_type, prev_ts = prev
        if now - prev_ts > DEBOUNCE_SECONDS:
            return False
        if prev_type == event.event_type:
            return True
        if event.event_type == "modified" and prev_type == "created":
            return True
        return False

    def _log(self, event: FileSystemEvent):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        kind = "DIR" if event.is_directory else "FILE"
        if event.event_type == "moved":
            line = f"{ts} | {AUTHOR} | MOVED    | {kind} | {rel_path(event.src_path)} -> {rel_path(event.dest_path)}"
        else:
            line = f"{ts} | {AUTHOR} | {event.event_type.upper():8s} | {kind} | {rel_path(event.src_path)}"
        try:
            with weekly_log_path().open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception as exc:
            print(f"[vigilante] Error escribiendo log: {exc}", file=sys.stderr)

    def on_created(self, event):
        if should_ignore(event.src_path):
            return
        if not event.is_directory:
            st = self._get_file_state(event.src_path)
            if st is not None:
                self._file_state[event.src_path] = st
        if not self._debounced(event):
            self._log(event)

    def on_modified(self, event):
        if event.is_directory or should_ignore(event.src_path):
            return
        # Ignorar lecturas (mtime_ns/size iguales) ANTES del debounce
        if not self._has_real_change(event.src_path):
            return
        if not self._debounced(event):
            self._log(event)

    def on_deleted(self, event):
        if not should_ignore(event.src_path):
            self._file_state.pop(event.src_path, None)
            self._last.pop(event.src_path, None)
            self._log(event)

    def on_moved(self, event):
        if should_ignore(event.src_path) and should_ignore(event.dest_path):
            return
        self._file_state.pop(event.src_path, None)
        self._last.pop(event.src_path, None)
        if not event.is_directory:
            st = self._get_file_state(event.dest_path)
            if st is not None:
                self._file_state[event.dest_path] = st
        self._log(event)


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


def run_foreground() -> int:
    pid = _read_pid()
    if pid and pid != os.getpid() and _pid_alive(pid):
        print(f"[vigilante] Ya hay otra instancia (PID {pid}). Saliendo.", file=sys.stderr)
        return 1
    _write_pid()
    print(f"[vigilante] Iniciando... Proyecto: {PROJECT_ROOT}")
    print(f"[vigilante] Log semanal: {weekly_log_path()}")
    print(f"[vigilante] Ignorando: {', '.join(sorted(IGNORE_DIRS))}")
    handler = ChangeHandler()
    observer = Observer()
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
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))