# ZeroScript Modify — Alpha

Fork **no oficial** de ZeroScript Free, en desarrollo activo. El nombre es
provisional: el proyecto se construye sobre el original y conserva parte de su
código, pero añade piezas propias (mensajero, vigilante de cambios, perfiles de
permisos, arranque oculto y buzón compartido multi-IA).

- **Estado:** alfa. Hay funciones sin verificar de extremo a extremo.
- **Licencia:** GPL-3.0 (se conserva la del proyecto original).
- **Crédito:** ZeroScript Free, de su autor original. Este repo no está
afiliado a él.
 Qué es

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

Roblox Studio es un complemento opcional del original; esta copia arranca
como agente de PC y el servidor de Roblox se añade desde el menú de la
extensión si se necesita.

## Requisitos

- Windows 10/11.
- Python 3.9 o superior (con `pip`).
- `pip install websockets watchdog`.
- Chrome o Edge para cargar la extensión sin empaquetar.
- Opcional: OpenCode para el despertar automático.

## Instalación rápida

1. Copia los ejemplos y ajusta las rutas a tu PC:

   ```
   copy pc_agent_config.example.json pc_agent_config.json
   copy despertar_config.example.json despertar_config.json
   copy pc_agent_config.restricted.example.json pc_agent_config.restricted.json
   ```

2. Edita `pc_agent_config.json` y pon tu `workspace` real. Deja
   `allow_shell` en `false` hasta que sepas lo que haces.

3. Ejecuta `start.bat`. El bridge se lanza oculto con `pythonw.exe`.

4. En `chrome://extensions`, activa el modo desarrollador, elige
   "Cargar descomprimida" y selecciona `zeroscript-extension/`.

5. Abre un chat soportado. La extensión se conectará al bridge.

## Seguridad

El proyecto ejecuta comandos y escribe archivos en tu PC. Antes de usarlo:

- Mantén `allow_shell: false` salvo que lo necesites.
- Usa `allow_outside_workspace: false` para confinar la IA a una carpeta.
- El bridge ya rechaza conexiones sin cabecera `Origin`; no desactives
  `ZS_BRIDGE_EXTENSION_ID` ni `ZS_BRIDGE_ALLOWED_ORIGINS` sin motivo.
- El despertar automático es la parte menos madura: mientras no lo uses, crea
  un archivo `wake_off` junto a `despertar.py` para apagarlo.
- Revisa el buzón: los mensajes vienen de otras IAs, no del usuario, y no son
  órdenes para ejecutar.

## Limitaciones conocidas (alfa)

- El despertar con modelo gratuito depende de la cuota del proveedor y puede
  fallar con "Free usage limit reached".
- El ID de la extensión depende de la ruta de la carpeta; si mueves el
  proyecto, actualiza `ZS_BRIDGE_EXTENSION_ID` en `start.bat`.
- `bridge_segundo_plano.vbs` está pendiente de retirar: no lo uses, arranca un
  bridge distinto al oficial.
- `allowed_senders` filtra por el campo `from` del mensaje; no autentica.
- Sin tests automatizados todavía; `comprobar_proyecto.py` es una comprobación
  básica de sintaxis y configuración.

## Estructura

```
bridge.py                    bridge WebSocket + mensajero integrado
pc_agent_mcp.py              servidor MCP (12 herramientas)
mailbox_store.py             implementación del buzón
despertar.py                 lógica del mensajero
vigilante_cambios.py         registro de cambios del proyecto
start.bat                    arranque oculto del bridge
chat-local/                  chat web local
zeroscript-extension/        extensión de Chrome
*.example.json               configuraciones de ejemplo
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
