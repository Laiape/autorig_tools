# Where data is represented

Parent: `modulos/vision/how_it_works.md`.
UI: `maya_tools/criterios-ui.md`.

When someone says "this information is here" (a Maya scene, a guides
file, a skin dump, an Unreal note), **do not invent a new window**.
Read this map, pick the row that matches the meaning, and put it there.

---

## How to resolve a source

1. Name what the data *means*.
2. Find that meaning in the table below.
3. Represent it on that Maya menu item or Unreal path, for the rigger.
4. If it fits two rows, keep the split (Maya rig vs Unreal notes).
5. After wiring a new file type, add it to the Sources column in the same task.

---

## Audience

| Who | Sees |
|---|---|
| Maya rigger | AutoRig Tools menu, AutoRig shelf, current scene |
| Unreal rigger | `ue_tools/docs/` notes. No editor UI in this repo yet |

---

## Map

| If the data is... | Show it on | Who uses it | Sources |
|---|---|---|---|
| Character Maya scene (`.ma` / `.mb`) | Character Manager | Maya rigger | Character Manager `ALLOWED_ENDINGS`; `maya_tools/scripts/utils/character_manager.py` |
| Guide locators / fit data (`.guides`) | Guides Manager (create, import, export, mirror, test) | Maya rigger | `maya_tools/scripts/utils/guides_manager.py` |
| Controller curve shapes (`.curves`) | Controllers Manager (export, mirror) | Maya rigger | `maya_tools/scripts/utils/curve_tool.py` |
| Skin cluster dump (`.skc`) | Skin Cluster Manager (export / import) | Maya rigger | `maya_tools/scripts/tools/skin_manager_api.py` |
| JSON / other sidecar listed by the manager | Character Manager | Maya rigger | `ALLOWED_ENDINGS` includes `.json` |
| Autorig build cache | Internal `maya_tools/cache/biped.cache` during build. Not a menu. | Build (`create_rig.AutoRig`) | `maya_tools/scripts/utils/data_manager.py` |
| Corrective blendshape export/import | Correctives submenu | Maya rigger | `maya_tools/scripts/tools/corrective_blendshape_manager.py` |
| Cloth / auto skin transfer | Auto Skin Transfer (Clothes) window | Maya rigger | `maya_tools/scripts/ui/skin_transfer_UI.py` |
| Pose test of the built rig | Test Rig (pose tester) | Maya rigger | `maya_tools/scripts/ui/pose_tester_UI.py` |
| Model sanity before rig | Model Checker | Maya rigger | `maya_tools/scripts/tools/model_checker.py` |
| Unreal production rigging notes | `ue_tools/docs/` | Unreal rigger | `ue_tools/docs/unreal_fest_chicago_2026_rigging_produccion.md` |

Wrong: a new dump window because the map had no row. Add a row with the user, or leave TODO.
Wrong: putting Unreal notes behind a Maya menu item.
Wrong: a second Character Manager.
