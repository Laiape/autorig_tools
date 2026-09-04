# utils (motor del build)

Parent: `maya_tools/como_funciona.md`.
Reglas: `.claude/rules/convenciones-rig.md`, `.claude/rules/datos-y-versionado.md`, `.claude/rules/deformacion-y-skin.md`.
Modulos que lo usan: `maya_tools/scripts/biped/autorig/como_funciona.md`, `maya_tools/scripts/quadruped/autorig/como_funciona.md`.
Orden del build y por que, checklist de QA y poses: `maya_tools/scripts/utils/criterios_build.md`.
API detallada en skills: `.claude/skills/corrective-joints/references/repo-y-qa.md` (`correctives.py`),
`.claude/skills/custom-deformers/references/repo-deformers.md` (`ribbon.py`, `de_boor_core.py`, `skincluster_*`).

## 1. Que es y para que existe

El motor: orquestacion del build, assets y versiones, guias, cache entre
modulos, matrices, ribbons de Boor, correctivas, controles, picker y el Asset
Manager. Los modulos de rig no leen ficheros ni conocen rutas: pasan por aqui.

## 2. Como esta montado

### 2.1 Fichero -> responsabilidad

| Fichero | Lineas | Que hace | Quien lo usa |
|---|---|---|---|
| `create_rig.py` | 563 | `AutoRig.build()`: la secuencia completa del build (2.2) | menu CREATE RIG, Asset Manager BUILD RIG |
| `rig_manager.py` | 1287 | assets y versiones, dispatch de modulos (`build_rig`), rig settings (`.build`), `character_extras`, space switches, esqueleto `_ENV` | `create_rig`, `guides_manager`, UI |
| `guides_manager.py` | 897 | export e import del `.guides`, cache por personaje, `get_guides`, mirror y orientacion de guias | modulos, UI, Asset Manager |
| `data_manager.py` | 98 | cache JSON entre modulos (`DataExportBiped`) | todos los modulos |
| `basic_structure.py` | 494 | grupos base, controles globales, organizacion de la geo, display layers | `create_rig` |
| `matrix_manager.py` | 668 | space switches, twist, bend factor, pole vector, mirror, offsets | modulos |
| `ribbon.py`, `de_boor_core.py` | 573, 91 | ribbons de Boor por matrices (`de_boor_ribbon`) y base B-spline | arm, leg, spine y neck quad, eyebrow, tail |
| `correctives.py` | 713 | primitivas de corrective joints, drivers de pose, skin apilado localizado | arm, leg, facial_correctives, `create_rig`, menu |
| `curve_tool.py` | 676 | `create_controller`, export e import de shapes (`.curves`), mirror, tags | todos los modulos, UI, Asset Manager |
| `picker.py` | 544 | genera el JSON de DWPicker (paneles Body y Face) y lo carga | `create_rig` (ultimo paso) |
| `character_manager.py` | 960 | Asset Manager (PySide); detalle en `maya_tools/scripts/ui/como_funciona.md` | menu PIPELINE, shelf |
| `custom_ik_solver.py` | 560 | `triangle_solver`, `single_chain_solver`, `stretch`, `soft_ik` por nodos | solo `arm_module_custom` y `leg_module_custom` (legacy) |
| `surface_pin.py` | 107 | `loft_from_chains`, `project_to_surface`, `pin_to_surface` (uvPin) | `wing_module` |
| `skincluster_curve.py`, `skincluster_surface.py` | 90, 122 | reparte pesos de un skinCluster por De Boor a lo largo de una curva o superficie | `deboor_tools_UI` |
| `blendshape.py` | 84 | corta un target de blendShape en N por De Boor a lo largo de una curva | `deboor_tools_UI` |
| `ui_utils.py` | 31 | `apply_maya_style(widget)` | todas las UIs |

### 2.2 `create_rig.AutoRig.build(leg_impl="self", leg_solver=None)` (secuencia exacta)

1. `rig_progress.RigProgressDialog` (icono mGear si `mGear_integration`).
2. `_begin_fast_session`: evaluationManager off, cycleCheck off, undo sin
   flush, refresh suspendido. Se restaura en `_end_fast_session` con un
   unico refresh.
3. `data_manager.DataExportBiped().new_build()` y `basic_structure()` (2.5).
4. `make_rig` -> `rig_manager.build_rig(char, on_step, leg_impl, leg_solver)`:
   dispatch por guias y `Rig_Type`; al final space switches,
   `skeleton_hierarchy()` y `apply_character_extras()`.
5. `label_joints` (side y type desde el prefijo `L_`/`R_`/`C_`),
   `hide_connections`, `inherit_transforms`; fin de la fast session.
6. `import_weights` -> `SkinManager().import_skins()`. Sin `.skc` da error
   y las mallas quedan sin piel.
7. `localize_correctives`: `correctives.localize_corrective_skin` en todo
   skinCluster con `corrective` en el nombre. Pose neutra: no moverlo.
8. `import_corrective_blendshapes` -> `CorrectiveBlendshapeManager().import_from()`.
9. `hide_all_utility_nodes`: `isHistoricallyInteresting = 0` a todo salvo
   `KEEP_TYPES` (transforms, joints, shapes, luces, deformers, ik, follicles,
   constraints, sets, layers, shading, animCurves, nodos de escena).
10. `picker_generator.generate_and_load()`; si falla, warning y sigue.

Comentados en el codigo: `apply_delta_mush` (patron listo, `_DMH`, escala
por `C_deltaMushScale_DCM`), `_auto_transfer_from_source` (transfer desde
`source` via `mesh_data_exporter` + `auto_skin_transfer`), `proxy_locator`.
`delete_unused_nodes` existe y no se llama desde `build`.

### 2.3 `rig_manager.py`

- Assets: `asset_path(character_name, path)`, `create_assets_folders`,
  `create_new_asset`, `get_character_name_from_build()` (optionVar
  `currentAssetRigName`), `get_character_name_from_scene(avoid)`,
  `prepare_rig_scene`, `open_model_scene`, `import_meshes_for_guides`,
  `create_new_scene`, `get_main_assembly_nodes`.
- Versiones: `get_latest_version(folder)` devuelve el fichero con mtime mas
  reciente, sea cual sea su extension. `get_next_version_name` esta ROTA
  (suma str + int y hace `.split` sobre un `Path`) y no la usa nadie.
- Settings: `create_rig_settings(guides_transform, load=False)` crea en
  `C_guides_GRP` los atributos del `.build` (enums y enteros 1-20 con
  separadores `<PREFIJO>_SEP`; los enums se refrescan si hay presets nuevos);
  `load_rig_settings` los lee; `get_rig_data` los vuelca a `<p>_v001.build`
  (sobreescribe); `build_rig_from_data` lee el `.build` mas reciente.
  `LEG_SOLVER_OPTIONS` y `resolve_leg_solvers(rig_settings, override)`.
- Build: `build_rig` (tablas de dispatch en las hojas de biped y quadruped),
  `apply_character_extras(rig_settings)`, `biped_space_switches`,
  `quadruped_space_switches`, `test_rig_by_guide` (menu Guides Manager).
- Export: `skeleton_hierarchy()` crea `skeletonHierarchy_GRP` bajo `rig_GRP`
  con raiz `C_freeze_ENV`, duplica cada joint de skin como `_ENV` quitando
  `Skinning` (`L_wristSkinning_JNT` -> `L_wrist_ENV`), encadena por modulo
  (`parented_chain`) y parentea la raiz de cada modulo: spine -> freeze,
  faciales -> `*head_ENV`, arm -> clavicle, fingers -> wrist, resto ->
  ultimo joint del modulo anterior. Los joints con `corrective` o `ring` en
  el nombre cuelgan del `_ENV` de su joint padre. `corrective_joints(joint,
  shape)` no lo usa nadie.
- Rarezas: el fichero se importa a si mismo y hace `reload(rig_manager)`,
  `reload(om)`, `reload(glob)`, `reload(pathlib)`; importa `auto_rig_UI`
  (dependencia circular utils <-> ui).

### 2.4 `guides_manager.py`

- Formato `.guides`: JSON `{personaje: {nombre_guia: {...}}}` con `isJoint`,
  `joint_matrix`, `parent`, `children`, `locator_position`, `curve_data`
  (`cvs`, `degree`, `form`, `knots`, `closed`) y `surface_data`. Exporta los
  joints y locators bajo `C_guides_GRP` y las curvas `*_CRV` y NURBS
  `*_NURB` que no pertenezcan al rig.
- `get_guides_info(path=None)`: exporta (sin ruta, `_v001`) y llama a
  `get_rig_data`, que escribe tambien el `.build`.
- `load_guides_info(filePath=None, new_scene=True, load_settings=False)`:
  escena nueva, recrea las guias y `create_rig_settings(load=load_settings)`.
- `get_guides(guide_export, parent=None)`: recrea en escena esa guia con sus
  descendientes desde el `.guides` cacheado del personaje activo y devuelve
  la lista de nodos. Cache `_GUIDES_CACHE` por personaje que sobrevive a
  `reload`; `clear_guides_cache()`.
- `mirror_guides` / `mirror_specific_guide(guide, is_joint)` (L -> R),
  `orient_guides(guides, primaryInputAxis, secondaryInputAxis, ribbon=False)`,
  `create_new_guides`, `read_guides_info`, `delete_guides`.

### 2.5 `data_manager.py` y `basic_structure.py`

- `DataExportBiped`: `new_build()`, `clear_build()`, `append_data(modulo,
  dict)`, `get_data(modulo, clave)`. Ruta `maya_tools/cache/biped.cache`
  calculada con `split("\\scripts")` (solo Windows; pendiente `pathlib`).
  `DataExportQuadruped` existe y no la usa nadie: el build de cuadrupedo
  escribe en `biped.cache`.
- `create_basic_structure(character_name=None, in_scene=False)`: jerarquia
  `<personaje>` > `rig_GRP`, `controls_GRP`, `geo_GRP` (`PROXY`, `FINAL`,
  `LOCAL`), `deformers_GRP`; mueve el modelo bajo `FINAL`
  (`_parent_model_under_final`) y crea display layers, incluidas las de
  AdonisFX. Controles: `C_character_CTL` (GRP/ANM), `C_masterwalk_CTL`
  (GRP/ANM; `GLOBAL_SCALE_SEP`, `globalScale`), `C_settings_CTL` (`GEO_SEP`,
  `geometryType`, `geoDisplay`, `RIG_SEP`, `showModules`, `showSkeleton`,
  `showSkeletonHierarchy`, `PLAYBLAST_SEP`, `hideControllersOnPlayblast`),
  `C_geoVis_COND`. Con `mGear_integration` reutiliza `masterWalk`,
  `C_global_CTL` y `setup`. Publica `basic_structure/skel_GRP`,
  `modules_GRP`, `masterwalk_ctl`, `character_ctl`, `preferences_ctl`,
  `rig_GRP`, `character_name`.

### 2.6 `matrix_manager`, `ribbon`, `correctives`, `curve_tool`, `picker`

- `matrix_manager`: `space_switches(target, sources, default_rotate,
  default_translate, sources_names, pv, base_ctl)` hornea offsets y apaga la
  herencia (dos clases de target: opm estatico o conectado); `extract_twist`
  (swing-twist por quaternions; arm, leg, patas quad, correctives);
  `local_mmx(ctl, grp)` (matriz local rest-relativa; todos los faciales);
  `fk_blend` (arm, leg, quad reference); `fk_constraint` (fingers, digits);
  `mirror_controllers`; `get_offset_matrix`; `getClosestParamsToPositionSurface`,
  `getClosestParamToWorldMatrixCurve`. Solo legacy (`_custom`):
  `create_matrix_pole_vector`, `bend_factor`, `segment_volume`. Sin uso:
  `ik_constraint`, `skeleton_hierarchy` (duplicado del de `rig_manager`).
- `ribbon.de_boor_ribbon(cvs, ctls_grp, aim_axis, up_axis, num_joints,
  tangent_offset, d, kv_type, ...)` devuelve `(joints, temporales)`; joints
  `{name}0{i}_JNT` con padding fijo de un digito (con 10 o mas salen
  `010`, `011`). `_insert_tangent_cvs` anade CVs de tangente.
  `de_boor_core.knot_vector(kv_type, cvs, d)`, `de_boor(n, d, t, kv)`.
- `correctives`: API completa en la skill; el build y el menu usan
  `corrective_skin_setup(mesh, joints, skin_name="C_corrective_SKC")` y
  `localize_corrective_skin(skin_cluster)`.
- `curve_tool.create_controller(name, offset=["GRP"], parent=None,
  locked_attrs=[], match=None, matrix=None)` devuelve `(grupos, ctl)`; la
  shape sale del `.curves` del personaje (`build_curves_from_template`, el
  mas reciente por mtime; fallback circulo). `lock_attributes`,
  `get_all_ctl_curves_data(path)`, `load_all_ctl_curves_data(path)`,
  `mirror_curves`, `tag_scene_curves` (`isCurvesTag` para ignorar controles
  del modelo). `replace_shapes`, `text_curve`, `scale_*` sin entrada de menu.
- `picker`: `build_picker_data(char_name)`, `generate_and_load(load=True)`,
  `_load_via_dwpicker`. Layout fijo; escribe `assets/<p>/picker/<p>_picker.json`
  (fallback a la carpeta temporal). Necesita DWPicker instalado para cargar.

## 3. Datos que lee y escribe

- Lee: `.guides` (cacheado), `.build`, `.curves`, `.skc`, `.json` de
  correctivas, optionVar `currentAssetRigName`.
- Escribe: `maya_tools/cache/biped.cache`, `<p>_v001.build`, `.guides` y
  `.curves` (v001 o la ruta que pida el Asset Manager), `<p>_picker.json`.

## 4. Estado hoy

- Bugs conocidos: `data_manager` con `split("\\scripts")`;
  `get_next_version_name` rota; `rig_manager` se importa a si mismo y
  depende de `auto_rig_UI`; `blendshape.py` usa el import corto
  (`from utils import`).
- Sin uso: `DataExportQuadruped`, `rig_manager.corrective_joints`,
  `matrix_manager.ik_constraint`, `matrix_manager.skeleton_hierarchy`;
  `custom_ik_solver` solo desde modulos legacy.
- `bend_factor` y `segment_volume`, citados por las skills como patron, hoy
  solo los llaman los modulos `_custom`.

## 5. Como probarlo

- Build completo de un biped y de un quadruped: consola limpia,
  `skeletonHierarchy_GRP` con todos los `_ENV`, picker cargado.
- `mayapy maya_tools/scripts/tools/tests/test_wing_module.py` ejercita
  `data_manager` (parcheado), `curve_tool`, `surface_pin`.
- `mayapy maya_tools/scripts/tools/tests/test_build_horse_leg_self.py`
  ejercita `guides_manager.get_guides`, `build_rig_from_data`,
  `matrix_manager.space_switches`.

## 6. Do not

- No anadir pasos al build fuera de `AutoRig.build` ni cambiar el orden
  `import_weights` -> `localize_correctives`.
- No leer ficheros de `assets/` desde un modulo: `guides_manager` y
  `rig_manager` son la unica puerta.
- No escribir en `cache/` sin `append_data`.
- No arreglar `get_next_version_name` a medias: o se usa y se testea o se borra.
