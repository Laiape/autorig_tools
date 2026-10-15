# Autorig Tools

Open **AutoRig Tools > Tool Framework** for the native dockable tool catalogue,
search, favorites and recently used tools. The first AutoRig shelf button opens
the same panel. The implementation roadmap is in
[Framework plan](maya_tools/framework_plan.md).

Pin a character with **Use selection**, then choose its mesh and skinCluster.
The panel includes **Tools**, **Workflow** and **Activity** tabs, persistent
work profiles and input checks before actions run. Workflow review marks are
your checklist; use the tools' actual reports to validate a rig.

Maya autorig and character tools, plus Unreal notes. Apache-2.0. See `LICENSE`.

This is not a web app. Riggers work inside Autodesk Maya.

Graph of how the repo is organised: `how_it_works.md`.

---

## Install on another PC

The full setup guide is [SETUP_OTHER_PC.md](SETUP_OTHER_PC.md).

```powershell
git clone https://github.com/Laiape/autorig_tools.git
cd autorig_tools
git lfs install
git lfs pull
python scripts/install_maya_module.py
& "C:/Program Files/Autodesk/Maya2026/bin/mayapy.exe" -m pip install --user -r requirements-maya.txt
```

Install Git LFS before cloning when possible. The module installer uses this
checkout's actual location, so the clone can live outside `C:/GIT`. Restart Maya
to load the **AutoRig Tools** menu and **AutoRig** shelf.

Character assets, guides, curves, build settings, skins and picker installers
are included. Large Maya scenes and skin files use Git LFS. The current Edward
working rig is `maya_tools/assets/Edward/scenes/Edward_working_v002.mb`.
Open it through `scripts/open_edward.py` inside Maya to resolve this clone's
textures automatically (see the setup guide).

Edward v002 uses regional wrinkles in the original head output. Switch
Animation / Review / Export in **Test Rig**, after loading a character mesh.
The implementation and measured limits are in
[Rig performance results](maya_tools/docs/rig_performance_results.md).
Nini's dress uses 12 chains of 6 joints in
`maya_tools/assets/Nini/scenes/Nini_dress_chains_v004.ma`; its settings control is
`C_dressSettings_CTL`. The independent skirt test is
`maya_tools/assets/KeepOutSkirt/scenes/KeepOutSkirt_autorig_smooth_v001.ma`.

Maya and third-party Maya plug-ins are installed separately; the guide identifies
which ones the tools and the saved scene need. Experiments, duplicate rig
packages, generated caches and validation output stay outside Git.

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
