#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Archiva mensajes leidos antiguos del buzon compartido de ZeroScript.

Por defecto solo muestra lo que haria (simulacion). Con --apply mueve los
mensajes leidos mas antiguos que mailbox_archive_days a
``mailbox_dir/archive/YYYY-MM``. Nunca mueve mensajes sin leer y nunca borra
nada.

Ejemplos:
    py -3 limpiar_buzon.py
    py -3 limpiar_buzon.py --apply
    py -3 limpiar_buzon.py --days 90 --apply
    py -3 limpiar_buzon.py --mailbox C:\\ruta\\al\\buzon
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mailbox_store  # noqa: E402


def log(message: str) -> None:
    print(f"[limpiar-buzon] {message}", file=sys.stderr, flush=True)


def config_path() -> Path:
    raw = os.environ.get("ZS_PC_CONFIG", "").strip()
    if not raw:
        return HERE / "pc_agent_config.json"
    raw = os.path.expandvars(os.path.expanduser(raw))
    path = Path(raw)
    return path if path.is_absolute() else HERE / path


def read_config(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as exc:
        log(f"no se pudo leer {path}: {exc}; usando valores por defecto")
        return {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Archiva mensajes leidos antiguos del buzon de las IAs.",
    )
    parser.add_argument(
        "--mailbox",
        default="",
        help="Carpeta del buzon (por defecto pc_agent_config.json o ZS_PC_MAILBOX_DIR).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=0,
        help="Antiguedad minima en dias (por defecto mailbox_archive_days, 30).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Mueve los mensajes; sin esta opcion solo cuenta (simulacion).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="No muestra los avisos de archivos corruptos o ilegibles.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = read_config(config_path())
    raw_mailbox = (
        args.mailbox
        or os.environ.get("ZS_PC_MAILBOX_DIR")
        or config.get("mailbox_dir")
    )
    root = mailbox_store.resolve_mailbox_dir(raw_mailbox, base_dir=HERE)

    try:
        configured = int(config.get("mailbox_archive_days") or 30)
    except Exception:
        configured = 30
    days = args.days if args.days else configured
    days = max(1, min(3650, days))

    try:
        moved, kept = mailbox_store.archive_messages(
            root,
            days=days,
            apply=bool(args.apply),
            log=None if args.quiet else log,
        )
    except Exception as exc:
        log(f"ERROR: {exc}")
        return 1

    print(f"Buzon: {root}")
    if args.apply:
        print(f"Mensajes leidos con mas de {days} dias movidos: {moved}.")
        print(f"Archivo: {root / 'archive'}")
    else:
        print(f"Mensajes leidos con mas de {days} dias que se moverian: {moved}.")
        print("Simulacion: no se movio nada. Usa --apply para archivar.")
    print(f"Conservados (sin leer o recientes): {kept}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
