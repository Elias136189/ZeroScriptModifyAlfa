#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprobacion basica del proyecto antes de un commit.

Uso:
  python comprobar_proyecto.py

Revisa:
  1. Que todos los .py compilen (py_compile).
  2. Que los JSON del proyecto sean validos y tengan las claves esperadas.
  3. Que el manifest de la extension siga siendo manifest v3 con las claves
     minimas y sin rutas absolutas.
  4. Que no haya rutas personales (C:\\Users\\<usuario>) en los archivos que
     se van a publicar.
  5. Que existan los archivos imprescindibles.

Devuelve 0 si todo esta bien y 1 si hay algun problema.
"""

import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROBLEMAS = []
AVISOS = []

PY_FILES = [
    "bridge.py",
    "pc_agent_mcp.py",
    "mailbox_store.py",
    "despertar.py",
    "vigilante_cambios.py",
    "limpiar_buzon.py",
    "launch_studio_mcp.py",
    "chat-local/server.py",
    "comprobar_proyecto.py",
]

JSON_FILES = {
    "pc_agent_config.example.json": ["workspace", "allow_shell", "allow_outside_workspace"],
    "pc_agent_config.restricted.example.json": ["workspace", "allow_shell", "allow_outside_workspace"],
    "despertar_config.example.json": ["enabled", "watch", "targets"],
    "zeroscript-extension/manifest.json": ["manifest_version", "name", "version", "content_scripts"],
    "config.json": [],
}

OBLIGATORIOS = [
    "bridge.py",
    "pc_agent_mcp.py",
    "start.bat",
    "LICENSE",
    "README-ALPHA.md",
    "zeroscript-extension/manifest.json",
    "chat-local/server.py",
]

# Rutas personales tipicas de este equipo. Se avisa, no se falla: los .example
# usan TU_USUARIO a proposito.
PATRONES_PERSONALES = ["C:\\Users\\Usuario", "/home/Usuario"]
ARCHIVOS_EXCLUIDOS_RUTAS = {"README-ALPHA.md", "comprobar_proyecto.py", ".gitignore"}


def revisar_python():
    for rel in PY_FILES:
        p = ROOT / rel
        if not p.exists():
            AVISOS.append(f"falta (opcional?): {rel}")
            continue
        try:
            py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as exc:
            PROBLEMAS.append(f"no compila {rel}: {exc.msg}")


def revisar_json():
    for rel, claves in JSON_FILES.items():
        p = ROOT / rel
        if not p.exists():
            PROBLEMAS.append(f"falta JSON obligatorio: {rel}")
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            PROBLEMAS.append(f"JSON invalido {rel}: {exc}")
            continue
        for clave in claves:
            if clave not in data:
                PROBLEMAS.append(f"{rel}: falta la clave '{clave}'")


def revisar_manifest():
    p = ROOT / "zeroscript-extension/manifest.json"
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return  # ya lo reporta revisar_json
    if data.get("manifest_version") != 3:
        PROBLEMAS.append("manifest.json: se esperaba manifest_version 3")
    if not data.get("content_scripts"):
        PROBLEMAS.append("manifest.json: content_scripts vacio")
    if "key" not in data:
        AVISOS.append("manifest.json: sin campo 'key'; el ID dependera de la ruta")
    hosts = data.get("host_permissions") or []
    if len(hosts) not in (8, 14):
        AVISOS.append(f"manifest.json: {len(hosts)} host_permissions (se esperaban 8 o 14)")


def revisar_obligatorios():
    for rel in OBLIGATORIOS:
        if not (ROOT / rel).exists():
            PROBLEMAS.append(f"falta archivo obligatorio: {rel}")


def revisar_rutas_personales():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(("backups/", "logs/", "__pycache__/", ".git/")):
            continue
        if rel in ARCHIVOS_EXCLUIDOS_RUTAS:
            continue
        if p.suffix.lower() not in (".py", ".json", ".md", ".bat", ".ps1", ".vbs", ".cmd", ".js"):
            continue
        try:
            texto = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for patron in PATRONES_PERSONALES:
            if patron in texto:
                AVISOS.append(f"ruta personal en {rel} ({patron})")
                break


def main() -> int:
    revisar_python()
    revisar_json()
    revisar_manifest()
    revisar_obligatorios()
    revisar_rutas_personales()

    print("== Comprobacion del proyecto ==")
    if PROBLEMAS:
        print(f"\nPROBLEMAS ({len(PROBLEMAS)}):")
        for p in PROBLEMAS:
            print(f"  - {p}")
    if AVISOS:
        print(f"\nAVISOS ({len(AVISOS)}):")
        for a in AVISOS:
            print(f"  - {a}")
    if not PROBLEMAS:
        print("\nOK: sin problemas bloqueantes.")
    return 1 if PROBLEMAS else 0


if __name__ == "__main__":
    raise SystemExit(main())
