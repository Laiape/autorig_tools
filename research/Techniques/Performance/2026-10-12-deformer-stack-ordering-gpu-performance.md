---
source: https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82
found: 2026-10-12
category: performance
priority: 2
tags: [maya, rigging, performance, deformer, blendshape, skincluster, gpu, deformation-order]
status: NEW
---

# Deformer Stack Ordering for GPU Performance in Maya

## Descripción
El orden de los deformadores en el stack de Maya no es solo semántico: determina si la evaluación corre en GPU (OpenCL, interactivo a 30+ fps) o cae a CPU serial. El artículo de kattkieru "Deformation Layering in Maya's Parallel GPU World" es la referencia práctica más completa, con reglas concretas para preservar GPU Override en rigs de producción complejos.

## Fundamento matemático / técnico

### The Deformer Stack as a Function Composition

Maya evaluates deformers as sequential function composition over mesh positions:

```
P_final = f_N ∘ f_{N-1} ∘ ... ∘ f_1(P_rest)
```

Each deformer fᵢ maps mesh positions to mesh positions. For GPU Override (OpenCL), Maya requires the entire chain to be representable as GPU compute kernels with no CPU readback.

### Rules That Govern GPU Compatibility

**Rule 1: Live animated mesh targets break GPU upstream**
If a `blendShape` node has an animated target (another mesh with changing geometry), Maya must read that target's CPU-computed positions before running the blendShape on GPU → the entire deformation chain upstream becomes CPU-only.

```
[animated target mesh] → blendShape.inputTarget → skinCluster  ← GPU BROKEN
```

Fix: precompute animated targets as baked blendShape weights (animCurve-driven), not live mesh connections.

**Rule 2: outMesh → inMesh connections between deforming meshes force CPU**
```python
# This breaks GPU for mesh_A's entire chain:
mc.connectAttr('mesh_A.outMesh', 'mesh_B.inMesh')  # DON'T DO THIS
```
Correct approach: use a `blendShape` as passthrough gateway between deformation layers.

**Rule 3: Deformation order within a single mesh**
Standard production-safe order (pre-deformation → skinCluster → post-deformation):
```
blendShape (Front of Chain) → tweak → skinCluster → deltaMush → blendShape (post)
```

- **blendShape BEFORE skinCluster** (Front of Chain): shapes sculpted in bind pose, then deformed by joints. Correct for correctives.
- **blendShape AFTER skinCluster** (Default): shapes applied in deformed space. Needed for game engines (FBX export requires this for some targets), but results differ.
- Corrective shapes: "Front of Chain" → joints then fix, OR use "Post-deformation" (parallel mode in Maya's poseInterpolator).

**Rule 4: deltaMush GPU support (Maya 2024+)**
`deltaMush` added GPU Override support in Maya 2024. Requires:
- No live mesh targets
- Topology unchanged
- Deformer placed correctly in stack (before or after skinCluster depending on intent)

### SC Deformation Order: the `deformationOrder` Flag

```python
# Check current deformation order of a skinCluster-driven mesh
mc.skinCluster('mesh_skinCluster', query=True, deformationOrder=True)
# Returns: 'after', 'before', 'default', 'parallel', 'post'

# Set blendShape to Front of Chain:
mc.reorderDeformers('mesh_blendShape', 'mesh_skinCluster', 'mesh')
```

The `reorderDeformers` command reorders the history stack without rebinding. Critical for production edits without losing skin weights.

### Performance Numbers (empirical estimates from community data)

| Stack Configuration | Typical Frame Time (body rig, 80k verts) |
|--------------------|-----------------------------------------|
| blendShape + skinCluster (GPU, correct order) | 0.8 – 1.5 ms |
| blendShape with live animated target (CPU fallback) | 4 – 12 ms |
| outMesh→inMesh chain (CPU forced) | 6 – 20 ms |
| deltaMush after skinCluster (Maya 2024, GPU) | +0.5 – 1.0 ms overhead |
| deltaMush (Maya 2023 or earlier, CPU only) | +3 – 8 ms overhead |

### Audit Function (Python)

```python
import maya.cmds as mc
import maya.api.OpenMaya as om

def audit_deformer_stack_gpu(mesh):
    """
    Check deformer stack of mesh for GPU compatibility issues.
    Returns list of (deformer, issue) tuples.
    """
    issues = []
    history = mc.listHistory(mesh, pruneDagObjects=True, interestLevel=1) or []
    
    # Check for live animated blendShape targets
    for node in history:
        if mc.nodeType(node) == 'blendShape':
            conns = mc.listConnections(node + '.inputTarget', source=True) or []
            for c in conns:
                if mc.nodeType(c) in ('mesh', 'nurbsSurface'):
                    # Check if this source mesh has deformers (animated target)
                    src_history = mc.listHistory(c, interestLevel=1) or []
                    if any(mc.nodeType(n) in ('skinCluster', 'blendShape', 'cluster') 
                           for n in src_history):
                        issues.append((node, 'ANIMATED_TARGET_GPU_BREAK: ' + c))
    
    # Check for outMesh→inMesh
    in_mesh_src = mc.listConnections(mesh + '.inMesh', source=True) or []
    for src in in_mesh_src:
        if mc.nodeType(src) == 'mesh':
            issues.append((src, 'OUTMESH_INMESH_GPU_BREAK'))
    
    return issues

def audit_scene_deformer_stacks():
    """Run audit on all meshes with skinClusters in scene."""
    for sc in mc.ls(type='skinCluster'):
        geo = mc.skinCluster(sc, query=True, geometry=True) or []
        for mesh in geo:
            issues = audit_deformer_stack_gpu(mesh)
            if issues:
                print(f"[WARN] {mesh}: {issues}")
```

## Comparación con autorig_tools
En un pipeline de producción como el de autorig_tools, el riesgo más común es añadir corrective blendShapes post-build que conecten live mesh targets (por ejemplo, un mesh intermedio de sculpt). También es frecuente el error de conectar outMesh→inMesh entre meshes de LOD para propagar la deformación, lo que fuerza CPU en toda la cadena upstream.

## Aplicable directamente
YES — Ejecutar `audit_scene_deformer_stacks()` en un rig de producción de autorig_tools. Los dos issues más probables:
1. Live animated blendShape targets de correctives añadidos manualmente en producción
2. Orden incorrecto de deformadores después de añadir correctives post-skinning

Tiempo estimado: 30 min para el audit + 1-2h para reordenar stacks problemáticos con `reorderDeformers`.

## Fuente
- kattkieru. "Deformation Layering in Maya's Parallel GPU World." https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82
- Autodesk Support: "Adding blendshape after skincluster causes rig to break." https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Adding-blendshape-after-skincluster-causes-rig-to-break.html
- Yantor3d: "Parallel Deformers." https://yantor3d.wordpress.com/2016/12/03/parallel-deformers/
- Autodesk Using Parallel Maya 2026: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html
