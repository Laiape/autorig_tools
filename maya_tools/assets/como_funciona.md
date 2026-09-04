# Assets (datos por personaje)

Parent: `como_funciona.md` (raiz).
Regla unica de versiones y layout: `.claude/rules/datos-y-versionado.md`.
Donde vive cada dato (y donde no): `maya_tools/mapa_datos.md`.
Quien escribe y lee cada fichero: `maya_tools/scripts/utils/como_funciona.md`
(`rig_manager`, `guides_manager`, `curve_tool`, `skin_manager_api`, `corrective_blendshape_manager`, `picker`).
UI: Asset Manager (`maya_tools/scripts/utils/character_manager.py`).

## 1. Que es y para que existe

Todo lo que cambia entre personajes: guias, settings del build, formas de
control, pesos, correctivas, picker y modelo. El codigo no lleva nada de esto.
El Asset Manager (menu PIPELINE > Character Manager) crea la carpeta, versiona
guides/curves/models/skin_clusters y fija el asset activo (optionVar
`currentAssetRigName`) que usan el build y los exports.

## 2. Contrato de carpeta

```
maya_tools/assets/<personaje>/
|-- <personaje>.png | .jpg | thumbnail.jpg    miniatura del Asset Manager
|-- build/<personaje>_v001.build            JSON de rig settings; siempre v001, se sobreescribe
|-- guides/<personaje>_vNNN.guides          JSON de guias (joints, matrices, padres, locators, curvas, NURBS)
|-- curves/<personaje>_vNNN.curves          formas de los controles
|-- models/<personaje>_vNNN.ma | CHAR_<p>_v0001.ma   modelo; los grandes por LFS
|-- skin_clusters/<personaje>_vNNN.skc      stack de skin por malla
|-- corrective_blendshapes/<personaje>_vNNN.json
|-- picker/<personaje>_picker.json          DWPicker, sin version
```

Como se resuelve cada version (detalle en la regla): `.skc` y blendshapes por
NUMERO mas alto; `.guides`, `.curves` y `.build` por FECHA de modificacion.

Export Guides escribe a la vez el `.guides` (v001 si se llama sin ruta) y el
`.build` desde los atributos de `C_guides_GRP` (`get_rig_data`). Desde el
Asset Manager, SAVE VERSION crea la siguiente version del tipo elegido y el
boton Overwrite pisa la seleccionada (unico caso).

## 3. Claves del `.build` (`rig_manager.create_rig_settings`)

| Clave | Tipo | Default | Quien la lee |
|---|---|---|---|
| `Rig_Type` | enum biped / quadruped (0/1) | 0 | `build_rig` (dispatch) |
| `spine_skinning_jnts` / `spine_controllers` | int 1-20 | 8 / 5 | spine |
| `neck_skinning_jnts` / `neck_controllers` | int | 5 / 2 | neck |
| `arm_skinning_jnts` | int | 5 | arm (ribbons) |
| `leg_skinning_jnts` | int | 5 | leg biped y quadruped |
| `tail_skinning_jnts` / `tail_controllers` | int | 5 / 5 | tail |
| `mGear_integration` | enum disabled / enabled | 0 | `basic_structure`, neck, space switches |
| `solver_mode` | enum maya solvers / custom solvers | 0 | `resolve_leg_solvers` (1 = `nodes`) |
| `solver_front_leg` / `solver_back_leg` | enum `LEG_SOLVER_OPTIONS` (spring, rp, spring_rp, nodes, sc_rp_sc, sc_rp_sc_carpus, rp_rp) | 0 | `resolve_leg_solvers` |
| `reciprocal_coupling` | enum off / on | 1 (ungulado) | `leg_module_self` |
| `foot_type` | enum hoof / paw | 0 | `leg_module_self` (`HoofFoot` / `PawFoot`) |
| `character_extras` | `{"set_attrs": [...], "add_attrs": [...]}` | ausente | `apply_character_extras` |

`character_extras` solo se puede escribir a mano en el JSON (el UI no lo
genera). Formato de cada entrada: dicts `node` / `name` / `value` (y `type`,
`min`, `max`, `default` en `add_attrs`); `node` admite `"modulo/clave"` del
cache. HOY NINGUN `.build` DEL REPO LO USA. Ojo: `get_rig_data` reescribe el
`.build` desde los atributos de `C_guides_GRP`, asi que al reexportar guias se
pierde el bloque a mano si no se vuelve a anadir (pendiente de resolver).

## 4. Personajes

| Personaje | Rig_Type | Carpetas | Notas |
|---|---|---|---|
| Edward | 0 biped | build, guides, curves, models (LFS), picker, skin_clusters | |
| anne | 0 biped | build, guides, curves, models, skin_clusters | `.mayaSwatches/` colado en models |
| freya | 0 biped | build, guides, curves, models, skin_clusters | dos modelos (`CHAR_freya_v0001.ma`, `freya_v002.ma`); `.mayaSwatches/` |
| maui | 0 biped | build, guides, curves, models, skin_clusters | |
| mechanic | 0 biped | build, guides, curves, models, skin_clusters | swatches de `CHAR_yin` colados |
| moana | 0 biped | build, guides, curves, models, skin_clusters | |
| thaiz | 0 biped | build, guides, curves, models, skin_clusters, corrective_blendshapes | el unico con CBS versionados |
| jamal | 0 biped | build, guides, curves, models, `scenes/` | pesos en formatos legacy (`jamal_v001.weights`, `facial_blendshapes.shp`) que el build NO importa |
| chihuahua | 0 en el build | build, guides | modelo excluido de git por tamano (`.gitignore`); Rig_Type 0 aunque los commits lo usan como canido |
| horse | 1 quadruped | build, guides, curves, models, picker, skin_clusters | `guides/` tiene `.bak`, `.bak2`, `.bak3` a borrar (Fase 4) |
| giraffe | 1 quadruped | build, guides, curves, models | spine uniforme (`UNIFORM_SPINE_CHARS`); sin skin |
| spot | sin build | guides, curves | no construye |
| source | sin build | models, skin_clusters (`.skc` + `THAIZ_BODY_PLY.skinmap`) | origen de transfers (`mesh_data_exporter`) |

Cambiar de personaje = seleccionarlo en el Asset Manager (LOAD SETTINGS solo
fija el optionVar; BUILD RIG abre escena nueva y construye).

## 5. Estado hoy y limpieza pendiente (Fase 4)

- Borrar `horse/guides/*.bak*` y todas las `models/.mayaSwatches/`.
- Decidir `jamal`: migrar sus pesos a `.skc` o marcar el personaje como legacy.
- `chihuahua`: `Rig_Type` 0 en el `.build` no cuadra con su uso como
  cuadrupedo en los commits; comprobar antes de construirlo.
- `character_extras` no sobrevive a un Export Guides: hace falta que
  `get_rig_data` conserve el bloque o un `dump_corrective_attrs`.

## 6. Do not

- No editar ni copiar versiones antiguas de `.guides`/`.curves`: cambia el
  mtime y el build las coge.
- No guardar `.bak`, swatches ni escenas sueltas dentro de `assets/`.
- No subir un `.ma` grande sin LFS.
- No inventar carpetas nuevas por personaje: si hace falta un dato nuevo,
  primero fila en `maya_tools/mapa_datos.md`.
