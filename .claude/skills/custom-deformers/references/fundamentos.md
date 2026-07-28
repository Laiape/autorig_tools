# Fundamentos: qué son los custom deformers y cuándo (no) escribir uno

## 1. Qué es un deformer

Definición canónica del devkit de Autodesk (cabecera de `offsetNode.cpp`, el ejemplo
oficial): *"A deformer is a node which takes any number of input geometries, deforms
them, and places the output into the output geometry attribute"*. Un nodo del dependency
graph que recibe geometría por `inputGeom`, **mueve puntos** y escribe en `outputGeom`.

En la jerarquía del API la clase base es el **geometry filter** (`MPxGeometryFilter`), de
la que derivan TODOS los deformers de Maya: skinCluster, blendShape, deltaMush, wire,
lattice, tension… ([API ref](https://help.autodesk.com/cloudhelp/2024/ENU/MAYA-API-REF/cpp_ref/class_m_px_geometry_filter.html)).
Un deformer NO mueve transforms ni joints: opera sobre componentes (vértices/CVs), aguas
abajo del esqueleto.

## 2. Qué es un CUSTOM deformer — y las 4 vías de conseguir uno

**Custom deformer** en sentido estricto: un deformer que el TD escribe como **plugin**
(C++ o Python) derivando de `MPxDeformerNode`/`MPxGeometryFilter` y registrándolo con
`MFnPlugin::registerNode(..., MPxNode::kDeformerNode)` (así lo hace cvwrap en
`pluginMain.cpp`). Al derivar de la clase base heredas gratis: atributo `envelope`,
membership (sets/component tags), **pesos por vértice pintables** y la integración con
`cmds.deformer(type=...)`.

En la práctica profesional hay CUATRO vías para una deformación que Maya no trae:

| Vía | Qué es | Cuándo | Ejemplos |
|---|---|---|---|
| **Plugin MPx** (el custom deformer "de verdad") | nodo compilado (C++) o Python | algoritmo inexistente en Maya + evaluación por frame + rendimiento | cvwrap, delta mush original, MG_collisionBulge, colliders de faldas |
| **Node network nativo** | red de nodos matrix/math que deforma vía joints, pins o pesos | cuando el grafo nativo llega; cero dependencias binarias | **la vía de este repo**: ribbons De Boor, correctivas, auto_collision; filosofía Cult of Rig (Raffaele Fragapane: nodos de matrices en vez de constraints, [cultofrig.com](http://www.cultofrig.com)) |
| **Bifrost compound** | graph sobre la malla que itera geometría automáticamente, multithreaded | efectos procedurales sin compilar; sustituto declarado de plugins pequeños | push/noise/collider deformers en Bifrost; Ingo Clemens retiró iDeform en favor de Bifrost (README de [iDeform](https://github.com/IngoClemens/iDeform)) |
| **Comercial** | plugin de terceros con soporte | sim de músculo/piel/grasa que no vas a escribir tú | **AdonisFX** (este pipeline), Ziva VFX (hoy interno de DNEG) |

Matiz importante: los sistemas por nodos de este repo (skinning De Boor, ribbon matricial)
NO son deformers en sentido estricto — mueven joints o reescriben pesos de un skinCluster
existente — pero cumplen el mismo papel en el stack y son la razón de que este repo no
necesite plugins. Ver `repo-deformers.md`.

## 3. Por qué los estudios escriben deformers custom

Motivos reales documentados, no teóricos:

1. **Rendimiento sobre el nativo**: cvwrap existe porque el wrap de Maya era lento y no
   re-bindable — README literal: *"faster than Maya's wrap deformer, can be rebounded,
   has a GPU implementation"* ([chadmv/cvwrap](https://github.com/chadmv/cvwrap)).
2. **Cambiar la economía del rigging**: Delta Mush (Rhythm & Hues, deformer del framework
   propietario Voodoo desde 2010) se formuló para que binds simples + un deformer genérico
   inteligente sustituyeran el tuning meticuloso por vértice; tan barato que los crowds
   llevaban deformación hero (paper DigiPro/SIGGRAPH 2014, Mancewicz/Derksen/Rijpkema/Wilson,
   [ACM](https://dl.acm.org/doi/10.1145/2633374.2633376)).
3. **Efectos que el stack nativo no da**: sticky lips (prAttractNode de Röthlein — caso de
   uso declarado *"sticky area between lips"*), colisión sin sim (iCollide,
   ny_collisionDeformer), cages (greenCageDeformer), skin sliding (iSkinDeform).
4. **Capas anatómicas propietarias**: Weta Tissue, Pixar curvenet/Profile Mover,
   DreamWorks Premo, Framestore FAT — el deformer stack ES ventaja competitiva de estudio
   (detalle en `catalogo-profesional.md` §2).

## 4. El ciclo de vida: custom → nativo

Patrón histórico que hay que conocer antes de escribir nada, porque a menudo la feature
ya llegó a Maya:

- **Delta Mush** (R&H 2010, paper 2014) → nodo nativo `deltaMush` en Maya 2016; variante
  runtime Direct Delta Mush (Le & Lewis, SIGGRAPH 2019) implementada en UE.
- **cometMuscle/poseDeformer** (Michael Comet) → Autodesk lo compró → **Maya Muscle**.
- **cvShapeInverter** (Chad Vernon) → comando nativo `invertShape` (2016.5) lo hizo
  innecesario (lo dice su propio README).
- **Tension**, morph, solidify: plugins caseros históricos → deformers nativos.
- **Wrap** → `proximityWrap` (2020): GPU, topología-independiente, multi-driver.

Regla derivada: antes de escribir un deformer, comprueba qué añadió Maya en las últimas
versiones (2020: proximityWrap/uvPin/proximityPin/offsetParentMatrix; 2022: component
tags + falloffs; 2024: math nodes; 2025.2: ML Deformer nativo).

## 5. La escalera de decisión profesional

Síntesis de las fuentes (paper Delta Mush, Wardlaw, Clemens, Vernon) — de más barato a
más caro:

1. **Stack nativo GPU-supported** (skinCluster + deltaMush + tension + proximityWrap +
   falloffs) mientras aguante. La lista de deformers con soporte GPU es pública
   ([Autodesk](https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-1B2D8791-55F7-4FF8-8DFC-56AC86630FFC)).
2. **Node network / joints correctivas** (la vía de este repo — skill `corrective-joints`)
   y blendshapes correctivos conducidos por pose (weightDriver RBF de braverabbit es el
   estándar de facto; extracción con `invertShape`).
3. **Bifrost compound** para efectos procedurales sin dependencia binaria.
4. **AdonisFX** para lo que sea simulación de tejido (músculo/fascia/grasa/piel) — ya
   está en el pipeline y tiene tooling propio en el repo.
5. **Plugin propio** SOLO cuando: el algoritmo necesita bind data pesado/estructuras
   aceleradoras (wrap, cages, solvers), debe evaluar por frame más rápido de lo que el
   grafo da, o necesita kernel GPU propio. Prototipo en Python → producción en C++ (el
   flujo que enseña Chad Vernon en sus cursos de CGCircuit).

## 6. Los costes de un plugin (lo que se paga después)

- **Compilación/ABI**: los binarios (.mll/.so/.bundle) se recompilan por versión mayor de
  Maya y por plataforma. Es la razón por la que Röthlein distribuye prAttractNode también
  en Python ("las C++ no están compiladas para todos los OS/versiones") y por la que
  Ingo Clemens cerró repos ("no más compilaciones para nuevas versiones"). Autodesk
  publica guía de migración de API cada año.
- **Unknown nodes**: toda escena que contenga el nodo escribe `requires` del plugin; sin
  el plugin la escena abre con unknown nodes (limpiar = `ls(type="unknown")` + delete +
  `unknownPlugin -remove`). **Un deformer custom es una dependencia dura de por vida en
  cada escena que lo toque** — los estudios los versionan y distribuyen como módulos.
- **Compatibilidad de features nuevas**: los component tags de Maya 2022 rompieron los
  deformers de terceros al salir (documentado en iDeform: había que desactivarlas en
  Preferences > Animation).
- **Evaluación moderna**: un nodo que no declare bien dependencias o no soporte cached
  playback (`getCacheSetup`) puede degradar la escena entera; un solo deformer no
  GPU-compatible en la cadena devuelve TODA la malla a CPU (ver `api-openmaya.md` §6).
- **Este repo ya pagó esta lección**: el plugin C++ de colliders de falda se integró y se
  eliminó dos commits después en favor de nodos nativos, y la versión por nodos también
  se acabó retirando (historia completa en `repo-deformers.md` §2).

## 7. Film vs juego (resumen — detalle en catalogo-profesional.md §3)

En film la malla se cachea (Alembic/USD): cualquier deformer vale. En engine el skeletal
mesh se evalúa como **joints (LBS/DQ) + morph targets**: ningún deformer de Maya viaja.
Salidas: hornear a joints (`bakeDeformer`, Dem Bones de EA), hornear a
correctivas/PSD-RBF (poseInterpolator, PoseWrangler→Pose Driver Connect), o reimplementar
en engine (UE5 Deformer Graph / ML Deformer entrenado con la deformación offline de Maya).
Para este repo: el esqueleto `_ENV` + morphs es el contrato de export — lo que un deformer
aporte y no esté horneado, no existe en el engine.
