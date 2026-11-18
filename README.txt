# ZeroScript - Free AI Agent for your PC (and Roblox Studio)

![GitHub stars](https://img.shields.io/github/stars/sebattfg/ZeroScript-Free?style=social)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey)
![License](https://img.shields.io/badge/license-GPL--3.0-blue)

**ZeroScript** is a free browser extension that turns ChatGPT, DeepSeek, Gemini, Kimi, GLM, Qwen, Arena or Meta AI into an agent for your own computer.
From a normal AI chat, the AI can read and write files, search folders, and run commands on your PC through a local bridge. No API key, no terminal, no coding needed. Roblox Studio is supported as an optional addon, so existing Roblox workflows keep working.

> 🌐 **Website: [zerodev.tools/zeroscript](https://zerodev.tools/zeroscript)**

Eight AI providers are supported: **DeepSeek** (chat.deepseek.com, recommended), **ChatGPT** (chatgpt.com), **Google Gemini** (gemini.google.com), **Kimi** (kimi.ai, Moonshot AI), **GLM** (chat.z.ai, Z.ai), **Qwen** (chat.qwen.ai), **Arena** (arena.ai, a multi-model playground) and **Meta AI** (meta.ai). On ChatGPT, screenshots and image input are turned off on purpose: the free tier limits files and images on a separate quota from messages, so vision would only work part of the day. Gemini and Kimi can be unstable: Gemini tends to stop using the ZeroScript commands in long sessions, and Kimi sometimes uses its own native tools instead of the ZeroScript commands. On Arena, use **Direct** mode (ZeroScript only supports Direct; it blocks Start in Battle / Side-by-Side / Agent modes). DeepSeek is the recommended provider.

> 💬 **Stuck? Join the [Discord community](https://discord.gg/9aNyZsMWcb)** get help, share feedback, and follow updates.

> *Also known as: ZeroScript PC agent, ZeroScript local AI agent, ChatGPT desktop agent, DeepSeek PC agent, free AI file editor, AI shell agent, ZeroScript Roblox, Roblox ChatGPT agent, Roblox DeepSeek agent, Roblox Studio AI automation, Luau AI, MCP Roblox, free MCP client*

## ⚠️ ZeroScript is Free Beware of Paid Copycats

ZeroScript is 100% free and open-source. It always has been, and it always will be. There is no official paid version, no subscription, and no sign-in required to use the extension.

If you come across a site or extension using the ZeroScript name that asks for payment or account creation, it is **not** this project. The only official links are the ones listed at the top of this README.

## How it works

```
AI chat (ChatGPT / DeepSeek / Gemini / Kimi / GLM / Qwen / Arena / Meta AI)
        -> ZeroScript extension
        -> Bridge (your PC, ws://127.0.0.1:17613)
        -> PC agent (files + shell)   [optional: Roblox Studio MCP]
```

The extension runs inside the chat page. When the AI writes a ZeroScript command, the extension sends it to the Bridge on your PC, which runs it through the local MCP servers and sends the result back to the chat. Files and commands are executed locally; the results then travel to the AI as part of the conversation, so treat this like pasting that output into the chat.

## What the AI can do

**On your PC (always available):**

- Inspect the system (OS, user, home folder, drives, workspace)
- List folders and read files, with line numbers
- Create and rewrite files, or make exact string edits
- Find files by glob and search file contents
- Run shell commands (PowerShell on Windows, bash on macOS/Linux)
- **Remember your project across sessions** with `.zeroscript-memory.md` in the workspace

**With Roblox Studio (optional addon):**

- Read and edit scripts, inspect the game tree and instances
- Run Luau code directly in Studio
- Generate meshes, materials, and models
- Browse and insert from the Creator Store
- Control play-testing
- Keep the shared project memory inside the place

## Setup

> 📺 **Lost? Watch the [setup tutorial on YouTube](https://youtu.be/kPKiZLZ9_Ps).**

### 1. Download the zip and install the extension

Download the latest zip from the **Releases** page and extract it. The zip contains both the **Bridge** and the **extension folder**.

To load the extension:

- Go to `edge://extensions` (Edge) or `chrome://extensions` (Chrome)
- Enable **Developer mode** (top right toggle)
- Click **Load unpacked**
- Select the `zeroscript-extension` folder from the extracted zip

### 2. Run the Bridge

- **Windows:** double-click `start.bat` inside the extracted folder.
- **macOS:** double-click `MacOS_Start.command` inside the extracted folder. The first time, macOS will show a security warning ("could not verify... free of malware") - this is normal for any script downloaded outside the App Store, click **Done**, then go to **System Settings > Privacy & Security**, scroll to the bottom, and click **Open Anyway**. You only need to do this once.

A small window opens, that means the Bridge is running. It starts the **PC agent** automatically - Roblox Studio is not needed for this.

### 3. Start a session

Go to https://chat.deepseek.com (recommended), https://chatgpt.com, https://gemini.google.com, https://www.kimi.ai, https://chat.z.ai, https://chat.qwen.ai, https://arena.ai or https://www.meta.ai and open a new chat. The ZeroScript bar appears above the input box. Click **Start agent** and tell the AI what to do.

> Only works on chat.deepseek.com, chatgpt.com, gemini.google.com, kimi.ai, chat.z.ai, chat.qwen.ai, arena.ai and meta.ai - it will not work on any other site.
> On Arena, keep the mode dropdown on **Direct** - ZeroScript blocks Start in Battle / Side-by-Side / Agent modes (it only drives a single Direct reply).

### 4. (Optional) Add Roblox Studio

Roblox is an addon in 2.0.0 and later:

1. In Studio, open a place and enable MCP: **Assistant AI > ... > Manage MCP Servers > Enable Studio as MCP Server**.
2. In the ZeroScript panel, open **MCP servers**, set the name to `roblox` and the start command to `launch_studio_mcp.py`, then click **Add server**.
3. The bridge restarts briefly and the Roblox commands appear next to the PC tools.

You can also add the `roblox` entry directly to `config.json`:

```json
{
  "mcpServers": {
    "pc": { "command": "pc_agent_mcp.py", "args": [] },
    "roblox": { "command": "launch_studio_mcp.py", "args": [] }
  }
}
```

### 5. (Optional) Connect Claude Desktop, OpenCode or Antigravity

`pc_agent_mcp.py` is also a standard **stdio MCP server**, so other MCP clients can launch it directly - the bridge does not need to be running. Check the setup and generate a ready-to-paste configuration:

```bat
py -3 pc_agent_mcp.py --check
py -3 pc_agent_mcp.py --print-config claude
```

`--print-config` accepts `generic`, `claude`, `antigravity` or `opencode`. See [MCP_CLIENTS.md](MCP_CLIENTS.md) for the exact settings file of each client, environment overrides and troubleshooting.

> Standalone clients bypass the browser confirmation for writes and shell commands. Use `pc_agent_config.json`, `ZS_PC_WORKSPACE`, `ZS_PC_ALLOW_OUTSIDE_WORKSPACE` or `ZS_PC_ALLOW_SHELL` to limit what they can do.

### 6. (Optional) Local chat between AIs

`start.bat` also starts a small page at <http://127.0.0.1:8765> that shows the shared mailbox as a chat. Messages you write there are signed as `usuario`; the page writes to the same folder as `msg_send`, does not mark anything read, and only listens on `127.0.0.1`. If you start the bridge another way, run `chat-local\iniciar_chat.bat`; stop the page with `chat-local\detener_chat.bat` (or close the bridge window, which stops it automatically).

Old read messages can be moved out of the active list without deleting them:

```bat
py -3 limpiar_buzon.py          REM dry run
py -3 limpiar_buzon.py --apply  REM move read messages older than 30 days
```

One AI can also wake the other when a new message arrives. The bridge starts the watcher automatically on boot, and `despertar.py` only simulates when you run it by hand:

```bat
py -3 despertar.py              REM show what it would do
py -3 despertar.py --apply      REM wake claude and opencode now
py -3 despertar.py --status     REM recent wakes, failures and remaining budget
py -3 despertar.py --watch --apply  REM watch in the foreground (bridge does this by itself)
```

The default method is `cli` (for example `claude -p` or `opencode run`); the GUI
fallback is opt-in in `despertar_config.json`. If the CLI is missing, fails, or
exits 0 without leaving a reply (checked by `require_reply`), the message stays
unread and the watcher retries with backoff. Create an empty file named `wake_off`
next to the script to disable it instantly. `ZS_WAKE_WATCH=0` disables the
automatic watcher for one launch. See `MCP_CLIENTS.md` for the loop limits and
the per-target configuration.

**Explicit wake token.** A new message only wakes the other AI when its subject
or body contains `@despertar` (or `[despertar]`); without it the message waits in
the mailbox and nobody answers. That keeps a chat with one AI from waking the
other one by accident. Replies never wake anyone. Change or disable the
requirement in the `trigger` block of `despertar_config.json`; `--status` shows
the current setting.

On this machine OpenCode is ready out of the box: the CLI copied from the Store
app lives at `%LOCALAPPDATA%\Programs\ZeroScript\opencode.exe`, shares the
`zeroscript-pc` MCP configuration, and uses the free
`opencode/deepseek-v4.1-flash-free` model. Claude is manual: the free account
only has chat, so it has no CLI and is not watched. Open Claude Desktop and ask
it for `msg_inbox`, or add a custom instruction to check the mailbox when a chat
starts.

## PC agent configuration

The PC agent reads `pc_agent_config.json` from the ZeroScript folder, next to `pc_agent_mcp.py`. The defaults are:

| Setting | Default | Meaning |
|---------|---------|---------|
| `workspace` | your home folder | Root for relative paths |
| `mailbox_dir` | `~/Documents/AI-Shared/mailbox` | Shared mailbox for messages between AI clients |
| `allow_outside_workspace` | `true` | Absolute paths outside the workspace are allowed |
| `allow_shell` | `true` | `pc_shell` may run commands |
| `shell_timeout_ms` | `120000` | Default shell timeout; a call may request up to 600000 |
| `max_read_bytes` | `2000000` | Larger files are refused |
| `max_output_chars` | `40000` | Tool output is truncated past this |
| `max_grep_results` | `100` | Default result cap for searches |
| `max_hops` | `6` | Maximum reply-chain length between AIs |
| `max_msgs_per_10min` | `30` | Maximum messages one sender may write in 10 minutes |
| `max_message_chars` | `20000` | Maximum mailbox message body |
| `mailbox_archive_days` | `30` | Age used by `limpiar_buzon.py` |
| `skip_dirs` | `.git`, `node_modules`, ... | Folders skipped by glob/grep |

To lock the agent to a project, set `workspace` to its folder and `allow_outside_workspace` to `false`. To disable shell access entirely, set `allow_shell` to `false`.

By default, `pc_write`, `pc_edit` and `pc_shell` ask you to confirm in the browser before they run. You can turn that off with **Ask me before writing files or running commands** in the panel (it is stored in `chrome.storage.local`).

## New in 2.3.0

- **`msg_wait` and safer inboxes.** A twelfth tool waits up to 55 seconds for a new message instead of forcing the model to poll. `msg_inbox` truncates long bodies per message, reports `body_chars`/`body_truncated`, marks read only what it actually returned, and prefixes every result with a warning that mailbox content comes from another AI and is untrusted.
- **Loop and flood protection.** `max_hops` (6), `max_msgs_per_10min` (30) and `max_message_chars` (20000) stop a reply chain or a runaway agent; invalid `reply_to` ids are rejected before a file is written.
- **Shared mailbox code.** `mailbox_store.py` now validates, reads, writes and marks messages atomically for both `pc_agent_mcp.py` and the chat page, so the two paths cannot drift apart.
- **Rewritten local chat.** `chat-local` uses the same store, reads `mailbox_dir` from `pc_agent_config.json`, adds `/api/health`, caches messages, scans connected agents at most every 30 seconds, requires a same-origin request for `usuario`, stores unsigned messages as `sin-firma`, validates `reply_to`, and sends security headers. The launcher waits for the page to answer, keeps a PID file, and supports `-Stop`; `detener_chat.bat` stops it.
- **`start.bat` lifecycle.** It checks `server.py`, `chat.html`, `lanzar_chat.ps1` and the Python path before launching the chat, passes port 8765 explicitly, and stops the chat server when the bridge exits so no orphan process keeps the port.
- **`limpiar_buzon.py`.** Moves read messages older than `mailbox_archive_days` to `mailbox_dir/archive/YYYY-MM`; dry-run by default, never touches unread mail, never deletes.
- **`as` label.** Optional sender/reader label for two AIs that share one MCP process; it is a convenience label, not authentication.
- **Client setup.** OpenCode V2 uses `opencode mcp add ... --env ZS_PC_AGENT_NAME=opencode`; Claude Desktop uses `"env": { "ZS_PC_AGENT_NAME": "claude" }`. See [MCP_CLIENTS.md](MCP_CLIENTS.md).

## New in 2.2.0

- **Shared mailbox between AI clients.** `msg_send`, `msg_inbox` and `msg_reply` let Claude Desktop, OpenCode, Antigravity or a browser-only client exchange messages through `~/Documents/AI-Shared/mailbox` (configurable with `mailbox_dir`).
- **One identity per client.** Set `ZS_PC_AGENT_NAME` to `claude`, `opencode` or any other name. `msg_inbox` returns only that name's messages and marks them read atomically; an empty inbox returns exactly `Sin mensajes nuevos.` so the model stays silent.
- **Safe message files.** One JSON file per message, with a chronological filename, ISO 8601 timestamp, unique id, optional subject and `reply_to`. All `msg_*` paths stay inside `mailbox_dir`.
- **Setup helpers updated.** `--check` shows the agent name, mailbox path and all 11 tools; `--print-config claude|opencode` adds the matching `ZS_PC_AGENT_NAME`.

See [MCP_CLIENTS.md](MCP_CLIENTS.md) for the mailbox workflow and the web-client alternative.

## New in 2.1.0

- **Any MCP client can use the PC agent.** Claude Desktop, OpenCode V2, Antigravity and other MCP clients can launch `pc_agent_mcp.py` directly over stdio. The bridge is only needed by the browser extension.
- **`MCP_CLIENTS.md`** documents the exact configuration file and steps for each client, plus environment overrides and troubleshooting.
- **Setup helpers.** `--check` validates Python, the workspace and permissions; `--print-config generic|claude|antigravity|opencode` prints a ready-to-paste JSON block with absolute paths. `pc_agent_mcp.cmd` finds Python automatically on Windows.
- **Better protocol compatibility.** The server negotiates MCP revisions from `2024-11-05` through `2025-11-25`, forces UTF-8 on stdio, sends initialization `instructions`, and adds tool titles and read-only/destructive annotations.
- **Per-connection profiles.** `ZS_PC_CONFIG`, `ZS_PC_WORKSPACE`, `ZS_PC_ALLOW_OUTSIDE_WORKSPACE`, `ZS_PC_ALLOW_SHELL` and `ZS_PC_SHELL_TIMEOUT_MS` override `pc_agent_config.json` without duplicating it.

## New in 2.0.0

- **ZeroScript is no longer Roblox-only.** The primary MCP server is now `pc`, a local agent that can inspect the system, list/read/write/edit files, find files with glob, search contents with grep, and run shell commands. It works with every supported provider.
- **Roblox Studio is an optional addon.** The default `config.json` contains only `pc`; add `roblox` from the panel when you want Studio tools. All the existing Studio diagnostics, Luau blocks and project memory keep working when it is connected.
- **Confirmations for local changes.** `pc_write`, `pc_edit` and `pc_shell` show a browser confirmation unless you disable it in the panel.
- **PC project memory.** The agent keeps durable notes in `.zeroscript-memory.md` at the workspace root, and still uses `game.ServerStorage.ZeroScript.Memory` for Roblox places.
- **Rewritten system prompt and UI.** The bar, setup card, popup and errors now describe a general PC agent instead of "Roblox Studio first", and only mention Studio when its server is actually configured.

See [CHANGELOG.md](CHANGELOG.md) for older releases.

## Panel status

| Dot | Meaning |
|-----|---------|
| Green | Bridge + PC agent ready |
| Yellow | Bridge OK, but the PC agent is offline - restart the bridge. With Roblox configured, it also means Studio is not usable yet (open a place or enable its MCP server) - hover the dot for the exact reason |
| Grey | Bridge offline - run start.bat (Windows) or MacOS_Start.command (macOS) |

## Requirements

- Windows or macOS
- Microsoft Edge or Chrome
- Python 3.9+ (installed automatically on Windows, or install it yourself on macOS - see [python.org/downloads](https://www.python.org/downloads/))
- Roblox Studio only if you want the optional Roblox addon

## Support

ZeroScript is free. If it saves you time: [Ko-fi](https://ko-fi.com/sebattfg) - Robux tip passes available in the extension panel

---

Credit: the idea for connecting other MCP servers (Blender, Sketchfab, etc.) alongside Roblox Studio came from [javnpa](https://github.com/javnpa).

Credit: macOS/Linux support contributed by [archivealf](https://github.com/archivealf).
