---
source: https://www.cgchannel.com/2025/11/autodesk-releases-maya-2026-3-and-maya-creative-2026-3/
found: 2026-08-24
category: performance
priority: 2
tags: [maya, performance, deformer, procedural, wrinkles, dga, 2026.3]
status: NEW
---

# Maya 2026.3 — Dynamic Geometry Attributes (dgaTension / dgaDelta / dgaVisualizer / dgaToArray)

## Descripción
Maya 2026.3 (nov 2025) introduce el sistema **DGA — Dynamic Geometry Attributes**: cuatro nodos nativos que analizan la deformación por-vértice en tiempo real y exponen los resultados como atributos consumibles por shading (Arnold), otros deformers, o UI de diagnóstico. Los dos "sensor" nodes — `dgaTension` y `dgaDelta` — comparan dos estados de la misma mesh (rest vs deformada) y producen un array de floats por vértice: tensión superficial y magnitud de delta posicional respectivamente. `dgaVisualizer` los rasteriza como heat map en viewport; `dgaToArray` los expone al material system (Arnold vertex data). Todo esto es nativo Maya, GPU-friendly (kParallel), sin plugins de terceros.

## Fundamento matemático / técnico

### dgaTension — tensión superficial por vértice

Dado un mesh con conexiones de vecinos `N(i)` (one-ring del vértice i), definir la tensión como la **razón de longitudes de arista** entre rest y deformada:
```
tension(i) = (1 / |N(i)|) · Σⱼ∈N(i)  (‖x'ᵢ − x'ⱼ‖ − ‖xᵢ − xⱼ‖) / ‖xᵢ − xⱼ‖
```
- `tension > 0` → estiramiento local (piel estirándose en el codo abierto).
- `tension < 0` → compresión (arruga: piel plegándose en el codo cerrado).
- `tension = 0` → deformación isométrica local (rígido).

Esto es equivalente numérico al primer invariante del **strain tensor de Cauchy-Green**:
```
C = FᵀF     (Cauchy-Green derecho, F = deformation gradient)
tr(C) − 3   ≈  2 · (linear strain), a primer orden
```
Discretizado por vecinos de vértice, `tension(i)` es la aproximación de `tr(C)−3` promediada en el one-ring de i.

### dgaDelta — magnitud posicional del delta

```
delta(i) = ‖x'ᵢ − xᵢ‖     (o el vector completo, dependiendo del modo)
```
Trivial pero útil: en combinación con weight-space (delta en tangent-space del vértice), es el driver clásico para *pose-space deformation*: se usa como input del RBF corrective en vez de leer directamente las rotaciones del joint.

### El flujo procedural completo

```
mesh_rest  ──┐
mesh_deformed ──► dgaTension  ──► tension_per_vertex_array  ──┐
mesh_rest  ──┐                                                 ├──► dgaVisualizer  → viewport heatmap
mesh_deformed ──► dgaDelta    ──► delta_per_vertex_array   ──┘
                                                              │
                                                              ├──► dgaToArray → Arnold vertexData → shader displacement / material blend
                                                              │
                                                              └──► arrayToTexture / blendShape weight → drive corrective blendshape
```

### Por qué esto es "performance" y no solo "features"

1. **Nodos nativos C++** — todos son `kParallel` compatibles. Van en la GPU deformer cluster.
2. **Sustituyen expression / MEL scripts** — todo el mundo pre-2026 escribía tension en un `pointOnCurveInfo` + expression que era `kGloballySerialize` y rompía la EG estática. Un solo dgaTension reemplaza 20-50 expression nodes de la técnica clásica.
3. **Reemplaza un plugin propietario** — Wrinklematic y utilities similares hacían este cálculo desde MEL/Python y no eran cache-friendly. DGA los subsume.
4. **Cero readback CPU** si el consumer también es GPU (Arnold vertex data, blendShape weight con conexión de attribute array).

### Node scheduling y evaluación

- `dgaTension`, `dgaDelta` — kParallel, kMPSafe. Van dentro de la GPU deformer cluster si el mesh de input está en GPU.
- `dgaVisualizer` — es un display node (viewport), se evalúa perezosamente cuando el viewport lo necesita. **Desactivarlo en producción** para no incurrir en overhead de rasterizado (activar solo para diagnóstico).
- `dgaToArray` — output se conecta directo a Arnold sin readback. Máximo throughput.

## Implementación en Maya

**Setup mínimo — driving corrective blendshape con dgaTension:**

```python
import maya.cmds as cmds

def setup_dga_tension_driven_wrinkle(mesh, wrinkle_bs_target_name, driver_axis='x'):
    """
    Conecta el tension array del mesh a un blendShape target de wrinkle.
    Cuando el codo se pliega -> tension < 0 en la cara interior -> wrinkle activo.
    """
    # 1. Duplicar el mesh en rest pose (necesita ser el input al dgaTension)
    rest = cmds.duplicate(mesh, name=mesh + '_rest')[0]
    cmds.setAttr(rest + '.template', 1)   # solo referencia, no visible

    # 2. Crear dgaTension
    tension = cmds.createNode('dgaTension')
    cmds.connectAttr(rest + '.outMesh', tension + '.restMesh')
    cmds.connectAttr(mesh + '.outMesh', tension + '.deformedMesh')

    # 3. dgaToArray → blendShape weightPerVertex
    to_array = cmds.createNode('dgaToArray')
    cmds.connectAttr(tension + '.tension', to_array + '.input')

    # 4. Conectar array a la weight-per-vertex del blendShape target
    #    (requiere blendShape con weight-per-vertex habilitado)
    bs = cmds.ls(type='blendShape')[0]      # asumido: existe blendShape
    idx = cmds.aliasAttr(bs, query=True).index(wrinkle_bs_target_name)
    cmds.connectAttr(to_array + '.output', bs + f'.inputTarget[0].inputTargetGroup[{idx}].targetWeights')

    # 5. Clamp/remap: solo tensiones negativas (compresión) drivean el wrinkle
    remap = cmds.createNode('remapValue')
    cmds.setAttr(remap + '.inputMin', -0.3)  # ~compresión moderada
    cmds.setAttr(remap + '.inputMax', 0.0)
    cmds.setAttr(remap + '.outputMin', 1.0)
    cmds.setAttr(remap + '.outputMax', 0.0)
    cmds.connectAttr(to_array + '.output[0]', remap + '.inputValue')   # scalar/uniform mode
    # (Para real per-vertex se necesita array shader network; ver Arnold vertexData path)

    return tension, to_array
```

**Setup de visualización de diagnóstico:**

```python
def show_tension_heatmap(mesh):
    """
    Activa el heatmap de tensión en viewport para inspeccionar el skinning.
    Uso en QA: bindear personaje, cyclar poses, ver zonas con tension anómala.
    """
    rest = cmds.duplicate(mesh, name=mesh + '_rest_ref')[0]
    cmds.setAttr(rest + '.visibility', 0)
    tension = cmds.createNode('dgaTension')
    cmds.connectAttr(rest + '.outMesh', tension + '.restMesh')
    cmds.connectAttr(mesh + '.outMesh', tension + '.deformedMesh')

    viz = cmds.createNode('dgaVisualizer')
    cmds.connectAttr(tension + '.tension', viz + '.input')
    cmds.connectAttr(mesh + '.outMesh', viz + '.mesh')
    # el viz aparece como overlay en viewport
    return viz
```

**Aviso — donde NO usarlo:**
- **Producción de crowd/BG:** desactivar `dgaVisualizer`, mantener `dgaTension`+`dgaDelta` solo si son consumers finales (shading). El viz añade overhead de rasterizado.
- **Wrinkles como blendShape targets vs shading displacement:** para performance máximo, usar shading (Arnold vertexData → bump/normal) en LOD 1+. Reservar blendShape targets para hero LOD 0.

## Comparación con autorig_tools

`autorig_tools` hoy hace correctives via:
- **RBF Manager** (mgear-style): driver = rotación del joint (Euler o 6D), target = blendShape delta. No usa strain — usa pose del joint como proxy.
- **SDK correctives:** conexiones directas rot.z → blendShape.weight.

DGA introduce una vía **strain-driven** (basada en la deformación real de la piel, no en la pose del joint):
- **Ventaja:** captura correctamente cuando el skinning ya produce compresión aunque la pose sea "normal" — por ej. un forearm twist con collision con el pecho.
- **Ventaja:** cero configuración por-pose. El artista sculpea UN target de wrinkle; el tension node lo activa según strain real.
- **Complemento no sustituto:** RBF sigue siendo la respuesta correcta para shape correctives grandes (shoulder, hip). DGA es para wrinkles finos y micro-detalles (nudillos, codo interior, entrecejo).

## Aplicable directamente

**YES** — aplicaciones directas de baja fricción:

1. **`build_wrinkle_deformer(mesh, wrinkle_targets)`** en autorig_tools/deformers/ — un helper que genera el network `dgaTension → dgaToArray → blendShape weightPerVertex` para cada target de wrinkle. Estimado: **2-3h**.
2. **Health check de skinning:** `show_tension_heatmap()` en el QA UI — permite al artista visualizar de un vistazo dónde el skinning tiene tensión inusual (indicador temprano de weights mal repartidos). Estimado: **1h**.
3. **Shading integration:** driving Arnold vertex data para wrinkles procedurales en LOD 1+ (hero characters). Estimado: **2-4h** + tiempo de shader authoring.

**Requisito de versión:** Maya 2026.3 (nov 2025). Para pipelines < 2026.3, el fallback es un `MPxDeformer` custom que compute la misma tensión — ya no valdría la pena escribirlo en 2026.

**Impacto esperado:**
- Wrinkles procedurales sin necesidad de sculpting por-pose. Un solo target activo se despliega según strain real.
- Sustitución de 20-50 expression nodes en rigs faciales legacy por 3-5 DGA nodes — desbloqueo de Cached Playback en la cadena facial.
- Diagnóstico visual del skinning sin scripts custom — el artista lo tiene en menú.

**Nota compatibilidad:** el sistema DGA es nuevo — verificar que los nodos aparezcan como `kParallel` en `dbtrace(keyword='eval')`. Si Autodesk los marcó `kSerialize` en la primera release, será por prudencia inicial y se reclasificarán en 2026.4+.

## Fuente
- CGChannel Maya 2026.3 release: https://www.cgchannel.com/2025/11/autodesk-releases-maya-2026-3-and-maya-creative-2026-3/
- 80.lv coverage: https://80.lv/articles/autodesk-released-maya-2026-3-3ds-max-2026-3
- Autodesk What's New in 2026.3: https://help.autodesk.com/cloudhelp/2026/ENU/Maya-WhatsNew/files/GUID-E30563A9-74A3-4E4B-A955-CDDD25A562FD.htm
- Video demo (YouTube): https://www.youtube.com/watch?v=GmhgMtMWzt8
- Digital Production: https://digitalproduction.com/2025/11/13/autodesk-launches-maya-2026-3-creative-2026-3/
- Related — **Corrective BlendShape Delta Extraction** (2026-08-03 en Drive) — tangent-space correctives.
- Related — **Expression Nodes & Dirty Propagation** (2026-07-27 en Drive) — DGA sustituye el patrón clásico expression-based.
