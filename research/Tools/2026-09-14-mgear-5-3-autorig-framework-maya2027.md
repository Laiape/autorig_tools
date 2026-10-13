---
source: https://github.com/mgear-dev/mgear/releases/tag/5.3.0
found: 2026-09-14
category: tool
priority: 3
tags: [maya, python, rigging, mgear, evaluation-graph, parallel, blendshape, sdk, performance, maya2027]
status: NEW
---
# mGear 5.3 — Autorig Framework for Maya 2022–2027

## Descripción
mGear 5.3 es la versión más reciente del framework de autorig de producción más usado en Maya, actualizado el 9 de septiembre de 2026 con compatibilidad hasta Maya 2027 y Python 3.13. Introduce 8 nuevas herramientas orientadas a performance (Evaluation Partition, Wire to Skinning, Skin Cluster Localization), workflow de blendshapes (Blendshape Setup Transfer), y automatización de SDKs (SDK Creator). El repo tiene ~400 estrellas y es activamente mantenido por el equipo mgear-dev con contribuciones de producción de estudios AAA.

## Fundamento matemático / técnico

### Evaluation Partition — Parallel Deformer Scheduling
The core insight is that Maya's Evaluation Graph (EG) schedules deformers per-mesh. A single mesh with one deformer chain is a single EG node, evaluated on one thread. mGear 5.3 introduces polygon group partitioning: a mesh is split into N face sets, each assigned to an independent deformer chain, enabling N-way parallelism.

Performance model:
```
T_parallel ≈ T_seq / N + T_merge
```
Where T_merge is the cost of recombining N mesh partitions (typically 0.1–0.3ms for <100K poly meshes).

For a 12ms deformer stack with N=4 groups:
```
T_parallel ≈ 12/4 + 0.2 ≈ 3.2ms  (3.75× speedup)
```

The partition config is saved as a `.evp` file (JSON v2.0):
```json
{
  "version": "2.0",
  "mesh": "body_geo",
  "groups": [
    {"id": 0, "faces": [0, 1, 2, ...], "deformers": ["skinCluster1"]},
    {"id": 1, "faces": [500, 501, ...], "deformers": ["skinCluster2"]},
    {"id": 2, "faces": [1000, 1001, ...], "deformers": ["skinCluster3"]},
    {"id": 3, "faces": [1500, 1501, ...], "deformers": ["skinCluster4"]}
  ]
}
```

Short names (no namespace) ensure portability across rigs with different namespaces.

### Wire to Skinning — Eliminating EG Blockers
Wire deformers have scheduling type `kGloballySerialize` — they serialize the entire EG, blocking GPU Override. Wire to Skinning converts them to skinClusters (`kParallel`):

1. Sample wire influence as per-vertex weights: for each vertex v, compute distance d(v, wire_curve), then w(v) = exp(-d²/σ²)
2. Create skinCluster with two joints: wire_base_joint, wire_tip_joint
3. Transfer sampled weights via skinPercent
4. Delete wireDeformer

The resulting skinCluster is `kParallel`, removing the globally_serialize blocker from the EG. GPU Override can then activate, moving deformation to the GPU.

### Skin Cluster Localization — Float32 Precision Fix
At large world coordinates (e.g., 10000 units from origin), float32 skinning precision degrades:
```
error ≈ |coord| × machine_epsilon × sqrt(n_transforms)
error ≈ 10000 × 1.2e-7 × sqrt(6) ≈ 0.003 units
```

Localization offsets the mesh to near-origin before skinning, reducing error to:
```
error ≈ 0.1 × 1.2e-7 × sqrt(6) ≈ 3e-7 units  (10000× improvement)
```

Implementation: offsetMatrix node inserted before skinCluster, inverseOffsetMatrix node after. The skinCluster sees coordinates ~[0,0,0].

### SDK Creator — Timeline-to-SDK Automation
Reads a set of keyframed poses from the Maya timeline and automatically generates Set Driven Keys:
1. For each frame f in [start, end]: read all driver attr values → read all driven attr values
2. For each driven attr: create animCurve with keys at driver values
3. Group by driver → connect to setDrivenKey network

Pattern extractable as `build_sdk_from_pose(driver_attr, driven_attrs, frames)`.

### Blendshape Setup Transfer
Transfers a complete blendshape setup (combo network + corrective targets + SDK drivers) between mesh variants:
1. Rebuild combo network: `createPlusMinusAverage3D` nodes for additive combos
2. Zero-delta cleanup: removes targets where ||delta||_F < epsilon (default 0.001)
3. Preserves SDK connections via remapped driver attributes

New API nodes: `createPlusMinusAverage3D`, `createBlendWeightedNode` (both in mgear.rigbits).

### Performance — OpenMaya2 Speedups
- Extract Controls: 5–10× speedup via OpenMaya2 MFnMesh batch queries vs. maya.cmds per-component
- Proxy Slicer: 8–12× on meshes >20K polygons via MFnMesh.getPoints() bulk array ops
- Anim Picker 2.0: Python 3.13 compatible, PySide6 ready

## Implementación en Maya

### Check for Wire Deformers and Convert
```python
import maya.cmds as mc
from mgear.rigbits import wire_to_skinning

# Find all wire deformers in scene
wire_deformers = mc.ls(type='wireDeformer')
print(f"Found {len(wire_deformers)} wire deformers: {wire_deformers}")

# Convert each to skinCluster
for wire in wire_deformers:
    wire_to_skinning.convert(wire, sigma=2.0)
    print(f"Converted {wire} → skinCluster")

# Verify EG no longer has globally_serialize nodes
# (check in Maya's Evaluation Toolkit)
```

### SDK Creator Pattern (Extractable)
```python
import maya.cmds as mc

def build_sdk_from_pose(driver_attr, driven_attrs, pose_frames):
    """
    Extract SDK pattern from mGear SDK Creator.
    driver_attr: str, e.g. 'ctrl.rotateX'
    driven_attrs: list[str], e.g. ['joint.translateX', ...]
    pose_frames: list[int], timeline frames to sample
    """
    for frame in pose_frames:
        mc.currentTime(frame)
        driver_val = mc.getAttr(driver_attr)
        for driven in driven_attrs:
            driven_val = mc.getAttr(driven)
            mc.setDrivenKeyframe(driven, 
                                  currentDriver=driver_attr,
                                  driverValue=driver_val,
                                  value=driven_val)
    print(f"SDKs built: {len(driven_attrs)} attrs × {len(pose_frames)} poses")
```

### Evaluation Partition — Apply .evp Config
```python
from mgear.rigbits import evaluation_partition

# Apply saved partition config to mesh
evaluation_partition.apply_from_file('body_geo', 'configs/body_geo.evp')

# Or create partition from scratch
evaluation_partition.create_partition('body_geo', num_groups=4, 
                                       method='geodesic_balanced')
```

### Skin Cluster Localization
```python
from mgear.rigbits import skin_localization

# Localize all skinClusters on mesh
skin_localization.localize_mesh('body_geo')

# Or batch
for mesh in mc.ls(type='mesh', long=True):
    transform = mc.listRelatives(mesh, parent=True)[0]
    skin = mc.ls(mc.listHistory(mesh), type='skinCluster')
    if skin:
        skin_localization.localize_mesh(transform)
```

## Comparación con autorig_tools
mGear 5.3 y autorig_tools son complementarios, no competidores. autorig_tools tiene su propio pipeline de construcción de rigs; mGear 5.3 aporta herramientas de **post-proceso y optimización** que son independientes del sistema de construcción. Las más directamente aplicables son Wire to Skinning (elimina globally_serialize blockers), Skin Cluster Localization (corrige float32 drift en assets a gran escala), y el patrón de SDK Creator (3-4h para implementar `build_sdk_from_pose()` en autorig_tools). La Evaluation Partition requiere que los meshes sean compatibles con la arquitectura de partición, lo que puede necesitar ajustes en el pipeline de deform stack de autorig_tools.

## Aplicable directamente
YES — **Wire to Skinning** es aplicable en 30-60 minutos: ejecutar `mc.ls(type='wireDeformer')` en cualquier rig de autorig_tools; si existen wire deformers, convertirlos elimina globally_serialize blockers del EG y habilita GPU Override. **SDK Creator pattern** es aplicable en 3-4h extrayendo el patrón `build_sdk_from_pose()`. **Skin Cluster Localization** aplica si hay assets ubicados a >1000 unidades del origen. **Evaluation Partition** requiere validación de compatibilidad con el deform stack actual (~1 día de investigación).

## Fuente
- https://github.com/mgear-dev/mgear/releases/tag/5.3.0
- https://github.com/mgear-dev/mgear
- https://github.com/mgear-dev/mgear/blob/develop/CHANGELOG.md
