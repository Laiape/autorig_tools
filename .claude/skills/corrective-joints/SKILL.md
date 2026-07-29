---
name: corrective-joints
description: 'Diseña, coloca y conecta corrective joints (helper joints / muscle pushers) en los rigs de este autorig de Maya — cuerpo Y cara. Sabe qué son, qué corrigen (pérdida de volumen, candy-wrapper, pliegues, bulges musculares), cuándo ponerlas (y cuándo NO), con qué driver activarlas (bend_driver, bend_factor, twist, cone, pesos de blendshape) y cómo integrarlas en el build de este repo (utils/correctives.py, naming, mirror L/R, skinCluster apilado, export _ENV, persistencia en el .build). Incluye el sistema de correctivas FACIALES: una por cada shape/expresión del set esculpido, más o menos según lo que rompa. Úsala SIEMPRE que el usuario hable de correctivas, corrective/helper joints, pushers, bulge de bíceps/deltoides, volumen que se pierde en codo/rodilla/hombro/cadera, correctivas faciales o por expresión/blendshape, drivers de pose, o pida añadir/tunear/mirrorear/exportar correctivas en cualquier módulo del autorig.'
---

# Corrective Joints (cuerpo + faciales)

Skill para trabajar con **joints correctivas** en este repo (`autorig_tools`): qué son,
dónde ponerlas, cómo drivearlas y cómo integrarlas en el build sin romper nada.

**Idea central**: el linear blend skinning solo nunca es suficiente — colapsa volumen en
flexiones (codo, rodilla, hombro), estrangula en twists (candy-wrapper) y no crea pliegues
ni bulges. Una corrective joint es una joint EXTRA del esqueleto de deformación, **no
animada a mano**, cuyo translate está **driveado proceduralmente por la pose** (ángulo del
codo, peso de un blendshape facial…) y que empuja la malla para devolver el volumen o la
forma que el skinning pierde.

## Referencias (léelas según la tarea)

| Fichero | Cuándo leerlo |
|---|---|
| `references/fundamentos.md` | Teoría: por qué existen, familias (twist vs pose), joints VS blendshapes, criterios de cuándo añadir. Léelo si hay que justificar decisiones o explicar conceptos. |
| `references/catalogo-corporal.md` | Catálogo por zonas del cuerpo (hombro, codo, cadera, rodilla…): cuántas joints, qué driver, rango en grados, dirección de empuje. Léelo SIEMPRE antes de añadir correctivas corporales a una zona nueva. |
| `references/drivers.md` | Cómo leer la pose: bend_driver, bend_factor, twist por quaternions, cone driver (receta), RBF, redes de nodos Maya 2024+, mirroring L/R, errores comunes de driver. Léelo antes de cablear cualquier driver nuevo. |
| `references/faciales.md` | **La parte facial**: catálogo de correctivas por expresión (smile, jaw open, blink…), drivers reales de este repo, flujo cabeza-esculpida→joint, combinaciones. Léelo SIEMPRE para trabajo facial. |
| `references/repo-y-qa.md` | API exacta de `utils/correctives.py`, integración en el build, persistencia de amounts, checklist de QA y errores comunes. Léelo antes de escribir código. |

## Lo que este repo YA tiene (no lo reinventes)

- **`scripts/utils/correctives.py`** — primitivas listas: `corrective_push`, `corrective_ring`,
  `corrective_offset_push`, `corrective_arc`, `corrective_extra`, `corrective_curve`
  (pose→curva→joints para siluetas continuas: nudillos, pliegues — UI en menú SKINNING),
  los pose-readers `bend_driver` (bisagras) y `cone_driver` (multi-eje auto-calibrado), y
  `localize_corrective_skin` (arregla la doble transformación del skinCluster apilado).
- **`scripts/utils/matrix_manager.py`** — `bend_factor` (flexión 0-1 por dot product, sin
  flips) y `extract_twist` (swing-twist por quaternions, aún sin usar como driver).
- **Ejemplos reales**: `arm_module.corrective_setup()` (bíceps/tríceps en arco + anillo de
  codo, driver = flexión del codo eje Y, rangos 0→±100°, amounts = 12% del hueso) y
  `leg_module.corrective_setup()` (thighFront/thighBack, rodilla eje Z).
- **Blendshapes correctivos**: `corrective_blendshape_manager.py` (export/import/mirror de
  targets frontOfChain con sus driven keys) — conviven con las joints: joint para volumen
  mecánico continuo, shape para esculpido fino.
- El build **localiza automáticamente** cualquier skinCluster con `corrective` en el nombre
  y **exporta** al esqueleto `_ENV` toda joint con `corrective`/`ring` en el nombre.

## Flujo de trabajo — CUERPO

1. **Evidencia primero.** Reproduce/crea la pose que rompe (ROM: codo/rodilla 0→140°,
   hombro >90°, squat…). Sin defecto visible no hay correctiva: primero skinning limpio +
   twists, la correctiva es la última capa.
2. **Consulta el catálogo** (`references/catalogo-corporal.md`) para la zona: nº de joints
   típico, driver y dirección de empuje.
3. **Elige el driver** (`references/drivers.md`): bisagra pura → `bend_driver` (eje de la
   bisagra primero); factor suave 0-1 → `bend_factor`; twist → `extract_twist`;
   hombro/cadera multi-eje → cone driver (receta en drivers.md); nunca leas controles FK ni
   `rotate` local de joints (van por matriz y valen 0).
4. **Instancia la primitiva** dentro de un `corrective_setup()` del módulo (patrón
   arm/leg): joint base = la de skinning de la zona, amounts por defecto proporcionales a
   la longitud del hueso (12%), attrs `Enable`/`Push*` bajo el separador `CORRECTIVES_SEP`
   del bendy CTL (fallback `settings_ctl`).
5. **Mirror**: construye L y en R **niega el vector de empuje COMPLETO** (`_ax`); el driver
   angular NO cambia de signo (regla verificada del repo, no la re-razones).
6. **Skin**: skinCluster aparte con `corrective` en el nombre (p.ej. `C_corrective_SKC`),
   pesos pico 0.2-0.5 robados del padre por normalización, parche pequeño; exporta `.skc`.
7. **QA** (`references/repo-y-qa.md`): rest = identidad, toggle Enable a 0 = skinning base,
   ROM completa de nuevo, masterwalk (escala/lejos del origen), mirror numérico.

## Flujo de trabajo — FACIAL (una correctiva por shape del set)

**Regla del set**: una correctiva por cada shape esculpida (las cabezas de referencia del
modelador) como punto de partida — más donde rompan combinaciones (smile+jaw open), menos
donde los joints de módulo ya deformen bien. Detalle y catálogo en `references/faciales.md`.

1. Lee `references/faciales.md` (catálogo por expresión + drivers concretos del repo).
2. Por cada cabeza esculpida: reproduce la expresión con los controles de módulo →
   compárala con el sculpt (blendShape temporal a peso 1 como "goal overlay") → el delta
   restante ES la correctiva.
3. Coloca la corrective joint en la zona de máximo delta, colgada de la skinning joint del
   módulo correspondiente (cheekbone, jaw, eyebrow…), con las mismas primitivas de
   `correctives.py`.
4. **Driver facial**: en la cara el control ES la fuente canónica de la pose (no hay
   dualidad FK/IK), así que aquí SÍ se lee del control o del peso del blendshape — p.ej.
   `C_jaw_CTL.rotateX` (apertura), `L_lipCorner_CTL.translateY` (smile/frown) o el peso de
   un target de `C_facial_local_BLS` (plug 0..1). Tabla completa de plugs, rangos reales y
   combos: `references/faciales.md` §2.
5. Lo que la joint no alcance (arruga fina, pliegue esculpido) → corrective blendshape con
   el CBS manager. Es el reparto híbrido: joint = volumen/movimiento, shape = detalle.
6. NO dupliques lo ya resuelto por diseño: teeth/tongue siguen la jaw por matriz, la
   colisión del upperJaw tiene `Auto_Collision`, los párpados tienen `Fleshy`, el pómulo ya
   empuja el socket. Revisa `references/faciales.md` §"qué no corregir".

## Reglas NO negociables del repo

- **Naming**: `{L|R|C}_nombreCorrective_JNT` (o `...Ring##_JNT`) — la palabra
  `corrective`/`ring` en el nombre es lo que hace que `skeleton_hierarchy()` la cuelgue del
  `_ENV` de su padre en el esqueleto de export. Sufijos de nodos: `_MUL`, `_SUM`, `_RMV`,
  `_MM`, `_DEC`… (ver repo-y-qa.md), siempre `ss=True`.
- **Todo tunable por plug**: amounts/límites como atributos (nunca horneados), `Enable` por
  correctiva. Los defaults se calculan de las guías (proporcionales al hueso) para ser
  independientes de escala.
- **Rest = identidad**: en bind pose la correctiva no mueve ni un vértice (translate 0 o
  rest_offset exacto). `localize_corrective_skin` se encarga del skin apilado — se llama
  solo desde el build, en pose neutra.
- **Nodos modernos**: familia math/matrix de Maya 2024+ (`multiply` con `input[i]`, `sum`,
  `subtract`, `remapValue` con auto-clamp, `rowFromMatrix`…). Nada de `multiplyDivide`
  nuevo. El repo asume Maya 2025+.
- **Persistencia por personaje**: valores tuneados → bloque `character_extras.set_attrs`
  del `.build` (ver repo-y-qa.md).
