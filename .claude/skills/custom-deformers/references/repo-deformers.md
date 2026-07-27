# El repo: qué deformación hay en `autorig_tools`, cómo se apila y cómo se persiste

Chuleta técnica para trabajar con deformers en este repo SIN documentar cosas que no
existen ni romper el stack. Encuadre: la deformación real de este rig se apoya en TRES
pilares — **skinCluster** (piel + curvas), **ribbons matriciales De Boor** (mecánica del
rig, sin NURBS ni follicles) y **corrective joints por nodos** (skill `corrective-joints`).
Todo lo demás (deltaMush, colliders…) es opcional, histórico o tooling.

## 1. Deformers nativos que SÍ se usan (y dónde)

| Deformer | Dónde | Para qué |
|---|---|---|
| `skinCluster` | omnipresente. Módulos faciales sobre CURVAS: labios (`jaw_module_bezier.py:446,687,1433`), NURBS de slide de mandíbula (`C_jawSlideNRB_SKIN`), párpados (`eyelid_module.py:472`); body via `skin_manager_api` | deformación principal. Firma típica: `cmds.skinCluster(jnts, geo, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1)` |
| `blendShape` | blink (`eyelid_module.py:436-466`, mezcla curvas up/down/blink), curva media de labios (`C_midLips_BS`), correctivos (`corrective_blendshape_manager.py:375`) | mezclar curvas guía y correctivas esculpidas (`frontOfChain=True, origin="local"`) |
| `deltaMush` | `create_rig.apply_delta_mush()` (`create_rig.py:366-398`) — **COMENTADO en build (94-95)**: patrón listo, hoy no corre | capa de suavizado post-skin: `smoothingIterations=10, smoothingStep=0.5, pinBorderVertices=True`, sufijo `_DMH`, `.scale` cableado a `C_deltaMushScale_DCM` (decompose del masterwalk) para sobrevivir a la escala global |
| `uvPin` | `jaw_module_nurbs.py:902` (`*_UVP`) | pinear vectores aim/up sobre las NURBS de labios |

**NO usados en el build** (solo aparecen en listas de tipos a preservar/detectar:
`create_rig.hide_all_utility_nodes()` KEEP_TYPES, `restore_node_visibility.py`,
`model_checker.py:468`): `wire`, `cluster`, `lattice/ffd`, `nonLinear`, `wrap`,
`proximityWrap`, `shrinkWrap`, `sculpt`, `jiggle`, `tension`, `softMod`, `muscle`,
`proximityPin`, `morph`. No documentes setups sobre ellos como si existieran: los labios
van por skinCluster sobre curvas + blendShape + uvPin, NO por wire/cluster.

## 2. Sistemas de deformación custom POR NODOS (la vía de este repo)

Este repo implementa "custom deformers" sin plugins: redes de nodos nativos + API de
OpenMaya para pesos. El núcleo matemático compartido es **`utils/de_boor_core.py`**
(`knot_vector`, `de_boor(n,d,t,kv)` → pesos B-spline por CV).

- **`utils/ribbon.py` — `de_boor_ribbon(...)`** (línea 55): el deformador custom
  principal. N joints cuyos position/tangent/up/scale salen de combinar matrices de CVs
  con pesos De Boor, todo con nodos (`pickMatrix`, `blendMatrix`, `aimMatrix`,
  `wtAddMatrix`, `fourByFourMatrix`…). Sustituye al ribbon clásico follicle-on-NURBS.
  Lo consumen arm/leg (`de_boor_ribbon_callout`), neck, eyebrow, spine…
  `_insert_tangent_cvs` añade CVs de tangente para que el bend llegue.
- **`utils/skincluster_curve.py` — `split_with_curve(verts, jnts, crv)`**: NO crea
  deformador; **reescribe pesos** de un skinCluster existente. Por vértice:
  `MFnNurbsCurve.closestPoint` → parámetro → `de_boor()` → reparte el peso total entre
  los joints según la base B-spline. `MFnSkinCluster.getWeights/setWeights` en bloque.
- **`utils/skincluster_surface.py` — `split_with_surface(verts, jnts_grid, srf)`**: igual
  en 2D (rejilla de joints U×V sobre NURBS surface, De Boor en U y en V).
- **`utils/blendshape.py` — `split_with_curve(mesh, base_mesh, crv, output_names)`**:
  reparte el delta (deformada − base) en N mallas target según De Boor a lo largo de una
  curva (`MFnMesh.setPoints`) → targets de blendShape "cortados" procesalmente.
- **`tools/auto_collision.py` — `auto_collision_rig(colliders, target, axis, direction)`**:
  colisión por distancia que empuja un JOINT (no la malla): `distanceBetween` por collider
  (worldMatrix directo a `inMatrix1/2`), `plusMinusAverage` en modo Minimum para el más
  cercano, `remapValue` (interp spline) distancia→push, salida a `translate{axis}` de un
  offset group. Attrs `collideRadius`/`pushAmount`. Legacy nodes — si lo tocas, migra a
  math nodes 2024+.
- **`utils/correctives.py`**: primitivas de corrective joints (skill `corrective-joints`).
- Las UIs de De Boor viven en `ui/deboor_tools_UI.py` (líneas 455, 557, 699).

### Historia de los colliders de falda (leer antes de reintentarlo)

Tres iteraciones, trazables por git (el árbol actual ya no las tiene):

1. `b1ab588` añadió `scripts/tools/colliders/` = fork del **plugin C++
   `azagoruyko/colliders`** (Apache 2.0): nodos deformadores `bellCollider`,
   `skirtBellCollider`, `planeCollider` (`colliders.mll`), usados en arm/leg.
2. `8d23ad3` lo ELIMINÓ y lo sustituyó por `utils/native_collider.py`: la misma colisión
   falda↔pierna 100% con nodos (closest-point a cápsula hip→knee→ankle, dot/normalize,
   `condition` LessThan, empuje fuera del radio).
3. `82f7bf2` eliminó también el script nativo.

Moraleja del repo: el plugin binario se descartó (dependencia de compilación/versión) y la
versión por nodos también (coste/beneficio). `git show 8d23ad3:scripts/utils/native_collider.py`
y `git show b1ab588:scripts/tools/colliders/__init__.py` son la referencia de diseño si se
retoma — la decisión plugin vs nodos ya se pagó una vez aquí.

## 3. Plugins propios del repo (qué hay y qué NO hay)

- **NO hay ningún `MPxDeformerNode`** en el árbol actual, ni `.mll`/`.so`.
- `tools/proxy_locator.py`: `ProxyLocatorNode(MPxLocatorNode)` + `MPxDrawOverride` (VP2).
  Es el ejemplo vivo del repo de plugin Python registrado con `MFnPlugin` —
  `initializePlugin/uninitializePlugin`, auto-`loadPlugin` del propio `.py`, carga en
  `userSetup.init_proxy_locator()` (ruta hardcodeada `C:/GIT/...` — parametrizar si se toca).
  Un deformer Python nuevo seguiría exactamente este patrón de registro/carga.
- `tools/ik_fk_match.py`: `MPxCommand` (comando, no deformer).
- Otros `loadPlugin`: solo `ikSpringSolver` (`quadruped/leg_module.py:595,640`).

## 4. AdonisFX: el custom deformer COMERCIAL del pipeline

`adonis/copyWeightsAdonis.py` (~2700 líneas) es el tooling propio para los deformadores
de AdonisFX (Inbibo). Tipos soportados (`_DEFORMER_MAPS`, líneas 116-124): **AdnSkin,
AdnFat, AdnSkinMerge, AdnMuscle, AdnRelax, AdnPush, AdnMush**.

- **Mapas de pesos por tipo**: AdnSkin 13 mapas (`weightMap`,
  `compressionResistanceMap`, `stretchingResistanceMap`, `hard/soft/slideConstraintsMap`,
  `massMap`…), AdnFat 6 (incl. `volumeShapePreservationMap`), AdnMuscle 11 (incl.
  `attachmentsToGeometry/Transform`, `fibersMultiplier`, `slideOnGeometry/Segment`).
  Relax/Push/Mush no tienen mapas → se mirrorizan por escalares.
- Ruta de attr: `node.<listAttr>[0].<elemAttr>[i]` (`_attr_path`). Copia índice a índice
  con misma topología; closest-point + interpolación **baricéntrica** (`_barycentric`) con
  distinta topología o mirror X. Localiza nodos con `_find_deformer` en el history.
- Crea deformadores con `cmds.deformer(shape, type="Adn...", frontOfChain=True)`.
- 4 pestañas: Transfer, Copy/Paste (buffer + mirror X), Mirror L→R (Relax/Push/Mush),
  Replace Mesh (`replace_mesh_in_setup`: transfiere skinCluster + todos los Adn a una
  malla nueva, con snapshot del grafo auxiliar).

## 5. Orden del stack (deformer order) — dónde se decide

Secuencia de `create_rig.build()` (líneas 65-108):

```
make_rig (módulos: skins de curvas, ribbons, blendShapes de blink/labios)
  → import_weights()            # skin_manager_api aplica skins de body
  → localize_correctives()      # bindPreMatrix en skins "*corrective*"
  → apply_delta_mush()          # COMENTADO — iría al final del stack
  → import_corrective_blendshapes()  # frontOfChain → quedan PRE-skin
  → picker / cleanup
```

Stack resultante en la malla (de dentro hacia fuera): **blendShape correctivo
(frontOfChain) → skinCluster body → skinCluster correctivas (localizado) → [deltaMush]**.

Mecanismos concretos:
- `corrective_blendshape_manager._push_before_skin()` (407-416):
  `cmds.reorderDeformers(bs, skin_nodes[-1], mesh)` si el `frontOfChain=True` no bastó;
  `_is_pre_deformation` lo valida. Docstring: "Targets are always placed before the
  skinCluster".
- `skin_manager_api` crea skins con **`multi=True`** (línea 401 — apilables) y reordena el
  stack completo tras importar (459-473, `reorderDeformers ... back=True` en orden).
- `correctives.localize_corrective_skin` (318): `bindPreMatrix[i] ←
  worldInverseMatrix` del padre de cada influencia → mata la doble transformación del
  skin apilado. El build la llama solo para skins con `corrective` en el nombre.
- El build corre en fast session (cycleCheck off) — valida ciclos en QA, no en build.

## 6. Persistencia / export por tipo de deformer

| Qué | Herramienta | Formato | Detalles |
|---|---|---|---|
| skinCluster (stack completo por malla) | `skin_manager_api.SkinManager` | `.skc` JSON versionado (`_vNNN`) | por skin: `attributes` (skinningMethod, normalize, maxInfluences…), influences, `sparse_weights` `{inf:{ix,vw}}` y `sparse_blend` (blendWeights DQ). Import respeta topología, añade influencias faltantes lockeadas, reordena stack |
| pesos por UV (transfer source→target) | `mesh_data_exporter.SourceSkinExporter` | `.skc` + `.skinmap` | usado por `create_rig._auto_transfer_from_source` |
| blendShape correctivo | `corrective_blendshape_manager` | `.json` versionado | por target: `w_idx`, `deltas [vtx,dx,dy,dz]`, `value`, `driven_key`; import recrea frontOfChain + aliases + SDKs; mirror con `MIRROR_NEGATE_ATTRS` |
| datos de build inter-módulo | `data_manager.DataExportBiped` | `cache/biped.cache` | plugs/nombres publicados por módulo (no pesos) |
| deltaMush / correctivas por nodos | — | — | NO se exportan: se reconstruyen en build |
| AdonisFX | `copyWeightsAdonis` | en escena / buffer | transfer/mirror/replace, sin fichero versionado propio |

## 7. Convenciones para deformación nueva

- **Sufijos**: skinCluster `_SKIN` (módulos) / `_SC` (skin_manager_ng) / `C_corrective_SKC`
  (correctivas); blendShape `_BLS` (curvas) / `_BS`; deltaMush `_DMH`; uvPin `_UVP`;
  ficheros de pesos `.skc`. Prefijos de lado `L_/R_/C_` obligatorios.
- **`ss=True`** en todo `createNode` utilitario; los deformers nativos van por su comando
  (`cmds.skinCluster`, `cmds.blendShape`, `cmds.deltaMush`) o `cmds.deformer(type=...)`.
- **Math/matrix nodes Maya 2024+** (`multiply`, `sum`, `subtract`, `power`, `multMatrix`,
  `pickMatrix`, `blendMatrix`, `aimMatrix`, `wtAddMatrix`…). `plusMinusAverage`/
  `multiplyDivide` solo sobreviven en legacy (auto_collision) — no en código nuevo.
- **Escala global**: todo deformer con parámetros en unidades de mundo debe leer el
  masterwalk (patrón `C_deltaMushScale_DCM`; `segment_volume` en matrix_manager).
- **Skin apilado** → SIEMPRE `localize_corrective_skin` (o bindPreMatrix equivalente).
- **Orden** → correctivos esculpidos pre-skin (`frontOfChain` + reorder), capas de
  suavizado post-skin, y el skin de correctivas entre medias, localizado.
- **Cleanup**: `hide_all_utility_nodes()` pone `isHistoricallyInteresting=0` a todo salvo
  KEEP_TYPES — si añades un tipo de deformer nuevo (custom o Adn), inclúyelo en
  KEEP_TYPES o desaparecerá del channel box/history del animador.

## 8. QA de deformación (antes de dar por bueno un deformer nuevo)

1. **Rest = identidad**: en bind pose, malla deformada ≈ modelo (tolerancia 1e-4).
   Envelope a 0 → idéntica al paso anterior del stack (A/B).
2. **Orden del stack**: `cmds.listHistory(mesh, pruneDagObjects=True)` — correctivo BS
   antes del skin, mush/suavizado después; `_is_pre_deformation` para los BS.
3. **Doble transformación**: mover el masterwalk (translate/rotate/escala 0.1x/10x, a
   1000 unidades) con el rig en pose — nada "nada" ni tiembla.
4. **ROM completa** con el deformer activo (no solo la pose objetivo) + mirror L/R.
5. **Ciclos**: `cycleCheck -e on` tras build (el build lo apaga) + consola limpia.
6. **Performance**: fps con el deformer ON vs OFF; en escenas pesadas comprobar Cached
   Playback (un deformer/nodo que lo invalida se ve en la barra azul del timeline).
7. **Persistencia**: pesos exportados (`.skc`/`.json`) y versionados en
   `assets/<char>/skin_clusters/`; settings tuneados → `character_extras` del `.build`.
8. **Export a engine**: el mesh final sigue naciendo de joints `_ENV` + morphs — lo que
   el deformer aporte y no esté horneado a joints/shapes NO viaja al engine.
