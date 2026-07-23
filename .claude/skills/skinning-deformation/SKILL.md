---
name: skinning-deformation
description: 'Guía completa de skinning para los rigs de este autorig de Maya: qué SHAPE hay que buscar en cada deformación (hombro, codo, muñeca, dedos, pecho/columna, cuello, cadera, rodilla, tobillo/pie, facial y quadruped), qué joints de deformación genera cada módulo del repo (ribbons de Boor, twists, Skinning_JNT), cómo repartir los pesos por zona, cómo diagnosticar deformaciones malas (candy-wrapper, colapsos, creases donde no toca) y cómo encaja todo en el build (.skc, skin_manager_api, orden de capas con correctivas). También busca REFERENCIAS VISUALES en la web a partir de fotos que pase el usuario (analiza la foto, identifica la zona y devuelve referencias fotográficas de cómo debe deformar). Úsala SIEMPRE que el usuario hable de skinnear, pintar pesos, weights, skinCluster, bind, deformación de una zona del cuerpo (hombro, codo, rodilla…), qué forma debe tener algo al doblarse, candy-wrapper, transferir/exportar/importar pesos (.skc), o pida referencias de anatomía/deformación para skinning.'
---

# Skinning por zonas — qué shape buscar en cada deformación

Skill para skinnear personajes de este repo (`autorig_tools`): la idea central es que
**los pesos no son el resultado, la SILUETA en pose sí**. Cada zona del cuerpo tiene una
"shape objetivo" — la forma que la anatomía real produce en la pose extrema — y el
skinning se evalúa poniendo el rig en esa pose y comparando la silueta con la
referencia. Esta skill dice, zona por zona, cuál es esa shape, con qué joints del repo
se consigue y cómo repartir los pesos.

## Referencias (léelas según la tarea)

| Fichero | Cuándo leerlo |
|---|---|
| `references/fundamentos.md` | Metodología: orden de capas (skin → twist → correctivas), flujo bloque→gradiente→pulido en pose, reglas de higiene, diagnóstico de deformaciones malas. Léelo al empezar un skinning nuevo o si algo deforma mal y no sabes por qué. |
| `references/catalogo-zonas.md` | **El corazón**: por zona (hombro, codo, antebrazo, mano, pecho/columna, cuello, cadera, rodilla, tobillo/pie, facial, quadruped) — pose de test, shape objetivo, joints exactos del repo, reparto de pesos y errores típicos. Léelo SIEMPRE antes de skinnear o corregir una zona. |
| `references/esqueleto-deformacion.md` | Inventario exacto del esqueleto de deformación que genera cada módulo (naming, cuántos joints, de dónde sale el número en el `.build`, cómo va el twist en los ribbons, export `_ENV`). Léelo si dudas de qué joint pinta qué o vas a tocar código. |
| `references/flujo-pesos-y-qa.md` | Pipeline de pesos: `.skc` versionado por personaje, orden del build, skinCluster apilado de correctivas, mirror, transferencia entre mallas/personajes, checklist de QA. Léelo antes de exportar/importar pesos o cerrar una versión. |
| `references/referencias-visuales.md` | Flujo de búsqueda de referencias con fotos: el usuario pasa una foto, se identifica zona y tipo de cuerpo, se busca en la web referencia fotográfica de la deformación. Recetas de búsqueda por zona. Léelo cuando el usuario pase una imagen o pida referencias. |

## Lo que este repo YA te da (no lo pelees, aprovéchalo)

- **El twist ya viene repartido**: brazo y pierna son ribbons de Boor con swing-twist por
  cuaternión (`utils/ribbon.py::de_boor_ribbon`). `L_armLower00_JNT → 04` ya interpola el
  twist codo(0)→muñeca(100%). Tu trabajo es pintar **bandas cilíndricas solapadas y
  uniformes** entre joints consecutivos; si te saltas un joint o las bandas son
  irregulares, reintroduces el candy-wrapper que el rig ya había resuelto.
- **Los números salen del `.build`**: `arm_skinning_jnts`, `leg_skinning_jnts` (def 5),
  `spine_skinning_jnts` (def 8), `neck_skinning_jnts`, `tail_skinning_jnts` (def 5).
- **No hay bind por defecto**: si no existe `.skc` en `assets/<char>/skin_clusters/`, el
  build deja las mallas SIN piel (no hay fallback). El primer bind es manual (o
  transferido con `auto_skin_transfer`) y después vive versionado en `.skc`.
- **Las correctivas van aparte**: el skinCluster del body NO incluye joints
  `*Corrective_JNT`/`*Ring*_JNT`; esas van en un skinCluster apilado con `corrective` en
  el nombre (ver skill `corrective-joints`). Primero skinning limpio, la correctiva es la
  última capa.

## Flujo de trabajo

1. **Identifica la zona y sus joints** (`references/catalogo-zonas.md` +
   `references/esqueleto-deformacion.md`): qué joints del repo pintan esa zona.
2. **Monta la pose de test** de la zona (ROM del catálogo: codo/rodilla 0→140°, brazo
   arriba 170°, sentadilla, puño, twist de torso 45°…).
3. **Ten clara la shape objetivo** — del catálogo, y si el usuario pasa fotos o pide
   referencia visual, busca fotos reales (`references/referencias-visuales.md`).
4. **Pinta hacia la silueta**: bloque rígido primero, gradiente solo en la banda de
   transición (corta en el lado del pliegue de las bisagras, larga en bolas
   hombro/cadera), pulido EN LA POSE mirando la silueta.
5. **Mirror y versiona**: mirror de pesos (no pintar dos veces), export `.skc`
   (`skin_manager_api` crea la versión siguiente automáticamente).
6. **QA** (`references/flujo-pesos-y-qa.md`): ROM completa de nuevo, masterwalk
   lejos del origen + escala, prune de pesos residuales, y solo entonces pasa a
   correctivas si aún falta volumen.

## Reglas rápidas que resuelven el 90%

- **Bisagra** (codo, rodilla, dedos, tobillo): el lado EXTERIOR se mantiene firme y
  marca el hueso, el INTERIOR pliega con crease definido. Transición CORTA en el
  interior, LARGA en el exterior.
- **Bola** (hombro, cadera): sin crease única — transiciones largas y difusas, la masa
  rota con el hueso y la raíz (torso/pelvis) apenas se mueve. El twist se reparte por
  el hueso, jamás se concentra en el pliegue.
- **Bloques semirrígidos**: caja torácica (`C_localChestSkinning_JNT`), pelvis
  (`C_localHipSkinning_JNT`), cráneo (`C_headSkinning_JNT`), falanges, talón/empeine.
  No los suavices con floods globales.
- **Columna/cuello**: la curva se reparte entre TODAS las joints (bandas horizontales
  solapadas), nunca bisagra en una sola vértebra.
- Pinta en pose, mirrorea al final de la sesión, exporta `.skc` a menudo.
