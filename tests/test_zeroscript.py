#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Suite de pruebas automatizadas en Python (biblioteca estandar)."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import bridge  # noqa: E402
import despertar  # noqa: E402
import mailbox_store  # noqa: E402
import pc_agent_mcp as mcp  # noqa: E402
import vigilante_cambios as vig  # noqa: E402


def _load_chat_server():
    spec = importlib.util.spec_from_file_location("chat_local_server", ROOT / "chat-local" / "server.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMailboxStore(unittest.TestCase):
    def test_create_list_mark_read_archive_and_ignore_hidden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mb = Path(tmp) / "mailbox"
            mb.mkdir()
            # Archivos ocultos y locks deben ignorarse en iter_messages
            (mb / ".wake_lock_antigravity.lock").write_text('{"expires_at": 9999999999}', encoding="utf-8")
            (mb / ".hidden.json").write_text('{"id":"x"}', encoding="utf-8")
            (mb / ".msg-tmp.json").write_text('{"id":"y"}', encoding="utf-8")

            mid, path, msg = mailbox_store.create_message(
                mb,
                sender="DeepSeek-V3",
                to="antigravity",
                body="Hola prueba",
                subject="[PROPUESTA] Prueba",
            )
            self.assertEqual(msg["from"], "DeepSeek-V3")
            self.assertFalse(msg["read"])

            items = mailbox_store.iter_messages(mb)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0][1]["id"], mid)

            updated = mailbox_store.mark_read(path, msg)
            self.assertTrue(updated["read"])

            # Forzar antiguedad para probar archivado sin dormir
            old_ts = "2020-01-01T10:00:00.000-04:00"
            updated["ts"] = old_ts
            mailbox_store.atomic_write_json(path, updated)
            moved_dry, _kept = mailbox_store.archive_messages(mb, days=1, apply=False)
            self.assertEqual(moved_dry, 1)
            self.assertTrue(path.exists())

            moved, kept = mailbox_store.archive_messages(mb, days=1, apply=True)
            self.assertEqual(moved, 1)
            self.assertEqual(kept, 0)
            self.assertFalse(path.exists())
            archived = list((mb / "archive").rglob("*.json"))
            self.assertEqual(len(archived), 1)


class TestPcAgentControls(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ws = (root / "ws").resolve()
        self.mb = (root / "mailbox").resolve()
        self.ws.mkdir()
        self.mb.mkdir()
        self._orig = {
            "workspace": mcp.CFG["workspace"],
            "mailbox_dir": mcp.CFG["mailbox_dir"],
            "agent_name": mcp.CFG["agent_name"],
            "agent_aliases": set(mcp.CFG.get("agent_aliases") or ()),
            "max_hops": mcp.CFG["max_hops"],
            "allow_write": mcp.CFG["allow_write"],
            "allow_shell": mcp.CFG["allow_shell"],
        }
        mcp.CFG["workspace"] = self.ws
        mcp.CFG["mailbox_dir"] = self.mb
        mcp.CFG["agent_name"] = "DeepSeek-V3"
        mcp.CFG["agent_aliases"] = {"deepseek"}
        mcp.CFG["max_hops"] = 6
        mcp.CFG["allow_write"] = True
        mcp.CFG["allow_shell"] = True

    def tearDown(self) -> None:
        for k, v in self._orig.items():
            mcp.CFG[k] = v
        self._tmp.cleanup()

    def test_optimistic_concurrency_and_consecutive_edits(self) -> None:
        target = self.ws / "demo.txt"
        target.write_text("uno\ndos\n", encoding="utf-8")

        read_out = mcp.tool_read({"path": "demo.txt"})
        self.assertIn("[rev:", read_out)

        # Modificacion externa en disco despues de pc_read
        target.write_text("uno externo\ndos\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Colision de concurrencia"):
            mcp.tool_edit({"path": "demo.txt", "old_string": "dos", "new_string": "tres"})
        with self.assertRaisesRegex(ValueError, "Colision de concurrencia"):
            mcp.tool_write({"path": "demo.txt", "content": "sobrescritura"})

        # Volver a leer habilita ediciones consecutivas del mismo agente
        mcp.tool_read({"path": "demo.txt"})
        r1 = mcp.tool_edit({"path": "demo.txt", "old_string": "dos", "new_string": "dos-ok"})
        r2 = mcp.tool_edit({"path": "demo.txt", "old_string": "dos-ok", "new_string": "dos-ok2"})
        self.assertIn("Edited", r1)
        self.assertIn("Edited", r2)
        self.assertIn("dos-ok2", target.read_text(encoding="utf-8"))

    def test_task_state_included_in_system_info(self) -> None:
        (self.ws / "ESTADO_TAREA.md").write_text(
            "## Objetivo\nValidar beta\n## Pendientes\nTests",
            encoding="utf-8",
        )
        out = mcp.tool_system_info()
        self.assertIn('"task_state_file": "ESTADO_TAREA.md"', out)
        self.assertIn("Validar beta", out)

    def test_fixed_identity_rejects_spoofing(self) -> None:
        self.assertEqual(mcp._resolve_alias({}), "DeepSeek-V3")
        self.assertEqual(mcp._resolve_alias({"as": "deepseek"}), "DeepSeek-V3")
        self.assertEqual(mcp._resolve_alias({"as": "zeroscript"}), "DeepSeek-V3")
        with self.assertRaisesRegex(ValueError, "Identidad fija"):
            mcp._resolve_alias({"as": "claude"})
        with self.assertRaisesRegex(ValueError, "Identidad fija"):
            mcp._resolve_alias({"as": "usuario"})

    def test_hops_pair_ring_cycle_and_unrelated_tasks(self) -> None:
        # 1. Tareas distintas sin ciclo: opencode -> gemini (hops=1), luego gemini -> antigravity con @despertar
        mcp.CFG["agent_name"] = "opencode"
        mcp.CFG["agent_aliases"] = set()
        r_init = mcp.tool_msg_send({"to": "gemini", "body": "respuesta inicial"})
        id_init = [ln.split(": ", 1)[1] for ln in r_init.splitlines() if ln.startswith("id: ")][0]
        mcp.CFG["agent_name"] = "gemini"
        mcp.tool_msg_reply({"id": id_init, "body": "sigo viendo"})
        # Otro mensaje de opencode -> gemini via msg_send (ahora hay arco opencode->gemini con hops=1)
        mcp.CFG["agent_name"] = "opencode"
        res_og = mcp.tool_msg_send({"to": "gemini", "body": "algo mas"})
        self.assertIn("hops:", res_og)

        # Ahora el usuario pide a gemini en su chat que despierte a antigravity (tarea nueva, sin ciclo)
        mcp.CFG["agent_name"] = "gemini"
        res_new = mcp.tool_msg_send({"to": "antigravity", "body": "@despertar revisa docs"})
        self.assertIn("hops: 0", res_new)

        # Verificar que despertar.py SI acepta ese mensaje para antigravity
        rows = despertar.collect_messages(
            self.mb,
            "antigravity",
            include_read=False,
            max_age_hours=24.0,
            processed=[],
            allowed_senders=["gemini*"],
            trigger_tokens=["@despertar"],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["reason"], "")

        # 2. Usuario reinicia o usamos tres nodos limpios en anillo: a -> b -> c -> a -> ...
        mailbox_store.create_message(self.mb, sender="usuario", to="todos", body="nuevo ciclo")
        ring = [("a", "b"), ("b", "c"), ("c", "a"), ("a", "b"), ("b", "c"), ("c", "a"), ("a", "b")]
        seen_hops = []
        for src, dst in ring:
            mcp.CFG["agent_name"] = src
            res = mcp.tool_msg_send({"to": dst, "body": "@despertar rebote"})
            hop_val = int([ln.split(": ", 1)[1] for ln in res.splitlines() if ln.startswith("hops: ")][0])
            seen_hops.append(hop_val)
        self.assertGreaterEqual(seen_hops[-1], 6)

        mcp.CFG["agent_name"] = "b"
        with self.assertRaisesRegex(ValueError, "Limite de saltos alcanzado"):
            mcp.tool_msg_send({"to": "c", "body": "bucle 7"})

    def test_wake_lock_blocks_mutations_and_clears_only_on_matching_reply(self) -> None:
        (self.ws / "nota.txt").write_text("hola\n", encoding="utf-8")
        mcp.CFG["agent_name"] = "antigravity"
        mcp.CFG["agent_aliases"] = set()
        mid, _p, _m = mailbox_store.create_message(
            self.mb,
            sender="opencode",
            to="antigravity",
            body="@despertar revisa",
        )
        lock_file = despertar.set_window_wake_lock(self.mb, "antigravity", mid, 90.0)
        self.assertTrue(lock_file.is_file())

        with self.assertRaisesRegex(PermissionError, "Modo despertar automatico activo"):
            mcp.tool_write({"path": "nota.txt", "content": "x"})
        with self.assertRaisesRegex(PermissionError, "Modo despertar automatico activo"):
            mcp.tool_edit({"path": "nota.txt", "old_string": "hola", "new_string": "adios"})
        with self.assertRaisesRegex(PermissionError, "Modo despertar automatico activo"):
            mcp.tool_shell({"command": "echo hi"})

        # Responder a otro id NO quita el wake_lock activo
        old_id, _p2, _m2 = mailbox_store.create_message(self.mb, sender="claude", to="antigravity", body="viejo")
        mcp.tool_msg_reply({"id": old_id, "body": "otro hilo"})
        self.assertTrue(lock_file.is_file())

        # Responder al id exacto SI limpia el wake_lock y desbloquea
        mcp.tool_msg_reply({"id": mid, "body": "leido y respondido"})
        self.assertFalse(lock_file.exists())
        mcp.tool_read({"path": "nota.txt"})
        self.assertIn("Edited", mcp.tool_edit({"path": "nota.txt", "old_string": "hola", "new_string": "ok"}))


class TestDespertarAndWatcherAndRouting(unittest.TestCase):
    def test_despertar_allowed_senders_wildcards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mb = Path(tmp) / "mb"
            mb.mkdir()
            mailbox_store.create_message(mb, sender="DeepSeek-V3", to="opencode", body="@despertar revisa")
            mailbox_store.create_message(mb, sender="sin-firma", to="opencode", body="@despertar intruso")
            rows = despertar.collect_messages(
                mb,
                "opencode",
                include_read=False,
                max_age_hours=24.0,
                processed=[],
                allowed_senders=["deepseek*", "usuario"],
                trigger_tokens=["@despertar"],
            )
            by_sender = {r["message"]["from"]: r["reason"] for r in rows}
            self.assertEqual(by_sender["DeepSeek-V3"], "")
            self.assertEqual(by_sender["sin-firma"], "remitente no permitido")

    def test_vigilante_ignores_zs_lock(self) -> None:
        self.assertTrue(vig.should_ignore(Path("archivo.py.zs.lock")))
        self.assertTrue(vig.should_ignore(Path(".archivo.py.zs.lock")))

    def test_bridge_disambiguates_tabs_and_chat_server_detects_flag(self) -> None:
        mgr = bridge.MCPManager()
        mgr.specs["pc"] = {"command": "pc_agent_mcp.py", "args": [], "env": {}}
        holder = bridge.MCPClient("pc", "pc_agent_mcp.py", [])
        mgr.clients["pc"] = holder

        c1 = mgr._client_for_agent(holder, "ChatGPT-4o", provider="chatgpt", tab_id=1)
        c2 = mgr._client_for_agent(holder, "ChatGPT-4o", provider="chatgpt", tab_id=2)
        self.assertEqual(c1.id, "pc:ChatGPT-4o")
        self.assertEqual(c2.id, "pc:ChatGPT-4o-2")
        self.assertIn("--agent", c1.args)
        self.assertIn("ChatGPT-4o", c1.args)
        self.assertIn("ChatGPT-4o-2", c2.args)

        chat_srv = _load_chat_server()
        match = chat_srv._AGENT_FLAG_RE.search('runtime\\python\\python.exe pc_agent_mcp.py --agent Qwen3.7-Plus')
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "Qwen3.7-Plus")


if __name__ == "__main__":
    unittest.main()
