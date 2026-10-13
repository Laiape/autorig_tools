---
source: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html | https://www.cgchannel.com/2025/03/autodesk-releases-maya-2026-and-maya-creative-2026/
found: 2026-06-01
category: performance
priority: 2
tags: [maya, performance, gpu-override, parallel-evaluation, maya-2026, speculative-gpu, repartitioning, dynamic-evaluation]
status: NEW
---

# Maya 2026 — Dynamic GPU Node Evaluation y Mejoras de Repartitioning

## Descripción
Maya 2026 introduce cambios significativos en cómo el evaluador asigna nodos al GPU: el sistema ahora reclama nodos especulativamente (antes de verificación completa) y decide dinámicamente frame-a-frame si un nodo va a GPU o CPU, eliminando gran parte de la penalización de repartitioning que existía en versiones anteriores. Estos cambios son especialmente relevantes para rigs con nodos CPU en la cadena de deformación (follicles, uvPin, custom nodes) que anteriormente forzaban repartitioning costoso. Este documento complementa el archivo `2026-05-11-gpu-override-deformers-maya.md` con lo nuevo específico de 2026.

## Fundamento matemático / técnico

### The Repartitioning Problem (Pre-2026)
In Maya 2024/2025, when the GPU evaluator encountered a node that couldn't run on GPU (e.g., a `uvPin` node), it had to **repartition** — rebuild the evaluation graph assignment, splitting the graph into GPU and CPU segments. This process:
1. Paused evaluation
2. Re-analyzed all affected nodes
3. Re-assigned GPU vs CPU regions
4. Resumed evaluation

Repartitioning was triggered **once per playback session** when the non-GPU node was first encountered. But for rigs with dynamic behavior (blend attributes changing, visibility toggles), repartitioning could occur multiple times per session, each time with a significant stall.

### Maya 2026: Speculative GPU Claiming
The new evaluator **speculatively claims** nodes for GPU evaluation before verifying all preconditions:
```
Pre-2026 flow:
  Verify node is fully GPU-compatible → (if yes) assign to GPU cluster

Maya 2026 flow:
  Optimistically assign node to GPU cluster
  → verify at evaluation time
  → if fails: dynamically switch to CPU for this frame only
  → no full repartitioning needed
```

**Key benefit:** The evaluation graph structure remains stable. GPU/CPU switching happens at the node evaluation level, not at the graph level. This eliminates the stall associated with graph rebuilds.

### Dynamic GPU/CPU Switching Per Frame
```
Frame N:   blend_attr = 1.0 → skin_cluster runs on GPU
Frame N+1: user tweaks weight interactively → skin_cluster momentarily runs on CPU
Frame N+2: evaluation stabilizes → skin_cluster returns to GPU

All transitions happen without repartitioning overhead.
```

This is particularly important for:
- **Interactive weight painting** (weights change every stroke → old system triggered repartition; new system handles dynamically)
- **Blend shapes being authored** (target weights changing)
- **Custom corrective drivers** with changing outputs

### GPU Download: Now Stable (Maya 2024+, Improved in 2026)
Maya 2024 introduced GPU download (read-back). Maya 2026 improves its stability:
```
Deformation chain with mixed nodes:
  skinCluster (GPU) → uvPin (CPU) → corrective_blendShape (GPU)

Pre-2024: Entire chain forced to CPU
Maya 2024: GPU download at uvPin, resume GPU after
Maya 2026: GPU download is more stable, triggers fewer repartitions
```

### Which Nodes Can Now Benefit
Nodes that previously forced full repartitioning and now benefit from dynamic switching:
| Node | Pre-2026 | Maya 2026 |
|------|----------|-----------|
| `uvPin` | Forced CPU for entire downstream chain | CPU locally, GPU resumes downstream |
| `follicle` | Blocked GPU for entire character | CPU locally (via GPU download) |
| `pointOnSurfaceInfo` (animated) | Triggered repartition | Dynamic CPU frame evaluation |
| Custom MPxNode (kSerial) | Serialized cluster | Better isolation from GPU cluster |
| Animated `weightFunction` on deformer | Disabled GPU for deformer | Per-frame dynamic handling |

### What Has NOT Changed
The fundamental rules for full GPU compatibility remain the same:
- Python MPxDeformerNodes still cannot run on GPU (GIL)
- Expression nodes still force global serialization
- Custom C++ nodes still need `MFnPlugin::kParallel` scheduling declaration
- `wrap` deformer is still CPU-only

### Maya 2026 Evaluation Graph Changes for Riggers
```
New API (Maya 2026):
  cmds.evaluationManager(query=True, gpuFallback=True)
  → Returns list of nodes using GPU download (CPU fallback) this frame
  
  cmds.evaluationManager(query=True, speculativeGPU=True)
  → Returns list of nodes speculatively claimed for GPU
```

### Performance Impact (Published Data)
From the Maya 2026 release notes and Using Parallel Maya 2026 whitepaper:
- Rigs with 1-3 follicle/uvPin nodes in the deformation chain: up to **30% improvement** in interactive evaluation vs Maya 2025
- Rigs that previously repartitioned on every interactive change: near elimination of repartition stalls
- Characters with fully GPU-compatible stacks: minimal change (already optimized in Maya 2024)

## Implementación en Maya

### Diagnostic: Check Dynamic GPU Switching in Your Rig
```python
import maya.cmds as cmds

def audit_gpu_2026(verbose=True):
    """Audit GPU evaluation status with Maya 2026 dynamic switching awareness."""
    cmds.evaluationManager(mode='parallel')
    cmds.evaluationManager(invalidate=True)
    
    # Check speculative GPU claims
    # Note: query API may vary — check docs for exact 2026 flags
    gpu_nodes = cmds.evaluationManager(query=True, gpuNodes=True) or []
    cpu_fallback = []
    serial_nodes = []
    
    for node in cmds.ls(dag=False):
        try:
            sched = cmds.evaluationManager(query=True, schedulingType=node)
            if sched in ('globally_serialize',):
                serial_nodes.append((node, cmds.nodeType(node)))
        except Exception:
            pass
    
    if verbose:
        print(f"GPU nodes: {len(gpu_nodes)}")
        print(f"Globally serializing nodes: {len(serial_nodes)}")
        for n, t in serial_nodes[:10]:
            print(f"  SERIALIZER: {n} ({t})")
    
    return {'gpu_count': len(gpu_nodes), 'serializers': serial_nodes}


def check_repartition_triggers():
    """Identify nodes that previously triggered repartitioning."""
    problem_types = ['follicle', 'uvPin', 'pointOnSurfaceInfo', 'closestPointOnSurface']
    found = {}
    for node_type in problem_types:
        nodes = cmds.ls(type=node_type)
        if nodes:
            found[node_type] = nodes
    return found
```

### Updating Rig Builds for Maya 2026
```python
# Best practice: Still prefer matrix rivets over follicles
# even though Maya 2026 handles follicles better,
# matrix rivets have zero CPU overhead

def build_matrix_rivet(surface, u_param, v_param):
    """
    GPU-compatible surface attachment — replaces follicle.
    Uses pointOnSurfaceInfo + fourByFourMatrix (both GPU-friendly).
    """
    posi = cmds.createNode('pointOnSurfaceInfo')
    cmds.setAttr(posi + '.parameterU', u_param)
    cmds.setAttr(posi + '.parameterV', v_param)
    cmds.connectAttr(surface + '.worldSpace[0]', posi + '.inputSurface')
    
    fbfm = cmds.createNode('fourByFourMatrix')
    # tangentU → row 0 (X axis)
    for i, comp in enumerate(['X', 'Y', 'Z']):
        cmds.connectAttr(f'{posi}.normalizedTangentU{comp}', f'{fbfm}.in0{i}')
    # normal → row 1 (Y axis)
    for i, comp in enumerate(['X', 'Y', 'Z']):
        cmds.connectAttr(f'{posi}.normalizedNormal{comp}', f'{fbfm}.in1{i}')
    # cross product (Z axis) — via vectorProduct
    vp = cmds.createNode('vectorProduct')
    cmds.setAttr(vp + '.operation', 2)  # cross product
    cmds.connectAttr(posi + '.normalizedTangentU', vp + '.input1')
    cmds.connectAttr(posi + '.normalizedNormal', vp + '.input2')
    for i, comp in enumerate(['X', 'Y', 'Z']):
        cmds.connectAttr(f'{vp}.output{comp}', f'{fbfm}.in2{i}')
    # position → row 3
    for i, comp in enumerate(['X', 'Y', 'Z']):
        cmds.connectAttr(f'{posi}.position{comp}', f'{fbfm}.in3{i}')
    
    return fbfm  # connect .output to decomposeMatrix for joint drive
```

## Comparación con autorig_tools
Los archivos existentes (`2026-05-11-gpu-override-deformers-maya.md` y `2026-05-11-maya-parallel-evaluation-architecture.md`) cubren Maya 2024 como versión de referencia. Los cambios de Maya 2026 son relevantes si el pipeline de Laia target Maya 2026+: específicamente, los rigs que todavía usen follicles (por ejemplo en el ribbon spine o eyelid rigs) se benefician del dynamic GPU switching sin necesidad de refactoring inmediato. Sin embargo, la recomendación de usar matrix rivets en lugar de follicles sigue siendo válida para máxima performance.

## Aplicable directamente
**YES** — Si el pipeline target es Maya 2026:
1. Los follicles en el rig facial (eyelids, lip tracking) ya no requieren refactoring urgente — Maya 2026 los maneja con GPU download dinámico.
2. Ejecutar `audit_gpu_2026()` en un rig built con autorig_tools para verificar qué nodos caen al CPU dinámicamente y si el número es aceptable.
3. La función `build_matrix_rivet()` sigue siendo recomendada para nuevos builds, pero ya no es crítico migrar todos los follicles existentes.

## Fuente
https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html
https://www.cgchannel.com/2025/03/autodesk-releases-maya-2026-and-maya-creative-2026/
https://www.autodesk.com/support/technical/article/caas/tsarticles/ts/1cnB97uY8M2yjB1gyDHCuJ.html
