# Autorig Tools - Maya UI criteria (source of truth)

Parent: `maya_tools/how_it_works.md`.
Apply these rules on every Maya UI change. Do not invent a parallel chrome.

Operating model: `modulos/vision/how_it_works.md` (required reading).
When a file type is pointed at: `modulos/vision/mapa_datos.md`.

Code and this file: ASCII (no accents, no emoji).

---

## 1. Product roles

- The user is a rigger inside Maya.
- Home is the Maya scene plus the AutoRig Tools menu. There is no web hub.
- New menu labels and window titles: English.

## 2. Navigation (fixed order)

Source: `maya_tools/scripts/ui/auto_rig_UI.py` `create_custom_menu`.
Do not reorder groups unless the user asks.

| Order | Group | Items |
|---|---|---|
| 1 | (top) | Reload UI |
| 2 | PIPELINE | Character Manager |
| 3 | MODELING | Model Checker |
| 4 | RIGGING | CREATE RIG, CREATE RIG SELF, CREATE RIG SELF MATH, BUILD LEG, Guides Manager, Controllers Manager |
| 5 | ANIMATION | Test Rig |
| 6 | CORRECTIVES | Corrective Blendshapes, Corrective Skin |
| 7 | SKINNING | Skin Cluster Manager, Corrective Curve, Auto Skin Transfer (Clothes) |
| 8 | SIMULATION | AdonisFX Copy Weights |

Guides Manager children: Create New Guides, Import Guides, Export Guides,
Mirror Guides, Test Rig by Guide.

Controllers Manager children: Export All Controllers, Mirror Controllers.

Skin Cluster Manager children: Export Skin Cluster, Import Skin Cluster,
Proxy Skinning.

Shelf `AutoRig` (`maya_tools/scripts/ui/auto_rig_shelf.py`): one button
AssetMgr that opens Character Manager. Add shelf buttons only in
`SHELF_BUTTONS`. Icons live in `maya_tools/icons`.

Menu id: `autorig_menu`. Label: `AutoRig Tools`. Parent: `MayaWindow`.

## 3. Chrome

- Character Manager is a Qt window (`maya_tools/scripts/utils/character_manager.py`).
  Palette tokens in that file (`C_BG0` .. `C_RED`). Reuse them on new Qt
  tools. Do not invent a second grey/blue set.
- Other tools: `skin_transfer_UI.py`, `pose_tester_UI.py`,
  `deboor_tools_UI.py`, `corrective_curve_UI.py`, `rig_progress.py`.
- PySide6 with PySide2 fallback, same as Character Manager.

## 4. Wrong

- A second top-level Maya menu for the same tools.
- Web tiles, breadcrumbs, or a cream app bar.
- A new window for a file type already on `modulos/vision/mapa_datos.md`.
- Replacing the menu with only the shelf, or the shelf with only the menu.
  Both stay: menu is full, shelf is the short cut (AssetMgr today).
