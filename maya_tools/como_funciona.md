# maya_tools (arranque, modulo de Maya, cache, plugin)

Parent: `como_funciona.md` (raiz).
Hijos: `maya_tools/scripts/utils/como_funciona.md`, `maya_tools/scripts/biped/autorig/como_funciona.md`,
`maya_tools/scripts/quadruped/autorig/como_funciona.md`, `maya_tools/scripts/tools/como_funciona.md`,
`maya_tools/scripts/ui/como_funciona.md`, `maya_tools/scripts/adonis/como_funciona.md`,
`maya_tools/assets/como_funciona.md`. Naming: `maya_tools/scripts/criterios_naming.md`.
Donde vive cada dato: `maya_tools/mapa_datos.md`.

## 1. Que es y para que existe

La raiz que Maya carga como modulo. Contiene el arranque (`userSetup.py`), el
codigo (`scripts/`), los datos por personaje (`assets/`), el cache del build
(`cache/`), los iconos del shelf y un plugin C++ sin uso.

## 2. Como esta montado

### 2.1 `self_module.mod` (modulo de Maya)

```
+ self_module 1.0 C:\GIT\autorig_tools\maya_tools
PYTHONPATH += C:\GIT\autorig_tools
```

- Ruta ABSOLUTA de Windows: al clonar en otro sitio hay que editarla y
  copiar o enlazar el `.mod` en la carpeta de modulos de Maya.
- Como modulo, Maya anade `maya_tools/scripts` al `sys.path` (por eso
  funcionan los imports cortos `from utils import x` de la UI) y
  `maya_tools/icons` al `XBMLANGPATH` (por eso el shelf pide solo el nombre
  del icono). El `PYTHONPATH +=` anade la raiz del repo y permite
  `from maya_tools.scripts.utils import x`, que es la forma de la regla.
- Consecuencia: el mismo fichero puede importarse por dos nombres
  (`utils.rig_manager` y `maya_tools.scripts.utils.rig_manager`) y ser dos
  modulos distintos para `reload`. Hoy `ui/auto_rig_UI.py` y
  `userSetup.py` usan la forma corta; el resto la larga.

### 2.2 `scripts/userSetup.py` (arranque)

`maya.utils.executeDeferred(init_auto_rig_UI)`, que ejecuta en este orden:

1. `ui.auto_rig_UI.create_custom_menu()` -> menu "AutoRig Tools" y
   `ui.auto_rig_shelf.create_shelf()` -> shelf "AutoRig" (solo AssetMgr).
2. `vs_code_ports()`: `commandPort` en `:4434`, `localhost:7001` (mel) y
   `:7002` (python) para VS Code.
3. `install_numpy()`: si `import numpy` falla, lanza `mayapy -m pip install
   --user numpy` y pide reiniciar. Solo Windows (`mayapy.exe`).
4. `init_proxy_locator()`: busca `tools/proxy_locator.py` en `sys.path` y lo
   carga como plugin.
5. `init_mcp_listener()`: `tools.mcp_listener.start()` en `localhost:9877`.

Cada paso captura su excepcion y avisa con `cmds.warning`; el arranque nunca
se corta.

### 2.3 Carpetas

| Carpeta | Contenido | Quien la usa |
|---|---|---|
| `scripts/utils/` | motor del build | todo |
| `scripts/biped/autorig/`, `scripts/quadruped/autorig/` | modulos de rig | `rig_manager.build_rig` |
| `scripts/tools/` | herramientas, tests, analisis | menu, Asset Manager, build (skin y CBS) |
| `scripts/ui/` | menu, shelf, UIs PySide | `userSetup` |
| `scripts/adonis/` | `copyWeightsAdonis` | menu SIMULATION |
| `assets/` | datos por personaje | Asset Manager, build |
| `cache/` | `biped.cache` y `quadruped.cache` (JSON): lo que cada modulo publica con `data_manager.append_data` en el ultimo build | modulos y space switches del build en curso |
| `icons/` | `myLogo.png` (shelf), `mGear.jpg` (dialogo de progreso en modo mGear) | shelf, `rig_progress` |
| `plugin/` | `collisionCommands.h/.cpp`, `pluginMain.cpp`: dos `MPxCommand` (`CreateCollisionCommand`, `DefineColliderCommand`) sin cuerpo | nadie: no hay `.mll` ni `loadPlugin`; resto del intento de colliders C++ |

`cache/`: `DataExportBiped` escribe `biped.cache`; `DataExportQuadruped`
apunta a `quadruped.cache` pero el build usa siempre `DataExportBiped`
(tambien en cuadrupedos). Se regenera con `new_build()` al empezar cada build;
no es configuracion ni se edita a mano.

## 3. Datos que lee y escribe

- Lee: `self_module.mod` (Maya), `assets/<p>/*` (build), `optionVar
  currentAssetRigName` (personaje activo).
- Escribe: `cache/*.cache`, `assets/<p>/*` al exportar, y en el arranque
  abre puertos TCP locales (4434, 7001, 7002, 9877).

## 4. Estado hoy

- `plugin/` es codigo muerto documentado: no se compila ni se carga.
- `install_numpy` depende de `mayapy.exe` y de permisos de `pip --user`.
- `cache/*.cache` esta commiteado aunque es estado del ultimo build (decision
  pendiente en `docs/plan_workflow.md`, Fase 4).

## 5. Como probarlo

Arrancar Maya 2025+ con el `.mod` instalado: debe aparecer el menu AutoRig
Tools, el shelf AutoRig, y en el Script Editor ningun warning de
`No se ha podido cargar`. `cmds.pluginInfo("proxy_locator", q=True, loaded=True)`
debe ser True. `cmds.commandPort(":7002", q=True)` debe ser True.

## 6. Do not

- No poner rutas absolutas nuevas en codigo: el `.mod` es la unica que existe
  y esta documentada aqui.
- No editar `cache/*.cache` a mano ni usarlo como fichero de configuracion.
- No mezclar los dos estilos de import dentro de un mismo fichero.
- No anadir un paso al arranque sin `try/except` y sin fila en 2.2.
