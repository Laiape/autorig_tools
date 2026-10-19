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

Source: `maya_tools/scripts/framework/registry.py` `GROUPS`, `SECTIONS` and
tool metadata. The menu and dockable catalogue render this same hierarchy.
Do not reorder groups unless the user asks.

| Order | Group | Items |
|---|---|---|
| 1 | (top) | Reload UI, Tool Framework |
| 2 | PIPELINE | Character Manager, Validated Rig Packages |
| 3 | MODELING | Model Checker |
| 4 | RIGGING | Guides, Build, Controllers, Utilities |
| 5 | ANIMATION | Test Rig, Character Picker |
| 6 | DEFORMERS | Skinning, Blendshapes, Correctives, Wrinkles, Wrap, Bake |
| 7 | SIMULATION | AdonisFX Copy Weights |

ANIMATION also exposes Release Selected Flower Petals and Attach Selected
Flower Petals. These registry actions match selected petal roots to World/Head
space and key the switch; they share the existing menu and Tool Framework.

Rigging > Guides: Create New Guides, Import Guides, Export Guides, Mirror Guides.
Rigging > Build: CREATE RIG, CREATE RIG SELF, CREATE RIG SELF MATH,
BUILD LEG (disabled legacy entry), Test Rig by Guide, De Boor Ribbon.
Rigging > Controllers: Export All Controllers, Mirror Controllers,
Replace Controller Shapes, Center Controller Shapes to Pivot, Controller Shape Library.
Rigging > Utilities: Rig Utilities, Restore PV / Eye Lines. The restore action
repairs misplaced display indicators in loaded rigs using the shared organizer.

Deformers > Skinning: Skinning Manager, skin import/export/copy, Proxy Skinning,
Export Source Skin Data, Auto Skin Transfer (Clothes), Skin Along Curve/Surface.

Deformers > Blendshapes: Pose Blendshapes, import/export/mirror of corrective
blendshapes and targets, Split Blendshape. Pose Blendshapes uses native Maya Qt
style (`ui_utils.apply_maya_style`), with mesh blendshape and target lists.
Deformers > Correctives: Joint Corrective Targets, Corrective Skin,
Corrective Curve. Deformers > Wrinkles: Wrinkle Regions / Presets, using native
Maya Qt style for vertex region fields, local controls and portable presets.

Deformers > Wrap: Proximity Wrap (Multiple Drivers).
Deformers > Bake: Bake Deformation to Skin. The bake uses Maya Qt style and exposes
fit range, held-out validation, accepted error, error colors and optional SKC.

Shelf `AutoRig` (`maya_tools/scripts/ui/auto_rig_shelf.py`): AssetMgr opens
Character Manager; CharacterPicker opens the guide-driven native body/face picker
for the selected character; Skinning opens Skinning Manager.
Portable installers add their character-specific button.
Add repository shelf buttons only in
`SHELF_BUTTONS`. Icons live in `maya_tools/icons`.

Tool Framework is the user-requested dockable catalogue inside Maya, opened
from the existing menu or the first shelf button. It preserves category order
and launches existing editors. Search, favorites and recent tools share the
same registry. Its native Qt shell uses `ui_utils.apply_maya_style`; source
artwork lives in `maya_tools/icons/red` and editor icons are tinted at runtime.
The shelf also
keeps Character Manager, Character Picker and Skinning Manager shortcuts.
The menu and shelf use these same red PNGs. Framework restoration uses Maya
`workspaceControl`, with a 300px minimum width and a default right dock.

The framework header contains work profiles and a Character context form
with explicit root, asset, mesh and skinCluster choices. Tools, Workflow and
Activity tabs share that context. Missing requirements explain why an action
is disabled. Workflow review marks are explicit, per-character notes; opening
an editor never marks quality validation as passed. Save layout and profile
switch/hide preserve view state, without changing the active character.

Menu id: `autorig_menu`. Label: `AutoRig Tools`. Parent: `MayaWindow`.

## 3. Chrome

- All repository editors inherit Maya's native palette, fonts and input controls.
  Shared styling lives in `maya_tools/scripts/utils/ui_utils.py`; explicit
  tool/action metadata and accent colors live in `utils/ui_theme.py`.
  Character Manager's old palette constants are not the shared theme.
- Main actions use a blue fill, save/apply actions green, preview/review actions
  amber and destructive actions muted red. Secondary actions remain native.
  Disabled controls retain disabled feedback; color does not replace a label.
- Headers reuse their existing title and gain a tool icon. Tabs and common
  secondary actions have meaningful icons from the existing artwork. Tint is
  adjusted for light/dark Maya palettes. Repeated styling must not add headers.
- Declare action roles with `ui_utils.action` or an explicit tool profile.
  Do not infer colored roles from generic verbs or recolor every button.
- `ui_utils.preserve_style` protects color swatches and LIVE feedback. Vendor
  editors remain style boundaries. No vendor installation files are modified.
- User exception: Skinning Manager and all editors embedded inside it retain
  their previous native appearance, without added tab icons, colored actions
  or header decoration. The standalone versions of those editors use the
  shared accents. `ui_theme.NATIVE_ONLY` enforces this through ancestry.
- Reload UI refreshes the theme in open editors without rebuilding their
  sessions, changing Maya selection or modifying scene data. Lazy-loaded
  panels and dynamically created version tabs use the same theme.
- Other tools: `skin_transfer_UI.py`, `pose_tester_UI.py`,
  `deboor_tools_UI.py`, `corrective_curve_UI.py`, `joint_correctives_UI.py`,
  `pose_blendshapes_UI.py`, `rig_progress.py`.
- Character picker: shared `maya_tools/scripts/tools/character_picker_runtime.py`,
  launched by `maya_tools/scripts/tools/character_picker.py`.
- Edward's photo picker remains available in its standalone/reference bundle.
- PySide6 with PySide2 fallback, same as Character Manager.

Skinning Manager is the requested dockable workspace next to the Outliner.
Its Skinning tab hosts the actual NG, Smooth, Transfer and Ramp native editors,
plus Utilities. NG exposes a SkinCluster selector above its native menus for
choosing among the loaded mesh's stacked deformers.
The native NG layer context menu exposes LIPS RIGGER, EYELID RIGGER and EYEBROW
RIGGER. These same actions are available on the native initialization page.
They use the selected loop and the active skin's joints without an extra dialog.
Inside NG, Layers / Paint keeps the native editor; Loop Rigger (Preview)
contains the requested lip/eye/brow complete-loop skinning prototype.
NURBS Skin follows Loop Rigger as the third NG editor tab. It loads its own
NURBS target, exposes NG layers/masks and a surface-aware brush, and releases
that brush on editor/page changes or hide. The independent package also attaches
NURBS Skin to standalone NG after Layers / Paint, without an AutoRig dependency
or edits to vendor files. See `docs/ng_nurbs_bridge.md`.
Its controls scroll within the existing dock and include a Nini review-region
selector for region/layer solo validation. Lips uses exactly one parent and
two children, Rotate above Non Rotate; joints are influences within those
layers. No extra standalone window or menu is added.
Corrective Blendshapes embeds the existing pose editor with a
compact layout and pinned sculpt actions. It inherits Maya's native palette,
and embedded vendor UIs retain their functional styles. Maya workspace controls
manage docking, floating and workspace restoration. Implementations:
`maya_tools/scripts/ui/skinning_manager_UI.py` and `skinning_tool_adapters.py`.

Test Rig embeds General rig tools with Rig roles, Validation profiles, Pose
library, Surface contact and Version migration tabs. The existing dialog uses
a scroll area to keep body ROM and build comparison accessible on smaller
screens. Implementation: `maya_tools/scripts/ui/rig_tools_panel.py` inside
`maya_tools/scripts/ui/pose_tester_UI.py`; no new menu or standalone chrome.

Model Checker keeps its existing MODELING entry and native Maya dialog. It uses
`ui_utils.apply_maya_style`, native status icons, grouped automatic results and
Visual review / Vertex comparison / Report tabs. Scope is pinned explicitly from
selection. Errors, incomplete reviews and stale scans are visible in the footer;
individual repairs use Maya Undo and refresh the scan.

## 4. Wrong

- A second top-level Maya menu for the same tools.
- Web tiles, breadcrumbs, or a cream app bar.
- A new window for a file type already on `modulos/vision/mapa_datos.md`.
- Replacing the menu with only the shelf, or the shelf with only the menu.
  Both stay: menu is full, shelf is the short cut (AssetMgr today).
