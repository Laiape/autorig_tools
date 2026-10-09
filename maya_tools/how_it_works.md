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

## 4. Edward photo picker

The separate DWPicker photo design and individual SVG/PNG controller assets
live in `maya_tools/assets/Edward/picker/reference_workflow/`. Load instructions:
`maya_tools/assets/Edward/picker/reference_workflow/README.md`.
The loader resolves background paths, checks scene targets/namespace and
embeds the document in DWPicker. The original picker is preserved.
Facial secondary controls use light blue on L and pink on R; the same
palette is applied to their independent SVG/PNG assets and DWPicker shapes.
The supplied `edward_reference_sheet.png` provides the frontal body A-pose.
The supplied `edward_face_front.png` is preserved as the original frontal face.
Its restored 1380 x 1140 version is `edward_face_front_hd.png`.
Native viewports isolate those views, with controls aligned to each source.
Offline builder: `maya_tools/scripts/tools/build_edward_reference_picker.py`.
Native SVG renderer: `maya_tools/scripts/tools/render_edward_reference_picker.cjs`.

The native Qt picker supports Maya 2024+ through PySide2/PySide6. Entry:
`AutoRig Tools > ANIMATION > Edward Picker` or shelf `EdwardPicker`.
It uses the same DWPicker data for controller geometry and target names,
with namespaces, selection synchronization, layers, zoom and pan.
The standalone `install_edward_picker.py` installs the runtime in shared
Maya user scripts and creates a persistent shelf button. Install/use details:
`maya_tools/assets/Edward/picker/reference_workflow/README_MAYA.md`.
Qt interaction tests with a simulated Maya API are in
`maya_tools/scripts/tools/tests/test_edward_picker.py`; live Maya and Qt5
runtime verification remain outstanding.

The current Edward curve export has 310 picker targets: 127 body and 183
face. Secondary digit points cover the additional finger joints; the removed
head squash control is excluded. Export coverage is checked by the Qt tests.
