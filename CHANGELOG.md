# Changelog

All notable changes to ZeroScript Free are documented here.

## [Unreleased]

### Fixed — evaluación y arreglo (18-nov-2026)
- **Extensión restaurada a la versión del agente de PC (2.2.0).** Ocho archivos de
  `zeroscript-extension` (`manifest.json`, `popup.html`, `popup.js`, `background.js`,
  `overlay.css`, `README.md`, `core/config.js`, `core/main.js`) habían vuelto a una
  versión anterior sin herramientas `pc_*` ni la confirmación previa `confirmPc`. Las 45
  pruebas de la extensión pasaban igualmente porque no cubren esas partes. Se
  restauraron desde el commit `c05399a`; lo que había quedó en
  `backups\extension-revertida-20261118`.
- **`comprobar_proyecto.py` detecta esa regresión** (falta de `confirmPc` o de
  `pc_shell`) y los `.bat`/`.cmd` con finales de línea LF.
- **`pc_write` y `pc_edit` escriben de forma atómica** (archivo temporal en la misma
  carpeta + `os.replace`): un corte o un disco lleno ya no dejan el archivo a medias.
- **`pc_edit` conserva la codificación** (UTF-8, UTF-8 con BOM o cp1252) y **adapta
  `\n` a CRLF** cuando el archivo usa CRLF, así que las ediciones de varias líneas
  casan y no quedan finales mezclados. Si el texto nuevo no cabe en la codificación
  original, escribe UTF-8 y lo avisa en la respuesta.
- **Los 6 `.bat`/`.cmd` que seguían en LF pasan a CRLF** y `.gitattributes` fija
  `*.bat` y `*.cmd` como `eol=crlf`.
- `background.js`: `const URL` renombrado a `BRIDGE_URL` (ya no oculta la clase global).
- `pc_agent_mcp.py`: eliminada `_safe_filename_part`, que no usaba nadie.
- `.gitignore`: se ignoran los accesos directos `*.lnk`.

### Added — preparación de la alfa
- **`vigilante_cambios.py`.** Registro semanal de cambios del proyecto con
  `watchdog`: CREATED/MODIFIED/DELETED/MOVED tanto de archivos como de
  carpetas, con el usuario de Windows como columna de autor. Se instala con
  `instalar_vigilante.bat` y se consulta con `ver [N]`.
- **`comprobar_proyecto.py`.** Comprobación previa al commit: `py_compile` de
  todos los `.py`, validez y claves de los JSON, manifest v3, archivos
  obligatorios y aviso de rutas personales.
- **`README-ALPHA.md`.** Presentación del fork no oficial: qué es, requisitos,
  instalación, seguridad, limitaciones conocidas y estructura.
- **Configuraciones de ejemplo** (`pc_agent_config.example.json`,
  `pc_agent_config.restricted.example.json`, `despertar_config.example.json`)
  para publicar el repo sin rutas reales de ningún PC.

### Changed — renombrado de la carpeta (18-nov-2026)
- **La carpeta del proyecto pasa a `ZeroScriptModify`.** `start.bat`,
  `bridge_segundo_plano.vbs`, el VBS de Inicio del vigilante y las
  configuraciones de los clientes MCP (OpenCode, Claude Desktop,
  Antigravity) apuntan a la ruta nueva. Como el manifest no declara `key`, el
  ID de la extensión cambia con la ruta: el valor fijado ahora es
  `jgigjkahlhhfcmbnlbmbbcdpeljdkidp`, y la extensión debe quitarse y volver a
  cargarse desde `zeroscript-extension`.

### Changed — preparación de la alfa
- **Rechazo de conexiones sin cabecera `Origin`.** El bridge ya no acepta
  clientes locales sin `Origin`; solo la extensión fijada en
  `ZS_BRIDGE_EXTENSION_ID` y los orígenes de `ZS_BRIDGE_ALLOWED_ORIGINS`.
  `ZS_BRIDGE_ALLOW_ANY_ORIGIN=1` lo desactiva (no recomendado).
- **`.gitignore` ampliado** para la publicación: ignora `backups/`, `*.antes-*`,
  `workspace_wake/`, `*.pid` y las configuraciones reales; los `.example.json`
  sí se publican.

### Fixed
- **`start.bat` no longer opens extra console windows.** It launches the bridge
  with `pythonw.exe` directly (no `cmd /c` wrapper, no VBScript), so the bridge
  and the PC agent run with no window at all and survive closing the launcher
  window. The launcher now reports the PID that owns port 17613.
- **`start.bat` uses CRLF again.** The LF-only copy made `cmd` mis-parse blocks
  and `goto`, which caused a random `pause` after "Found pythonw.exe", the
  final `No se esperaba .` and the interpreter-less `-m`/`-c` errors.
- **`:validate_py` no longer runs with an empty `PY`**, so cmd stops printing
  `"-m" no se reconoce` / `"-c" no se reconoce` before Python is found.
- **The local chat server is no longer stopped** three seconds after the
  launcher opens it; it now stays available at `http://127.0.0.1:8765`.
- `taskkill /T` when replacing a bridge, so its `pc_agent_mcp.py` child does not
  stay behind as an orphan.

### Changed
- **The mailbox wake watcher is now called "mensajero"** in bridge logs, `--status`
  and `start.bat` text. It still runs as a hidden daemon thread inside the bridge
  and the CLI wake already uses `CREATE_NO_WINDOW`, so waking an AI opens no
  console window. Internal file names (`despertar.py`, `despertar_config.json`,
  `despertar.bat`) are unchanged for compatibility.

## [2.4.0] - 2026-11-15

### Added
- **Automatic wake watcher.** `bridge.py` starts `despertar.watch_loop()` in a
  daemon thread: it polls the shared mailbox every 2.5 s and wakes at most one
  target per cycle. It stops with the bridge and terminates any CLI child.
  `ZS_WAKE_WATCH=0` disables it for one launch.
- **CLI wake method.** `despertar.py` now defaults to `cli` (`claude -p`,
  `opencode run`) with an optional per-target `fallback` list; the GUI
  clipboard/SendKeys path is opt-in only.
- **Failure backoff.** Failed wakes are recorded in `wake_state.json` with
  exponential backoff (30/60/120/240/300 s, `max_attempts: 5`); the message is
  never marked read or processed. `--reset-failures` re-arms it. A CLI that
  exits 0 without leaving a reply is a failure too (`require_reply`).
- **`allowed_senders`.** Optional allow-list of mailbox identities that may
  trigger a wake.
- **Explicit wake token.** `"trigger": {"require": true, "tokens": ["@despertar",
  "[despertar]"]}` means a new message only wakes the AI when the subject or body
  contains one of the tokens. Without it the message waits in the mailbox, so a
  chat with one AI cannot wake the other by accident. Replies never wake anyone.
- **Window wakes verify the reply.** `require_reply` now also covers
  `--method window`: it waits `window_reply_timeout_seconds` (90 s for `claude`)
  and records a failure with backoff if no reply appears. The launcher taps ALT,
  retries `SetForegroundWindow`/`AppActivate` and minimize+restore before typing,
  because Windows blocks focus changes from background processes, and it never
  pastes if it cannot confirm the target window is in front.

### Changed
- `--watch` requires `--apply`; `--status` reports failures and watcher state.
- `despertar.bat` and `start.bat` text now describe the automatic watcher.
- **Claude is manual.** The free Claude account only has chat, so there is no
  Claude Code CLI to wake. The `claude` target is `method: "none"` and is not in
  the watcher; open Claude Desktop and ask for `msg_inbox`.

### Fixed
- `despertar.bat` no longer shows the help block for `/claude` or `/opencode`:
  an unescaped `)` inside the `if not defined TARGET (...)` block closed it
  early, so the help lines and `exit /b 1` ran unconditionally. The launcher now
  uses `goto` labels and no parenthesised blocks.

## [2.3.0] - 2026-11-14

### Added
- **`msg_wait`.** A twelfth mailbox tool waits up to 55 seconds for a new
  unread message and returns it like `msg_inbox`; on timeout it returns exactly
  `Sin mensajes nuevos.` This gives the other AI a turn without asking the user
  to poll in a loop.
- **Reply and flood limits.** `max_hops` (default 6) rejects a reply chain that
  is already too long, `max_msgs_per_10min` (default 30) rejects a sender that
  floods the mailbox, and `max_message_chars` (default 20000) rejects an
  oversized body before writing the file.
- **`as` label.** `msg_send`, `msg_inbox`, `msg_wait` and `msg_reply` accept an
  optional mailbox label for two AIs that share one MCP process. It is a label,
  not authentication; normal setups should keep using `ZS_PC_AGENT_NAME`.
- **`limpiar_buzon.py`.** Moves read messages older than
  `mailbox_archive_days` (default 30) to `mailbox_dir/archive/YYYY-MM`.
  Dry-run by default, `--apply` to move, `--days N` to change the age; unread
  messages are never moved and nothing is deleted.
- **Chat health and lifecycle.** `chat-local/server.py` exposes
  `/api/health`, and `chat-local/lanzar_chat.ps1` waits for that endpoint and
  the page before opening the browser, writes a per-port PID file, reuses an
  existing server, and supports `-Stop`. `chat-local/detener_chat.bat` stops it.

### Changed
- **One mailbox implementation.** New `mailbox_store.py` validates, reads,
  writes, marks and archives messages for both `pc_agent_mcp.py` and
  `chat-local/server.py`, so both paths enforce the same limits and atomic
  replacement instead of keeping two slightly different copies.
- **Per-message truncation.** `msg_inbox` now shortens each body individually
  and reports `body_chars`/`body_truncated`. It marks read only the messages it
  actually returned, so a large message cannot hide the rest of the inbox or
  silently consume messages that were never shown.
- **Untrusted-content warning.** Every inbox result starts with a warning that
  the messages come from other AIs, not from the user, and must not be treated
  as instructions to run commands or modify files.
- **Chat page hardening.** The page sends an explicit `from: usuario`; the
  server accepts that identity only from a same-origin request, stores a
  missing sender as `sin-firma`, validates `reply_to` and its hop count, reads
  `mailbox_dir` from `pc_agent_config.json`, caches messages, scans connected
  agents at most every 30 seconds, limits requests to 1 MB, and sends
  `Content-Security-Policy`, `X-Frame-Options`, `Referrer-Policy` and
  `X-Content-Type-Options` headers. Polling is every 3 seconds.
- **`start.bat` lifecycle.** It checks `chat-local\server.py`,
  `chat-local\chat.html`, `chat-local\lanzar_chat.ps1` and the resolved Python
  path before launching, passes `-Port 8765` explicitly, and calls
  `lanzar_chat.ps1 -Stop` when the bridge exits so no orphan `python.exe`
  keeps the port open.
- **Client setup.** OpenCode V2 can pass the identity directly:
  `opencode mcp add zeroscript-pc --global --env
  ZS_PC_AGENT_NAME=opencode -- <python> <pc_agent_mcp.py>`. Claude Desktop uses
  `"env": { "ZS_PC_AGENT_NAME": "claude" }`. `MCP_CLIENTS.md` and the README
  document both, plus the new limits and the chat page.

### Fixed
- **Inbox truncation consumed unseen messages.** The old code marked every
  selected message read and then truncated the combined JSON, so a long first
  message could hide later ones that were already marked read. Truncation is
  now per message and only returned messages are marked.
- **Invalid `reply_to` created an orphan.** `msg_send` now rejects a
  `reply_to` that does not exist in the mailbox, and `msg_reply` uses the same
  hop check as a normal reply.
- **Chat server left running after the bridge.** `start.bat` now stops the
  chat server it launched; the launcher refuses to stop a PID whose command
  line is not `chat-local\server.py`.
- **`--check` count.** It reports 12 tools and all mailbox limits instead of the
  old 11-tool list.

### Security
- **Mailbox confinement.** Only simple `*.json` filenames directly inside
  `mailbox_dir` are read; symlinks, `.msg-*` temporaries, oversized files and
  corrupt JSON are skipped and logged. Writes use a temp file in the same
  folder plus `os.replace`.
- **Local chat boundary.** The server binds to `127.0.0.1`, rejects a foreign
  `Host` or `Origin`, requires a same-origin request for `usuario`, and caps
  request bodies at 1 MB.

## [2.2.0] - 2026-11-14

### Added
- **Shared AI mailbox.** The PC agent now exposes `msg_send`, `msg_inbox` and
  `msg_reply`, backed by one JSON file per message in a common folder. Several
  MCP clients (Claude Desktop, OpenCode, Antigravity, a browser-only client
  using `pc_read`/`pc_write`, ...) can exchange messages asynchronously without
  sharing a conversation or a process.
- **`mailbox_dir`.** New `pc_agent_config.json` key, default
  `~/Documents/AI-Shared/mailbox`; relative values resolve against the script
  folder like `ZS_PC_CONFIG`, and `ZS_PC_MAILBOX_DIR` overrides it.
- **Per-client identity.** `ZS_PC_AGENT_NAME` sets the `from` used by
  `msg_send`/`msg_reply` and the `to` filtered by `msg_inbox` (default
  `zeroscript`). `--print-config claude|opencode` adds `claude`/`opencode`
  automatically.
- **Safe, ordered messages.** Filenames start with a fixed-width Unix
  millisecond timestamp and use sanitized agent/id components. Message ids are
  UUIDs; `ts` is ISO 8601; `reply_to` links a reply to its original message.
- **Atomic inbox consumption.** `msg_inbox` returns only messages addressed to
  this agent, oldest first, marks the returned ones read through a temp file +
  `os.replace`, and returns exactly `Sin mensajes nuevos.` when there is
  nothing new, so the model knows it should stay silent.

### Changed
- **`--check`** reports the detected agent name and the mailbox path (and
  whether the folder already exists), in addition to the 11 tools.
- **`MCP_CLIENTS.md`** documents the Claude Desktop and OpenCode `env` blocks,
  the write/read/reply workflow, and how a web client can use the same mailbox
  without the `msg_*` tools.
- Bridge and extension versions bumped to `2.2.0`.

### Security
- **Mailbox confinement.** `msg_*` paths are always simple filenames inside
  `mailbox_dir`; absolute paths, `..`, separators and symlinks are rejected or
  skipped. Message creation and read-state updates use temp files plus atomic
  replacement, so a crash cannot leave half-written JSON.

## [2.1.0] - 2026-11-14

### Added
- **Standalone MCP clients can use the PC agent.** `pc_agent_mcp.py` is a
  standard stdio MCP server, so Claude Desktop, OpenCode V2, Antigravity and
  any other MCP client can launch it directly. The bridge is only needed by the
  browser extension. Setup for each client is documented in `MCP_CLIENTS.md`.
- **`--check` and `--print-config`.** `--check` validates Python, the config,
  the workspace and the tool list. `--print-config [generic|claude|antigravity|
  opencode]` prints a ready-to-paste JSON block with the absolute Python and
  script paths.
- **`pc_agent_mcp.cmd`** launcher for Windows, which finds `py -3` or `python`
  and forwards arguments without writing to stdout.
- **Per-connection profiles.** `ZS_PC_CONFIG`, `ZS_PC_WORKSPACE`,
  `ZS_PC_ALLOW_OUTSIDE_WORKSPACE`, `ZS_PC_ALLOW_SHELL` and
  `ZS_PC_SHELL_TIMEOUT_MS` override `pc_agent_config.json`.

### Changed
- **MCP compatibility.** The server echoes the client's protocol revision when
  it is `2024-11-05`, `2025-03-26`, `2025-06-18` or `2025-11-25`, and falls
  back to `2024-11-05` for anything newer. It forces UTF-8 on stdin/stdout/
  stderr, returns initialization `instructions`, and adds tool titles plus
  read-only/destructive annotations that clients such as Claude Desktop and
  Antigravity understand.
- Bridge and extension versions bumped to `2.1.0`.

### Security
- Documented that standalone clients have no ZeroScript browser confirmation.
  The workspace, `allow_outside_workspace` and `allow_shell` settings (or the
  environment overrides) are the boundary for those clients.

## [2.0.0] - 2026-11-14

### Added
- **PC agent: ZeroScript can now work on your whole computer.** A new local
  MCP server (`pc_agent_mcp.py`, configured as the primary `pc` server) exposes
  `pc_system_info`, `pc_list`, `pc_read`, `pc_write`, `pc_edit`, `pc_glob`,
  `pc_grep` and `pc_shell`. The web AI can inspect the system, read and edit
  files, search folders and run shell commands through the same local bridge.
  It works with every supported provider.
- **Confirmations for local changes.** `pc_write`, `pc_edit` and `pc_shell`
  ask for confirmation in the browser by default. The toggle lives in the panel
  under **PC access** and is stored as `zsConfirmPc` in `chrome.storage.local`.
- **PC project memory.** The agent keeps durable notes in
  `.zeroscript-memory.md` at the workspace root.
- **`pc_agent_config.json`** to set the workspace, outside-workspace access,
  shell access, timeouts and output limits.

### Changed
- `list_commands` and the periodic tool reminder default to the primary `pc`
  server; other servers are listed on demand with `list_mcp_servers`.
- Bridge and extension versions bumped to `2.0.0`.

## [1.5.5] - 2026-09-10

### Fixed
- **DeepSeek: the agent starts again on DeepSeek's new unified model.**
  DeepSeek merged Instant, Expert and Vision into a single model and removed
  the model picker from the chat box. ZeroScript waited for one of those tabs
  to be selected before starting, so "Start agent" stopped with
  "DeepSeek mode not ready". A chat box with no model picker is now recognised
  as the unified model: ZeroScript switches Search off as before, leaves
  DeepThink on, and starts.
- **DeepSeek: screenshots work on every chat.** Images used to need the Vision
  tab, which no longer exists, so `screen_capture` was refused. The unified
  model reads images, and ZeroScript now sends them - one capture or several
  in a row. Older conversations still marked Instant or Expert stay text-only.

## [1.5.4] - 2026-09-06

### Fixed
- **ChatGPT: the ZeroScript bar is back where it belongs, above the composer.**
  ChatGPT redesigned its input box and renamed the layout slots it is built
  from: the full-width row across the top used to be called `header` and is now
  called `eyebrow`. ZeroScript still asked for `header`, a name that no longer
  exists, so the browser invented a place for the bar instead - it landed in a
  stray strip at the bottom right of the composer, and the text field itself was
  squeezed to zero width in the process. The bar now claims the correct row, and
  it also reads the layout live rather than trusting a fixed name, so the next
  time ChatGPT renames its slots the bar will follow instead of breaking.

### Changed
- **ChatGPT: replies are read straight from the page again.** The same redesign
  replaced the code-block editor that used to render each line separately and
  cut long lines off around 2000 characters - the cause of the truncated
  commands fixed in 1.5.1. Code blocks are now plain text with real line breaks,
  and a 400-line block reads back whole. The workaround stays in place for
  anyone still on the old interface.

## [1.5.3] - 2026-08-22

### Changed
- **Kimi moved to kimi.ai.** Kimi's old address, `kimi.com`, now asks for a
  Chinese phone number to sign in, which locked most people out. Kimi runs on
  `kimi.ai` from now on - the extension only activates there. The page itself is
  unchanged, so nothing about using Kimi with ZeroScript is different: open
  https://www.kimi.ai, the bar appears above the input box as before. If you had
  Kimi tabs open on the old address, reopen them on the new one.
- **DeepSeek: the Instant model is now allowed to run the agent.** Starting a
  session forced the Expert tab and, worse, the readiness gate only ever accepted
  Expert or Vision - so picking Instant left "Start agent" spinning
  forever with no explanation. Instant is now respected like Vision: pick it
  before starting and the session runs on it. It is much faster than Expert, at
  the cost of the reasoning pass. Images stay disabled on Instant exactly as they
  are on Expert - the Vision tab is still the only one that can see screenshots,
  so `screen_capture` is not offered to the model on the other two.

### Fixed
- **DeepSeek: a reply written in DeepSeek's own tool-call markup no longer kills
  the turn.** DeepSeek sometimes answers with its internal DSML invoke tags
  instead of a ZeroScript command. That format carries none of the markers
  ZeroScript looks for, so nothing recognised it as a command attempt: the tool
  never ran, the raw tags were left on screen, and the agent silently stopped
  with the user waiting on a dead turn. It is now detected, the markup is hidden
  behind a tool chip like any other command, and DeepSeek is told the format is
  unreadable so it rewrites the call properly. The chip shows the usual spinner
  while the model is still writing, then settles red as "wrong format".
- **ChatGPT: the ZeroScript bar no longer collides with the composer's rounded
  corners.** The composer card is rounded by 28px and the bar sits flush against
  its top edge, so the Discord button's corner fell outside the rounded shape and
  was sliced off by the card. Both ends of the bar are inset to clear the curve.

## [1.5.2] - 2026-08-14

### Added
- **ChatGPT: the operating instructions are now re-stated periodically.** ChatGPT
  summarises its own context mid-session, and the part it drops first is the
  *mechanism* - that an extension reads its replies and really runs them. It
  would then answer "I can't invoke those commands in this session" while the
  extension sat there, ready. The full instructions are now re-sent
  automatically, riding along on a tool result so they cost no extra message and
  stay hidden from you (they appear as a "Reminder" chip). A tool result is
  never shortened to make room: if the pair would not fit, the reminder simply
  waits for the next one. ChatGPT only - no other provider needs it.
- **ChatGPT: an image you send is now treated as reference material.** Unless you
  explicitly ask for a picture, ChatGPT used to answer a screenshot or a mockup
  by *generating a new image* instead of doing the work it was meant to
  illustrate - and its image tool cannot reach your place anyway.

### Fixed
- **ChatGPT: you can chat normally again without starting an agent.** On a blank
  ChatGPT tab the extension refused to let a message send until you clicked
  "Start agent". Every other provider only suggests it; ChatGPT was the
  odd one out.
- **A finished command is no longer stranded as "not run".** After a long reply
  (seen on Qwen writing for 400s and more) the loop could give up while the model
  was still going; eight seconds later the completed command was written off for
  good. That window is now three minutes, so the command actually runs.
- **A clear message when ZeroScript is updated while a tab is open.** Chrome
  updates extensions underneath open tabs, which leaves the page running a
  version that no longer exists. ZeroScript reported this as "the bridge stopped
  on your PC - run start.bat", sending you to fix something that was never
  broken. It now says plainly that the page needs reloading, and offers a Reload
  button - the local bridge is untouched.
- **The AI no longer claims your bridge is offline without checking.** After one
  momentary outage it would keep repeating "the bridge is offline" from memory, even
  once everything was back. It must now actually run a command before saying so.

## [1.5.1] - 2026-08-13

### Added
- **ChatGPT support (chatgpt.com).** ZeroScript now runs on ChatGPT as an
  eighth provider. Image input is deliberately disabled there: ChatGPT's free
  tier caps files/images on a separate quota from messages, so vision would
  work only part of the day. Reasoning mode ("Analyser") and the model picker
  are left entirely to you.

### Fixed
- **Meta AI: fixed large commands failing with "bad JSON".** Meta renders a
  ```json block as an interactive viewer whose default *Tree* view does not
  merely decorate the JSON - it **abridges** it: a large array or object is
  replaced by a summary placeholder. A 19103-character `multi_edit` was present
  in the page as 223 characters ending in `"edits":[1 item]`, so ZeroScript sent
  the parser a truncated object and the command came back as a parse error every
  time. This is also why the tool chip's token counter climbed while the reply
  streamed and then **collapsed to about 44 tokens** the moment the block
  finished rendering - the counter was faithfully reporting what could be read.
  Command blocks are now switched to the viewer's *Raw* tab, which holds the
  verbatim source; the 19103-character payload is read whole.
- **ChatGPT: fixed most tool calls failing outright.** ChatGPT renders code
  blocks with CodeMirror, which puts one element per line and **no newline
  characters at all** in the page. Reading a reply the usual way therefore
  returned the whole script glued onto a single line, so a perfectly valid
  command came back as a parse error because the code was read on one line.
  Replies are now read with the line structure preserved.
- **ChatGPT: fixed long commands being executed truncated.** Beyond roughly
  2000-4000 characters, CodeMirror only renders *part* of a long line and the
  rendered text then stays frozen while the model keeps writing - the tool
  chip's token counter would climb, drop back to about 500 tokens, freeze
  there, and the command would run cut off. Measured live: a 21273-character
  command of which the page exposed 4049. ZeroScript now reads the editor's
  real document instead of the rendered page, through a new MAIN-world tap
  (`providers/chatgpt-cm.js`), the same approach already used for Qwen's
  Monaco editor. A 5.3k-token `multi_edit` now applies whole.
- **ChatGPT: fixed the raw command staying visible.** When the model writes a
  command without wrapping it in a code fence, ChatGPT splits it into dozens of
  sibling paragraphs (68 of them for a 208-line script) and only the first one
  carried the marker, so the rest of the script stayed on screen. The whole
  marker-to-marker range is now hidden, including while it streams.
- **Fixed the agent dying silently when the model called a tool the
  function-calling way.** A reply like
  `{"toolName": "list_items", "item_id": "…"}` names a real tool but
  uses the wrong key, so nothing recognised it as a command: the turn was
  finalised as a plain-text answer and the loop simply ended, leaving the agent
  looking frozen (seen on ChatGPT in a long session). ZeroScript now spots a
  known tool named under `toolName` / `tool` / `name` / `function` / `action`
  and asks the model to rewrite it with the proper envelope, exactly as it
  already did for a missing `###MCP_TOOL###` opener or bare parameters. Prose that
  merely mentions a tool name is not affected - the check requires a tool that
  is really in the catalogue.
- **Fixed the "Agent is working…" cover hanging past the composer on the first
  send.** Injecting the system prompt grows the composer, the page gains a
  scrollbar and the content column narrows, so the composer slides sideways -
  and a site that animates that move updates its layout after the cover has
  already been placed, leaving it a frame behind (28px past the card's right
  edge on ChatGPT). The cover is now clamped to the composer card, so a stale
  measurement can never be seen. Only the first send was affected, because the
  composer stops moving once it is docked at the bottom.

## [1.5.0] - 2026-07-30

### Fixed
- **Backgrounding the AI tab no longer strands a pending command as a grey
  "not run".** `waitForResponse` now parks entirely while the tab is hidden and
  shifts every internal deadline (inactivity timeout, warm-up, text-stability,
  etc.) forward by the parked duration, instead of letting them keep ticking
  off-screen. `waitVisible` switched from polling to listening for
  `visibilitychange` - Chrome clamps chained background timers to one tick per
  minute after 5 minutes hidden, which used to delay the resume by up to a
  minute. The bar now shows a **Paused** state while parked, and a genuinely
  empty reply from the site now shows a banner instead of ending the loop
  silently.
- **Gemini: fixed the page freezing (nothing clickable) on a large tool
  result.** Gemini's composer inserts text line by line, synchronously, on the
  main thread - a 2599-line `http_get` result froze the page for about a
  minute. Outgoing text is now capped (120k chars / 1200 lines, head and tail
  kept) and the insert yields to the browser every 120 lines.
- **Gemini: fixed the system prompt occasionally never leaving the composer on
  Start.** The wedged-stop-button detector latches for 2 seconds from the
  first time it sees a stop button, so the single recovery attempt at boot -
  the very first sighting - was refused by its own guard. It now retries
  across that window and retypes as a last resort.
- **Kimi: fixed the model picker opening and closing in a loop.** Kimi's K3
  update removed the model (K2.6) the default-model routine used to select,
  so it kept hunting for a row that no longer exists. It now only acts when
  the current model is **K3 Swarm** (matched by name, any UI language) and
  gives up after a few tries instead of looping. The native-agent warning
  guard was equally broken by the same update and now reads the model label
  at its new location.
- **Degraded mode (PC agent offline, running on an addon server only)
  starts much faster.** The tool catalogue request blocks until timeout when
  the primary agent is down, and the boot sequence called it three times in a row. Added
  a 30s cache on the catalogue and cut the request timeout from 25s to 10s.

## [1.4.9] - 2026-07-24

### Added
- **Popup: new Settings button.** Opens the same Switch AI / support panel
  as the in-page bar, without needing an already-started conversation. The
  footer text no longer singles out chat.deepseek.com - it now points to
  "a supported AI" since seven providers are supported.
- **Bridge: auto-recovers its own port on relaunch.** Relaunching `start.bat`
  while a previous Bridge was still holding port 17613 (window closed with
  the X, a crash, a double launch) used to crash with a cryptic, sometimes
  localized `OSError [WinError 10048]`. The Bridge now detects and kills a
  leftover Bridge process it can positively identify (by command line, never
  by process name alone) before binding, and falls through to a clear,
  actionable message - with the exact `netstat`/`taskkill` commands and the
  `ZS_BRIDGE_PORT` override - if the port is held by something else.

### Fixed
- **The agent could parse/execute commands while its AI tab was backgrounded
  or the window minimized.** Background tabs throttle rendering and timers,
  which made DOM reads unreliable and could send duplicate feedback or run a
  tool blind (observed live: GLM kept running a command while minimized).
  The agent loop, the tool-dispatch step, and the auto-resume watchdog now
  all gate on `document.visibilityState` and park - with no time limit -
  until the AI tab is the foreground tab again, then resume exactly where
  they left off. Working in another app while the AI tab stays
  the active tab in its own window is unaffected; this only pauses execution
  while that tab is truly backgrounded or its window minimized.

## [1.4.8] - 2026-07-22

### Added
- **DeepSeek: outgoing messages are now truncated to fit its input limit.**
  DeepSeek's composer silently refuses to send past 163840 characters
  (validated live), which could wedge the agent in the input box after a
  large tool result (a big `http_get` / `get_page_text` / code dump). Long
  results are now truncated to a safe margin below that limit, keeping both
  the start and the end of the content, the same approach already used for
  Qwen and Arena.

## [1.4.7] - 2026-07-21

### Fixed
- **Qwen: a tool could show a green "done" check while it never ran and returned
  no result** (seen rarely with repeated large command calls, with
  no Stop or regenerate involved). Qwen virtualizes its message list, so the
  off-DOM "already executed" record was keyed on the positional turn index, and
  two turns that shared the same 60-character command prefix could collide on the
  same index. That false positive made the auto-resume watchdog skip the fresh
  command (so it never ran, no result was injected) while the chip was still
  painted a green check. The dedupe now keys on Qwen's stable per-turn id
  (`chat-response-message-<uuid>`, exposed as `itemKey`) instead of the index, so
  the collision cannot happen.
- **Qwen: the ZeroScript bar covered the "Expand more models" submenu.** That
  fly-out is a separate body-portalled `.ant-dropdown` at a low z-index, not the
  main model dropdown, so the bar drew on top of it. Raised just that dropdown
  above the bar (scoped so other Ant menus and tooltips are untouched).

### Added
- **Per-model image support on Qwen.** Qwen offers both multimodal and text-only
  models, switchable mid-conversation, and image input only works on the
  multimodal ones. `screen_capture` and image input are now enabled only on a
  vision-capable model (Qwen3.7-Plus, Qwen3.6-Plus, Qwen3.6-27B, Qwen3.8-Max-Preview)
  and correctly withheld on a text-only one (Qwen3.7-Max, Qwen3.6-Max-Preview),
  read from the selected model and updated when you switch models.
- **Image support on DeepSeek's Vision model.** DeepSeek forces its Expert model
  for the agent, but if you choose the Vision tab that choice is now respected and
  `screen_capture` plus image input are enabled for it. Selecting Vision is
  detected reliably, including after switching conversations. Image attachment was
  also fixed: it used to stage the same image multiple times and never send,
  because the upload went through a paste that only made a local preview and never
  uploaded the file. It now uses DeepSeek's real file upload and sends once the
  upload completes.

## [1.4.6] - 2026-07-19

### Fixed
- **Kimi's login and "priority queue" popups were covered by the ZeroScript
  bar**: both render as full-screen fixed masks (`.login-modal-mask` and
  `.modal-mask`) rather than a standard `[role="dialog"]`, so the generic
  overlay probe used by other providers never caught them. The anchored bar
  (a full-width fixed element hugging the composer) and the "unstable"
  warning pill sat on top of the mask and could intercept clicks meant for
  its buttons (e.g. "Continue with Google"). Added a Kimi-specific
  `overlayBlocking()` that detects both mask classes by real visibility; the
  core already hides the whole bar while it reports true, and restores it the
  instant the mask clears.

### Added
- **Kimi now defaults fresh chats to K2.6**: Kimi lands new chats on K3,
  which is flagged unstable here and easy to miss switching away from. A
  brand new or emptied chat now picks K2.6 automatically, once; a deliberate
  manual switch to K3 on that same chat is left alone.

## [1.4.5] - 2026-07-18

### Fixed
- **DeepSeek re-executed old tool commands when scrolling up in a long
  conversation**: DeepSeek virtualizes its message list, so scrolling up makes
  an OLD command turn the last *rendered* assistant turn - its injected result
  sits below the fold (unrendered), the in-memory "already executed" record is
  empty after a page reload, and the node change makes generation detection
  flicker true, refreshing the auto-resume watchdog's freshness clock. The
  watchdog then re-fired the historical tool. Three-layer fix (validated live):
  - The off-DOM executed/halted dedupe maps now key on a virtualization-stable
    per-turn id (`itemKey`, DeepSeek's `data-virtual-list-item-key`) instead of
    the positional assistant index, which collides across scroll windows.
  - The watchdog skips any command turn whose stable id is below the session's
    high-water mark (`A.maxTurnId`) - a scrolled-back old turn can never resume,
    even right after a reload (`resume.skipOld` in the diag ring).
  - The watchdog also skips a command turn whose injected result is rendered
    right below it (settled history), a provider-generic guard.
- **Gemini stranded a tool result in the composer ("Message could not be
  sent")**: after a generation ends, Gemini's action button can stay WEDGED on
  the stop icon instead of reverting to the send arrow. The loop's generation
  *detection* already tolerates this (WEDGE_MS), so the tool ran, but the *send*
  waited for an `arrow_upward` button that never appeared - four retries failed
  and the injected result sat unsent in the composer. `typeAndSend` now resets a
  frozen stop button (clicking it, guarded by the same not-actually-generating
  check) so the send button reappears, then sends (validated live). The native
  stop-click hook now ignores non-trusted (programmatic) clicks, so this
  un-wedge click is never mistaken for the user halting the agent - otherwise
  the next legitimate command was wrongly marked "stopped".

## [1.4.4] - 2026-07-16

### Fixed
- **Qwen fired tool commands mid-stream ("Bad JSON" while Qwen was still
  writing)**: Qwen's frontend update (fe 0.2.73) now emits `status:"finished"`
  in its SSE stream ~12s before the stream actually closes. The network tap
  treated that as the turn's end, so a still-incomplete command (e.g. an
  unclosed `###MCP_TOOL###` block) was extracted and sent, and the loop's premature
  "unclosed" feedback was injected while the model kept writing. Fixed by no
  longer treating `status:"finished"` as done, and by having generation
  detection check the DOM stop button first (validated live: it now tracks the
  real stream end closely, unlike its old ~6s lag).

### Changed
- **Removed the "⚠ unstable" badge on Qwen's Auto/Think modes**: those modes
  used to make Qwen claim a tool "does not exist" without even trying it. The
  extension never force-switches Qwen's mode, so Auto (Qwen's own default) is
  left untouched.

## [1.4.3] - 2026-07-15

Adds a seventh AI provider (Meta AI), fixes a Qwen tool-turn regression, and
improves MCP-server recovery and the system prompt.

### Added
- **Meta AI (www.meta.ai) as a provider**: full ZeroScript support on Meta AI -
  new `providers/meta.js`, manifest content script + host permissions, and the
  provider switcher entry. Handles Meta's React DOM: reasoning ("Réflexion")
  chain-of-thought is excluded from the read text, the interactive JSON viewer
  and collapsible code blocks are masked so a streamed command never flashes, and
  the composer card is fully covered while typing. Meta AI accepts very large
  prompts, so no Qwen-style send cap is needed.

### Fixed
- **Qwen tool result took ~30s to inject on every tool turn**: Qwen dropped the
  assistant turn's own `id`, so `lastAssistantId()` returned null and the core
  fell back to the virtualized flat count, waiting the full ~30s NO_TURN_GRACE
  each turn. It now reads the stable `chat-response-message-<uuid>` descendant
  (with the old id kept as a fallback).
- **Qwen refused oversized messages**: a large tool result past Qwen's 131072
  character composer cap silently wedged the loop in the input box. Outgoing text
  is now truncated to a safe margin, keeping the head and tail and marking the gap
  so the model does not re-run the command.

### Changed
- **Friendlier, less restrictive system prompt**: the "do not use native tools"
  wording is reframed as a technical note (the site's own sandbox cannot reach the
  user's project) rather than a hard prohibition, with an explicit "you can act
  directly in the user's project" section. Reduces provider refusals.
## [1.4.2] - 2026-07-13

Follow-up robustness fixes for MCP-server connection failures the 1.4.1 work
did not cover, including port conflicts and missing configured commands.

### Fixed
- **`_port_owner` was IPv4-only**: the internal port-owner probe ran
  `netstat -p TCP`, so a squatter listening on IPv6 loopback was invisible to
  it; it now scans TCP and TCPv6.
- **A missing custom-MCP command (e.g. `uvx` not installed) looked like an
  endless silent restart loop**: when a configured server's command could not
  be found on PATH, the process never started, so there was no exit code and no
  stderr, and the crash-loop banner printed "the server printed no error output
  before dying". The bridge now catches the launch failure and names the real
  cause ("command not found: 'uvx' ...") both on the first attempt and in the
  crash-loop banner, while auto-restart keeps retrying in case the dependency
  is installed later.

### Changed
- The extension now tells non-technical users to "Run start.bat" instead of
  "Run python bridge.py" / "Run the ZeroScript bridge" in the offline panel,
  popup, and startup banner, matching the one-click launcher the README ships.

## [1.4.1] - 2026-07-11

### Fixed
- **Watcher crash silently stopping status updates**: an unbound
  variable could kill the background watcher
  right after a reconnect, silently stopping every status update until the
  next bridge restart. Fixed, and both watchers are now supervised: a crash
  is logged in red and the watcher restarts itself in 5 seconds.
### Added
- **Fast startup with MCP servers**: servers now launch in parallel and
  the extension-facing socket opens immediately, so a slow server no longer
  delays other addons. The bridge pushes status
  updates to already-connected extensions as servers come up - previously an
  extension that connected early could keep a stale "addon offline" snapshot
  forever (greyed Start button instead of the orange degraded start).
- Terminal spinner during slow startup phases, so the console never looks frozen;
  only one spinner animates at a
  time.
- start.bat hardening: refuses to run from an unextracted ZIP, handles
  missing winget, rescans install folders after a winget install (PATH not
  refreshed), prints the Python version and the bridge's exit code on
  screen, and logs the Windows build - so a single screenshot of the
  terminal carries enough context for support.

## [1.4.0] - 2026-07-08

### Added
- Multi-MCP addon servers (experimental): a new "MCP servers" section in the
  panel menu lets you add or remove additional MCP servers (Blender,
  Sketchfab, or any local MCP command) alongside the always-primary PC agent.
  The bridge rewrites `config.json` and restarts itself to load a change; the
  primary server stays protected from edits/removal and its status dot is scoped
  to the primary connection so an addon going down never misrepresents it.
  The new `list_mcp_servers` command and a `server` param on
  `list_commands` let the model discover and use addon tool sets on demand.
  When the primary agent is down but an addon server is alive, the panel now offers a
  degraded start instead of refusing to start at all.
- Vision support (screen_capture / other tool-returned images) enabled for
  Arena, Gemini, GLM, Kimi and Qwen, each with a real "upload finished" signal
  before sending instead of trusting the first local preview, fixing several
  silent-attachment-drop and duplicate-attachment-on-retry bugs. A tool from
  any connected server that returns an image now gets the camera chip and is
  remembered for future calls, even for a custom MCP server whose name gives
  no hint it returns images.
- Parser: a JSON command cut off by the model's own output limit, missing
  only its trailing closing brackets, is now auto-completed and executed
  instead of failing with a parse error and forcing a full retry turn.
  Strictly refuses to salvage anything where real content (not just closers)
  was cut off.
- Per-reason parse-error feedback (cut off, bad JSON, missing ###MCP_TOOL###
  opener, wrong envelope) instead of one generic "bad JSON" message, so the
  model fixes the actual problem instead of guessing.

### Fixed
- DeepSeek: a command's chip could show green "done" while DeepSeek was still
  streaming the reply, on back-to-back calls to the same tool. Caused by
  DeepSeek's list virtualization defeating the turn-count identity guard;
  fixed with a stable per-turn id.
- GLM: new "scroll to bottom" buttons were mistaken for the Stop button and
  permanently latched generation state to "busy." Raw command JSON could leak
  into the visible reply when nested inside a paragraph. An image filename
  could corrupt result-chip detection.
- Kimi: added detection of Kimi's own native "Agent" mode, which conflicts
  with ZeroScript's command protocol; Start is disabled with a warning until
  it's turned off. Fixed the hidden file-upload input not existing until the
  "+" menu is opened, raw command text leaking when nested/oversized, and
  normal model prose containing "try again" being misread as a site error.
- Qwen: same "try again" false-busy fix as Kimi. A/B "carousel" comparison
  turns (where the composer disappears mid-carousel) now auto-resolve to
  Response 1 once both candidates finish, instead of stalling or misreading a
  candidate as a truncated command.
- Arena: send is now confirmed until the composer actually clears instead of
  trusting a single click, preventing stranded messages/attachments; the chip
  now anchors below the reply text instead of floating above it.
- A command turn abandoned mid-stream (reload, or superseded by a
  regenerate) no longer shows a false green checkmark; it now shows a
  neutral "not run" state instead.
- A tool's own in-body error (e.g. "Output of '...': Error executing code...")
  now settles the chip red instead of green, even when the tool didn't use
  ZeroScript's own ERROR wrapper.
- Regenerating a stopped command no longer briefly re-shows the old call's
  chip before the new one streams in.

### Changed
- The version number next to the ZeroScript name in the panel is now small,
  plain text instead of a bordered green badge.
- System prompt updated to cover multiple MCP servers: the model must call
  `list_mcp_servers` before assuming a capability is unsupported,
  and the tool list is no longer inlined in the prompt (fetched on demand via
  `list_commands`).

## [1.3.9] - 2026-07-04

### Fixed
- Bridge: kill the full process tree on restart instead of just the wrapper
  process, which could leave child processes behind and interfere with the next
  launch.
- Bridge: a dead MCP server is now auto-restarted by a background watchdog
  instead of waiting for the next tool call to notice.
- Extension: the status bar no longer shows a falsely healthy "N tools" label
  when the agent is active but an MCP server or the bridge isn't usable; it now
  names the real blocker.
- Cross-provider: DeepSeek, Gemini, Kimi, GLM and Qwen composer menus, model
  pickers and tooltips (including GLM's search hover card and Kimi's model
  popover) no longer render clipped or hidden behind ZeroScript's own
  bar/pill/cover.
- Cross-provider: a thinking model quoting command JSON in its own reasoning
  area no longer makes the tool chip flap between done/run/done (Gemini, Kimi,
  GLM and Qwen).
- The "Agent is working" composer cover now blocks clicks into the composer
  underneath it instead of letting them through, and can no longer balloon
  past the composer's visible band or drag itself off position when a site
  recreates its editor node mid-session (seen on Kimi).
- A command chip could briefly flash or restart its spinner when revisiting a
  past turn; it now settles to done correctly instead.
- DeepSeek: the raw system-prompt turn no longer flashes for a frame before
  being hidden.
- Gemini: "New chat" no longer gets stuck on "Agent active" from a reused
  previous conversation URL.
- Kimi: reasoning is read separately from the actual reply, so a command
  drafted while the model is still "thinking" is no longer detected or
  executed; input can no longer be typed mid-run after the editor node is
  recreated.
- Arena: unsupported-mode gate now also covers Web Search and Generate Image,
  and chip alignment is fixed when a command turn renders as an A/B
  model-comparison carousel.
- Bridge: a long-running tool call no longer starves the connection's ping
  handling and trips the half-open-socket watchdog.

### Changed
- Bridge and installer logs moved to `logs/bridge_debug.log` and
  `logs/start.log`; the console now only shows what a user actually needs to
  read, full detail still lands in the log files.
- `start.bat` now detects and explains a double launch instead of silently
  replacing the previous instance, and warns clearly if port 17613 stays held
  after trying to free it.
- Removed remaining em dashes from user-visible strings.
- Removed remaining em dashes from user-visible strings.

## [1.3.3] - 2026-06-24

### Fixed
- `bridge.py` now runs a `.py` MCP command with the same Python interpreter as
  the bridge, so it works on installs where only the `py` launcher exists.

## [1.0.0] - 2026-06-09

### Added
- Initial public release of ZeroScript Free
- Browser extension for Chrome and Edge (DeepSeek chat integration)
- Panel status indicator (green / yellow / grey)
- Auto kill port 17613 on start to avoid conflicts
- Setup tutorial video on YouTube
