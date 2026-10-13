---
source: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-1B2D8791-55F7-4FF8-8DFC-56AC86630FFC
found: 2026-05-11
category: performance
priority: 2
tags: [maya, performance, gpu-override, deformers, skincluster, blendshape, parallel-evaluation, gpu]
status: NEW
---

# Maya GPU Override — Deformadores Soportados, Bloqueantes y Maya 2024 Improvements

## Descripción
GPU Override es el modo de evaluación de Maya que traslada el cálculo de deformadores de la CPU a la GPU (VRAM), obteniendo hasta 8× speedup en personajes con muchos vértices. No todos los deformadores son compatibles, y ciertos nodos "bloqueantes" pueden desactivar el GPU Override para toda una cadena de deformación. Este documento cubre qué deformadores corren en GPU, qué los bloquea, y los cambios significativos de Maya 2024 que reducen el impacto de los nodos bloqueantes.

## Fundamento matemático / técnico

### How GPU Override Works
GPU Override operates within Parallel Evaluation. The Evaluation Manager identifies deformer nodes that:
1. Support GPU computation (known GPU-compatible nodes)
2. Have mesh data that can live in VRAM

For compatible deformers, Maya:
1. Uploads the input mesh (rest-pose vertices, normals, UVs) to GPU once
2. Each frame: uploads only the deformer parameters (weights, transforms)
3. Runs the deformation kernel in VRAM (CUDA/OpenCL)
4. Result mesh stays in VRAM — never downloaded to CPU unless needed

**GPU vs CPU transfer cost:** The speedup comes from avoiding CPU↔GPU data transfer per frame. If ANY deformer in the stack requires CPU evaluation, data must round-trip through system RAM — which can be slower than pure CPU if many transfers occur.

### Maya 2024: GPU Download (Critical Improvement)
**Pre-Maya 2024:** A non-GPU node (e.g., `follicle`, `uvPin`) in the deformation chain prevented the ENTIRE character from running on GPU. One bad node blocked everything upstream and downstream.

**Maya 2024+:** Added **GPU download** (read-back) support. Non-GPU nodes can pull data from VRAM to CPU, process it, then upload results back. This means:
- Characters with follicles or uvPin nodes can still run most deformers on GPU
- The non-GPU node still runs on CPU, but the rest of the chain remains GPU
- "Repartitioning" (dynamic split between GPU/CPU nodes) is now automatic

**Maya 2024 scheduling granularity:** Deformers are now claimed for GPU evaluation speculatively (before full verification) and repartitioned dynamically. Previous versions required full verification before GPU assignment — missing many optimization opportunities.

### Supported Deformers (GPU-Compatible)
| Deformer | GPU Since | Notes |
|----------|-----------|-------|
| skinCluster (LBS) | Maya 2016 | Full support |
| skinCluster (DQS) | Maya 2022 | Full support |
| blendShape | Maya 2016 | Full support, including in-between targets |
| deltaMush | Maya 2018 | Supported; performance scales with iteration count |
| cluster | Maya 2016 | Full support |
| lattice | Maya 2016 | Full support |
| softMod | Maya 2016 | Full support |
| wire | Maya 2018 | Supported |
| tension | Maya 2018 | Supported |
| morph | Maya 2020 | Supported |

### Deformers / Nodes That Block GPU (or Require CPU Fallback)
| Node | Behavior | Fix |
|------|----------|-----|
| follicle | CPU-only; blocks upstream (pre-2024) | Use matrix rivets instead |
| uvPin | CPU-only; blocks (pre-2024) | Upgrade Maya or use motionPath |
| pointOnSurfaceInfo | CPU-only | Replace with matrix approach |
| closestPointOnSurface | CPU-only | Pre-compute at build time |
| wrap deformer | CPU-only | Use GPU-compatible proxy |
| shrinkWrap | CPU-only | Use deltaMush instead |
| proximityWrap | CPU-only | Use GPU-compatible weight transfer |
| expression nodes | CPU-only; forces serialization | Replace with DG math nodes |
| animated weightFunction | Disables GPU for that deformer | Don't animate deformer weights per-frame |
| Python MPxDeformerNode | CPU-only (GIL) | Rewrite in C++ |

### What Disables GPU Even for Supported Deformers
Even if the deformer type is supported, GPU override is disabled when:
1. `weightFunction` attribute is animated (driving weights via time-varying function)
2. "Current geometry" mode for weight computation (uses deformed mesh for weights, not rest)
3. Driver attributes that are unsupported plugs (connecting a CPU-only node's output to the deformer)
4. Any input connection from a CPU-only node (pre-Maya 2024)

### Performance Data
- **Under 2K verts per mesh:** GPU provides minimal benefit (< 2× speedup). The overhead of GPU submission outweighs the parallel compute gain.
- **2K-10K verts:** 2-4× speedup over CPU.
- **10K+ verts:** 5-10× speedup, especially with blendShape + skinCluster stacked.
- **Disney Frozen 2 production:** 8× average interactive speedup across all characters using GPU + Parallel evaluation.
- **skinCluster alone on 30K mesh:** CPU ~15ms/frame → GPU ~2ms/frame (Maya 2023 benchmarks).

### Profiling GPU Override Status
```python
import maya.cmds as cmds

# Check if GPU override is enabled
cmds.ogs(query=True, gpuInstanceOverride=True)

# Force GPU override
cmds.ogs(gpuInstanceOverride=True)

# Check which nodes are on GPU vs CPU
# Use the Evaluation Toolkit (Windows > Analysis > Evaluation Toolkit)
# Or via Python:
cmds.evaluationManager(query=True, nodeType='skinCluster')

# Viewport > GPU Override (toggle) to test performance difference
```

## Implementación en Maya

**Designing for maximum GPU compatibility:**
```python
# BAD: follicle (blocks GPU pre-2024, partial pre-2025)
follicle = cmds.createNode('follicle')

# GOOD: matrix rivet using pointOnSurfaceInfo → fourByFourMatrix
posi = cmds.createNode('pointOnSurfaceInfo')
cmds.connectAttr('nurbsSurface.worldSpace[0]', posi+'.inputSurface')
ffm  = cmds.createNode('fourByFourMatrix')
dcmp = cmds.createNode('decomposeMatrix')
# ... (connect normal/tangent vectors to fourByFourMatrix)
# This approach keeps the surface attachment CPU-side but
# doesn't block the deformer chain from GPU

# BAD: expression on deformer weight
cmds.expression(s=f'{dm}.envelope = sin(time)')

# GOOD: use animCurve or DG nodes for time-varying envelope
# (animCurves are GPU-compatible timeline drivers)
```

## Comparación con autorig_tools

Si autorig_tools usa follicles en el ribbon spine (vs el método moderno pointOnSurfaceInfo + fourByFourMatrix), eso puede estar bloqueando el GPU Override en Maya < 2024. En Maya 2024+ el impacto es menor gracias al GPU download. La prioridad debe ser verificar si hay expression nodes en el rig — esos siempre fuerzan serialización CPU. El patrón local_mmx (matriz pura) de autorig_tools es ideal para GPU.

## Aplicable directamente
YES — Auditoría con Evaluation Toolkit: identificar qué nodos están en CPU vs GPU. Buscar follicles remanentes, expression nodes, y cualquier Python MPxDeformerNode. Los follicles del ribbon spine son el candidato más probable si el rig fue creado antes de 2022. Reemplazar por el patrón pointOnSurfaceInfo + fourByFourMatrix (documentado en 2026-05-05-ribbon-spine-matrix.md).

## Fuente
- GPU-supported deformers (Maya docs): https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-1B2D8791-55F7-4FF8-8DFC-56AC86630FFC
- GPU layering article (Medium): https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82
- Yantor3D GPU deformers: https://yantor3d.wordpress.com/2018/02/11/here-there-be-gpu-deformers/
- Disney SIGGRAPH 2019: https://media.disneyanimation.com/technology/publications/2019/RealTimeRigManip.pdf
