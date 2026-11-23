# ZeroScript Modify — Beta (v0.3.0)

Fork **no oficial** de [ZeroScript Free](https://github.com/sebattfg/ZeroScript-Free) orientado a la **colaboración horizontal multi-IA** (sin agente jefe) sobre tu propio PC en Windows.

- **Estado:** Beta (`0.3.0-beta`). Core local probado con suite automatizada en Python y pruebas JS de la extensión.
- **Licencia:** GPL-3.0 (heredada del proyecto original).
- **Alcance:** Windows 10/11 con Python 3.12 embebido portable y extensión Chrome/Edge (MV3).

## Qué aporta esta versión

1. **Dos vías unificadas sobre el mismo workspace:**
   - **IAs en el navegador** (`zeroscript-extension/`): ChatGPT, DeepSeek, Gemini, Kimi, GLM, Qwen, Arena y Meta AI conectadas mediante `bridge.py` (`ws://127.0.0.1:17613`).
   - **Clientes MCP de escritorio**: OpenCode, Claude Desktop, Antigravity, Codex CLI y Kimi Code CLI conectados por stdio a `pc_agent_mcp.py`.
2. **Aislamiento por pestaña web y nombres reales (`bridge.py`, `chat-local/`):**
   - Cada pestaña de IA web recibe su propio proceso `pc_agent_mcp.py --agent <NombreDeLaWeb>` con lectura automática del modelo/nombre visible en la página web y sufijo numérico si hay dos pestañas iguales.
   - El chat grupal (`http://127.0.0.1:8765`) detecta y muestra por separado a cada IA web y CLI conectada.
3. **Coordinación horizontal sin agente jefe:**
   - **Buzón compartido (`mailbox_store.py`):** escritura atómica, archivo histórico y control anti-bucles.
   - **Anti-evasión de `max_hops` con detección de ciclos:** `msg_send` encadena `reply_to` y suma `hops` tanto en pares (`A ↔ B`) como en ciclos dirigidos de 3+ IAs (`A → B → C → A`), sin bloquear tareas nuevas dirigidas a terceros sin ciclo (`opencode → gemini`, luego `gemini → antigravity` con `@despertar`).
   - **Estado vivo de tarea (`ESTADO_TAREA.md`) y caja negra de 48h (`vigilante_cambios.py`):** si existe `ESTADO_TAREA.md` reciente en la raíz, `pc_system_info` lo adjunta automáticamente junto con los diffs compactos (`.zs` atribución `mcp:<agente>`) y las últimas acciones MCP de las últimas 48 horas.
   - **Protocolo anti-eco:** asuntos tipados (`[PROPUESTA]`, `[AUDITORIA]`, `[EJECUCION]`, `[BLOQUEO]`), verificación obligatoria de `archivo:línea` antes de validar diagnósticos y prohibición de respuestas vacías de cortesía.
4. **Seguridad y control de concurrencia:**
   - **Identidad fija por proceso (`_resolve_alias`):** cuando el servidor tiene identidad asignada, rechaza intentos de suplantar o leer otro agente vía `"as"`.
   - **Límites del workspace:** `allow_shell: false` y `allow_outside_workspace: false` en el perfil inicial; cualquier intento de escritura o shell fuera de la carpeta designada exige confirmación nativa en Windows (`prompt_outside_workspace`, un solo uso, "No" por defecto).
   - **Concurrencia optimista y lock por archivo:** `pc_read` registra la huella SHA-256 del archivo; `pc_write` y `pc_edit` usan lock `.zs.lock` entre procesos y abortan con error de colisión si otra IA modificó el archivo tras la lectura.
   - **Despertar automático seguro (`despertar.py`):** los CLI se ejecutan bajo `pc_agent_config.restricted.json` (sin escritura ni shell); en modo `window` crea un `.wake_lock_<destino>.lock` temporal que bloquea `pc_write`, `pc_edit` y `pc_shell` en `pc_agent_mcp.py` hasta responder con `msg_reply` al `message_id` exacto (o expirar el TTL).

## Instalación rápida (portable)

1. Copia o extrae el proyecto en cualquier carpeta (por ejemplo `C:\ZeroScriptModify`; evita `Documentos` si Windows Defender tiene activo *Acceso controlado a carpetas*).
2. Ejecuta `start.bat` (o `start.bat /nochat` si no quieres abrir el navegador del chat local).
   - La primera vez prepara `runtime\python\` (Python 3.12.10 embebido + `websockets` + `watchdog`) y crea los `.json` locales desde `*.example.json`.
   - Mantén abierta la ventana de consola: al cerrarla (`X` o `Ctrl+C`), un Windows Job Object apaga limpiamente `bridge.py`, sus hijos MCP, `despertar` y `chat-local`.
3. En `chrome://extensions`, activa el modo desarrollador, pulsa **"Cargar descomprimida"** y elige `zeroscript-extension/`.
   - El `manifest.json` fija el ID de extensión `kmjgngkgeagldpddkklmdmllbkdopldb` en cualquier carpeta o PC.
4. Abre tus IAs web o configura tus clientes MCP siguiendo [MCP_CLIENTS.md](MCP_CLIENTS.md).

## Pruebas y comprobación

```bat
runtime\python\python.exe -m unittest discover -s tests -v
runtime\python\python.exe comprobar_proyecto.py
runtime\python\python.exe pc_agent_mcp.py --check
node zeroscript-extension\test-parser.js
node zeroscript-extension\test-chatgpt.js
```

## Limitaciones conocidas (Beta)

- **Dependencia del DOM en los proveedores web:** las 8 integraciones de `zeroscript-extension/providers/` dependen de la interfaz web de cada proveedor y pueden requerir ajustes si un sitio cambia su DOM.
- **Herramientas nativas fuera de MCP en modo `window`:** el bloqueo `.wake_lock` detiene `pc_write`, `pc_edit` y `pc_shell` dentro de `pc_agent_mcp.py`, pero no puede interceptar herramientas propias internas del IDE o aplicación anfitriona (para aislamiento completo usa destinos `method: "cli"`).
- **Cuotas gratuitas en `despertar.py`:** el despertar con modelos gratuitos depende de la disponibilidad del proveedor externo.
- **Entorno objetivo:** diseñado y probado principalmente para Windows 10/11.

## Documentación adicional

- Arquitectura interna y detalles técnicos: [PROYECTO.md](PROYECTO.md)
- Configuración de clientes MCP de escritorio: [MCP_CLIENTS.md](MCP_CLIENTS.md)
- Historial de cambios: [CHANGELOG.md](CHANGELOG.md)
