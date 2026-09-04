# UI (menu AutoRig Tools, shelf, ventanas PySide)

Parent: `maya_tools/como_funciona.md`.
Reglas: `.claude/rules/idioma-y-ascii.md` (los simbolos de las UIs PySide ya existentes se toleran).
Tools que abre: `maya_tools/scripts/tools/como_funciona.md`. Asset Manager: `maya_tools/scripts/utils/character_manager.py`.

## 1. Que es y para que existe

El menu "AutoRig Tools" de la barra de Maya (`auto_rig_UI.create_custom_menu`),
el shelf "AutoRig" y las ventanas PySide de las herramientas. Cada item del
menu es una funcion corta de `auto_rig_UI.py` que hace `reload` del modulo y
delega. `userSetup` lo crea al arrancar; "Reload UI" lo regenera.

## 2. Como esta montado

### 2.1 Menu (orden real)

| Seccion | Item | Funcion en `auto_rig_UI` | Delega en |
|---|---|---|---|
| - | Reload UI | `rebuild_ui` | `create_custom_menu` |
| PIPELINE | Character Manager | `show_character_manager_ui` | `utils.character_manager.AssetManagerUI` |
| MODELING | Model Checker | `open_model_checker` | `tools.model_checker.show` |
| RIGGING | CREATE RIG | `rig(leg_impl="reference")` | escena nueva, `data_manager.new_build`, `create_rig.AutoRig().build(leg_impl, leg_solver)` |
| RIGGING | CREATE RIG SELF | `rig(leg_impl="self")` | idem (patas `leg_module_self`) |
| RIGGING | CREATE RIG SELF MATH | `rig(leg_impl="self", leg_solver="nodes")` | idem forzando el solver de nodos |
| RIGGING | BUILD LEG | `leg_rig` | `leg_module_self.LegModule().make()` SIN argumentos (roto: `make` exige `side`; el comentario del codigo lo admite) |
| RIGGING > Guides Manager | Create New Guides | `create_new_guides` | `guides_manager.create_new_guides` |
| | Import Guides | `import_guides` | `guides_manager.load_guides_info()` |
| | Export Guides | `export_guides` | `guides_manager.get_guides_info()` (escribe `.guides` v001 y `.build`) |
| | Mirror Guides | `mirror_guides` | `guides_manager.mirror_guides` |
| | Test Rig by Guide | `test_rig_by_guide` | `rig_manager.test_rig_by_guide` |
| RIGGING > Controllers Manager | Export All Controllers | `export_all_controllers` | `curve_tool.get_all_ctl_curves_data()` (v001) |
| | Mirror Controllers | `mirror_controllers` | `curve_tool.mirror_curves` |
| ANIMATION | Test Rig | `open_pose_tester` | `ui.pose_tester_UI.show` |
| CORRECTIVES > Corrective Blendshapes | Export / Import | `export_corrective_blendshapes` / `import_corrective_blendshapes` | `tools.corrective_blendshape_manager` |
| CORRECTIVES | Corrective Skin - Setup / Localize | `setup_corrective_skin` | `utils.correctives.corrective_skin_setup` (malla + joints seleccionados) |
| SKINNING > Skin Cluster Manager | Export / Import Skin Cluster | `export_skin_cluster` / `import_skin_cluster` | `tools.skin_manager_api.SkinManager` |
| | Proxy Skinning | `proxy_skinning` | `tools.proxy_skinning.proxy_skin` (seleccion: proxy primero, alta despues) |
| SKINNING | Corrective Curve (Pose -> Curve -> Joints) | `open_corrective_curve_ui` | `ui.corrective_curve_UI.show` |
| SKINNING | Auto Skin Transfer (Clothes) | `open_skin_transfer_ui` | `ui.skin_transfer_UI.show` (backend dado por roto) |
| SIMULATION | AdonisFX Copy Weights | `open_adonis_copy_weights` | `adonis.copyWeightsAdonis.show` |

Definidas en `auto_rig_UI.py` pero SIN item de menu: `create_new_asset`,
`open_library`, `replace_shapes`, `tag_scene_curves`,
`mirror_corrective_blendshapes`, `mirror_corrective_blendshape_targets`,
`copy_skin_cluster`, `export_source_skin_data`, `show_curve_library`,
`show_rig_tools`.

### 2.2 Shelf (`auto_rig_shelf.py`)

`SHELF_BUTTONS` es una lista de tuplas (etiqueta, icono, anotacion, comando).
Hoy un boton: AssetMgr (`myLogo.png`) -> Character Manager. Anadir un boton =
una fila mas; los iconos van en `maya_tools/icons`. No se crea en batch.

### 2.3 Ventanas

| Fichero | Que es | Llama a |
|---|---|---|
| `character_manager.py` (en `utils/`) | Asset Manager: lista de assets con miniatura, pestanas de versiones (guides, curves, models, skin_clusters) con SAVE VERSION / IMPORT / Overwrite, Quick Tools (reset y mirror de controles, toggles de visibilidad, history, freeze, pivot, unused nodes, zero joint orients, quick bind, copy skin, unbind, proxy locators), LOAD SETTINGS (fija el asset activo) y BUILD RIG; menubar File / Tools (ngSkinTools, Rabbit Skinning Tools, Kangaroo, mGear, AdonisFx) / Help | `guides_manager`, `curve_tool`, `skin_manager_api`, `create_rig`, `proxy_locator` |
| `rig_progress.py` | dialogo de progreso del build (`RigProgressDialog`, icono mGear si `mGear_integration`), se cierra solo | lo abre `create_rig.build` |
| `deboor_tools_UI.py` | pestanas De Boor Ribbon, Split Blendshape, Skin - Curve, Skin - Surface | `utils.ribbon`, `utils.blendshape`, `utils.skincluster_curve`, `utils.skincluster_surface` (sin item de menu: `deboor_tools_UI.show()`) |
| `skin_transfer_UI.py` | UI del auto skin transfer (mapa de joints, secciones plegables) | `tools.auto_skin_transfer` |
| `corrective_curve_UI.py` | flujo curva base -> duplicar target -> esculpir en pose -> joints | `utils.correctives.corrective_curve` |
| `pose_tester_UI.py` | una fila por zona con desplegable de poses ROM | `tools.pose_tester` |

Todas las UIs llevan fallback `PySide6` / `PySide2` (+ `shiboken6`/`shiboken2`).

## 3. Datos que lee y escribe

Ninguno propio: la UI solo llama a utils y tools, que escriben en
`maya_tools/assets/<p>/`. `character_manager` guarda el asset activo en la
optionVar `currentAssetRigName` y la restaura al abrir (`_restore_session`).

## 4. Estado hoy

- `BUILD LEG` no funciona tal como esta (llama `make()` sin `side`).
- `deboor_tools_UI` no tiene entrada de menu; se abre por Script Editor.
- Imports cortos (`from utils import ...`) en `auto_rig_UI.py`: funcionan por
  el `.mod` pero crean modulos duplicados frente a la forma
  `maya_tools.scripts...` (ver `maya_tools/como_funciona.md`).
- Textos del menu en ingles y mensajes `inViewMessage` en castellano: se deja
  como esta (regla de idioma).

## 5. Como probarlo

Reload UI y recorrer cada item con una escena de prueba; cada item debe
acabar en un `inViewMessage` o en una ventana, nunca en un traceback mudo.

## 6. Do not

- No anadir logica en `auto_rig_UI.py`: solo `reload` + delegacion + mensaje.
- No crear un item de menu que apunte a una funcion sin tool detras (el caso
  BUILD LEG).
- No duplicar el fallback PySide en cada ventana con variantes distintas:
  copiar el bloque existente tal cual.
