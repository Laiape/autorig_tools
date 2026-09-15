# Maya tools

Parent: `how_it_works.md`.
Vision (required): `modulos/vision/how_it_works.md`.
UI: `maya_tools/criterios-ui.md`.

## 1. Overview

Maya module named `self_module`. Load via `maya_tools/self_module.mod`.
That file lists known clone roots (`C:\proyectos_laia\autorig_tools`,
`C:\GIT\autorig_tools`). Maya skips a missing path and uses the first
folder that exists. Add a new clone as another `+` block; do not
overwrite the list. Maya finds the `.mod` when it is in
`Documents/maya/modules/` (copy of the same file) or when
`MAYA_MODULE_PATH` includes `maya_tools`. Details: `README.md`.
Live `.mod` is the source of truth.

On start (`maya_tools/scripts/userSetup.py`, deferred):

- AutoRig Tools menu (`maya_tools/scripts/ui/auto_rig_UI.py`)
- AutoRig shelf (`maya_tools/scripts/ui/auto_rig_shelf.py`)
- VS Code command ports 4434 / 7001 / 7002
- numpy install via mayapy if missing
- `proxy_locator` plugin
- MCP TCP listener on localhost port 9877 (`maya_tools/scripts/tools/mcp_listener.py`)

Autorig build: `maya_tools/scripts/utils/create_rig.py` class `AutoRig`.
Biped modules under `maya_tools/scripts/biped/autorig/`.
Quadruped modules under `maya_tools/scripts/quadruped/autorig/`.
Leg impl flags on CREATE RIG: `reference` | `self`; optional `leg_solver="nodes"`.

Language of this file: English ASCII. Some existing Maya `inViewMessage`
strings are Spanish; do not bulk-rewrite them unless asked.

## 2. Layout

```
maya_tools/
|-- self_module.mod
|-- scripts/
|   |-- userSetup.py
|   |-- ui/              menu, shelf, Qt windows
|   |-- utils/           autorig core, guides, cache, curves
|   |-- tools/           skin, export, MCP, tests
|   |-- biped/autorig/   biped modules
|   |-- quadruped/autorig/
|-- plugin/              C++ collision (pluginMain.cpp)
|-- icons/
|-- assets/
|-- cache/               biped.cache during build
```

## 3. Menu vs tools

UI chrome and item order: `maya_tools/criterios-ui.md`.
Where files appear: `modulos/vision/mapa_datos.md`.

Do not add a web frontend. Do not invent a second autorig entry point
outside the menu / shelf / `userSetup.py`.

Docs guide; live scripts are the source of truth.
