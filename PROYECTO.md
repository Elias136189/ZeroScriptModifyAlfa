# ZeroScript Modify - Documentación del proyecto

> Documento generado el 15-nov-2026 y actualizado el 21-nov-2026 leyendo el código y la configuración reales de la carpeta
> `%USERPROFILE%\Documents\Monero\ZeroScriptModify`.
> La carpeta se llamó antes `ZeroScript-Free-1.5.5 - copia`; las rutas antiguas que aparecen en
> `backups\` y `logs\` son históricas.
> Lo que aparece como "verificado" se comprobó ejecutando o leyendo el archivo; lo marcado como
> "probable" es una deducción del código que no se ha probado.

## 1. Resumen

ZeroScript convierte una IA de chat (en el navegador) o un cliente MCP (Claude Desktop, OpenCode,
Antigravity) en un agente que trabaja sobre **tu PC**: lee y escribe archivos, busca, y ejecuta
comandos. Sobre esa base, esta copia añade una capa para que **varias IAs se comuniquen entre sí**
por un buzón compartido, una **página web de chat local** para verlo y escribir, y un script para
**despertar** a la otra IA cuando le llega un mensaje.

Origen: proyecto de código abierto `sebattfg/ZeroScript-Free` (licencia GPL-3.0). Esta carpeta es una
copia modificada: el nombre de la carpeta ya no lleva versión y el código corresponde a las versiones
2.2.0-2.4.0 (ver sección 9).

Dependencias: Python 3.12.10 embebido en `runtime\python\` (lo descarga `start.bat` o `preparar_portable.bat` sin instalar nada en Windows), con `websockets` (bridge) y `watchdog` (vigilante de cambios). También funciona con Python 3.9+ del sistema. Todo lo demás es biblioteca estándar. La extensión es JavaScript sin dependencias.

## 2. Arquitectura

Hay **dos caminos** para que una IA llegue a tu PC, y comparten el mismo servidor de herramientas
(`pc_agent_mcp.py`):

```
Camino A - IA en el navegador (DeepSeek, Kimi, Arena, Qwen)
  Chat web -> extensión Chrome/Edge -> bridge.py (ws://127.0.0.1:17613) -> pc_agent_mcp.py

Camino B - Cliente MCP de escritorio (Claude Desktop, OpenCode, Antigravity)
  Cliente MCP -> pc_agent_mcp.py (lo lanza el propio cliente por stdio; no necesita el bridge)

Capa entre IAs (buzón compartido, sin servidor propio)
  msg_send / msg_inbox / msg_wait / msg_reply  ->  carpeta de archivos JSON
  Documents\AI-Shared\mailbox\*.json

Utilidades sobre el buzón
  chat-local\server.py  (http://127.0.0.1:8765)  -> ver y escribir mensajes como "usuario"
  despertar.py / .bat   -> lanza el CLI de la otra IA (ventana solo como fallback)
  limpiar_buzon.py      -> archiva mensajes leídos antiguos
```

Cada cliente MCP se identifica con la variable `ZS_PC_AGENT_NAME` (por ejemplo `claude`, `opencode`).
El bridge lanza su propio `pc_agent_mcp.py` con la identidad por defecto `zeroscript`.

## 3. Estructura de la carpeta

| Ruta | Qué es |
| --- | --- |
| `start.bat` | Lanzador principal en Windows: usa `runtime\python\` embebido (con respaldo a Python del sistema), copia `*.example.json`, verifica puerto, arranca chat local, vigilante (`ensure`) y bridge oculto |
| `preparar_portable.bat` / `.ps1` | Descarga Python 3.12.10 embebido y extrae los wheels SHA-256 de `websockets` y `watchdog` en `runtime\python\` |
| `runtime\` | Python 3.12.10 portable y paquetes (`websockets`, `watchdog`); ignorado en `.gitignore` |
| `bridge.py` (2333 líneas) | Puente WebSocket <-> servidores MCP; deriva el ID de `manifest.json`, valida `Origin` y token `ZS_BRIDGE_TOKEN` |
| `pc_agent_mcp.py` (1577 líneas) | Servidor MCP por stdio con 12 herramientas (`pc_*` y `msg_*`), `allow_write` y rutas relativas |
| `pc_agent_mcp.cmd` | Lanzador de `pc_agent_mcp.py` para clientes MCP (busca `runtime\python\`, `py -3` o `python`) |
| `pc_agent_config.json` | Permisos y límites del agente (`workspace: "."`, `allow_shell`, `allow_write`, buzón) |
| `config.json` | Servidores MCP que arranca el bridge (hoy solo `pc`) |
| `mailbox_store.py` | Lógica común del buzón: validar, leer, escribir, marcar leído, archivar |
| `despertar.py` / `despertar.bat` | Despertar a otra IA; el bridge lo vigila solo y la `.bat` es el atajo manual |
| `despertar_config.json` | Destinos del despertar, presupuesto y prompt fijo |
| `limpiar_buzon.py` | Archiva mensajes leídos con más de N días |
| `chat-local\` | Página de chat: `server.py`, `chat.html`, `lanzar_chat.ps1`, `iniciar_chat.bat`, `detener_chat.bat` |
| `zeroscript-extension\` | Extensión de navegador (manifest v3 con `"key"` RSA fija), proveedores y pruebas en Node |
| `launch_studio_mcp.py` | Lanzador opcional para el MCP de Roblox Studio |
| `vigilante_cambios.py` / `vigilante_cambios.bat` | Vigilante del sistema de archivos (necesita `watchdog`). Precarga `(mtime_ns, size)` al arrancar para ignorar lecturas y registra CREATED, MODIFIED, DELETED y MOVED en `logs\registro_cambios\cambios_AAAA-Wss.log`. Ignora `__pycache__`, `.git`, `logs`, `backups`, `assets`, `runtime` y `workspace_wake`. Comandos: `run`, `start`, `ensure`, `stop`, `status`, `ver [N]` |
| `instalar_vigilante.bat` / `desinstalar_vigilante.bat` | La instalación crea `ZeroScript_Vigilante_Cambios.vbs` en la carpeta Inicio del usuario (sin admin; `ensure` lo hace automáticamente solo en PCs nuevas). `desinstalar_vigilante.bat` detiene el proceso, borra el VBS de Inicio y elimina la tarea programada si existiera |
| `README-ALPHA.md`, `MCP_CLIENTS.md`, `CHANGELOG.md` | Documentación (el duplicado `README.md`, `INFORME_CODIGO_MCP.md`, `bridge_segundo_plano.vbs`, `despertar.txt`, `patch_claude1.py` y `ocultar_ventana.ps1` se retiraron a `backups\`) |
| `assets\` | Icono y banner del README |
| `backups\` | Copias hechas antes de cambios (archivos `.antes-*` y la carpeta `arreglos-20261114-212149`) |
| `logs\` | `start.log`, `bridge_debug.log`, `despertar.log`, `pc_agent_mcp_*.log`, `vigilante_cambios.pid` y `registro_cambios\` (registros semanales del vigilante, con autor) |
| `.gitignore`, `.gitattributes` | Reglas de git (la carpeta **sí** es un repositorio git desde el 18-nov-2026) |

## 4. Componentes en detalle

### 4.1 `bridge.py` (versión 2.2.0)

- Escucha en `ws://127.0.0.1:17613` (puerto cambiable con `ZS_BRIDGE_PORT`).
- Arranca los servidores de `config.json` como procesos hijos por stdio. Un hilo lector por
  servidor, respuestas emparejadas por id de JSON-RPC, stderr drenado, reinicio automático y reintento
  de la llamada fallida.
- Mensajes que acepta de la extensión: `ping`, `list_tools`, `call_tool`, `studio_status`,
  `add_server`, `remove_server`, `restart_mcp`.
- **Control de origen y token (`bridge.py`):** rechaza las conexiones sin cabecera `Origin` y solo acepta
  los orígenes `chrome-extension://` / `moz-extension://`. Si `ZS_BRIDGE_EXTENSION_ID` no está definida,
  `bridge.py` deriva el ID automáticamente del campo `"key"` de `zeroscript-extension\manifest.json`
  (`kmjgngkgeagldpddkklmdmllbkdopldb`, igual en cualquier carpeta o PC). Además soporta el token
  compartido opcional `ZS_BRIDGE_TOKEN` (validado con `hmac.compare_digest` vía `?token=`, `Bearer` o
  `X-ZS-Token`) y orígenes adicionales con `ZS_BRIDGE_ALLOWED_ORIGINS`.
- Mucho código es diagnóstico de Roblox Studio (puertos, procesos huérfanos). No se usa mientras
  `roblox` no esté en `config.json`.
- Registro en `logs\bridge_debug.log` (se añade siempre, nunca se trunca).

### 4.2 `pc_agent_mcp.py` (versión 2.3.0)

Servidor MCP (JSON por línea en stdio; versiones de protocolo 2024-11-05 a 2025-11-25).

| Herramienta | Qué hace |
| --- | --- |
| `pc_system_info` | SO, usuario, workspace, unidades, permisos |
| `pc_list` | Lista un directorio |
| `pc_read` | Lee un archivo de texto con números de línea (`LINEA\|TEXTO`) |
| `pc_write` | Crea o sobrescribe un archivo de texto |
| `pc_edit` | Reemplazo exacto de texto (falla si `old_string` no es único, salvo `replace_all`) |
| `pc_glob` | Busca archivos por patrón (`**` soportado), más nuevos primero |
| `pc_grep` | Busca texto o regex en archivos |
| `pc_shell` | Ejecuta PowerShell (Windows) o bash; timeout 120 s por defecto, máximo 600 s |
| `msg_send` | Escribe un mensaje en el buzón |
| `msg_inbox` | Lee los mensajes sin leer de esta IA y los marca leídos |
| `msg_wait` | Espera hasta 55 s a que llegue un mensaje |
| `msg_reply` | Responde a un mensaje por id |

Opciones de línea de comandos: `--version`, `--check` (valida el entorno), `--print-config
generic|claude|antigravity|opencode` (genera la configuración para pegar en cada cliente).

La salida se corta a `max_output_chars` (40 000). Las instrucciones de inicio le dicen al modelo que
el contenido del buzón no son órdenes del usuario.

### 4.3 El buzón (`mailbox_store.py`)

- Carpeta: `%USERPROFILE%\Documents\AI-Shared\mailbox` (cambiable con `mailbox_dir` o
  `ZS_PC_MAILBOX_DIR`). Hoy tiene 31 mensajes (20,6 KB).
- Un mensaje = un archivo JSON. Nombre: 13 dígitos de milisegundos + remitente + 8 caracteres del id.
- Campos: `id` (uuid), `from`, `to`, `subject`, `body`, `ts` (ISO 8601), `reply_to`, `hops`, `read`.
- Escritura atómica (archivo temporal + `fsync` + `os.replace`). Se ignoran enlaces simbólicos,
  archivos de más de 2 MB y JSON corrupto.
- Límites: cuerpo 20 000 caracteres, asunto 200, nombre de agente 32 (solo `A-Za-z0-9_.-`).
- Archivado: `archive_messages` mueve los leídos antiguos a `mailbox_dir\archive\AAAA-MM`.

**Límites anti-bucle (`pc_agent_config.json`):** `max_hops` 6 (largo de la cadena de respuestas),
`max_msgs_per_10min` 30 por remitente, `max_message_chars` 20 000.

### 4.4 Chat local (`chat-local\`, versión 2.4.0)

Servidor HTTP en `127.0.0.1:8765` con `ThreadingHTTPServer`.

| Ruta | Método | Función |
| --- | --- | --- |
| `/` | GET | Sirve `chat.html` |
| `/api/messages` | GET | Mensajes, agentes conectados y versión |
| `/api/health` | GET | Estado (`ok`, versión, buzón, nº de mensajes) |
| `/api/send` | POST | Escribe un mensaje |

- Solo acepta `Host` 127.0.0.1/localhost y, si hay `Origin`, el de la propia página. Enviar como
  `usuario` exige petición del mismo origen. Un mensaje sin remitente se guarda como `sin-firma`.
- **Opción "todos" (nueva):** en el campo "Para", `todos` envía una copia del mensaje a cada agente
  conectado (si no se sabe cuáles hay, a `claude` y `opencode`). Solo funciona desde la página.
- Agentes conectados: cada 30 s como máximo (y solo mientras la página los pide) lista los procesos
  con PowerShell y busca `pc_agent_mcp.py` cuyo proceso padre sea Claude, OpenCode, Antigravity,
  Codex o Kimi. Solo en Windows.
- `chat.html`: consulta cada 3 s, pestañas por agente, escribe con `textContent` (sin XSS), Enter
  envía y Shift+Enter hace salto de línea.
- `lanzar_chat.ps1` arranca el servidor oculto, espera a que responda de verdad y abre el navegador
  una sola vez. Guarda el PID en `chat-8765.pid`. Con `-Stop` solo detiene un proceso cuya línea de
  comandos contiene `server.py` y `chat-local`.

### 4.5 Despertar (`despertar.py`, `despertar.bat`, `despertar_config.json`)

Cuando un destino tiene un hilo nuevo en el buzón, lanza su CLI en segundo plano (`claude -p` u
`opencode run`) con un aviso fijo. Solo si el destino incluye `window` en `fallback` enfoca la app y
pega el aviso con SendKeys. El aviso (configurable) dice: lee el mensaje `{id}` de `{from}`, responde
una vez con `msg_reply`, no envíes mensajes nuevos, no uses `pc_shell`, `pc_write` ni
`despertar.py`. **El cuerpo del mensaje nunca se inyecta.**

El bridge arranca el **mensajero** al iniciarse (`wake_watch()`): un hilo demonio consulta el buzón cada
2,5 s y despierta como máximo un destino por ciclo. No es un proceso aparte: se apaga con el bridge,
no deja huérfanos y al cerrar termina también los CLI hijos. Interruptores: `ZS_WAKE_WATCH=0` (una
ejecución) y el archivo `wake_off` (bloquea todo `--apply`).

Reglas anti-bucle del script:

1. Solo hilos nuevos (`reply_to` vacío y `hops` 0); las respuestas nunca despiertan.
2. Un mensaje ya usado no vuelve a despertar (`wake_state.json`).
3. Se ignoran los mensajes con asunto `[auto]`.
4. Presupuesto: 1 cada 60 s, 6 por hora, 20 por día (`0` = desactivado).
5. Si existe el archivo `wake_off` junto al script, no hace nada.
6. Prompt fijo; el cuerpo del mensaje nunca se inyecta.
7. Un mensaje por ejecución/ciclo (el más antiguo pendiente).
8. Bloqueo con archivo `.lock` (caduca a los 180 s) y antigüedad máxima de 24 h.
9. Fallo del CLI o de la ventana: el mensaje no se marca leído ni procesado; backoff de
   30/60/120/240/300 s y `max_attempts: 5`. `--reset-failures` lo reactiva. Si el CLI sale con 0
   pero no hay respuesta, `require_reply` lo cuenta como fallo (detecta un CLI sin el MCP del
   buzón). Con `window` se espera `window_reply_timeout_seconds` (90 s) y se registra fallo si el
   cliente no responde.
10. `allowed_senders` opcional limita qué identidades pueden disparar un despertar.
11. **Disparador explícito:** con `"trigger": {"require": true}` (activo en esta instalación) el
    mensaje debe contener `@despertar` o `[despertar]` en el asunto o el cuerpo; si no, queda en el
    buzón y nadie se despierta. Así una charla normal con la otra IA no provoca respuestas
    automáticas. Las respuestas (`reply_to`) nunca despiertan, con o sin token.

Destinos configurados: `claude` (manual en esta cuenta: `method: none`, sin CLI) y `opencode` (CLI
`opencode run`, ventana `OpenCode Dev`/`OpenCode`). Método por defecto `cli`; `window` solo se usa si
aparece en `fallback`. El CLI debe tener el servidor `zeroscript-pc` en su propio perfil: `claude -p`
no comparte configuración con Claude Desktop, mientras que el CLI de OpenCode 2.1.4 sí lee el mismo
`~/.config/opencode/opencode.json` que la app.

En esta instalación el destino `opencode` ya está operativo: el CLI 2.1.4 se copió de la app de
Store a `%LOCALAPPDATA%\Programs\ZeroScript\opencode.exe`, comparte
`~/.config/opencode/opencode.json` (MCP `zeroscript-pc` conectado) y lo lanza con `run --agent wake --model openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` (verificado en `despertar_config.json`; las pruebas del 15-nov se hicieron con `opencode/deepseek-v4.1-flash-free`). No he comprobado qué permisos tiene el agente `wake`. No se debe añadir `--standalone`, porque ese modo no carga los
servidores MCP. `claude` queda en manual (`method: none`): la cuenta gratis solo tiene chat y el
watcher solo vigila `opencode`.

**Uso de `despertar.bat` (cambiado el 15-nov-2026):**

```bat
despertar.bat /opencode            Despierta a OpenCode (aplica de verdad)
despertar.bat /claude              Solo muestra el estado; Claude no se despierta
despertar.bat /claude /simular     Muestra qué haría, sin activar nada
despertar.bat                      Sin comando: muestra la ayuda y no hace nada (código de salida 1)
```

El lanzador usa etiquetas `goto` en vez de bloques `if (...)` porque un `)` sin escapar dentro de un
bloque lo cierra antes de tiempo: la ayuda y el `exit /b 1` se ejecutaban siempre y `/claude` y
`/opencode` parecían no reconocerse.

`despertar.py` simula por defecto; `--apply` despierta de verdad, `--watch --apply` vigila en primer
plano y `--status` muestra presupuesto, fallos y últimos despertares. `--method` fuerza `cli` o
`window`. `wake_state.json` guarda 3 despertares reales (15 y 16-nov) y 1 fallo pendiente; ver la
sección 8 para el detalle.

### 4.6 `start.bat`

Pasos: (1) prepara `workspace_wake\` y copia `*.example.json` si faltan las configuraciones locales;
(2) comprueba el Python embebido en `runtime\python\` (si falta, llama a `preparar_portable.ps1`) y
verifica si puede escribir en `logs\` (si Windows Defender CFA lo bloquea dentro de `Documentos`, cae
automáticamente a Python 3.9+ del sistema como respaldo); (3) comprueba `websockets`; (4) si el puerto
del bridge (`ZS_BRIDGE_PORT`, 17613) está ocupado, verifica por línea de comandos que pertenezca a
`bridge.py` antes de cerrarlo; (5) arranca el chat local, muestra el estado del mensajero, ejecuta
`vigilante_cambios.py ensure` (instala y arranca el vigilante solo si detecta una PC nueva) y lanza
`bridge.py` oculto con `pythonw.exe` (o en consola con `/consola`). Acepta también `/nochat` y `/nopause`.

`pythonw.exe` es un binario de subsistema GUI: **no tiene consola**, así que el bridge, el PC agent
y el mensajero corren sin ninguna ventana y sobreviven al cierre de la ventana de `start.bat`. El
lanzador espera ~3 s y muestra el PID que quedó escuchando en `ws://127.0.0.1:17613`; si no
responde, avisa y apunta a `logs\bridge_debug.log`. El chat local (`http://127.0.0.1:8765`) sigue
vivo tras cerrar el lanzador (`lanzar_chat.ps1` reutiliza el servidor en el siguiente arranque).

El archivo debe estar en **CRLF**: en LF, `cmd.exe` desalinea bloques y `goto`, y aparecen errores
como un `pause` inesperado o `No se esperaba . en este momento`. Todo queda en `logs\start.log`.

### 4.7 Extensión de navegador (`zeroscript-extension\`, versión 2.2.0)

- Manifest v3. Un service worker (`background.js`) mantiene el WebSocket al bridge con reconexión y
  latido. `core\main.js` (263 KB) contiene el bucle del agente, la interfaz y la confirmación antes de
  escribir o ejecutar comandos. `core\parser.js` interpreta los comandos de la IA.
- Un archivo por proveedor en `providers\`: DeepSeek, Kimi, Arena, Qwen, ChatGPT, Gemini, GLM, Meta.
- **El manifest actual carga los 8 proveedores** (verificado leyendo `manifest.json`): DeepSeek, ChatGPT, Gemini, Kimi, GLM, Arena, Meta AI y Qwen. ChatGPT y Qwen inyectan además un script en el mundo MAIN (`chatgpt-cm.js`, `qwen-net.js`).
- Pruebas en Node: `node test-parser.js` y `node test-chatgpt.js`.

### 4.8 Otros

- `limpiar_buzon.py`: `py -3 limpiar_buzon.py` (simula) y `--apply` (mueve leídos de más de 30 días;
  nunca mueve no leídos ni borra).
- `launch_studio_mcp.py`: lanzador opcional para el MCP de Roblox Studio (ver archivo).

## 5. Flujos principales

**A. Una IA del navegador ejecuta una acción:** la IA escribe un comando, la extensión lo envía por
WebSocket, el bridge lo pasa a `pc_agent_mcp.py`, y el resultado vuelve al chat. La extensión pide
confirmación para `pc_write`, `pc_edit` y `pc_shell`.

**B. Una IA le escribe a otra:** `msg_send(to="opencode", ...)` crea el JSON; la otra lo lee con
`msg_inbox` (o espera con `msg_wait`) y responde con `msg_reply` (suma 1 a `hops`).

**C. Despertar:** después de `msg_send`, el mensajero del bridge (o `despertar.bat /opencode` a mano)
elige el mensaje pendiente más antiguo, aplica las reglas y lanza el CLI de OpenCode en segundo plano
(`opencode run`); registra el despertar en `wake_state.json` y en `logs\despertar.log`. El método
`window` (pegar el aviso en la ventana) solo se usaría si apareciera en `fallback`, y hoy ningún
destino lo usa.

**D. Tú escribes desde la página:** `http://127.0.0.1:8765` -> campo "Para" (un agente o `todos`) ->
mensaje firmado como `usuario`.

## 6. Configuración

`pc_agent_config.json` (y su plantilla `pc_agent_config.example.json`, con rutas relativas para funcionar en cualquier PC):

| Clave | Valor | Significado |
| --- | --- | --- |
| `workspace` | `.` (carpeta del proyecto) | Raíz de las rutas relativas |
| `allow_outside_workspace` | `false` | No permite rutas fuera del workspace |
| `allow_shell` | `true` (en `.example.json`: `false`) | Activa/desactiva `pc_shell` |
| `allow_write` | `true` (en `.restricted`: `false`) | Activa/desactiva `pc_write` y `pc_edit` |
| `shell_timeout_ms` | 120000 | Tiempo por defecto de un comando |
| `max_read_bytes` | 2000000 | Tamaño máximo que lee `pc_read` |
| `max_output_chars` | 40000 | Salida máxima de una herramienta |
| `max_grep_results` | 100 | Coincidencias máximas de `pc_grep` |
| `max_hops` / `max_msgs_per_10min` / `max_message_chars` | 6 / 30 / 20000 | Límites del buzón |
| `mailbox_dir` | `~/Documents/AI-Shared/mailbox` | Carpeta del buzón |
| `mailbox_archive_days` | 30 | Antigüedad para archivar |
| `skip_dirs` | `.git`, `node_modules`, `bin`, `env`... | Carpetas que se saltan `pc_glob` y `pc_grep` |

`pc_agent_config.restricted.json` es el perfil que usa el despertar para el CLI: mismas claves y
límites, pero el workspace es `workspace_wake`; `allow_shell`, `allow_write` y
`allow_outside_workspace` están en `false`. Si falta cualquier `.json` local, `pc_agent_mcp.py`,
`despertar.py` y `chat-local\server.py` hacen fallback automático a su `*.example.json`.

`despertar_config.json`: `enabled`, `default_targets`, `min_seconds_between` 60, `max_per_hour` 6,
`max_per_day` 20, `max_age_hours` 24, `max_attempts` 5, `retry_base_seconds` 30, `require_reply`,
`allowed_senders`, `prompt`, bloque `watch` (`enabled`, `interval_seconds` 2.5, `targets`) y por
destino `method`, `fallback`, `process`, `title`, `command` y `cli_timeout_seconds` (240 para Claude
y 300 para OpenCode).

Variables de entorno: `ZS_PC_CONFIG`, `ZS_PC_WORKSPACE`, `ZS_PC_ALLOW_OUTSIDE_WORKSPACE`,
`ZS_PC_ALLOW_SHELL`, `ZS_PC_ALLOW_WRITE`, `ZS_PC_SHELL_TIMEOUT_MS`, `ZS_PC_AGENT_NAME`,
`ZS_PC_MAILBOX_DIR`, `ZS_BRIDGE_PORT`, `ZS_BRIDGE_EXTENSION_ID`, `ZS_BRIDGE_TOKEN`,
`ZS_BRIDGE_ALLOWED_ORIGINS`, `ZS_BRIDGE_ALLOW_ANY_ORIGIN`, `ZS_VIGILANTE_STARTUP_DIR`,
`CHAT_LOCAL_PORT`, `CHAT_LOCAL_SCAN_SECONDS`, `ZS_STUDIO_MCP_PATH`.

Puertos: 17613 (bridge, WebSocket) y 8765 (chat local, HTTP). Ambos solo en 127.0.0.1.

## 7. Comandos útiles

```bat
start.bat                                   REM arranca bridge + chat local
py -3 pc_agent_mcp.py --check               REM valida la instalación
py -3 pc_agent_mcp.py --print-config claude REM configuración para Claude Desktop
chat-local\iniciar_chat.bat                 REM solo el chat
chat-local\detener_chat.bat                 REM detiene el chat
despertar.bat /opencode /simular            REM prueba sin activar
despertar.bat /opencode                     REM despierta a OpenCode ahora
despertar.bat /claude                       REM solo estado; Claude no se despierta
py -3 despertar.py --watch --apply          REM vigila el buzon en primer plano
py -3 despertar.py --status                 REM presupuesto, fallos y ultimos despertares
py -3 despertar.py --reset-failures         REM reactiva destinos con fallos agotados
py -3 limpiar_buzon.py --apply              REM archiva leídos de más de 30 días
type nul > wake_off                         REM apaga el despertar al instante
```

## 8. Estado de esta instalación (actualizado el 21-nov-2026)

- **Portabilidad y arranque embebido (19–21 nov 2026):** `runtime\python\` incluye Python **3.12.10**
  portable con `websockets 17.4` y `watchdog 7.1.0` (`preparar_portable.bat`/`.ps1`). `start.bat` lo
  usa por defecto (y cae al Python del sistema si Defender CFA bloquea `Documentos`). Todas las
  configuraciones usan rutas relativas (`"."` y `"workspace_wake"`), y `manifest.json` fija el ID
  `kmjgngkgeagldpddkklmdmllbkdopldb` mediante `"key"` RSA (falta recargar una vez en Chrome para
  dejar el ID anterior `jgigjkahlhhfcmbnlbmbbcdpeljdkidp`).
- **Vigilante de cambios activo:** `vigilante_cambios.py` corriendo (`pythonw.exe`, PID `10356`) sin
  falsos positivos al leer archivos y con auto-instalación automática en PCs nuevas (`ensure`).
- **`wake_off` activo:** el despertar automático está frenado temporalmente hasta validar el agente
  `wake` de OpenCode con un modelo con cuota disponible.
- **Pruebas:** `comprobar_proyecto.py` pasa con 0 problemas y 0 avisos; `pc_agent_mcp.py --check`
  pasa en perfil normal y restringido (`allow_write: false`); pruebas JS de la extensión 45/45.

**Registro histórico de pruebas previas (15–18 nov 2026):**

- **Renombrado el 18-nov-2026:** la carpeta pasó a `ZeroScriptModify`. La configuración del agente,
  los clientes MCP (OpenCode, Claude Desktop, Antigravity), el VBS de Inicio y los dos lanzadores ya
  apuntan a la ruta nueva. Todos los procesos del proyecto están detenidos. Falta recargar la
  extensión desde `zeroscript-extension` y reiniciar los clientes MCP para que lean la configuración
  nueva.
- Windows 10 (build 19044). Python **3.15.0rc3** (versión candidata, no la final).
- Los 8 archivos `.py` de la raíz compilan sin errores; `pc_agent_mcp.py --check` termina en "Result: OK" con
  12 herramientas.
- Pruebas de la extensión: 37 + 8 = 45 correctas, 0 fallos.
- Último arranque del bridge en `logs\bridge_debug.log` (verificado el 18-nov): 18-nov 11:52:30, v2.2.0, pid 3900. La extensión se conectó a las 11:52:34 con origen `chrome-extension://ljkcldlijdibhfookemkeeefpmgijcge` (ID antiguo, de la carpeta `ZeroScript-Free-1.5.5`; el ID actual de `ZeroScriptModify` es `jgigjkahlhhfcmbnlbmbbcdpeljdkidp`). El bridge solo declara un servidor MCP, `pc` (comprobado con `list_mcp_servers` y en `config.json`). El 17-nov hubo muchos reinicios seguidos (28 arranques, 26 de ellos entre las 13:00 y las 19:00), coherentes con las ediciones de ese día. El log no dice con qué variables de entorno se lanzó el bridge, así que sigue sin comprobarse que `ZS_BRIDGE_EXTENSION_ID` estuviera definida en el proceso actual.
- Prueba de origen registrada el 16-nov a las 00:55:16: se rechazaron `https://evil.example`, `http://127.0.0.1:8765` y `chrome-extension://aaaa...` y, justo después, se aceptó una conexión con `origin=None`. Eso fue antes o durante el endurecimiento: el código actual (`bridge.py:1445-1447`) rechaza `origin=None`, pero no he repetido la prueba contra el bridge actual.
- El mensajero (vigilante del buzón) estaba activo hasta el cierre de procesos del 18-nov: desde el 17-nov el log usa el prefijo `mensajero:` en lugar de `wake watcher:`. El último arranque registrado del 18-nov a las 11:52:31 registra `mensajero: despertar_config.json cada 2.5 s; destinos: opencode` (`bridge.py:1921-1976`).
- El vigilante de cambios del proyecto estaba activo (verificado el 18-nov: `pythonw.exe` pid 10416) y quedó detenido al cerrar los procesos: `logs\registro_cambios\cambios_2026-W47.log` tiene 322 líneas y registra cada cambio con fecha, autor (`Usuario`), evento, FILE/DIR y ruta relativa.
- Buzón: 31 mensajes, ninguno archivable todavía.
- `start.log` acumula 73 ejecuciones de `start.bat` (24 el 17-nov y 1 el 18-nov a las 11:52); las
  últimas no muestran errores, incluida la comprobación de `despertar`.
- Ya existe la carpeta `.git` (el proyecto es un repositorio desde el 18-nov-2026) y no hay `wake_off` en la raíz (verificado con `pc_list` el 18-nov). `wake_state.json` (modificado el 16-nov a las 10:00) registra 3 despertares reales: OpenCode por CLI el 15-nov a las 22:00, Claude por ventana el 15-nov a las 22:17 y OpenCode por CLI el 16-nov a las 08:58. Además guarda 1 fallo pendiente: el mensaje `03dd4a7a...` para `opencode` lleva 4 intentos de 5 (`max_attempts`) con el error "Free usage limit reached" del CLI. Ese error es de antes del cambio de modelo en `despertar_config.json` (modificado el 16-nov a las 14:23); no he comprobado si el modelo actual funciona. Con 4 de 5 intentos, un fallo más agotaría el destino hasta `--reset-failures`; en la práctica el mensaje ya tiene más de 24 h (`max_age_hours`), así que queda fuera de la ventana y no se reintenta.
- CLI de OpenCode 2.1.4 copiado a `%LOCALAPPDATA%\Programs\ZeroScript\opencode.exe`;
  `opencode mcp list` conecta `zeroscript-pc`. Claude queda manual (cuenta gratis solo chat;
  `method: none`) y no está en `watch.targets`.
- Despertar automático probado el 15-nov a las 21:33: el watcher detectó un mensaje de prueba y el
  CLI de OpenCode respondió `OK-WATCHER`; los mensajes de prueba se borraron. En ese momento no se
  creó `wake_state.json`; los despertares reales llegaron después (ver arriba).
- Bridge de prueba a las 21:41: el log muestra `wake watcher: despertar_config.json cada 2.5 s;
  destinos: opencode`. `despertar.bat` corregido: `/opencode` y `/claude` funcionan (código 0) y sin
  argumentos muestra la ayuda y sale con 1.
- Disparador probado el 15-nov a las 21:50 contra el buzón real y el CLI de OpenCode: el mensaje sin
  token quedó pendiente (`falta el disparador @despertar`) y el que llevaba `@despertar` despertó al
  CLI, que respondió con `reply_to` correcto. Se borraron los mensajes de prueba y
  `wake_state.json`.
- Claude Desktop despertado por ventana el 15-nov a las 22:03: `--method window` enfocó la ventana,
  pegó el aviso y pulsó Enter; Claude usó `msg_inbox` y respondió `hello` con `msg_reply`. La primera
  vez hay que pulsar "Permitir siempre" en los avisos de permiso de cada herramienta. Su config está
  en `%LOCALAPPDATA%\Claude-Data\claude_pzs8sxrjxfjjc\claude_desktop_config.json` (identidad
  `claude`), no en `%APPDATA%\Claude`. El bridge que estaba corriendo despertó a OpenCode a las 22:00
  con un mensaje de `claude1`.
- Repetido a las 22:17 tras reforzar el foco: el primer intento falló porque Windows no dejaba traer
  Claude al frente con OpenCode a pantalla completa; con el toque de ALT, `AppActivate` y
  minimizar/restaurar, el segundo intento enfocó, pegó, Claude respondió `hello` y el script lo dio
  por bueno solo al ver la respuesta (`window_reply_timeout_seconds`). Se borraron los mensajes de
  prueba; `wake_state.json` conserva los dos despertares de esa noche (opencode 22:00, claude
  22:17); el tercero (opencode, 16-nov 08:58) se añadió después.

## 9. Revisión: errores y puntos a mejorar

Prioridad: **Alta** = riesgo real o fallo probable; **Media** = conviene corregirlo; **Baja** =
limpieza o detalle.

### 9.1 Errores y riesgos

| # | Prioridad | Dónde | Problema | Arreglo sugerido |
| --- | --- | --- | --- | --- |
| 1 | Baja | `pc_agent_mcp.py:937-940` | **Resuelto (verificado con pc_grep).** El `Popen` de `pc_shell` ya lleva `stdin=subprocess.DEVNULL`, así que el hijo no hereda el canal JSON-RPC. | — |
| 2 | Baja | `zeroscript-extension\manifest.json` | **Resuelto (verificado leyendo el manifest).** El manifest actual carga los 8 proveedores, de modo que coincide con lo que anuncian README, `popup.js`, `background.js` y `main.js`. | — |
| 3 | Media | `bridge.py` (`_origin_allowed`, `_check_token`) | **Parcialmente resuelto (19-nov-2026).** El ID de extensión se deriva automáticamente de `"key"` en `manifest.json` y se añadió soporte para token compartido `ZS_BRIDGE_TOKEN` (`hmac.compare_digest` + `chrome.storage.local` en `background.js`). Pendiente: activar el token por defecto y añadir campo para configurarlo en el popup | Añadir UI del token en `popup.html`/`popup.js` |
| 4 | Media | Diseño del despertar | **Mayormente resuelto (verificado en `despertar.py:614-619` y `despertar_config.json`).** Antes de lanzar el CLI, `despertar.py` fuerza `ZS_PC_CONFIG=pc_agent_config.restricted.json` (`allow_shell: false`, `allow_outside_workspace: false`, workspace `workspace_wake`) y falla en cerrado si el perfil no existe. `allowed_senders` limita quién dispara y el token `@despertar` es obligatorio. Pendiente: (a) el método `window` no aplica el perfil restringido, así que no debe añadirse a ningún `fallback` mientras Claude Desktop use su propia configuración; hoy ningún destino lo usa. (b) No he comprobado que el hijo MCP de `opencode run --agent wake` herede `ZS_PC_CONFIG` ni qué permisos tiene el agente `wake` | Probar con un despertar real que `pc_shell` sea rechazado en el CLI; mantener `fallback: []` |
| 5 | Media | `bridge.py` (`restart_self`, líneas 770-803) | El código intenta `os.execv` y, si falla, abre una copia nueva con `subprocess.Popen`, la deja sin ventana y termina la instancia anterior con `os._exit(0)`. **Pendiente de prueba real en Windows:** no he ejecutado un `add_server`/`remove_server` para comprobar que el bridge nuevo conserva el puerto y que no queda una instancia duplicada. Desde el 17-nov `start.bat` lanza el bridge oculto y ya no lee su salida ni detiene el chat local, así que ese punto ya no aplica | Probar el ciclo completo de reinicio en Windows y revisar `logs\bridge_debug.log` |
| 6 | Media | `pc_agent_mcp.py` (`msg_wait`) | Cada 0,5 s relee y analiza todos los JSON del buzón, hasta 55 s. El coste crece con el número de mensajes. Además el servidor es de un solo hilo: un `msg_wait` o un `pc_shell` largo bloquean cualquier otra llamada de ese proceso | Comparar solo nombres y fechas con `os.scandir` y analizar solo lo nuevo; servir llamadas en hilos |
| 7 | Media | `pc_agent_mcp.py` (`pc_write`/`pc_edit`) | **Resuelto el 18-nov-2026 (verificado con 15 pruebas en una carpeta temporal; el servidor en marcha usa el código nuevo al reiniciarlo).** Ahora escriben con archivo temporal y `os.replace`, `pc_edit` conserva la codificación y el BOM y adapta `\n` a CRLF. Antes: escribían directamente (no atómico: un corte deja el archivo a medias). `pc_edit` lee en UTF-8/cp1252/latin-1 pero siempre escribe UTF-8 sin BOM, lo que cambia la codificación y quita el BOM. Tampoco conserva los finales de línea que enviaba el modelo | Escribir a un temporal y `os.replace`; recordar codificación y BOM originales |
| 8 | Media | Todos los `.bat` / `.cmd` | **Resuelto el 18-nov-2026 (verificado: 0 LF sueltos en los 8 `.bat`/`.cmd`; `.gitattributes` fija `eol=crlf` y `comprobar_proyecto.py` lo vigila).** Antes (parcial): `start.bat` y `despertar.bat` ya estaban en CRLF (0 LF). Siguen en LF `chat-local\iniciar_chat.bat`, `chat-local\detener_chat.bat`, `instalar_vigilante.bat`, `desinstalar_vigilante.bat`, `vigilante_cambios.bat` y `pc_agent_mcp.cmd`. En `cmd.exe`, un `.bat` en LF puede fallar con `goto` o `call :etiqueta` según el desplazamiento de bytes; fue la causa del `pause` fantasma y del `No se esperaba .` en `start.bat` | Convertir los 6 restantes a CRLF y añadir a `.gitattributes`: `*.bat text eol=crlf` y `*.cmd text eol=crlf` |
| 9 | Baja | `despertar.bat` | **Resuelto el 15-nov-2026.** Sin comando termina con error y `/claude` aplica de verdad. `MCP_CLIENTS.md`, `README.txt` y `CHANGELOG.md` ya lo describen como atajo manual. | — |
| 10 | Baja | `despertar.py` | **Resuelto el 15-nov-2026.** (a) Los fallos se registran con backoff 30/60/120/240/300 s y `max_attempts: 5`; el mensaje nunca se marca leído ni procesado. (b) Cualquier destino fallido fuerza código de salida 1. (c) `processed` y `failures` usan el destino en minúsculas. (d) `0` desactiva el presupuesto. (e) El método por defecto es `cli`; `window` queda como fallback opcional. `require_reply` trata un CLI que sale con 0 sin responder como fallo. | — |
| 11 | Baja | `start.bat` | **Resuelto el 21-nov-2026.** Antes de cerrar un proceso en el puerto del bridge (`ZS_BRIDGE_PORT`), comprueba por línea de comandos que sea `bridge.py`; si pertenece a otro programa, avisa y no lo cierra. | — |
| 12 | Baja | Versiones | Carpeta `ZeroScriptModify` (antes "1.5.5 - copia"), bridge y extensión 2.2.0, `pc_agent_mcp.py` 2.3.0, chat local 2.4.0. El CHANGELOG ya tiene 2.4.0 y una entrada `Unreleased`, y `MCP_CLIENTS.md` documenta `despertar.bat`; README.txt sigue sin sección 2.4.0 y la opción `todos` no aparece en la documentación | Unificar el número y añadir la sección 2.4.0 al README |
| 13 | Baja | Python 3.15.0rc3 | Es una versión candidata, no la final | Usar la última estable |
| 14 | Baja | README y `MCP_CLIENTS.md` (líneas 118 y 480-481) | Dicen que la página no marca nada como leído; `server.py:383-386` sí marca el original como leído si llega `reply_to`. La página actual no envía `reply_to`, así que hoy no ocurre | Corregir el texto o quitar el marcado |
| 15 | Baja | Chat local | Cada 3 s pide todos los mensajes (sin paginar). Un mensaje a `todos` se ve como una burbuja por agente. Un agente que haga `msg_send(to="todos")` crea un mensaje sin destinatario real | Paginar o pedir solo lo nuevo; documentar que `todos` es solo de la página |
| 16 | Baja | Registros | `bridge_debug.log` crece sin rotación (284 KB hoy). `start.log` mezcla codificaciones y se ve con acentos rotos en PowerShell 5.1 | Rotar el log; escribirlo siempre en UTF-8 |
| 17 | Baja | `background.js:11` | **Resuelto el 18-nov-2026 (renombrado a `BRIDGE_URL`).** Antes: `const URL = ...` ocultaba la clase global `URL` (hoy no se usa como constructor, así que no falla) | Renombrar a `BRIDGE_URL` |
| 18 | Alta | `zeroscript-extension\` (8 archivos) | **Resuelto el 18-nov-2026.** `manifest.json`, `popup.html`, `popup.js`, `background.js`, `overlay.css`, `README.md`, `core/config.js` y `core/main.js` estaban en la versión original «Roblox Studio Agent 1.5.5» (sin herramientas `pc_*`, sin la confirmación `confirmPc` y con Roblox como servidor principal), mientras que el commit `c05399a` tenía la versión buena del agente de PC. El registro de cambios anota modificaciones de esos archivos a las 21:06 y a las 22:08 del 18-nov, con fecha de archivo de octubre (típico de una copia que conserva fechas). No se ha identificado qué lo causó. Las 45 pruebas de la extensión pasaban igual con las dos versiones, porque no cubren esas partes | Restaurados desde `c05399a`; copia de lo que había en `backups\extension-revertida-20261118`; `comprobar_proyecto.py` ahora lo detecta. Pendiente: recargar la extensión en el navegador |

### 9.2 Limpieza y organización

- `patch_claude1.py` y `despertar.txt` se eliminaron en git el 19-nov-2026 (hay copia en `backups\`).
- `INFORME_CODIGO_MCP.md`, el duplicado `README.md`, `bridge_segundo_plano.vbs`,
  `chat-local\ocultar_ventana.ps1` y el PID huérfano `chat-8765.pid` se retiraron el 21-nov-2026
  (respaldados en `backups\limpieza-20261121\`).
- `_safe_filename_part` (sin usos; la lógica está en `mailbox_store.py`) se eliminó de `pc_agent_mcp.py` el 18-nov-2026.
- `backups\` ya está en `.gitignore` y contiene una copia de `claude_desktop_config.json`
  (configuración personal de Claude Desktop, 17 KB); no viaja al repositorio.
- El proyecto **sí** es un repositorio git desde el 18-nov-2026 (commit inicial `c05399a`). Varias IAs
  editan los mismos archivos; conviene hacer commits pequeños en lugar de acumular respaldos
  manuales `.antes-*`.
- Los scripts de PowerShell están en ASCII a propósito (bien): así no dependen de la codificación.

## 10. Lo que está bien

- **Buzón sólido:** escritura atómica, saneado de nombres, límites de tamaño, ignora enlaces
  simbólicos, archivos enormes y JSON corrupto, y un solo módulo (`mailbox_store.py`) compartido
  por el servidor MCP y el chat, para que no se desfasen.
- **Anti-bucle en capas:** `max_hops`, tope de mensajes por 10 minutos y de tamaño, y en el despertar:
  solo hilos nuevos, estado persistente, asunto `[auto]`, presupuesto por minuto/hora/día,
  interruptor `wake_off`, prompt fijo y bloqueo contra ejecuciones simultáneas. Todo por defecto en
  simulación.
- **Contenido no confiable:** las instrucciones del servidor y cada `msg_inbox` avisan de que los
  mensajes vienen de otras IAs y no son órdenes.
- **Chat local bien acotado:** solo 127.0.0.1, validación de `Host` y `Origin`, mismo origen para
  `usuario`, cabeceras CSP/`X-Frame-Options`, `textContent` en lugar de `innerHTML`, límite de 1 MB,
  caché por firma del directorio y detección de agentes bajo demanda.
- **Lanzadores cuidadosos:** `start.bat` comprueba archivos y Python, da mensajes claros y registra en
  `start.log`; `lanzar_chat.ps1` no mata procesos ajenos y espera a que `/api/health` responda.
- **Bridge robusto:** un hilo lector por servidor, reinicio automático, supervisión de las tareas de
  vigilancia, latido en WebSocket y control de origen ya incorporado.
- **Calidad verificada:** todo compila, `--check` pasa y las pruebas de la extensión pasan (45 de 45).
- **Poca dependencia externa:** `websockets` para el bridge y `watchdog` para el vigilante de
  cambios; el resto es biblioteca estándar.
- **Documentación abundante:** README, `MCP_CLIENTS.md` y CHANGELOG detallados, y respaldos hechos antes
  de cada cambio de esta sesión.

## 11. Cambios hechos en esta sesión (14-15 nov 2026)

- `despertar.bat`: solo activa con `/opencode` o `/claude` (este último solo muestra el estado);
  opción `/simular`. Reescrito con etiquetas `goto` porque un `)` sin escapar cerraba el bloque de
  ayuda y hacía que siempre saliera con 1.
- `despertar.py`: método `cli` por defecto (`claude -p` / `opencode run`), `fallback` opcional,
  `window` solo opt-in, backoff de fallos en `wake_state.json`, `--watch --apply`,
  `--reset-failures`, `allowed_senders`, `trigger` (token `@despertar`/`[despertar]` obligatorio)
  y destinos normalizados a minúsculas.
- `bridge.py`: `wake_watch()` arranca el **mensajero** dentro del bridge (hilo demonio que se
  apaga con él y termina los CLI hijos).
- `start.bat`: nueva subrutina `:check_despertar` (comprueba archivos e informa; el bridge arranca
  el mensajero).
- OpenCode CLI: copiado el binario 2.1.4 de la app de Store a
  `%LOCALAPPDATA%\Programs\ZeroScript\opencode.exe`; probado con
  `opencode/deepseek-v4.1-flash-free` y una respuesta real `OK-CLI`/`OK-WATCHER`.
- Claude: pasa a `method: none` y sale de `default_targets`/`watch.targets`; la cuenta gratis solo
  permite chat, así que se revisa abriendo Claude Desktop y pidiendo `msg_inbox`.
- Chat local: opción `todos` en el campo "Para" (`server.py` y `chat.html`, versión 2.4.0).
- Respaldos en `backups\`: `despertar.bat.antes-comandos`, `start.bat.antes-despertar`,
  `chat.html.antes-todos`, `server.py.antes-todos`.
- Pendiente de decidir: botones de despertar dentro de la página del chat (no se tocaron en esta
  sesión).
- CHANGELOG.md actualizado con la entrada 2.4.0; README.txt y `MCP_CLIENTS.md` documentan el
  despertar y el chat local, pero la opción `todos` sigue sin documentarse.

**Cambios del 17-18 de noviembre de 2026 (arranque oculto y nombre del mensajero):**

- El vigilante del buzón se llama **mensajero** en los textos visibles (`bridge.py`,
  `despertar.py --status`, `start.bat`, documentación). Los archivos internos
  (`despertar.py`, `despertar.bat`, `despertar_config.json`) no cambian.
- `start.bat` lanza el bridge con `pythonw.exe` (sin consola) y termina enseguida: el bridge, el PC
  agent y el mensajero siguen vivos al cerrar la ventana del lanzador. Se elimina el envoltorio
  `cmd /c` y el VBScript intermedio, y se muestra en pantalla el PID que escucha en el 17613.
- `start.bat` vuelve a estar en **CRLF** (estaba en LF) y `:validate_py` comprueba que `PY` no esté
  vacío. Con eso desaparecen el `pause` inesperado, el `No se esperaba . en este momento` y los
  errores `"-m"`/`"-c" no se reconoce`.
- `start.bat` ya **no detiene el chat local** al terminar (antes lo paraba 3 s después de abrir el
  navegador). `lanzar_chat.ps1` reutiliza el servidor en el siguiente arranque.
- `taskkill /F /T` al reemplazar un bridge, para no dejar huérfano su `pc_agent_mcp.py` hijo.
- `bridge.py`: `CREATE_NO_WINDOW` al lanzar el MCP y al reiniciar, y `_NullStream`/`_NullStdin` para
  sobrevivir bajo `pythonw.exe` (sin `stdout`/`stdin`).
