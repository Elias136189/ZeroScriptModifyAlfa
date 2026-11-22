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
  6. Que `ZS_BRIDGE_EXTENSION_ID` en los lanzadores coincida con el ID que
     Chrome deriva de la ruta actual (la carpeta puede cambiar de nombre).
  7. Que la extension siga incluyendo las herramientas del agente de PC.
  8. Que los .bat/.cmd usen finales de linea CRLF (cmd.exe falla con goto/call
     de etiquetas en archivos LF).

Devuelve 0 si todo esta bien y 1 si hay algun problema.
"""

import base64
import hashlib
import json
import py_compile
import re
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
ARCHIVOS_EXCLUIDOS_RUTAS = {
    "README-ALPHA.md",
    "comprobar_proyecto.py",
    ".gitignore",
    "INFORME_CODIGO_MCP.md",  # informe historico, conserva rutas reales
}


def revisar_python():
    for rel in PY_FILES:
        p = ROOT / rel
        if not p.exists():
            AVISOS.append(f"falta (opcional?): {rel}")
            continue
        try:
            source = p.read_bytes()
            compile(source, str(p), "exec")
        except SyntaxError as exc:
            PROBLEMAS.append(f"no compila {rel}: linea {exc.lineno}: {exc.msg}")
        except OSError as exc:
            PROBLEMAS.append(f"no se pudo leer {rel}: {exc}")


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
    else:
        try:
            raw_key = base64.b64decode(str(data["key"]), validate=True)
            if len(raw_key) < 64:
                PROBLEMAS.append("manifest.json: el campo 'key' es demasiado corto")
        except Exception:
            PROBLEMAS.append("manifest.json: el campo 'key' no es base64 valido")
    hosts = data.get("host_permissions") or []
    if len(hosts) not in (8, 14):
        AVISOS.append(f"manifest.json: {len(hosts)} host_permissions (se esperaban 8 o 14)")


def id_extension(ruta: Path) -> str:
    """ID de una extension unpacked: SHA-256 de su ruta absoluta en UTF-16LE."""
    digest = hashlib.sha256(str(ruta).encode("utf-16-le")).hexdigest()[:32]
    return "".join(chr(ord("a") + int(c, 16)) for c in digest)


def id_extension_desde_key(key_b64: str) -> str:
    """ID de una extension con campo 'key' en manifest.json: SHA-256 del DER."""
    digest = hashlib.sha256(base64.b64decode(key_b64)).hexdigest()[:32]
    return "".join(chr(ord("a") + int(c, 16)) for c in digest)


def revisar_id_extension():
    manifest = ROOT / "zeroscript-extension/manifest.json"
    if not manifest.exists():
        return
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return  # ya lo reporta revisar_json

    if "key" in data:
        try:
            esperado = id_extension_desde_key(str(data["key"]))
        except Exception:
            return  # ya lo reporta revisar_manifest
    else:
        esperado = id_extension(ROOT / "zeroscript-extension")

    patron = re.compile(r"ZS_BRIDGE_EXTENSION_ID=([a-p]{32})")
    vistos = {}
    for rel in ("start.bat", "bridge_segundo_plano.vbs"):
        p = ROOT / rel
        if not p.exists():
            continue
        texto = p.read_text(encoding="utf-8", errors="ignore")
        m = patron.search(texto)
        if not m:
            # Con "key" en manifest.json, bridge.py deriva el ID automaticamente
            if "key" not in data:
                AVISOS.append(f"{rel}: no fija ZS_BRIDGE_EXTENSION_ID")
            continue
        vistos[rel] = m.group(1)
        if m.group(1) != esperado:
            PROBLEMAS.append(
                f"{rel}: ZS_BRIDGE_EXTENSION_ID={m.group(1)} no coincide con el ID "
                f"esperado ({esperado})"
            )
    if len(set(vistos.values())) > 1:
        PROBLEMAS.append("start.bat y bridge_segundo_plano.vbs fijan IDs distintos")


def revisar_extension_agente_pc():
    """La extension debe incluir las herramientas del agente de PC."""
    esperados = {
        "zeroscript-extension/core/main.js": "confirmPc",
        "zeroscript-extension/core/config.js": "pc_shell",
    }
    for rel, marca in esperados.items():
        p = ROOT / rel
        if not p.exists():
            continue  # lo cubre OBLIGATORIOS o la carga de la extension
        try:
            texto = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if marca not in texto:
            PROBLEMAS.append(
                f"{rel}: falta '{marca}'; faltan herramientas del agente de PC "
                "o la confirmacion previa"
            )


def revisar_bat_crlf():
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in (".bat", ".cmd"):
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(("backups/", "logs/", ".git/", "runtime/")):
            continue
        try:
            datos = p.read_bytes()
        except OSError:
            continue
        sueltos = len(re.findall(rb"(?<!\r)\n", datos))
        if sueltos:
            PROBLEMAS.append(f"{rel}: {sueltos} finales de linea LF (los .bat/.cmd deben ser CRLF)")


def revisar_obligatorios():
    for rel in OBLIGATORIOS:
        if not (ROOT / rel).exists():
            PROBLEMAS.append(f"falta archivo obligatorio: {rel}")


def revisar_rutas_personales():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(("backups/", "logs/", "__pycache__/", ".git/", "runtime/")):
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
    revisar_id_extension()
    revisar_extension_agente_pc()
    revisar_bat_crlf()
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
