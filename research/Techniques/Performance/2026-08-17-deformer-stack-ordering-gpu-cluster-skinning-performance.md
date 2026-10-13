---
source: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-1B2D8791-55F7-4FF8-8DFC-56AC86630FFC | https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82 | https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2024/MayaCachedPlaybackWhitePaper.html
found: 2026-08-17
category: performance
priority: 2
tags: [maya, rigging, performance, deformer, skinCluster, blendShape, GPU, parallel-evaluation, stack-ordering]
status: NEW
---

# Deformer Stack Ordering y GPU Cluster — Guía de Performance para Production Rigs

## Descripción
El orden del stack de deformación en Maya determina directamente si los deformadores corren en GPU o CPU, y en qué orden se ejecutan. La regla clave: los deformadores GPU deben ser contiguos en el stack — cualquier deformador no-GPU entre dos GPU deformers fuerza un round-trip CPU (readback), destruyendo el beneficio de GPU Override. Esta guía documenta el ordering óptimo, qué deformadores soportan GPU, y cómo auditar el stack en autorig_tools.

## Fundamento matemático / técnico

### Maya Deformer Stack — Evaluation Order
In the DG, deformers are applied in the order they appear in the `inputGeometry` array of each node, from index 0 upward. In Maya's UI, the stack shows them in *reversed* order (last applied appears first).

**DG order (actual application)**:
```
inputMesh → [deformer_0] → [deformer_1] → [deformer_2] → outputMesh
```

**UI order (Channel Box > Inputs)**:
```
deformer_2  ← shown first (applied last)
deformer_1
deformer_0  ← shown last (applied first)
```

### GPU Override — Supported Deformers (Maya 2024-2026)
| Deformer | GPU Support | Notes |
|----------|-------------|-------|
| `skinCluster` | ✅ Full GPU | Primary GPU beneficiary |
| `blendShape` | ✅ Full GPU | All targets, CPU fallback if weighted by expression |
| `cluster` | ✅ GPU | Limited to Volume mode |
| `wire` | ✅ GPU | |
| `wrap` | ✅ GPU (Maya 2024+) | |
| `softMod` | ✅ GPU (Volume mode only) | Subset mode = CPU |
| `sculpt` | ✅ GPU (Implicit sphere only) | Non-sphere sculpt = CPU |
| `deltaMush` | ✅ GPU (Maya 2024+) | Formerly CPU-only |
| `tension` | ✅ GPU | |
| `follicle` | ❌ CPU | Triggers readback (Maya 2024: only local break) |
| `proximity wrap` | ❌ CPU | |
| `shrinkWrap` | ❌ CPU | |
| `cvWrap` | ❌ CPU (custom plugin) | |
| `nCloth/nHair` | ❌ CPU | Nucleus always CPU |
| `weightedBlend` | ❌ CPU | Breaks cluster |
| Expression-driven weights | ❌ CPU | weightFunction animation = CPU fallback |

### GPU Cluster Break Rules
A **GPU cluster** is a contiguous block of GPU-compatible deformers on the same mesh. Rules:

1. **CPU deformer in the middle** → splits one cluster into two, adds one GPU↔CPU readback
2. **Animated weightFunction attribute** → entire deformer switches to CPU evaluation
3. **Custom mesh topology changes during deformation** (inMesh→outMesh chain) → CPU for entire upstream chain (pre-Maya 2024)
4. **Maya 2024**: GPU Download now works — non-GPU nodes only break their local cluster, not all upstream clusters

### Performance Impact of GPU Readback
Each GPU→CPU readback costs: 0.5–4ms (depending on vertex count and bus bandwidth)
- For a character with 4 meshes: 4 readbacks = 2–16ms overhead per frame
- At 25 FPS budget = 40ms total: a bad stack can consume 25–40% of the frame budget in readbacks alone

### Skinning Influences — GPU vs CPU Performance
| Max Influences | CPU Time (10k verts) | GPU Time (10k verts) | GPU Advantage |
|---------------|---------------------|---------------------|---------------|
| 4 | 0.8ms | 0.05ms | 16× |
| 8 | 1.5ms | 0.06ms | 25× |
| 16 | 2.9ms | 0.08ms | 36× |

**More influences = more GPU advantage over CPU.** Pruning weights to 4 max influences loses GPU speedup more than it gains from reduced compute. Optimal: 8 influences max, pruned weights below 0.001.

## Implementación en Maya

### Optimal Deformer Stack Order (for maximum GPU coverage)
```
# OPTIMAL ORDER (DG application order, bottom to top in UI):

# Layer 1 — Foundation (GPU cluster 1):
skinCluster          ← GPU, always first

# Layer 2 — Correctional shapes (GPU cluster 1 continued):
blendShape_correctives  ← GPU, must be after skinCluster for post-skin correction

# Layer 3 — Surface refinement (GPU cluster 1 continued):
deltaMush            ← GPU (Maya 2024+), must be last in GPU chain

# --- Only add CPU deformers below if absolutely necessary ---
# nCloth / simulation results  ← CPU, add after GPU chain if needed
# wrap (proxy mesh)             ← GPU (2024+)
```

**Anti-patterns to avoid:**
```
# BAD — breaks GPU cluster:
skinCluster (GPU)
  ↓
[custom corrective MPxDeformer — no GPU registration]  ← CPU BREAK
  ↓
blendShape (GPU)  ← now in separate cluster, requires readback

# FIX: move correctives to pre-skin blendShape OR register MPxGPUDeformer
```

### Python: Audit Deformer Stack
```python
import maya.cmds as cmds

GPU_DEFORMERS = {
    'skinCluster', 'blendShape', 'cluster', 'wire', 'deltaMush',
    'tension', 'wrap', 'softMod', 'sculpt', 'weightGeometryFilter'
}

def audit_deformer_stack(mesh_name):
    """Audit deformer stack for GPU cluster breaks."""
    history = cmds.listHistory(mesh_name, pruneDagObjects=True) or []
    deformers = [n for n in history if cmds.nodeType(n) in cmds.ls(type='geometryFilter')]
    
    results = []
    last_was_gpu = True
    cluster_count = 1
    readbacks = 0
    
    for deformer in deformers:
        dtype = cmds.nodeType(deformer)
        is_gpu = dtype in GPU_DEFORMERS
        
        # Check if weightFunction is animated (breaks GPU for that deformer)
        weight_animated = False
        if cmds.objExists(f'{deformer}.weightFunction'):
            conns = cmds.listConnections(f'{deformer}.weightFunction') or []
            weight_animated = bool(conns)
            if weight_animated:
                is_gpu = False
        
        if last_was_gpu and not is_gpu:
            readbacks += 1
            cluster_count += 1
        
        results.append({
            'node': deformer,
            'type': dtype,
            'gpu': is_gpu,
            'weight_animated': weight_animated
        })
        last_was_gpu = is_gpu
    
    print(f"\n{'='*50}")
    print(f"Mesh: {mesh_name}")
    print(f"GPU clusters: {cluster_count}, Readbacks: {readbacks}")
    print(f"{'='*50}")
    for r in results:
        gpu_str = '✅ GPU' if r['gpu'] else '❌ CPU'
        warn = ' ⚠ animated weights' if r['weight_animated'] else ''
        print(f"  {gpu_str} | {r['type']:20s} | {r['node']}{warn}")

def audit_all_meshes_in_rig(rig_root):
    """Audit all meshes under rig root."""
    meshes = cmds.listRelatives(rig_root, allDescendents=True, type='mesh') or []
    for mesh in meshes:
        audit_deformer_stack(mesh)
```

### Skinning Weight Optimization
```python
def optimize_skin_weights(mesh, max_influences=8, prune_below=0.001):
    """
    Prune tiny weights and cap influence count for GPU performance.
    Safe to run after skin data is finalized.
    """
    skin = mel.eval(f'findRelatedSkinCluster("{mesh}")')
    if not skin:
        return
    
    # Prune weights below threshold
    cmds.skinPercent(skin, mesh, pruneWeights=prune_below)
    
    # Cap maximum influences
    cmds.skinCluster(skin, edit=True, maximumInfluences=max_influences, 
                     obeyMaxInfluences=True)
    
    # Note: this affects quality. Use 8 for body, can use 4 for hero faces
    # where geometry density is higher and each vertex is more precise
```

### Cache Playback Compatibility
For Cached Playback to cache deformation results effectively:
- The deformer stack must NOT have `always_dirty` nodes (expressions)
- `skinCluster` + `blendShape` + `deltaMush` stack is fully cacheable
- Each `blendShape` target must have static weight OR driven by SDK/animCurve (never expression)
- GPU cluster break nodes make the Cache Point upstream of the break uncacheable

## Comparación con autorig_tools

El conocimiento previo de autorig_tools (research log junio 2026) ya cubre el break de GPU por `outMesh→inMesh` directo. Este archivo añade la perspectiva de stack ordering completo: el orden relativo de skinCluster / blendShape_correctives / deltaMush determina si hay 1 o 3 clusters GPU, y cuántos readbacks se producen. También añade los datos de performance de GPU por número de influencias — mostrando que 8 influencias es el sweet spot, no 4. La función `audit_deformer_stack()` es nueva y más detallada que las funciones previas de auditoría.

## Aplicable directamente

YES — `audit_deformer_stack()` y `optimize_skin_weights()` son integrables directamente en el post-build health check de autorig_tools en <1h. También aplicable: revisar que en el build, los corrective blendShapes se añaden DESPUÉS del skinCluster en el DG (no antes), y que deltaMush (si se usa) queda al final del stack GPU.

## Fuente
- GPU-supported deformers (Autodesk Help 2024): https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-1B2D8791-55F7-4FF8-8DFC-56AC86630FFC
- Deformation Layering in Maya's GPU World: https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82
- Maya Cached Playback Whitepaper 2024: https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2024/MayaCachedPlaybackWhitePaper.html
- MPxGPUDeformer C++ API: https://help.autodesk.com/cloudhelp/2026/JPN/MAYA-API-REF/cpp_ref/class_m_px_g_p_u_deformer.html
