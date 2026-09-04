# autorig_tools: indice de documentacion

> Punto de entrada. Reglas de trabajo: `CLAUDE.md` y `.claude/rules/`.
> Hijos: `maya_tools/como_funciona.md`, `ue_tools/como_funciona.md`,
> `.claude/skills/como_funciona.md`, `docs/`. Cada carpeta de codigo o datos
> tiene su propia hoja `como_funciona.md` (tabla al final).

---

## Vision general

Autorig modular para Maya 2025+ en Python. Cuatro ideas lo definen:

- **Rig por matrices**: `offsetParentMatrix`, `multMatrix`, grupos offset. Sin
  constraints clasicos. Ribbons de Boor propios (`utils/ribbon.py`) en vez de
  follicles.
- **Build data-driven**: cada personaje tiene `.guides` + `.build` en
  `maya_tools/assets/<personaje>/`; el build lee eso y construye los modulos
  cuyas guias existen. Nada de posiciones en el codigo.
- **Deformacion**: skinCluster (`.skc` versionado) + ribbons matriciales +
  corrective joints por nodos. AdonisFX para simulacion.
- **Export**: esqueleto `_ENV` en `skeletonHierarchy_GRP` + morphs. Notas de
  Unreal en `ue_tools/docs/`.

```
autorig_tools/
|-- CLAUDE.md                     flujo obligatorio + indice de entrada
|-- como_funciona.md              este fichero
|-- .claude/rules/                reglas cortas, una por tema
|-- .claude/skills/               conocimiento de dominio (6 skills)
|-- docs/                         plan de workflow y docs transversales
|-- maya_tools/
|   |-- self_module.mod           modulo de Maya: registra maya_tools y el PYTHONPATH
|   |-- scripts/
|   |   |-- userSetup.py          arranque: menu, shelf, puertos VS Code, numpy, proxy_locator, MCP :9877
|   |   |-- utils/                motor: create_rig, rig_manager, guides_manager, data_manager,
|   |   |                         matrix_manager, ribbon, de_boor_core, correctives, curve_tool, picker
|   |   |-- biped/autorig/        modulos biped: cuerpo (arm, leg, spine, neck, clavicle, fingers, wing)
|   |   |                         y cara (jaw, eyelid, eyebrow, cheekbone, nose, ear, tongue, teeth, facial_correctives)
|   |   |-- quadruped/autorig/    modulos quadruped: leg_module_self (activo), leg_module (referencia),
|   |   |                         spine, neck, tail, digits
|   |   |-- tools/                herramientas de artista + tests headless (tools/tests)
|   |   |-- ui/                   menu AutoRig Tools, shelf, UIs PySide
|   |   |-- adonis/               copyWeightsAdonis (AdonisFX)
|   |   |-- criterios_naming.md   tabla canonica de sufijos por tipo de nodo
|   |-- assets/<personaje>/       build, guides, curves, models, skin_clusters, corrective_blendshapes, picker
|   |-- cache/                    biped.cache / quadruped.cache: estado del ultimo build (efimero)
|   |-- icons/                    iconos del shelf
|   |-- plugin/                   C++ collisionCommands (no lo usa el build)
|-- ue_tools/                     docs de UE (Unreal Fest 2026); scripts vacio
```

---

## Pipeline de build

```mermaid
flowchart TD
    A["Asset Manager (menu PIPELINE > Character Manager)"] --> B["Guias en escena: C_guides_GRP con los rig settings como atributos"]
    B --> C["Export Guides -> .guides ; rig settings -> .build"]
    C --> D["CREATE RIG: auto_rig_UI.rig -> escena nueva -> create_rig.AutoRig.build"]
    D --> E["basic_structure: rig_GRP, modules_GRP, skel_GRP, C_masterwalk_CTL, C_character_CTL, C_settings_CTL"]
    E --> F["rig_manager.build_rig: modulos segun guias + Rig_Type, space switches, apply_character_extras, skeleton_hierarchy (_ENV)"]
    F --> G["label_joints, hide_connections, inherit_transforms"]
    G --> H["import_weights (.skc) -> localize_correctives"]
    H --> I["import_corrective_blendshapes (.json, frontOfChain)"]
    I --> J["hide_all_utility_nodes -> picker.generate_and_load"]
```

- El build corre en "fast session" (cycleCheck off, EM off) entre `basic_structure`
  e `inherit_transforms`. Los ciclos se validan en QA.
- `apply_delta_mush` y `_auto_transfer_from_source` existen en
  `maya_tools/scripts/utils/create_rig.py` pero estan comentados.
- Comunicacion entre modulos: `data_manager.DataExportBiped().append_data` /
  `get_data` sobre `maya_tools/cache/*.cache`. Nunca nombres de nodo a mano.
- Que modulo se construye lo deciden las guias presentes (`check("L_hip_JNT")`...)
  y `Rig_Type` (0 biped, 1 quadruped). Quadruped: `leg_impl` self/reference,
  presets de solver por pata, `foot_type` hoof/paw, `reciprocal_coupling`.
- Orden del stack de deformacion y reglas de skin: `.claude/rules/deformacion-y-skin.md`.

---

## Personajes

| Personaje | Rig_Type | Que hay en `maya_tools/assets/<p>/` |
|---|---|---|
| Edward | 0 biped | build, guides, curves, skin_clusters, picker, modelo (LFS) |
| anne | 0 biped | build, guides, curves, skin_clusters, modelo |
| freya | 0 biped | build, guides, curves, skin_clusters, modelos |
| maui | 0 biped | build, guides, curves, skin_clusters, modelo |
| mechanic | 0 biped | build, guides, curves, skin_clusters, modelo |
| moana | 0 biped | build, guides, curves, skin_clusters, modelo |
| thaiz | 0 biped | build, guides, curves, skin_clusters, corrective_blendshapes, modelo |
| jamal | 0 biped | build, guides, curves, modelo, escena en `scenes/`; pesos en formatos legacy (`.weights`, `.shp`) |
| chihuahua | 0 en el build | solo build + guides; modelo excluido de git por tamano |
| horse | 1 quadruped | build, guides (con `.bak` a limpiar), curves, skin_clusters, picker, modelo |
| giraffe | 1 quadruped | build, guides, curves, modelo; spine uniforme (`UNIFORM_SPINE_CHARS`) |
| spot | sin build | solo guides y curves |
| source | sin build | origen de transfers de skin (`.skc` + `.skinmap`) |

Detalle por personaje y claves del `.build`: `maya_tools/assets/como_funciona.md`.
Reglas de versionado: `.claude/rules/datos-y-versionado.md`.

---

## Que leer segun la tarea

### Lee `CLAUDE.md` si necesitas...
- El flujo obligatorio, la convencion de rutas, como lanzar build y tests.

### Lee `.claude/rules/convenciones-rig.md` y `maya_tools/scripts/criterios_naming.md` si necesitas...
- Naming, sufijos de nodos, matrices vs constraints, nodos 2024+, patron de modulo.

### Lee `.claude/rules/datos-y-versionado.md` si necesitas...
- Que fichero escribe y lee cada cosa, como se resuelven las versiones, `.build`.

### Lee `.claude/rules/deformacion-y-skin.md` si necesitas...
- Orden del stack, skin apilado localizado, `.skc`, deformers permitidos, QA.

### Lee `maya_tools/como_funciona.md` si necesitas...
- Arranque de Maya, `self_module.mod`, `userSetup`, cache, iconos, plugin C++.

### Lee `maya_tools/scripts/utils/como_funciona.md` si necesitas...
- La secuencia exacta del build, `rig_manager`, `guides_manager`, `data_manager`, matrices, ribbons, picker.

### Lee `maya_tools/scripts/biped/autorig/como_funciona.md` si necesitas...
- Que guias activan cada modulo biped o facial, que joints y controles crea, que publica en cache.

### Lee `maya_tools/scripts/quadruped/autorig/como_funciona.md` si necesitas...
- Patas `leg_module_self` frente a referencia, solvers, pie hoof/paw, spine y cuello quad.

### Lee `maya_tools/scripts/tools/como_funciona.md` si necesitas...
- Que hace cada tool, su entrada de menu, su estado y como lanzar los tests.

### Lee `maya_tools/scripts/ui/como_funciona.md` si necesitas...
- El menu item a item, el shelf, el Asset Manager y las ventanas PySide.

### Lee `maya_tools/scripts/adonis/como_funciona.md` si necesitas...
- El tooling de AdonisFX (`copyWeightsAdonis`).

### Lee `maya_tools/assets/como_funciona.md` si necesitas...
- El contrato de carpeta por personaje, la tabla de personajes, las claves del `.build`.

### Lee `ue_tools/como_funciona.md` si necesitas...
- Que hay de Unreal (solo notas) y el contrato de export.

### Lee `.claude/skills/como_funciona.md` si necesitas...
- Que skill abrir para skinning, correctivas, deformers, ropa o estandares.

### Lee `docs/plan_workflow.md` si necesitas...
- El plan de las hojas por area pendientes y las plantillas de doc/regla/criterios.

### Lee `ue_tools/docs/unreal_fest_chicago_2026_rigging_produccion.md` si necesitas...
- Control Rig, deformers y data-driven en UE 5.8 aplicados a este pipeline.

---

## Resumen

| Carpeta | Que es | Hoja |
|---|---|---|
| `.claude/rules/` | Como trabajar y las convenciones no negociables | cada regla |
| `.claude/skills/` | Conocimiento de rigging aterrizado en este repo | `.claude/skills/como_funciona.md` |
| `maya_tools/` | Arranque, `.mod`, cache, plugin | `maya_tools/como_funciona.md` |
| `maya_tools/scripts/utils/` | Motor del build | `maya_tools/scripts/utils/como_funciona.md` |
| `maya_tools/scripts/biped/autorig/` | Modulos biped y cara | `maya_tools/scripts/biped/autorig/como_funciona.md` |
| `maya_tools/scripts/quadruped/autorig/` | Modulos quadruped | `maya_tools/scripts/quadruped/autorig/como_funciona.md` |
| `maya_tools/scripts/tools/` | Herramientas y tests | `maya_tools/scripts/tools/como_funciona.md` |
| `maya_tools/scripts/ui/` | Menu, shelf, ventanas | `maya_tools/scripts/ui/como_funciona.md` |
| `maya_tools/scripts/adonis/` | AdonisFX | `maya_tools/scripts/adonis/como_funciona.md` |
| `maya_tools/assets/` | Datos por personaje, versionados | `maya_tools/assets/como_funciona.md` |
| `ue_tools/` | Export a Unreal (solo docs hoy) | `ue_tools/como_funciona.md` |
| `docs/` | Plan de workflow | `docs/plan_workflow.md` |
