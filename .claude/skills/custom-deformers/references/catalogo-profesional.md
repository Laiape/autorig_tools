# Catálogo profesional: deformers custom de producción, stacks de estudio y film→engine

Panorama de QUIÉN usa custom deformers y PARA QUÉ, con fuentes (autor/estudio + URL).
Sirve para justificar decisiones ("esto lo hace así la industria") y para robar diseño.

## 1. Deformers comerciales (custom deformers "de compra")

### Ziva VFX — la referencia FEM, y su moraleja de pipeline

Simulación FEM de músculo/grasa/piel como nodos de Maya: `zSolver`, `zTissue`, `zBone`,
`zCloth`, `zAttachment` (mapas pintables), `zMaterial`, `zTet`, `zFiber` (excitación
muscular) y `zLineOfAction` (curvas que excitan la fibra al contraerse). Serialización de
setups con zBuilder ([docs.zivadynamics.com](https://docs.zivadynamics.com/),
[zBuilder](https://ziva-vfx.readthedocs.io/en/latest/zBuilder.nodes.ziva.html)).

Cronología: Unity lo compra en 2022 → lo **descataloga en abril de 2024** → DNEG adquiere
licencia exclusiva del IP y lo vuelve interno (Dune 2, Godzilla x Kong; SciTech Award 2025)
([Unity](https://unity.com/blog/news/update-about-ziva),
[DNEG](https://www.dneg.com/news/dneg-acquires-exclusive-license-to-ziva-technologies-from-unity)).
**Moraleja**: un deformer comercial es una dependencia dura del pipeline — puede morir.
El hueco comercial lo ocupa hoy AdonisFX
([CG Channel, "Is AdonisFX 2.0 the new Ziva VFX?"](https://www.cgchannel.com/2026/03/is-adonisfx-2-0-the-new-ziva-vfx/)).

### AdonisFX (Inbibo) — el custom deformer comercial de ESTE pipeline

Doc oficial versionada: [inbibo.co.uk/docs/adonisfx](https://inbibo.co.uk/docs/adonisfx/v1.7.2/introduction).
El repo ya lo soporta (`adonis/copyWeightsAdonis.py` — ver `repo-deformers.md` §4).

**Deformers/nodos (prefijo `Adn`)**:
| Nodo | Qué es | Claves |
|---|---|---|
| `AdnMuscle` | sim muscular volumétrica | constraints internos + attachments/slide-on-segment externos, preservación de volumen, activación de fibras que modula rigidez; pesos por constraint pintables, un vértice puede pesar distinto por CADA attachment |
| `AdnRibbonMuscle` | músculo plano/membrana | mismos constraints, para tejido rápido |
| `AdnSkin` | sim de piel sobre targets internos | 3 pesos pintables NORMALIZADOS entre sí por vértice: **Hard** (dv 1.0, rígido al closest point del target), **Soft** (doc recomienda flood ~0.2), **Slide** (dv 0.0, pintar solo donde debe deslizar). Pintar AL FINAL los valores prioritarios — la normalización interna sobrescribe |
| `AdnFat` | capa de grasa fascia↔piel | también en Houdini |
| `AdnGlue` | combina músculos simulados en UNA malla con glue constraints | compacta musculatura, evita huecos; en 2.0 lleva self-collisions triángulo-a-triángulo |
| `AdnSkinMerge` | mezcla malla simulada + malla de animación en la malla final | el hand-off CFX→pipeline |
| `AdnSimshape` | facial: dinámica sobre el rig facial | activaciones calculadas en vértices de piel; opcionalmente desde Muscle Patches aprendidos (ML: neutra + targets de todas las expresiones) |
| `AdnRelax` / `AdnPush` / `AdnMush` | utilitarios post-sim | sin mapas de peso (se mirrorizan por escalares — ya lo explota `copyWeightsAdonis`) |

**Drivers**: `AdnSensorPosition` (+ distancia/ángulo) computa velocidad/aceleración de un
transform y la **remapea a activaciones** de los deformers (p.ej. activar músculo por
aceleración del hueso); `AdnLocator*` los visualiza
([sensors](https://inbibo.co.uk/docs/adonisfx/v1.6.0/maya/nodes/sensors)).

**Workflow canónico por capas** ([A Simple Setup](https://inbibo.co.uk/docs/adonisfx/v1.7.2/maya/simple_setup)):
un AdnMuscle por músculo → combinar (AdnGlue) → fascia por shrinkwrap de la piel sobre
músculos → fascia = AdnSkin con músculos como targets → grasa = AdnFat/AdnSkin sobre
fascia → piel = AdnSkin sobre grasa → AdnSkinMerge a la malla final. Es el deformer
stack de estudio (§2), en versión comercial.

**Tooling**: Paint Tool (pintar tendon weights genera estimación inicial de dirección de
fibras; fibras/tendones SOLO en el frame de inicialización), Mirror Tool, Export/Import.

**Estado 2026**: AdonisFX 2.0 (mar 2026) añade Houdini nativo (SOPs, mismos rigs idénticos
en ambos DCC), músculo anisótropo y self-collisions
([nota de prensa](https://inbibo.co.uk/news/adonisfx-2-0-press-release)). Adonis 2.1
(jul 2026) divide la marca en **AdonisFX + AdonisML** (ML Deformer pose-based entrenado
sobre el personaje pesado + SmartTissue + transferencia de anatomía topology-independent)
([CG Channel](https://www.cgchannel.com/2026/07/inbibo-releases-adonis-2-1-with-adonisml/)).
Compatibilidad: Maya 2023+, Houdini 20+.

### Otros hitos

- **Weta Tissue**: FEM músculo/piel/grasa propietario (Clutterbuck, Jacobs, Dorling) —
  Avatar, Apes, The Hobbit; SciTech Award
  ([wetafx.co.nz](https://www.wetafx.co.nz/research-and-tech/technology/tissue)). James
  Jacobs fundó después Ziva: continuidad directa Tissue→Ziva.
- **Weta Animatomy** (Avatar 2, SIGGRAPH Asia 2022): facial por curvas musculares
  (strains) en vez de FACS puro
  ([fxguide/Letteri](https://www.fxguide.com/fxfeatured/exclusive-joe-letteri-discusses-weta-fxs-new-facial-pipeline-on-avatar-2/)).
- **cometMuscle / poseDeformer** (Michael Comet, hoy Pixar): el poseDeformer open source
  (PSD real: shapes en joint-space reaplicadas tras el skinCluster) y el músculo que
  **Autodesk compró y convirtió en Maya Muscle**
  ([comet-cartoons.com](https://www.comet-cartoons.com/maya.html)). Precedente histórico
  del patrón "deformer custom → feature nativa".

## 2. Deformer stacks de estudio (deformación por capas)

La idea compartida: la malla final atraviesa CAPAS ordenadas — skeleton/skinning →
músculo/fascia → skin slide → smooth/tension → correctivas → cloth — y las capas caras
son deformers propietarios.

- **Rhythm & Hues — Delta Mush** (el caso canónico de la capa smooth): deformer
  propietario del software Voodoo, en TODOS los rigs de R&H desde 2010. Paper SIGGRAPH
  2014 (Mancewicz, Derksen, Wilson): binds simples + deformers bastos + suavizado que
  preserva detalle; tan barato que hasta los crowds llevan deformación hero
  ([ACM](https://dl.acm.org/doi/10.1145/2614106.2614144)). Autodesk lo hizo nativo
  (`deltaMush`) — segundo gran "custom → estándar".
- **Pixar (Presto)**: tándem **curvenet + Profile Mover** — deformación detail-preserving
  controlada por curvas 3D sobre la superficie (SIGGRAPH 2022, de Goes/Sheffler/Fleischer),
  usado desde Turning Red; en Inside Out 2 la mano va COMPLETA por curvenet compartible
  entre personajes, sin rigging por geometría
  ([Elemental talk](https://research.pixar.com/docs/2023.SiggraphTalks.NTSHFG.pdf),
  [Inside Out 2 talk](https://research.pixar.com/docs/2024.SiggraphTalks.HNSZ.pdf)).
- **DreamWorks (Premo)**: facial por Featurelines + "sistema de deformación altamente en
  capas" con deformer de curvas en la base, evaluando a ~60 fps con manipulación directa
  (DigiPro 2015, [ACM](https://dl.acm.org/doi/10.1145/2791261.2791262)); motor multihilo
  LibEE (DigiPro 2012).
- **Disney — dRig** (SIGGRAPH **2012**, Smith/Goldberg/McLaughlin/Lin/Hanner): framework
  OO de construcción de rigs, reuso por elemento
  ([PDF](https://media.disneyanimation.com/uploads/production/publication_asset/7/asset/dRigTalk_v05.pdf)).
- **Framestore — FAT** (Framestore Anatomy Toolkit, SIGGRAPH 2026): sustituye "legacy
  deformer workflows" por plataforma de sim end-to-end con constraints auto-construidos
  por etiquetado geométrico; **converge Rigging y Creature FX**
  ([Framestore](https://www.framestore.com/events/siggraph-la-2026)). Tendencia: del
  stack artesanal a la plataforma anatómica automatizada.
- **MPC — The Lion King**: sim muscular corre automáticamente al bakear la animación; el
  fur recibe el movimiento de muscle+skin sim
  ([fxguide](https://www.fxguide.com/fxfeatured/how-virtual-production-worked-on-set-of-the-lion-king/)).

## 3. Film vs juego: el deformer NO viaja al engine

En film la malla se cachea (Alembic/USD) y se renderiza: cualquier deformer vale. En
engine el skeletal mesh se evalúa en runtime como **joints (LBS/DQ) + morph targets**: un
deformer de Maya no existe allí. Vías de salida, de más simple a más moderna:

1. **`cmds.bakeDeformer`** (Skin > Bake Deformation to Skin Weights): resuelve por
   optimización pesos de skinning que aproximan CUALQUIER deformación (skin
   decomposition sobre pares malla/pose). Funciona especialmente bien con rigid bind y
   delta mush ([Autodesk](https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-DD430C9B-95E7-4EBB-8D2B-A566018B4AC4)).
   El equivalente de estudio es **Dem Bones** (skinning decomposition open source de EA).
2. **PSD/RBF exportable**: nativo Maya = Pose Editor + `poseInterpolator`
   ([Autodesk](https://help.autodesk.com/cloudhelp/2022/ENU/Maya-CharacterAnimation/files/GUID-45D389D6-B8E4-4225-B27B-9927BB61C28D.htm));
   Epic **PoseWrangler → Pose Driver Connect**: front-end Maya de los MISMOS solvers RBF
   que evalúa UE — exporta JSON+FBX y genera el AnimBP equivalente: correctiva idéntica
   en DCC y runtime ([repo](https://github.com/chrisevans3d/poseWrangler),
   [blog UE](https://www.unrealengine.com/en-US/blog/create-more-realistic-animation-in-less-time-with-pose-driver-connect),
   [MetaHuman RBF](https://dev.epicgames.com/documentation/metahuman/authoring-rbf-in-maya)).
3. **UE5 Deformer Graph** ("Optimus"): escribir deformers DENTRO del engine como compute
   shaders (grafos + kernels HLSL sobre cualquier skinned mesh)
   ([doc](https://dev.epicgames.com/documentation/en-us/unreal-engine/deformer-graph-in-unreal-engine)).
4. **UE5 ML Deformer** — el flujo "deformer custom en Maya → ML en runtime": generar la
   deformación buena en Maya (músculo/sim/stack completo), exportar FBX (poses) +
   Alembic (malla deformada), entrenar en UE, evaluar en runtime.
   Plugin oficial de Maya para generar datos (ROM aleatorio, por defecto **50.000 poses**:
   [ue4plugins/MayaMLDeformer](https://github.com/ue4plugins/MayaMLDeformer)). Modelos:
   **Neural Morph Model** (morphs comprimidos + red en CPU que emite pesos de morph por
   frame desde rotaciones de huesos/curvas; explicación de John van der Burg, Epic:
   [80.lv](https://80.lv/articles/unreal-engine-5-1-s-updated-ml-deformer-explained)),
   Nearest Neighbor (ropa), Vertex Delta (legacy)
   ([framework](https://dev.epicgames.com/documentation/en-us/unreal-engine/ml-deformer-framework-in-unreal-engine)).
5. **Maya ML Deformer nativo** (2025.2): aproxima deformación cara entrenando desde
   animación (mocap/keys/Pose Generator) con Driver Controls como input — para trabajar
   interactivo y volver al rig real en render
   ([Autodesk](https://help.autodesk.com/cloudhelp/2025/ENU/Maya-CharacterAnimation/files/GUID-F386DC20-6C66-40D7-AD40-2C1B66937A71.htm)).
   Precedente académico-industrial: "Fast and Deep Deformation Approximations"
   (Bailey/Otte/DiLorenzo/O'Brien, SIGGRAPH 2018, con DreamWorks — lineal esqueleto +
   residual no lineal aprendido, 5-10x más rápido); crowds por ML en Golaem (DigiPro 2024,
   [arXiv](https://arxiv.org/abs/2406.09783)). AdonisML (§1) es la misma idea en
   producto.

## 4. Casos de uso que justifican un deformer custom (ejemplos publicados)

| Caso | Ejemplos con fuente |
|---|---|
| Sticky lips / zipper | demos de **Hans Godard** ([Sticky Lips Deformer](https://www.youtube.com/watch?v=1G7xYWod2bw)) — atrae vértices a una curva con falloff; comercial: Lip Deformer de M. Hasanzadeh ([Gumroad](https://mh999.gumroad.com/l/smdpmc)); open source aplicable: prAttractNode de Parzival Roethlein |
| Colisión piel-piel sin sim | **iCollide** (iDeform, Ingo Clemens — discontinuado en Maya 2024, migrado a Bifrost: [GitHub](https://github.com/IngoClemens/iDeform)); ny_collisionDeformer de Nazmi Printer (multi-collider + bulge + smooth, paintable: [GitHub](https://github.com/nazmiprinter/ny_collisionDeformer)); #rigTip de colisión por matrices de Marco D'Ambros ([Vimeo](https://vimeo.com/channels/1321512/49104367)) |
| Tension maps (wrinkles por tensión) | nodo **tension** de wiremas ([GitHub](https://github.com/wiremas/tension)), Tensify ([GitHub](https://github.com/mehdiahmadicg/tensify)), jsStress; Maya trae **Tension deformer nativo** desde 2017u3 ([Autodesk](https://help.autodesk.com/view/MAYAUL/2026/ENU/?guid=GUID-57E188A4-4CA8-41AA-AA50-57B8D7E5C340)) |
| Skin sliding sobre fascia | **iSkinDeform** (braverabbit); versión sim: Slide de AdnSkin, attachments de Ziva |
| Wrap high-res sobre low-res | **cvwrap** (Chad Vernon): más rápido que el wrap de Maya, re-bindable, GPU, inverted front-of-chain blendshapes ([GitHub](https://github.com/chadmv/cvwrap)); hay forks de estudio en producción (Sinking Ship) |
| Delta mush y variantes | paper R&H (§2); port a Unity de ejemplo ([ahmidou](https://github.com/ahmidou/Unity-deltamush)) |
| Cualquier deformación → joints | **Skinning Converter** y RBF Solver de Hans Godard; su MTJ aprende posiciones de joints desde secuencias de malla ([CGPress](https://cgpress.org/archives/hans-godards-new-tool-uses-machine-learning-for-muscle-deformation.html)); Dem Bones |
| Volumen muscular | zFiber/zLineOfAction (Ziva), activaciones AdnMuscle, Maya Muscle/cometMuscle, Tissue/FAT |

## 5. Profesionales con código/material público (para robar diseño)

- **Chad Vernon** — cvwrap, cmt, cvshapeinverter (invertir shapes a través de la cadena
  para correctivas front-of-chain). Serie en CGCircuit construyendo cvwrap desde cero.
  [github.com/chadmv](https://github.com/chadmv) · [chadvernon.com](https://www.chadvernon.com/)
- **Ingo Clemens (brave rabbit)** — SHAPES, **weightDriver** (RBF/vector-angle, estándar
  de facto para correctivas RBF en Maya), brSmoothWeights, rampWeights, iDeform.
  [braverabbit.com](https://www.braverabbit.com/) · [weightDriver wiki](https://github.com/IngoClemens/weightDriver/wiki)
- **Marco D'Ambros** — tutoriales de deformers (dynamic weight maps con Bifrost, colisión
  por matrices, optimización), mentor del curso Maya API C++ de Rigging Dojo, eBook
  gratuito "Making Plugins for Maya" (construye el tcHarmonicDeformer, usa Dem Bones).
  [marcodambrostd.com](https://marcodambrostd.com/tutorials) ·
  [eBook](https://www.riggingdojo.com/2019/12/24/free-maya-api-training-ebook/)
- **Hans Godard** — Character TD en Naughty Dog; sticky lips, Skinning Converter, RBF
  Solver, MTJ (ML muscular). [vimeo.com/user14195390](https://vimeo.com/user14195390)
- **Perry Leijten** — SkinningTools v5 (usada en los estudios de Sony).
  [github.com/peerke88/SkinningTools](https://github.com/peerke88/SkinningTools)
- **Roy Nieterau (BigRoy)** — nodos para deformar matrices con los algoritmos de los
  deformers no lineales, utilidades de node-math por Python; gists de referencia.
  [github.com/BigRoy](https://github.com/BigRoy)
- **Michael Comet** — poseDeformer/cometMuscle (→ Maya Muscle); hoy Pixar.
  [comet-cartoons.com/maya.html](https://www.comet-cartoons.com/maya.html)
- **Chris Evans** — poseWrangler, tutorial clásico de músculo.
  [github.com/chrisevans3d/poseWrangler](https://github.com/chrisevans3d/poseWrangler)
- **Dhruv Govil** — MLDeform (ML de deformación open source educativo).
  [github.com/dgovil/MLDeform](https://github.com/dgovil/MLDeform)
- **Shizuo Kaji** — deformers académicos con código: ProbeDeformer, CageDeformer,
  PoissonMLS. [github.com/shizuo-kaji](https://github.com/shizuo-kaji)
- **Marieke van Neutigem** — tutorial "Writing a basic deformer for Maya in Python"
  ([blog](https://mariekevanneutigem.nl/blog/bL6m/writing-a-basic-deformer-for-maya-in-python))
