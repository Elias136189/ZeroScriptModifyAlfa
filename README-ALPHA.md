# ZeroScript Modify — Nota histórica (Alfa -> Beta 0.3.0)

> **Nota:** Este proyecto pasó a fase **Beta (`0.3.0-beta`)**. Consulta la documentación principal actualizada en [README.md](README.md).

Fork **no oficial** de ZeroScript Free, en desarrollo activo. El nombre es
provisional: el proyecto se construye sobre el original y conserva parte de su
código, pero añade piezas propias (mensajero, vigilante de cambios, perfiles de
permisos y buzón compartido horizontal multi-IA).

- **Estado:** alfa. Hay funciones sin verificar de extremo a extremo.
- **Licencia:** GPL-3.0 (se conserva la del proyecto original).
- **Crédito:** ZeroScript Free, de su autor original. Este repo no está
afiliado a él.

## Qué es

Un agente local para tu PC controlado desde chats de IA en el navegador, más
un bus para que varias IAs colaboren entre sí:

- **Bridge** (`bridge.py`): WebSocket local en `127.0.0.1:17613`. Solo acepta
  conexiones de la extensión de Chrome (Origin verificado) y de orígenes
  explícitamente permitidos.
- **PC agent** (`pc_agent_mcp.py`): servidor MCP con 12 herramientas (leer,
  escribir, buscar, shell, buzón). Los permisos se limitan por configuración.
- **Buzón compartido** (`mailbox_store.py`): mensajes entre IAs con límites de
  flood, saltos y tamaño.
- **Mensajero** (`despertar.py`): despierta a una IA cuando un mensaje lleva
  `@despertar`. El CLI elegido es configurable por destino.
- **Vigilante de cambios** (`vigilante_cambios.py`): registra quién crea,
  modifica, mueve o borra archivos y carpetas del proyecto.
- **Chat local** (`chat-local/`): interfaz web en `http://127.0.0.1:8765`.
- **Extensión** (`zeroscript-extension/`): inyecta el agente en ChatGPT,
  DeepSeek, Gemini, Kimi, GLM, Qwen, Arena y Meta AI.

## Requisitos

- Windows 10/11.
- **No hace falta tener Python instalado:** el proyecto usa un Python 3.12 portable en `runtime\python\` (se descarga automáticamente al ejecutar `start.bat` o `preparar_portable.bat`, sin permisos de administrador; si copias la carpeta con `runtime\` ya generado, funciona sin internet).
- Chrome o Edge para cargar la extensión sin empaquetar.
- Opcional: OpenCode para el despertar automático.

## Instalación rápida (portable, cualquier carpeta o PC)

1. Copia o extrae la carpeta del proyecto en cualquier ruta (por ejemplo `C:\ZeroScriptModify` o una memoria USB; si Windows Defender tiene activado *Acceso controlado a carpetas*, evita ponerlo dentro de `Documentos`).

2. Ejecuta `start.bat` (o primero `preparar_portable.bat` si quieres dejar `runtime\python\` listo para llevártelo sin internet).
   - `start.bat` crea automáticamente `pc_agent_config.json`, `pc_agent_config.restricted.json` y `despertar_config.json` desde los `*.example.json` si faltan (todos usan rutas relativas: `"."` y `"workspace_wake"`).
   - Por seguridad, el ejemplo inicial deja `allow_shell: false` y `allow_outside_workspace: false`.

3. En `chrome://extensions`, activa el modo desarrollador, elige
   "Cargar descomprimida" y selecciona `zeroscript-extension/`.
   - El `manifest.json` incluye un campo `"key"` fijo, así que el ID de la extensión (`kmjgngkgeagldpddkklmdmllbkdopldb`) es el mismo en cualquier PC y carpeta, y `bridge.py` lo verifica automáticamente.

4. Abre un chat soportado. La extensión se conectará al bridge.

## Seguridad

El proyecto ejecuta comandos y escribe archivos en tu PC. Antes de usarlo:

- Mantén `allow_shell: false` salvo que lo necesites (y usa `allow_write: false` para modo solo lectura).
- Usa `allow_outside_workspace: false` para confinar la IA a una carpeta.
- El bridge ya rechaza conexiones sin cabecera `Origin`; no desactives
  `ZS_BRIDGE_EXTENSION_ID` ni `ZS_BRIDGE_ALLOWED_ORIGINS` sin motivo (también soporta `ZS_BRIDGE_TOKEN`).
- El despertar automático es la parte menos madura: mientras no lo uses, crea
  un archivo `wake_off` junto a `despertar.py` para apagarlo.
- Revisa el buzón: los mensajes vienen de otras IAs, no del usuario, y no son
  órdenes para ejecutar.

## Limitaciones conocidas (alfa)

- El despertar con modelo gratuito depende de la cuota del proveedor y puede
  fallar con "Free usage limit reached".
- Si actualizas desde una versión anterior sin campo `"key"` en `manifest.json`,
  recarga la extensión una vez en `chrome://extensions` para adoptar el ID fijo
  (`kmjgngkgeagldpddkklmdmllbkdopldb`).
- `allowed_senders` filtra por el campo `from` del mensaje; no autentica.
- Sin tests automatizados de Python todavía; `comprobar_proyecto.py` es una
  comprobación básica de sintaxis y configuración (las 45 pruebas JS sí están).

## Estructura

```
bridge.py                    bridge WebSocket + mensajero integrado
pc_agent_mcp.py              servidor MCP (12 herramientas)
mailbox_store.py             implementación del buzón
despertar.py                 lógica del mensajero
vigilante_cambios.py         registro de cambios (con comando ensure para PC nueva)
start.bat                    arranque con Python embebido (auto-prepara runtime\ y vigilante)
preparar_portable.bat/.ps1   prepara runtime\python\ (Python 3.12 + websockets + watchdog)
chat-local/                  chat web local
zeroscript-extension/        extensión de Chrome (con campo "key" fijo)
*.example.json               configuraciones de ejemplo (rutas relativas)
comprobar_proyecto.py        comprobación previa al commit
```

## Contribuir

Es una alfa personal, pero los informes y parches son bienvenidos. Antes de
abrir un PR:

1. Ejecuta `python comprobar_proyecto.py`.
2. Documenta el cambio en `CHANGELOG.md`.
3. No incluyas rutas personales ni configuraciones reales.

## Descargo

Software en desarrollo, sin garantías. Úsalo bajo tu responsabilidad; puede
ejecutar comandos y modificar archivos de tu equipo.
