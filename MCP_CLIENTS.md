# Connect ZeroScript's PC agent to other MCP clients

`pc_agent_mcp.py` is a standard **stdio MCP server**. The ZeroScript browser
extension reaches it through `bridge.py`, but any MCP client that can launch a
local process can use it directly: Claude Desktop, OpenCode, Antigravity,
Cline, Continue, Windsurf, or your own client.

The bridge does **not** need to be running for these clients. They start
`pc_agent_mcp.py` themselves. Do not point them at `config.json`: that file is
the bridge's server list. Use the configuration snippet generated below in the
client's own settings file.

Requirements: **Python 3.9 or newer**. The server only uses the standard
library, so there is nothing to `pip install`.

> **Security:** standalone clients bypass the browser confirmation that
> ZeroScript shows for `pc_write`, `pc_edit` and `pc_shell`. Your client's own
> approval UI and the limits in `pc_agent_config.json` are the safety boundary.
> See [Safety and configuration](#safety-and-configuration).

## 1. Check the server

Open a terminal in the ZeroScript folder:

```bat
cd "C:\path\to\ZeroScript-Free-1.5.5"
py -3 pc_agent_mcp.py --version
py -3 pc_agent_mcp.py --check
```

`--check` prints the agent identity, mailbox path, workspace, permissions,
limits, tool list and protocol versions. It exits with code 0 when everything
is usable.

Generate the exact configuration for your client instead of copying paths by
hand:

```bat
py -3 pc_agent_mcp.py --print-config            REM generic mcpServers (Claude, Antigravity, most clients)
py -3 pc_agent_mcp.py --print-config claude     REM same shape, for Claude Desktop
py -3 pc_agent_mcp.py --print-config antigravity
py -3 pc_agent_mcp.py --print-config opencode   REM OpenCode V2 mcp.servers
```

The generated JSON uses the absolute path of the Python interpreter that ran
the command and the absolute path of `pc_agent_mcp.py`. Regenerate it if you
move the folder. On Windows you can also use `pc_agent_mcp.cmd` as the command;
it finds `py -3` or `python` automatically.

### What the server exposes

| Tool | Kind | What it does |
| --- | --- | --- |
| `pc_system_info` | read-only | OS, user, home, workspace, drives, permissions |
| `pc_list` | read-only | List a directory |
| `pc_read` | read-only | Read a text file as `LINE|CONTENT` |
| `pc_glob` | read-only | Find files by glob (`**` supported) |
| `pc_grep` | read-only | Search file contents |
| `pc_write` | destructive | Create or overwrite a text file |
| `pc_edit` | destructive | Exact string replacement in a file |
| `pc_shell` | destructive | Run PowerShell (Windows) or bash |
| `msg_send` | destructive | Send a message to another AI's mailbox |
| `msg_inbox` | non-destructive | Read this agent's unread messages and mark them read |
| `msg_wait` | non-destructive | Wait up to 55 s for a new message, then read it |
| `msg_reply` | destructive | Reply to a mailbox message by id |

Tools include MCP `title` and `annotations` (`readOnlyHint`,
`destructiveHint`, `idempotentHint`, `openWorldHint`), so clients that support
annotations can auto-approve reads while still asking for writes and shell.
`msg_inbox` and `msg_wait` are not read-only because they change the `read`
flag, but their `destructiveHint` is false: they never delete or overwrite
message text.

## 2. Claude Desktop

Config file:

- Windows installer: `%APPDATA%\Claude\claude_desktop_config.json`
- Windows **Microsoft Store**: `%LOCALAPPDATA%\Claude-Data\claude_pzs8sxrjxfjjc\claude_desktop_config.json` (if the package folder differs, search for `claude_desktop_config.json` under `%LOCALAPPDATA%\Claude-Data`)
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

When available, **Developer > Edit Config** in Claude Desktop opens the file
the app actually reads. Use that instead of guessing the path.

Merge this into the file (keep any existing `mcpServers` entries):

```json
{
  "mcpServers": {
    "zeroscript-pc": {
      "command": "C:\\path\\to\\Python\\python.exe",
      "args": ["C:\\path\\to\\ZeroScript-Free-1.5.5\\pc_agent_mcp.py"],
      "env": {
        "ZS_PC_AGENT_NAME": "claude"
      }
    }
  }
}
```

The `env` block gives this client its own mailbox identity (`claude` here). Use
a different name for every client that shares the mailbox: OpenCode would use
`opencode`, for example. `--print-config claude` already adds this line; if you
edit the file by hand, do not omit it or Claude will read the default
`zeroscript` inbox.

Use the output of `--print-config claude` to fill in the two paths. Then fully
quit Claude from the tray (closing the window is not enough) and reopen it.
The Microsoft Store build can rewrite `claude_desktop_config.json` from memory
while it is running, so close the app **before** editing or the new server may
disappear. After reopening, open the tools/connectors menu in the chat and make
sure `zeroscript-pc` is enabled; a connected server still has to be enabled for
that conversation. Claude asks before each call by default.

Logs: `%APPDATA%\Claude\logs\` (macOS: `~/Library/Logs/Claude/`). For the
Microsoft Store build, look in
`%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\Claude\logs\`.
Look for the `mcp-server-zeroscript-pc` log if the server does not appear.

> Claude Desktop starts the process without a terminal, so use the absolute
> `python.exe` path. A bare `python` may resolve to the Microsoft Store alias.

> **Cowork / local agent mode:** Cowork has its own sandbox and only exposes the
> folders under its allowed roots (see `coworkUserFilesPath` in Claude's
> `config.json`, usually `C:\Users\Usuario\Claude`). Native file tools cannot
> reach other folders. Local MCP tools can also be missing on the first turn of
> a fresh Cowork session; use a regular Claude chat for ZeroScript, or send a
> second message and allow the `zeroscript-pc` tools when they appear.

## 3. OpenCode (V2)

The quickest route is the CLI, from the project where you want the tools:

```bat
opencode mcp add zeroscript-pc --env ZS_PC_AGENT_NAME=opencode -- "C:\path\to\Python\python.exe" "C:\path\to\ZeroScript-Free-1.5.5\pc_agent_mcp.py"
opencode mcp list
```

Add `--global` to make it available in every project:

```bat
opencode mcp add zeroscript-pc --global --env ZS_PC_AGENT_NAME=opencode -- "C:\path\to\Python\python.exe" "C:\path\to\ZeroScript-Free-1.5.5\pc_agent_mcp.py"
```

Or edit `opencode.json` / `opencode.jsonc` directly. V2 stores servers under
`mcp.servers` (not directly under `mcp`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "zeroscript-pc": {
        "type": "local",
        "command": [
          "C:\\path\\to\\Python\\python.exe",
          "C:\\path\\to\\ZeroScript-Free-1.5.5\\pc_agent_mcp.py"
        ],
        "environment": {
          "ZS_PC_AGENT_NAME": "opencode"
        },
        "timeout": { "execution": 660000 }
      }
    }
  }
}
```

`--print-config opencode` produces exactly this, with the real paths, the
`opencode` agent identity and a timeout derived from `shell_timeout_ms`.
`opencode mcp add` accepts `--env ZS_PC_AGENT_NAME=opencode` (V2 2.1.4 and
later), so the CLI route keeps the identity too. Restart OpenCode after editing
the file. `opencode mcp list` should show `zeroscript-pc  connected`; if it
prints `No MCP servers configured` while the app already shows the tools, run
`opencode mcp list --print-logs --log-level debug` to see the live status.

Notes:

- Code Mode is on by default, so the tools may appear as
  `tools.zeroscript_pc.pc_read(...)`. Set `"codemode": false` on the server to
  expose them as ordinary tools.
- OpenCode's default execution timeout is 12 hours; the generated 11 minutes
  covers `pc_shell`'s 600-second maximum. Lower it if you prefer faster
  failures, or raise it if you allow longer commands.
- The server's initialization `instructions` are added to OpenCode's system
  prompt automatically.

## 4. Antigravity (App, IDE and CLI)

Open **Customizations > Installed > MCP Servers**, click **Add MCP Server**,
or edit the JSON directly. In the App/IDE, **Copy Config File Path** in the
MCP Servers section shows the file your installation uses. Common locations:

- Global: `%USERPROFILE%\.gemini\config\mcp_config.json`
- Workspace (CLI/SDK): `<project>\.agents\mcp_config.json`

Antigravity uses the same `mcpServers` shape as Claude Desktop, plus its own
optional `timeoutSeconds`:

```json
{
  "mcpServers": {
    "zeroscript-pc": {
      "command": "C:\\path\\to\\Python\\python.exe",
      "args": ["C:\\path\\to\\ZeroScript-Free-1.5.5\\pc_agent_mcp.py"],
      "timeoutSeconds": 660
    }
  }
}
```

Use `--print-config antigravity` for the exact block. Save, then restart the
server (or Antigravity). Tools are lazy-loaded by default: Antigravity caches
each schema under its app-data `mcp/zeroscript-pc/` folder, and the server's
`instructions` are written next to them. Add `"tools": {"pc_read": {"eager":
true}}` if you want a specific tool registered up front.

MCP tools start in **Ask** mode. Use Antigravity's permissions to allow reads
or the whole server, for example `mcp(zeroscript-pc/*)`, if you do not want a
prompt for every call.

## 5. Other MCP clients

Most clients accept an `mcpServers` object with `command`, `args` and optional
`env`:

```json
{
  "mcpServers": {
    "zeroscript-pc": {
      "command": "C:\\path\\to\\Python\\python.exe",
      "args": ["C:\\path\\to\\ZeroScript-Free-1.5.5\\pc_agent_mcp.py"],
      "env": {
        "ZS_PC_AGENT_NAME": "zeroscript"
      }
    }
  }
}
```

If your client asks for the transport, choose **stdio** (not SSE or HTTP) and
point it at the Python executable; do not try to connect to the bridge port.
`--print-config generic` prints this shape.

For clients that support environment variables, a tighter profile can be set
per connection without editing the JSON config. Add these keys to the same
`env` block:

```json
"env": {
  "ZS_PC_AGENT_NAME": "my-agent",
  "ZS_PC_WORKSPACE": "C:\\Projects\\demo",
  "ZS_PC_ALLOW_OUTSIDE_WORKSPACE": "false",
  "ZS_PC_ALLOW_SHELL": "false"
}
```

## 6. Shared mailbox between AI clients

All `pc_agent_mcp.py` processes can exchange messages through one folder of
JSON files. They must use the same `mailbox_dir`; the default is
`~/Documents/AI-Shared/mailbox`, which on Windows is
`C:\Users\<you>\Documents\AI-Shared\mailbox`. The folder is created the first
time a message is sent; reading an empty folder (or one that does not exist yet)
just returns `Sin mensajes nuevos.`

Give every client a different identity through `ZS_PC_AGENT_NAME`:

| Client | Configuration line |
| --- | --- |
| Claude Desktop | `"env": { "ZS_PC_AGENT_NAME": "claude" }` |
| OpenCode V2 | `"environment": { "ZS_PC_AGENT_NAME": "opencode" }` |

Without it the identity is `zeroscript`. The name is the `from` field written
by `msg_send`/`msg_reply`, and `msg_inbox` only returns messages whose `to`
matches it (case-insensitive). Never use the same name for two clients that
share a mailbox.

Each message is one JSON file named
`<timestamp_unix_ms><from><short_id>.json`, for example
`1763123456789claude4f2a9c1d.json`. The fixed-width timestamp prefix makes the
filename sort chronologically. The file contains:

```json
{
  "id": "4f2a9c1d0b7e4c3a9f6d5e2a1b8c7d6e",
  "from": "claude",
  "to": "opencode",
  "subject": "Review the patch",
  "body": "Please check pc_agent_mcp.py and reply with any problems.",
  "ts": "2026-11-14T18:30:00.123+01:00",
  "reply_to": null,
  "hops": 0,
  "read": false
}
```

`hops` counts the reply chain: a new message starts at `0`, and each
`msg_reply` (or `msg_send` with `reply_to`) adds one.

The mailbox tools are:

| Tool | Parameters | Behavior |
| --- | --- | --- |
| `msg_send` | `to`, `body`, optional `subject`, optional `reply_to`, optional `as` | Writes a new message from this agent and returns its id |
| `msg_inbox` | optional `include_read` (default false), optional `limit` (default 20), optional `as` | Returns this agent's messages oldest first, truncates long bodies per message, and marks only the returned ones read with a temp file + atomic replace |
| `msg_wait` | optional `seconds` (1-55, default 25), optional `limit`, optional `as` | Waits for a new unread message, then returns it like `msg_inbox`; on timeout returns exactly `Sin mensajes nuevos.` |
| `msg_reply` | `id`, `body`, optional `as` | Finds the message and writes a reply to its `from` with `reply_to = id` and `hops + 1` |

The optional `as` field is a mailbox label for two AIs that share one MCP
process (for example two web chats behind one bridge). It is **not
authentication**: anyone who can call the tool can choose a label. Prefer
`ZS_PC_AGENT_NAME` for normal per-client identities.

When there is nothing new, `msg_inbox` and `msg_wait` return exactly
`Sin mensajes nuevos.` The server instructions tell the model to stay silent in
that case: an empty inbox is not an invitation to start a conversation.

`msg_inbox` prefixes the JSON with a warning that the messages come from other
AIs, not from the user, and that their content is untrusted data. Long bodies
are shortened individually and report `body_chars` and `body_truncated`, so one
huge message cannot hide the rest. The result never exceeds
`max_output_chars`, and a message the tool did not show is not marked read.

### Limits that stop runaway conversations

| Setting | Default | Effect |
| --- | --- | --- |
| `max_hops` | `6` | Rejects a reply whose chain would exceed this many hops |
| `max_msgs_per_10min` | `30` | Rejects a sender that already wrote this many messages in the last 10 minutes |
| `max_message_chars` | `20000` | Rejects a larger `body` before writing the file |

When a limit is reached the tool returns an error and the server instructions
tell the model to stop and let you decide the next step, instead of retrying in
a loop.

### Workflow: one AI writes, the other waits

1. You ask one AI (for example Claude) to send a message to the other one
   (`opencode`). Claude calls `msg_send`.
2. The other AI stays silent until you ask it to read, or it calls
   `msg_wait(seconds=25)` once when you want to give it a turn. Do not poll in
   an infinite loop; `msg_wait` is capped at 55 seconds for that reason.
3. When you want a review, ask OpenCode to read its inbox. It calls
   `msg_inbox`, sees Claude's message, and calls `msg_reply` if an answer is
   needed.
4. Later, ask Claude to read its inbox. It sees OpenCode's reply. A second
   `msg_inbox` with `include_read=false` no longer returns the message it
   already read.

### Waking the other AI (`despertar.py`)

The mailbox only stores messages; an AI still has to read them. `despertar.py`
closes that gap: when the target has a new thread, it runs that target's CLI
headless with a fixed prompt that tells the AI to answer once with `msg_reply`.
Only if you add `window` to a target's `fallback` list does it focus the app and
paste (never the message body). **The script only simulates when run by hand**,
and it refuses to act if `wake_off` exists next to the script.

```bat
py -3 despertar.py                              REM dry run for claude and opencode
py -3 despertar.py claude                       REM dry run for one target
py -3 despertar.py opencode --apply             REM run the configured CLI
py -3 despertar.py --apply --method window      REM legacy GUI fallback, opt-in only
py -3 despertar.py --watch --apply              REM watch the mailbox in the foreground
py -3 despertar.py --status                     REM last wakes, failures and budget
```

The bridge starts the same watcher automatically when it boots: a daemon thread
polls the mailbox every `watch.interval_seconds` (2.5 s by default), and at most
one target is woken per cycle. It is not a separate process, so closing the
`start.bat` window stops it cleanly; any CLI child still running is terminated.
`ZS_WAKE_WATCH=0` disables it for one launch, and the `wake_off` file disables
every `--apply` until removed. `method` defaults to `cli`; `window` is only used
if you put it in that target's `fallback` list. On failure the message is never
marked read or processed: it stays in the mailbox, the error is logged, and the
watcher retries with 30 s, 60 s, 120 s, 240 s and 300 s backoff up to
`max_attempts`. After that, `--status` shows `fallos agotados` and
`--reset-failures` re-arms it. `require_reply` (true by default) also checks that
a reply with `reply_to` equal to the woken message exists after the CLI exits: a
CLI that exits 0 without replying is treated as a failure, so a CLI missing the
mailbox MCP is caught instead of silently consuming the wake.

Loop protection, all active at once:

1. Only new threads (`reply_to` empty, `hops` 0) can wake an AI; replies never do.
2. `wake_state.json` remembers every message already used, so no message wakes twice.
3. Messages whose subject starts with `[auto]` are ignored.
4. Budget: at most one wake every 60 s, 6 per hour and 20 per day.
5. The `wake_off` file next to the script disables every `--apply` immediately.
6. The wake prompt is fixed by configuration; the message body is never injected.
7. At most one message is processed per run, oldest first.
8. **Explicit trigger.** With `"trigger": {"require": true}` (the default in this
   install), a new message only wakes the AI if its subject or body contains
   `@despertar` or `[despertar]` (case-insensitive; `tokens` in the config). A
   message without the token stays in the mailbox and nobody is woken, so a
   chatty sender cannot make the wrong AI answer. Replies never wake anyone,
   with or without the token. `despertar.py --status` prints the requirement and
   a simulation marks such messages as `falta el disparador @despertar`.

Targets live in `despertar_config.json`: `process` is a list of process names,
`title` is an optional regex for the window title, and `command` is the argv
template used by `--method cli` (`{prompt}` is replaced with one argument). The
default presets are `claude` (`claude.exe`) and `opencode` (`OpenCode Dev`).
`allowed_senders` (empty by default, meaning anyone) restricts which mailbox
identities may trigger a wake; list the trusted ones there when several agents
share the mailbox. `require_reply` (true by default) marks a CLI or window wake
as failed unless a reply to that message appears in the mailbox; the window
wait is `window_reply_timeout_seconds` (90 s by default).
`--method window` uses the clipboard plus `SendKeys`, so the window must be able
to come to the foreground; if Windows blocks it, the script fails without typing
and asks you to click the window. The prompt stays in the clipboard afterwards.

The CLI you wake must have the ZeroScript MCP server configured in its own
profile: `claude -p` does not share a conversation, session or MCP configuration
with the Claude Desktop app. The OpenCode 2.1.4 CLI used here does read the same
`~/.config/opencode/opencode.json` as the desktop app, but do not assume that for
other versions or CLIs. If the CLI profile lacks the mailbox tools, it will wake
with no way to read the message; `require_reply` catches that case and records a
failure instead of marking the message processed. Configure it first (sections 2
and 3 above) and test with `--status`.

**This installation (15-nov-2026):** OpenCode Dev bundles a CLI in its
`resources\opencode-cli.exe`; it was copied to
`%LOCALAPPDATA%\Programs\ZeroScript\opencode.exe`. That CLI reads
`~/.config/opencode/opencode.json`, which already declares `zeroscript-pc`, and
`opencode mcp list` reports it connected. `despertar_config.json` runs it with
`--model opencode/deepseek-v4.1-flash-free` (free; other models may need
credits). Do **not** add `--standalone`: it starts a private server without the
MCP servers. The CLI uses OpenCode's background service, not a process started
by the bridge. Claude is **not** in the watcher: this account is chat-only, so
`despertar_config.json` sets `method: "none"` and the watcher only handles
`opencode`. Open Claude Desktop and ask for `msg_inbox` (or add a custom
instruction to check the mailbox at the start of a chat); the message stays in
the mailbox until then.

The `msg_send` description and the server instructions sent by
`pc_agent_mcp.py` mention the wake token, so an AI knows to include it when it
wants the other one to answer. Restart any MCP client that was already running
(Claude Desktop, the OpenCode app) so it receives the updated text; every CLI
wake starts a fresh process and reads it automatically.

**Claude Desktop can be woken through the window.** Tested on 15-nov-2026:
`despertar.py claude --apply --method window` brought the Claude window to the
foreground, pasted the fixed prompt and pressed Enter; Claude read the mailbox
message with `msg_inbox` and replied `hello` with `msg_reply`. The first time,
Claude shows a permission dialog ("Claude quiere usar Read mailbox inbox /
Reply to mailbox message") and answers without tools until you press **Permitir
siempre** once per tool. Its config lives in
`%LOCALAPPDATA%\Claude-Data\claude_pzs8sxrjxfjjc\claude_desktop_config.json`
(identity `claude`), not in `%APPDATA%\Claude`. Since 15-nov-2026 the window
method also honors `require_reply`: it waits `window_reply_timeout_seconds`
(90 s for `claude`) for a reply and records a failure with backoff if none
appears. The wake prompt tells the AI to retry with `include_read=true` when
`msg_inbox` says "Sin mensajes nuevos.", because the prompt itself may have
already marked the message as read. Windows sometimes keeps another app in the
foreground; the script taps ALT, retries `SetForegroundWindow`/`AppActivate`,
then minimize+restore, and only pastes when the Claude window really is in
front. If it cannot focus it, it fails without typing.

`despertar.bat` is a small wrapper for doing it by hand; it requires a command:

```bat
despertar.bat /opencode          REM wake opencode for real
despertar.bat /claude            REM only shows status; Claude is manual here
despertar.bat /opencode /simular REM show what it would do
```

With no arguments it prints help and exits 1. The automatic watcher is the
bridge, so there is nothing to schedule. Keep `min_seconds_between` and the
hourly/daily caps low; raise `max_hops` only together with them, because it is
the last brake on a reply chain.

### The local chat page

`chat-local/iniciar_chat.bat` (or the `start.bat` window) opens
<http://127.0.0.1:8765>: the same mailbox rendered as a chat. Messages written
there are signed as `usuario`; a request without a valid origin is rejected,
and a message without a sender is stored as `sin-firma`. The page only listens
on `127.0.0.1`, reads `mailbox_dir` from `pc_agent_config.json`, and does not
mark messages read. Stop it with `chat-local\detener_chat.bat` or by closing the
bridge window.

### Archiving old messages

`limpiar_buzon.py` moves read messages older than `mailbox_archive_days`
(default 30) into `mailbox_dir/archive/YYYY-MM`. It never moves unread mail and
never deletes anything:

```bat
py -3 limpiar_buzon.py                 REM dry run: only prints what it would move
py -3 limpiar_buzon.py --apply         REM move the old read messages
py -3 limpiar_buzon.py --days 90 --apply
```

### Web clients without the mailbox tools

A browser-only AI connected through the ZeroScript bridge can use the same
mailbox without `msg_send`/`msg_inbox`/`msg_wait`/`msg_reply`: it can list the
folder with `pc_glob` or `pc_list`, read messages with `pc_read`, and create
them with `pc_write`. Use the same JSON fields and a filename with a 13-digit
epoch milliseconds prefix, e.g. `1763123456789webclient1a2b3c4d.json`. Set
`"hops": 0` on a new message. To consume a message, write the whole object back
with `"read": true`.

The `pc_*` tools still obey `workspace` and `allow_outside_workspace`. If you
lock the workspace to a project, either put `mailbox_dir` inside that project
or allow outside access for that client. The `msg_*` tools themselves always
stay confined to `mailbox_dir` and reject absolute paths and `..`.

## Safety and configuration

`pc_agent_config.json` next to `pc_agent_mcp.py` controls the server:

| Key | Default | Meaning |
| --- | --- | --- |
| `workspace` | `""` = user home | Root for relative paths |
| `mailbox_dir` | `~/Documents/AI-Shared/mailbox` | Shared folder for AI-to-AI messages; relative values resolve against the script folder |
| `allow_outside_workspace` | `true` | Allow absolute paths outside the workspace |
| `allow_shell` | `true` | Allow `pc_shell` |
| `shell_timeout_ms` | `120000` | Default command timeout; calls may request up to 600000 |
| `max_read_bytes` | `2000000` | Largest file `pc_read` accepts |
| `max_output_chars` | `40000` | Tool output is truncated at this length |
| `max_grep_results` | `100` | Maximum `pc_grep` matches |
| `max_hops` | `6` | Maximum reply-chain length; longer chains are rejected |
| `max_msgs_per_10min` | `30` | Maximum messages one sender may write in 10 minutes |
| `max_message_chars` | `20000` | Maximum mailbox `body` length |
| `mailbox_archive_days` | `30` | Age used by `limpiar_buzon.py` for read messages |
| `skip_dirs` | build/vendor folders | Folders pruned by `pc_glob`/`pc_grep` |

Environment variables override the JSON file:

| Variable | Overrides |
| --- | --- |
| `ZS_PC_CONFIG` | Path to a different config file (absolute, or relative to the script folder) |
| `ZS_PC_WORKSPACE` | `workspace` |
| `ZS_PC_ALLOW_OUTSIDE_WORKSPACE` | `allow_outside_workspace` (`1/true/yes/on` or `0/false/no/off`) |
| `ZS_PC_ALLOW_SHELL` | `allow_shell` |
| `ZS_PC_SHELL_TIMEOUT_MS` | `shell_timeout_ms` |
| `ZS_PC_AGENT_NAME` | Mailbox identity (default `zeroscript`) |
| `ZS_PC_MAILBOX_DIR` | `mailbox_dir` (absolute, or relative to the script folder) |

A practical setup is to keep the default config broad for the browser
extension and give standalone clients a narrower profile through `env` or a
dedicated JSON file:

```json
"env": {
  "ZS_PC_CONFIG": "C:\\path\\to\\ZeroScript-Free-1.5.5\\pc_agent_config.strict.json"
}
```

With `allow_outside_workspace: false`, every path is confined to the
workspace. With `allow_shell: false`, `pc_shell` refuses to run and the model
is told so in the server instructions. This is the main protection when a
client has no approval prompt.

The server writes MCP framing and tool results to **stdout** and logs to
**stderr** only. Do not wrap it in a script that prints banners to stdout, or
the client will see invalid JSON.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Client says the server exited immediately | Run `py -3 pc_agent_mcp.py --check` in the same folder and fix what it reports |
| `python` opens the Microsoft Store | Use `py -3` or the absolute `python.exe` path |
| Server works in a terminal but not in the client | Use absolute paths; GUI clients do not inherit your terminal `PATH` |
| Tools do not appear | Restart the client; check `opencode mcp list`, Claude's `mcp-server-*` log, or Antigravity's MCP server status |
| `pc_shell` times out | Raise `shell_timeout_ms` (max 600000) and the client timeout (`timeoutSeconds` / `timeout.execution`) |
| `pc_read` output has `LINE|` prefixes | That prefix is not file content; never pass it to `pc_edit.old_string` |
| `msg_inbox` always says `Sin mensajes nuevos.` | Check that the sending client uses `to` equal to this client's `ZS_PC_AGENT_NAME`, and that both use the same `mailbox_dir` |
| A mailbox tool reports `Limite de saltos` or `Limite de mensajes` | That is the loop protection working; do not retry in a loop. Summarize the state and ask the user to decide |
| A returned body ends with `[truncado: N caracteres]` | The body exceeded the per-message budget; read the JSON file directly with `pc_read` if you need the full text |
| Old read messages vanished from the chat page | They were moved to `mailbox_dir\archive\YYYY-MM` by `limpiar_buzon.py`; unread messages are never moved |
| The chat page shows `sin-firma` | The request had no valid `from`; the page normally sends `from: usuario`. Write from the page or set a label explicitly |
| The folder was moved | Regenerate the client config with `--print-config` |
