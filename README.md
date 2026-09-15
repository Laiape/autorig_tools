# Autorig Tools

Maya autorig and character tools, plus Unreal notes. Apache-2.0. See `LICENSE`.

This is not a web app. Riggers work inside Autodesk Maya.

Graph of how the repo is organised: `how_it_works.md`.

---

## Load in Maya

The module file is `maya_tools/self_module.mod`. It lists known clone
roots. Maya skips a `+` block whose folder is missing and uses the first
path that exists:

- `C:\proyectos_laia\autorig_tools`
- `C:\GIT\autorig_tools`

Do not replace a block when you clone somewhere else: copy a new `+`
block with that root and `PYTHONPATH`. Icons stay `maya_tools/icons`.

Maya only reads a `.mod` if it sits on `MAYA_MODULE_PATH` or in the user modules folder.

**Option A (no env var).** Put `maya_tools/self_module.mod` in:

`Documents/maya/modules/self_module.mod`

On this machine that copy is already there. Restart Maya.

**Option B.** Set user environment variable `MAYA_MODULE_PATH` to the
`maya_tools` folder of the clone you want (the `.mod` still picks the
first existing root from its list).

Restart Maya.

On a successful load you get:

- Menu **AutoRig Tools** (Maya menu bar)
- Shelf **AutoRig** (AssetMgr opens Character Manager)

If the menu is missing, the `.mod` path does not match this clone, or Maya did not see the module folder. Script Editor will show `userSetup.py` warnings.

---

## Layout

| Folder | What it is |
|---|---|
| `maya_tools/` | Maya module, scripts, C++ collision plugin, icons |
| `ue_tools/` | Unreal production notes; `scripts/` is empty |
| `modulos/` | Vision, data map, parked list (for Cursor) |
| `.cursor/rules/` | Agent rules |

Maya UI order and chrome: `maya_tools/criterios-ui.md`.
Where scene / guides / skin files show up: `modulos/vision/mapa_datos.md`.

---

## Unreal

No Unreal plugin in this repo yet. Notes live in `ue_tools/docs/`.
