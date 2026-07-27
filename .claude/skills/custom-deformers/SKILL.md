---
name: custom-deformers
description: 'Explica, evalúa y ayuda a construir custom deformers en los rigs de este autorig de Maya. Sabe qué es un deformer (geometry filter), qué es un custom deformer (plugin MPxDeformerNode/MPxGeometryFilter en C++ o Python) y las 4 vías profesionales de conseguir deformación custom: plugin MPx, node networks nativos (la vía de este repo: ribbons De Boor, skinning por de Boor, auto_collision), Bifrost compounds y comerciales (AdonisFX/Ziva). Conoce la API (deform(), pesos pintables, MPxGPUDeformer/OpenCL, parallel evaluation, cached playback, component tags), los criterios de cuándo escribir un plugin y cuándo NO (costes: ABI, unknown nodes, GPU chain), el deformer stack de este repo (orden blendShape correctivo→skin→correctivas→deltaMush, localize, .skc), el tooling de AdonisFX del repo (copyWeightsAdonis: AdnSkin/AdnMuscle/AdnFat...), y el flujo film vs juego (bakeDeformer, Dem Bones, PSD/RBF, UE5 Deformer Graph y ML Deformer). Úsala SIEMPRE que el usuario hable de deformers (custom o nativos), MPxDeformerNode, GPU deformers, wrap/proximityWrap, deltaMush, tension, colisiones de malla, sticky lips, skin sliding, deformer order/stack, deformers de AdonisFX, Bifrost como deformer, o de hornear/exportar deformación a engine.'
---

# Custom Deformers (teoría profesional + este repo)

Skill para trabajar con **deformers** en este repo (`autorig_tools`): qué son, qué vías
hay para crear deformación custom, cuándo compensa cada una y cómo encaja en el build.

**Idea central**: un deformer es un nodo que toma geometría de entrada, mueve sus puntos
y escribe la salida (`MPxGeometryFilter`). "Custom deformer" en sentido estricto = plugin
propio (`MPxDeformerNode`, C++/Python). Pero la vía del plugin es la ÚLTIMA de una
escalera: este repo deforma con **skinCluster + ribbons matriciales De Boor + correctivas
por nodos** (+ AdonisFX para sim), y ya probó y descartó un plugin C++ (colliders de
falda) — dos veces. Antes de escribir un deformer, agota el grafo nativo.

## Referencias (léelas según la tarea)

| Fichero | Cuándo leerlo |
|---|---|
| `references/fundamentos.md` | Teoría: definición, las 4 vías (plugin/nodos/Bifrost/comercial), por qué los estudios escriben deformers, el ciclo custom→nativo, la escalera de decisión, costes reales de un plugin, film vs juego. Léelo para justificar decisiones o explicar conceptos. |
| `references/api-openmaya.md` | La API: MPxDeformerNode/MPxGeometryFilter, deform() de producción (patrón cvwrap), pesos pintables, Python vs C++ (GIL, API 1.0), MPxGPUDeformer/OpenCL, parallel eval, cached playback, component tags. Léelo SIEMPRE antes de escribir o revisar código de plugin. |
| `references/catalogo-profesional.md` | El panorama: Ziva→DNEG, **AdonisFX al detalle** (nodos Adn*, workflow por capas, 2.0/2.1+AdonisML), stacks de Pixar/DreamWorks/Weta/Framestore, Delta Mush, film→engine (bakeDeformer, PSD/RBF, UE5 Deformer Graph, ML Deformer), casos de uso con ejemplos publicados y profesionales con código público. Léelo para elegir referencia o robar diseño. |
| `references/repo-deformers.md` | Este repo: qué deformers nativos se usan de verdad (y cuáles NO), los sistemas custom por nodos (De Boor, ribbon, auto_collision), la historia de los colliders, AdonisFX tooling, orden del stack, persistencia (.skc/.json), convenciones y QA. Léelo SIEMPRE antes de tocar deformación en el build. |

## Lo que este repo YA tiene (no lo reinventes)

- **Deformación por nodos** (sin plugins): `utils/ribbon.py` (`de_boor_ribbon` — joints
  posicionados por matrices con pesos B-spline), `utils/skincluster_curve.py`/
  `skincluster_surface.py` (reparto de pesos de skin por De Boor), `utils/blendshape.py`
  (targets partidos por curva), `tools/auto_collision.py` (push por distancia),
  `utils/correctives.py` (skill `corrective-joints`).
- **Deformers nativos en uso**: skinCluster (malla y curvas), blendShape (blink, labios,
  correctivos), deltaMush (patrón listo pero comentado en build), uvPin (labios NURBS).
  Wire/cluster/lattice/wrap/etc. NO se usan — no documentes setups sobre ellos.
- **AdonisFX**: `adonis/copyWeightsAdonis.py` — transfer/mirror/replace-mesh de pesos y
  escalares para AdnSkin/AdnFat/AdnSkinMerge/AdnMuscle/AdnRelax/AdnPush/AdnMush.
- **Stack y persistencia resueltos**: orden blendShape correctivo (frontOfChain) →
  skinCluster body → skin de correctivas (localizado por bindPreMatrix) → [deltaMush];
  export `.skc` (stack completo, sparse, DQ blendWeights) y `.json` de correctivos.
- **Patrón de plugin Python**: `tools/proxy_locator.py` (registro MFnPlugin, carga en
  userSetup) — el esqueleto a seguir si algún día se registra un deformer propio.

## Flujo de trabajo — "necesito una deformación que no tengo"

1. **Define el efecto en términos de capa**: ¿volumen por pose? ¿suavizado? ¿colisión?
   ¿sliding? ¿wrap? ¿sim de tejido? La capa determina la vía y el orden en el stack.
2. **Sube la escalera, no la saltes** (`fundamentos.md` §5):
   1. ¿Lo hace el stack nativo GPU-supported (deltaMush, tension, proximityWrap,
      falloffs) o un node network del estilo del repo? → hazlo ahí.
   2. ¿Es corrección por pose? → skill `corrective-joints` (joints) o corrective
      blendshapes (CBS manager) — no es territorio de deformer.
   3. ¿Es procedural y autocontenido? → considera Bifrost compound (cero dependencia
      binaria; la razón por la que braverabbit retiró iDeform).
   4. ¿Es simulación de músculo/fascia/grasa/piel? → AdonisFX (workflow por capas en
      `catalogo-profesional.md` §1; pesos con el Paint Tool; tooling del repo para
      transfer/mirror).
   5. Solo si nada de lo anterior llega → plugin propio (`api-openmaya.md`): prototipo
      Python (API 1.0, patrón proxy_locator) → C++ con GPU override si evalúa por frame.
3. **Antes de escribir un plugin, verifica el precedente**: ¿Maya ya lo añadió
   (custom→nativo, `fundamentos.md` §4)? ¿Hay implementación profesional open source que
   forkear (cvwrap, iDeform, ny_collisionDeformer — `catalogo-profesional.md` §4)?
   ¿El repo ya lo intentó (colliders, `repo-deformers.md` §2)?
4. **Intégralo en el build respetando el stack** (`repo-deformers.md` §5): posición
   correcta (correctivo pre-skin, suavizado post-skin), `localize` si apilas skins,
   KEEP_TYPES si es un tipo nuevo, escala global cableada al masterwalk, export/persistencia.
5. **QA** (`repo-deformers.md` §8): rest = identidad, envelope a 0 = paso anterior,
   masterwalk (escala/lejos del origen), ROM completa, ciclos, fps y Cached Playback,
   `.skc`/`.json` versionados.

## Reglas NO negociables

- **La vía por defecto de este repo son nodos nativos, no plugins.** Un plugin nuevo se
  justifica por escrito (algoritmo + rendimiento + por qué no Bifrost/nativo) o no se
  escribe. La historia de los colliders no se repite una tercera vez sin motivo.
- **Nada de deformers "fantasma"**: no montar setups sobre wire/cluster/lattice/wrap
  como si el repo los usara — no los usa. Si se introducen, se documenta aquí y se
  añaden a KEEP_TYPES.
- **El stack tiene orden fijo**: blendShape correctivo (frontOfChain) → skin body →
  skin correctivas localizado → capas de suavizado al final. Todo skin apilado pasa por
  `localize_corrective_skin` (bindPreMatrix) o equivalente.
- **Escala global**: cualquier deformer con parámetros en unidades de mundo lee el
  masterwalk (patrón `C_deltaMushScale_DCM`).
- **Naming del repo**: `_SKIN`/`_SC`/`_SKC`, `_BLS`/`_BS`, `_DMH`, `_UVP`, prefijos
  `L_/R_/C_`, `ss=True`, math/matrix nodes Maya 2024+ (nada de
  multiplyDivide/plusMinusAverage en código nuevo).
- **Un deformer que no viaja al engine no existe para el export**: el contrato es
  esqueleto `_ENV` + morphs. Lo demás se hornea (bakeDeformer/Dem Bones/PSD-RBF) o se
  queda en Maya/render.
- **Python solo para prototipos y tools one-shot**: nada que evalúe por frame en el rig
  de animación se queda en Python (GIL → Globally Serial, `api-openmaya.md` §4).
