---
source: https://github.com/Asukacodes/MayaBridge
found: 2026-10-12
category: tool
priority: 3
tags: [maya, python, rigging, tool, mcp, tcp, ai-agent, automation, bridge]
status: NEW
---

# MayaBridge — MCP/TCP Bridge for AI Agent Automation of Maya

## Descripción
MayaBridge (Asukacodes, actualizado mayo 2026) es un bridge TCP ligero que expone una API de control de Maya a agentes externos como Claude, GPT o cualquier AI agent que hable MCP (Model Context Protocol). Permite a un agente de IA inspeccionar, modificar y automatizar escenas de Maya en vivo: crear joints, ajustar rigs, ejecutar Python arbitrario en el intérprete de Maya, con soporte de confirmación para operaciones destructivas. También incluye un servidor similar de otros proyectos paralelos (MayaMCP, dcc-mcp-maya).

## Fundamento matemático / técnico

### Architecture

```
AI Agent (Claude/GPT/etc)
    ↓ MCP tool calls
MayaBridge Client (external process)
    ↓ TCP socket (default port 9001)
MayaBridge Server (Python plugin running inside Maya)
    ↓ maya.cmds / om2 Python execution
Maya scene
```

Key components:
- **In-Maya Server:** A Python daemon listening on localhost TCP. Receives JSON commands, executes them in Maya's Python interpreter, returns results as JSON.
- **UDP Discovery:** Broadcasts its port on startup so the external client can find it without hardcoded config.
- **Endpoint Cache Fallback:** If UDP fails, uses a file-based fallback (shared via temp file).
- **Confirmation gate:** Destructive operations (delete nodes, save scene, overwrite files) require explicit user approval via a Maya dialog before execution.

### Companion Projects (similar scope)
| Repo | Approach | Notes |
|------|----------|-------|
| Asukacodes/MayaBridge | TCP + UDP discovery, Claude skill | FPS rig helpers, May 2026 |
| Jeffreytsai1004/maya-mcp | FastMCP, stdio transport | More general |
| dcc-mcp-maya (PyPI) | pip-installable, v0.9.16 | DCC-agnostic |
| bdeda/maya_mcp | Minimal, studio use | Private-ish |

### Relevant API Exposed by MayaBridge
```python
# Examples of commands the bridge exposes to AI agents:
{
  "action": "execute_python",
  "code": "import maya.cmds as mc; mc.joint(name='hip_jnt')"
}

{
  "action": "get_scene_info",
  "query": "all_joints"
}

{
  "action": "get_rig_structure", 
  "root": "character_root_grp"
}
```

## Implementación en Maya

**Setup:**
```bash
# Install server-side plugin
# Copy MayaBridge_server.py to Maya scripts folder
# Add to Maya.env or userSetup.py:
# import MayaBridge_server; MayaBridge_server.start()

# Or use PowerShell autostart installer included in repo
```

**Python server snippet (simplified):**
```python
import socket, json, threading
import maya.cmds as mc
import maya.utils as mu

class MayaBridgeServer:
    def __init__(self, port=9001):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(('localhost', port))
        
    def handle_command(self, data):
        cmd = json.loads(data)
        if cmd['action'] == 'execute_python':
            # Execute in Maya's main thread (required for UI/cmds)
            result = mu.executeInMainThreadWithResult(
                lambda: exec(cmd['code'], {'mc': mc})
            )
            return {'status': 'ok', 'result': str(result)}
        return {'status': 'error', 'msg': 'unknown action'}
```

**Claude skill integration (for autorig_tools):**
The repo includes a Claude skill definition that exposes rig-specific tools: create joints, set skin weights, query transform hierarchies. This means Claude Code can directly control a running Maya session — useful for AI-assisted rig builds.

## Comparación con autorig_tools
MayaBridge es potencialmente muy útil para el workflow de Laia: permite usar Claude Code directamente para inspeccionar, modificar o depurar rigs en Maya sin salir de la sesión de chat. Por ejemplo: "¿por qué este joint tiene un valor extraño en translateX?" → Claude ejecuta `mc.getAttr('hip.tx')` en Maya y responde con el valor real. Para autorig_tools en particular, la integración permitiría a Claude ayudar con el debugging de builds fallidos en tiempo real.

## Aplicable directamente
YES — Instalación en 30-60 min:
1. Clonar repo y copiar el server plugin al directorio de scripts de Maya
2. Añadir `import MayaBridge_server; MayaBridge_server.start()` a `userSetup.py`
3. Configurar el skill de Claude para conectar al puerto TCP local
4. Precaución: solo usar en local (no exponer el TCP a red externa — sin autenticación)

Uso inmediato: debugging interactivo de autorig_tools builds con asistencia de Claude Code.

## Fuente
- GitHub: https://github.com/Asukacodes/MayaBridge
- Mirror: https://ithub.global.ssl.fastly.net/Asukacodes/MayaBridge
- Related: dcc-mcp-maya on PyPI: https://pypi.org/project/dcc-mcp-maya/
- Related: MayaMCP troubleshooting: https://glama.ai/mcp/servers/@Jeffreytsai1004/maya-mcp/blob/fbefb311b0891fda32b603b12892e0b58fa67649/docs/TROUBLESHOOTING.md
