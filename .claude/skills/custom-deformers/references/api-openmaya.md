# Escribir un deformer: API de Maya (MPx), Python vs C++, GPU y evaluación moderna

Chuleta para cuando SÍ toca escribir un deformer (o leer el de otro). Fuentes: devkit de
Autodesk (`offsetNode`), código real de cvwrap (Chad Vernon), Ryan Porter (yantor3d),
Charles Wardlaw, whitepapers "Using Parallel Maya" y "Cached Playback" de Autodesk.

## 1. Clases y registro

- **`MPxGeometryFilter`**: clase base de todo deformer. Deriva de ella y heredas la
  maquinaria interna (membership por sets/component tags, `envelope`, integración con
  `cmds.deformer -type`).
- **`MPxDeformerNode`**: añade sobre la anterior los **pesos por vértice** (`weightList`)
  — es la base habitual.
- Registro: `MFnPlugin::registerNode(name, id, creator, initialize,
  MPxNode::kDeformerNode)` (así en `pluginMain.cpp` de
  [cvwrap](https://github.com/chadmv/cvwrap/blob/master/src/pluginMain.cpp)).
- Regla oficial de Autodesk: **NO sobreescribas `compute()` — implementa `deform()`**,
  que es invocado por el `compute()` de la clase base. Devuelve `MS::kSuccess` salvo
  error real.

## 2. deform(): el bucle canónico

Firma C++: `MStatus deform(MDataBlock& block, MItGeometry& iter, const MMatrix& mat,
unsigned int multiIndex)` — `mat` = matriz local→world de la geometría; `multiIndex` =
índice de la geometría de salida (un deformer puede deformar varias mallas a la vez).

Bucle didáctico del devkit (`offsetNode.cpp`):

```cpp
for ( ; !iter.isDone(); iter.next()) {
    MPoint pt = iter.position();
    pt *= omatinv;                                         // a espacio del driver
    float w = weightValue(block, multiIndex, iter.index()); // peso pintado
    pt.y += env * w;                                       // el algoritmo
    pt *= omat;
    iter.setPosition(pt);
}
```

Autodesk avisa: offsetNode "no pretende ser un deformer práctico, solo explica
conceptos". **El deform() de producción** (patrón extraído del código real de cvwrap):

1. Leer el driver del datablock (`data.inputValue(aDriverGeo).asMesh()`); si nulo,
   `return kSuccess` (no-op elegante).
2. **Bind data cacheado en atributos del nodo** (compound array: sample weights, bind
   matrix, baricéntricas…): se computa UNA vez en un comando aparte (`cvWrap`), persiste
   en escena, se exporta a fichero (`.wrap`), es re-bindable (`-rb`) y solo se relee si
   está dirty (`setDependentsDirty` mantiene el flag). **Nunca** recalcular el bind por
   frame.
3. Lecturas EN BLOQUE: `MFnMesh::getPoints(pts, MSpace::kWorld)`,
   `itGeo.allPositions(...)`; capturar `membership` y `paintWeights` en un solo bucle.
4. Early-out: `if (envelope == 0.0f) return;`.
5. Deformar multithread (`MThreadPool::newParallelRegion`), aplicando
   `peso_pintado * envelope` por punto.
6. Escritura EN BLOQUE: `itGeo.setAllPositions(...)`.

Extra útil de la base: `accessoryAttribute()`/`accessoryNodeSetup(MDagModifier&)` — crear
un nodo auxiliar (p.ej. locator driver) al hacer `deformer -type`, que al borrarse limpia
el deformer.

## 3. Pesos pintables

- `weightValue(block, geomIndex, vtxIndex)` = *"combinación de painted weights y falloff
  weights"* (API ref). 
- Hacerlos pintables con Artisan = una línea MEL en `initialize()`. Literal de cvwrap:

```cpp
MGlobal::executeCommandOnIdle(
    "makePaintable -attrType multiFloat -sm deformer cvWrap weights");
```

- En el GPU override NO existe `weightValue()`: se lee `weightList` del datablock a mano
  con `jumpToElement(geomIndex)` (si falla, todos los pesos = 1 — comentario literal en
  cvwrap).

## 4. Python vs C++ (hechos verificados, no opiniones)

- **Python API 2.0 (`maya.api.OpenMaya`) NO expone MPxGeometryFilter/MPxDeformerNode**
  (confirmado en el foro oficial de Autodesk). Un deformer en Python se escribe con
  **API 1.0**: `maya.OpenMayaMPx.MPxDeformerNode` — aunque uses om2 para las mates
  (ejemplo real: [greenCageDeformer](https://github.com/ryusas/maya_greenCageDeformer)).
  Gotcha histórico: en Maya <2016 los estáticos eran `MPxDeformerNode_outputGeom`; desde
  2016, `MPxGeometryFilter_outputGeom` (rompió scripts — issue real en cvshapeinverter).
- **Rendimiento**: Autodesk documenta que los nodos Python se programan **"Globally
  Serial"** en Parallel Evaluation por el GIL (los hilos se serializan; la recomendación
  oficial es reescribir en C++ lo que pese —
  [Using Parallel Maya](https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2024/UsingParallelMaya.pdf)).
- **Postura profesional consistente**: Python para prototipos, tools que corren UNA vez
  (invertir un shape, un bake) y aprendizaje; C++ para todo lo que evalúe por frame en un
  rig de animación. Es el flujo que enseña Chad Vernon (curso Jiggle Deformer: prototipo
  Python → C++ production-ready) y que cuantifica Parzival Röthlein con prAttractNode
  (doble implementación .py/.mll; la C++ además ganó 10-30% con OpenMP).
- Tutorial de arranque en Python: Marieke van Neutigem, "Writing a basic deformer for
  Maya in Python" + [template](https://github.com/mvanneutigem/tutorials/blob/master/plugins/deformerTemplate.py).
- **En este repo**: el patrón de plugin Python ya existe — `tools/proxy_locator.py`
  (registro `MFnPlugin`, `initializePlugin/uninitializePlugin`, auto-loadPlugin, carga en
  userSetup). Un deformer Python nuevo seguiría ese mismo esqueleto de registro.

## 5. GPU Override (`MPxGPUDeformer`)

- Desde Maya 2016: un override GPU sustituye la implementación CPU de un deformer
  (nativo o custom) cuando el Evaluation Manager está activo y el plugin
  `deformerEvaluator` cargado. El porqué (whitepaper): en vez de deformar en CPU y subir
  la malla a la GPU cada frame, la geometría sin deformar vive en la gráfica, se deforma
  en **OpenCL** y pasa a VP2 sin read-back.
- Implementarlo = 4 piezas (guía de Ryan Porter,
  ["Here There Be (GPU) Deformers"](https://yantor3d.wordpress.com/2018/02/11/here-there-be-gpu-deformers/)):
  1. Kernel **OpenCL** (`.cl`) que replica el algoritmo (cvwrap: `cvwrap.cl`, 17 args,
     un punto por `get_global_id(0)`); se localiza en disco desde
     `MFnPlugin::loadPath()`.
  2. Subclase de `MPxGPUDeformer` con `evaluate(...)` (la firma cambió en 2018+ —
     cvwrap la condiciona por `MAYA_API_VERSION`).
  3. Subclase de `MGPUDeformerRegistrationInfo` con
     `validateNodeInGraph()/validateNodeValues()` (decidir si el nodo es soportable).
  4. Registro: `MGPUDeformerRegistry::registerGPUDeformerCreator(...)`.
- **Maya 2023+ lo simplificó**: `MPxGPUStandardDeformer` + `MOpenCLUtils`/
  `MOpenCLKernelInfo` (el `offsetNode` del devkit 2024 ya deriva de la Standard y pasa
  tablas CPU→GPU con `getFixedSetupData(name)`).
- **Cifras y reglas operativas**:
  - La GPU solo entra con mallas de más de **500 verts (AMD) / 2000 (NVIDIA)**;
    configurable con `MAYA_OPENCL_DEFORMER_MIN_VERTS`.
  - **Toda la cadena de deformación debe ser GPU-compatible**: un solo nodo no soportado
    devuelve la malla ENTERA a CPU. Lista oficial de nativos soportados: blendShape,
    cluster, deltaMush, jiggle, lattice, morph, nonlinears, proximityWrap, sculpt,
    solidify, skinCluster, softMod, tension, tweak, wire.
  - Diagnóstico: comando `deformerEvaluator` (dice por qué una cadena no entra en GPU).
  - Consejo de Charles Wardlaw ("Deformation Layering in Maya's Parallel GPU World",
    [Medium](https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82)):
    perfila SIEMPRE con el Profiler — lo que aceleraba en el viejo DG puede ralentizar en
    el mundo paralelo.

## 6. Parallel Evaluation y Cached Playback (requisitos modernos)

- Declarar dependencias correctamente (`attributeAffects`, `setDependentsDirty`) y ser
  thread-safe. Los nodos Python van en serie (GIL, §4).
- **Cached Playback**: sobreescribir `MPxNode::getCacheSetup()` para declarar soporte de
  background evaluation (ejemplos oficiales `apiMeshShape`, `simpleSimulationNode` —
  [whitepaper](https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2024/MayaCachedPlaybackWhitePaper.html)).
  Un deformer que no lo haga puede desactivar el caching de toda la escena (barra azul
  del timeline → apagada).

## 7. Component tags y falloffs (Maya 2022+)

- Sustituyen groupParts/groupId/tweak/objectSets: membership por expresión (`!tag`
  desde 2022.1) y falloffs procedurales por ramp/volumen reutilizables entre deformers.
- Ojo: al salir **rompieron los deformers de terceros** (documentado en iDeform: había
  que desactivar component tags en Preferences > Animation). Si un deformer ajeno no
  deforma nada en 2022+, revisa esto primero.

## 8. Alternativas antes de compilar (recordatorio)

- **proximityWrap** (2020): GPU, topología-independiente, sin rest state, multi-driver —
  mata la mayoría de wraps caseros. `uvPin`/`proximityPin` + `offsetParentMatrix` matan
  follicles/rivets.
- **Bifrost**: un graph sobre la malla actúa como deformer, itera geometría
  automáticamente y corre multithreaded sin C++. Declaración de Ingo Clemens al retirar
  iDeform: con Bifrost "los efectos pueden crearse con custom compounds con más
  flexibilidad; no habrá más updates ni compilaciones". Casos publicados: push, noise y
  collider deformers (este último: prototipo Python → conversión íntegra a Bifrost en
  vez de portar a C++).
- El grafo matricial nativo (la vía de este repo): ver `repo-deformers.md` §2.
