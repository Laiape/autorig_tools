# Donde vive cada dato

Parent: `maya_tools/como_funciona.md`.
Regla: `.claude/rules/datos-y-versionado.md`. Contrato de carpeta: `maya_tools/assets/como_funciona.md`.
Quien escribe y lee cada fichero: `maya_tools/scripts/utils/como_funciona.md`.

Cuando haya que guardar o leer algo nuevo ("esto lo tuneo a mano", "este
valor cambia por personaje", "esto lo necesita otro modulo"), NO se inventa
un fichero, una carpeta ni un atributo suelto: se busca la fila que
corresponde al SIGNIFICADO del dato y se usa ese sitio. Si no hay fila, se
anade aqui primero y despues se escribe el codigo.

---

## Como resolver un dato

1. Nombra que ES el dato: posicion de guia, parametro de build, forma de
   control, peso de skin, valor tuneado, nombre de nodo entre modulos,
   decision medida...
2. Busca esa fila en las tablas de abajo.
3. Usa el fichero, la API de escritura y la de lectura de esa fila.
4. Si el dato cabe en dos filas, se mantiene la separacion. Ejemplo: un
   amount de correctiva es un atributo del rig (fila "cantidad tunable") Y
   un valor por personaje (fila `character_extras`): el rig lo expone, el
   `.build` lo persiste.
5. Al cablear un dato nuevo, rellenar la columna "Estado" de su fila en la
   misma tarea.

---

## Por personaje (`maya_tools/assets/<p>/`)

| Si el dato es... | Vive en | Lo escribe | Lo lee | Estado |
|---|---|---|---|---|
| Posicion y orientacion de una guia (joint, locator, curva o NURBS de guia) | `guides/<p>_vNNN.guides` | Export Guides o Asset Manager SAVE VERSION -> `guides_manager.get_guides_info` | `guides_manager.get_guides` (cache por personaje) | activo; el build coge la mas reciente por mtime |
| Parametros de build (`Rig_Type`, numero de joints y controles, solvers, `foot_type`, `reciprocal_coupling`, mGear) | atributos de `C_guides_GRP` -> `build/<p>_v001.build` | `rig_manager.create_rig_settings` (UI) y `get_rig_data` (al exportar guias) | `rig_manager.build_rig_from_data` | activo; siempre v001, se sobreescribe |
| Un valor tuneado a mano en escena que debe sobrevivir al rebuild (amount de correctiva, limite, default) | bloque `character_extras.set_attrs` del `.build` | a mano en el JSON | `rig_manager.apply_character_extras` | cableado; ningun personaje lo usa; Export Guides lo pisa (pendiente) |
| Un atributo extra por personaje que el rig no crea | `character_extras.add_attrs` | a mano en el JSON | `apply_character_extras` | idem |
| Forma, color y escala de los controles | `curves/<p>_vNNN.curves` | Export All Controllers o Asset Manager -> `curve_tool.get_all_ctl_curves_data` | `curve_tool.build_curves_from_template` al crear cada control | activo; mas reciente por mtime |
| Pesos de skin (stack completo por malla, DQ blendWeights, attrs del skinCluster) | `skin_clusters/<p>_vNNN.skc` | `SkinManager.export_skins` (menu SKINNING, Asset Manager) | `create_rig.import_weights` | activo; numero mas alto |
| Pesos del skin apilado de correctivas | el mismo `.skc` (el skinCluster con `corrective` en el nombre va en la lista de la malla) | idem | idem, y `localize_correctives` lo localiza | activo |
| Blendshapes correctivos esculpidos y sus driven keys | `corrective_blendshapes/<p>_vNNN.json` | menu CORRECTIVES > Export | `create_rig.import_corrective_blendshapes` | activo (solo thaiz) |
| Layout del picker | `picker/<p>_picker.json` | `picker.generate_and_load` al final del build | DWPicker | activo; se regenera en cada build |
| El modelo | `models/<p>_vNNN.ma` | Asset Manager SAVE VERSION | `rig_manager.open_model_scene`, `prepare_rig_scene` | activo; LFS si es grande |
| Miniatura | `<p>.png`, `<p>.jpg` o `thumbnail.jpg` | Asset Manager (boton de camara) | Asset Manager | activo |
| Pesos de origen para transfer entre personajes | `assets/source/skin_clusters/*.skc` y `*.skinmap` | `mesh_data_exporter.SourceSkinExporter` | `create_rig._auto_transfer_from_source` (comentado) | no cableado |
| Capas de ngSkinTools | `skin_clusters/<p>.json` | `skin_manager_ng.export_skins` | `skin_manager_ng.import_skins`; el build no lo lee | herramienta de trabajo |

---

## Del build en curso (efimero)

| Si el dato es... | Vive en | Lo escribe | Lo lee |
|---|---|---|---|
| Nombre de un nodo que otro modulo necesita (grupos base, masterwalk, controles IK y FK, matrices locales de la jaw, joints raiz, MTP) | `maya_tools/cache/biped.cache` | `data_manager.DataExportBiped().append_data("<modulo>", {...})` al final de `make` | `get_data("<modulo>", "<clave>")` en `__init__` o donde toque; `apply_character_extras` con `"modulo/clave"`; space switches |
| Personaje activo | optionVar `currentAssetRigName` | Asset Manager (LOAD SETTINGS, BUILD RIG) | `rig_manager.get_character_name_from_build` |
| Estado de Maya durante el build (EM, cycleCheck, undo, refresh) | memoria (`_begin_fast_session`) | `create_rig` | `_end_fast_session` |

---

## Del rig construido (en escena, no en fichero)

| Si el dato es... | Vive en |
|---|---|
| Una cantidad o limite que el animador o el rigger puede tocar | atributo en el control de la zona bajo su separador (`CORRECTIVES_SEP`, `FOOT_ATTRIBUTES`, `SCAPULA_ATTRIBUTES`, `EXTRA_ATTRIBUTES`...), con `Enable` si es un automatismo; defaults proporcionales al hueso |
| La pose, para drivers de correctivas | matrices mundo de los joints del rig (`bend_driver`, `cone_driver`, `extract_twist`); en la cara, el control |
| El esqueleto que viaja al engine | `skeletonHierarchy_GRP` (`_ENV`), generado por `rig_manager.skeleton_hierarchy` |
| Un valor de calibracion horneado en build (twist del spring, offsets FK/IK, `restY` del sling, residuo de la escapula) | nodo o atributo creado por el modulo y recalculado en cada build; nunca en el `.build` |

---

## Decisiones y criterios (documentacion)

| Si el dato es... | Vive en |
|---|---|
| El sufijo canonico de un tipo de nodo | `maya_tools/scripts/criterios_naming.md` |
| Un solver, un signo de pole vector, un ratio o una excursion MEDIDOS del cuadrupedo | `maya_tools/scripts/quadruped/autorig/criterios_solvers.md` |
| El orden del build y por que, y las poses de QA | `maya_tools/scripts/utils/criterios_build.md` |
| Que shape buscar al skinnear una zona, catalogo de correctivas, metodos de ropa, estandares | `.claude/skills/como_funciona.md` |
| Como se trabaja en el repo | `CLAUDE.md` y `.claude/rules/` |

---

## Do not (donde NO va)

| Dato | Sitio equivocado | Sitio correcto |
|---|---|---|
| Posicion de un joint o control | numero en el codigo del modulo | `.guides` |
| Nombre de un nodo de otro modulo | string a mano en `make` | `append_data` / `get_data` |
| Un valor por especie o por personaje (acoplamiento, tipo de pie, bias, superficie de parpado) | subclase por animal o `if character_name == ...` | clave del `.build`. `UNIFORM_SPINE_CHARS` y `EYELID_SURFACE_CHARS` en `rig_manager` son excepciones a migrar |
| Un amount tuneado en escena | solo en la escena | `character_extras` del `.build` |
| Pesos pintados | solo en la escena o en un `.ma` | `.skc` exportado |
| Una version vieja "por si acaso" | `.bak`, copia con otro nombre | git |
| Una constante de rigging medida | solo en un mensaje de commit | docstring de la clase y `criterios_*.md` |
| Un fichero nuevo por personaje | carpeta inventada en `assets/<p>/` | fila nueva en este mapa primero |
| Configuracion del build | `maya_tools/cache/*.cache` | `.build` |
