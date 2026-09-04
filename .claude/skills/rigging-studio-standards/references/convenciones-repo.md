# Convenciones reales de este autorig (y qué unificar)

Antes de proponer nada, alinéate con lo que **ya existe** en `autorig_tools`. La consistencia con el
repo pesa más que cualquier "mejor práctica" traída de fuera. Esto es lo observado en el código.

## Arquitectura y organización

```
scripts/
├── biped/autorig/*_module.py      # un módulo por parte (arm, leg, spine, neck, jaw, eyelid…)
├── quadruped/autorig/*_module.py   # variante cuadrúpedo (limb, spine, neck, tail…)
├── utils/                          # motor compartido (matrix_manager, guides_manager, rig_manager,
│                                   #   data_manager, ribbon, de_boor_core, correctives, blendshape…)
├── tools/                          # herramientas de artista (skin managers, correctives, auto_skin_
│                                   #   transfer, ik_fk_match, model_checker, auto_collision…)
├── ui/                             # UIs PySide (auto_rig_UI, deboor_tools_UI, skin_transfer_UI…)
└── adonis/                         # integración AdonisFX (copyWeightsAdonis)
cache/                              # cache de build (biped.cache, JSON)
assets/<char>/skin_clusters/*.skc  # skinClusters versionados por asset (v001, v002…)
```

**Patrón de módulo** (respétalo al crear uno nuevo, p. ej. un clothing module):

- Importa utils y hace `reload()` de cada uno al principio (flujo de iteración en Maya).
- Clase `XxxModule(object)`; en `__init__` **lee datos del build** con
  `data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")` en vez de hardcodear.
- Método `make(side, ...)` que construye; parametrizado (nº de joints de skinning, controladores…).
- Fallback `PySide2` / `PySide6` en las UIs (portabilidad entre versiones de Maya).

## Flujo de datos: data-driven, no hardcodeado

- **Guides**: cada personaje tiene un `.guides` (JSON) versionado; `guides_manager` lo cachea por
  personaje (con guard que sobrevive a `reload`) para no releer disco de red en cada build. El rig se
  construye **a partir de las guías**, no de posiciones fijas.
- **Build cache**: `DataExportBiped` escribe/lee `cache/biped.cache` (JSON) para que los módulos
  compartan datos del build (grupos, controladores maestros…). Un módulo publica sus nodos ahí y otro
  los consume. No se pasan nombres a mano.
- **Skin**: `SkinManager` (`skin_manager_api.py`) exporta/importa skinClusters a `.skc` versionados,
  guardando también `skinningMethod`, `maxInfluences`, `normalizeWeights`, etc.

Cualquier cosa nueva debería seguir esta línea: **datos fuera del código, versionados, leídos por
API**, no valores incrustados.

## Rig por matrices (el estándar de deformación aquí)

El repo rige con matrices, no con constraints clásicos:

- Conexión directa a `offsetParentMatrix` para colgar de un control sin nodo intermedio.
- `multMatrix` (nodos nombrados `_MMT`, derivados de `_JNT`) + `worldInverseMatrix[0]` para offsets.
- Lectura directa de `worldMatrix[0]` en nodos como `distanceBetween.inMatrix1/2` (sin
  `decomposeMatrix` cuando no hace falta), como en `auto_collision.py`.
- **Grupos offset** para evitar *dobles transforms* y mantener los canales del control/joint limpios
  (patrón visible en `auto_collision`: crea un `_Offset_GRP` y reparenta ahí).
- **Ribbons de Boor** propios (`de_boor_core` + `ribbon`) para setups bendy/spline (limbs, cara, cuello).

## Naming

La politica unica de naming, sufijos y nodos vive en
`.claude/rules/convenciones-rig.md`; la tabla canonica de sufijos por tipo de nodo,
con los legacy y su recuento, en `maya_tools/scripts/criterios_naming.md`. Aqui no se
repite: si hay que cambiar un sufijo, se cambia alli y se migra entero.

## Inconsistencias detectadas (candidatas a unificar)

Señálalas cuando toque, con criterio (no como ataque): unificar sube el nivel y evita bugs.

1. **Sufijos de nodos utilitarios divergentes.** El caso de los sufijos DAG ya esta
   resuelto (`_JNT` 429 usos frente a 1 `_jnt`; restos en minusculas solo en 4 ficheros,
   listados en `maya_tools/scripts/criterios_naming.md`). Lo que SI diverge son los
   sufijos de nodos utilitarios: multMatrix `_MMX`/`_MMT`/`_MM`, blendMatrix
   `_BLM`/`_BMT`/`_BMX`, aimMatrix `_AMX`/`_AIM`/`_AMT`, y `_PMX` usado a la vez para
   parentMatrix y pickMatrix. El canonico de cada tipo esta fijado en
   `criterios_naming.md`; la migracion se hace entera por sufijo, no a parches.
2. **Rutas dependientes de plataforma.** En `data_manager` la ruta se calcula con
   `split("\\scripts")` (separador de Windows y con `\s` que además es una secuencia de escape
   frágil). Un estándar de estudio usa `pathlib`/`os.path` para que el build corra en Windows y Linux
   por igual (relevante: este mismo entorno es Linux).
3. **Imports accidentales/no usados.** Hay algún import que parece colado por autocompletado (p. ej.
   `from numpy import character` en `rig_manager`). Un pase de limpieza de imports evita confusión y
   dependencias fantasma.

Trátalas como oportunidades priorizadas: la #1 (naming) es la de más impacto porque puede romper
builds; la #2 afecta portabilidad; la #3 es cosmética.

## Cómo usar esto

Cuando el usuario cree o revise algo, comprueba que **encaja** en estos patrones: ¿lee datos por API en
vez de hardcodear? ¿rige por matrices con grupos offset? ¿sigue el naming (y cuál de los dos casos)?
¿es un módulo/tool coherente con la estructura? Si se aparta, dilo y ofrece alinearlo. Si el usuario
quiere cambiar una convención, propón migrarla **entera** y de forma centralizada, no a parches.
