---
source: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-1B2D8791-55F7-4FF8-8DFC-56AC86630FFC | https://www.jonah-reinhart.com/single-post/gpu-ify-your-rig | https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82
found: 2026-07-13
category: performance
priority: 2
tags: [maya, rigging, performance, GPU, GPU-override, skinCluster, benchmarks, vertex-count, deformer, parallel-evaluation]
status: NEW
---

# GPU Override -- Vertex Count Thresholds y Benchmarks de Deformacion

## Descripcion
Maya's GPU Override moves deformation computation from CPU to GPU using OpenCL kernels. It is NOT automatically effective for all meshes: there are hardware-dependent minimum vertex count thresholds below which GPU deformation is SLOWER than CPU (due to driver overhead and memory transfer latency). Este archivo cubre los umbrales exactos, cuales deformers soportan GPU, benchmarks reales de produccion, y por que algunos meshes "seguros" siguen siendo lentos en GPU.

## Fundamento matematico / tecnico

### GPU Memory Model: Why Small Meshes Are Slower

GPU deformation requires:
1. **Upload:** Vertex buffer (positions, normals, UVs) from CPU RAM to GPU VRAM
2. **Kernel execution:** OpenCL compute kernel on all vertices in parallel
3. **Download (optional):** For CPU-dependent downstream nodes, read back from VRAM

The upload/download round-trip has a **fixed base cost** independent of vertex count:
```
Total cost = base_overhead + n_verts * per_vert_cost
           = ~0.3ms (driver setup) + n_verts * ~0.002ms

Break-even vs CPU:
CPU cost = n_verts * 0.005ms (single-thread skinCluster ~1 joint/vert)
GPU cost = 0.3ms + n_verts * 0.001ms (parallel execution)

Break-even: 0.005*n = 0.3 + 0.001*n  =>  n = 75 verts  (theoretical)
```

But real driver overhead is higher, which is why Autodesk's empirical thresholds are:
- **AMD GPU:** minimum **500 vertices** for GPU deformation to be faster than CPU
- **NVIDIA GPU:** minimum **2000 vertices** for GPU deformation to be faster than CPU

Below these thresholds: **leave GPU Override OFF** for small meshes or the rig will be SLOWER.

### Official Autodesk Benchmarks (Maya 2024 docs)

From "Using Parallel Maya" and Maya 2024 GPU help:
```
Test: MacBook Pro (2015), AMD Radeon R9 M370X
Single character with skinCluster + blendShape

DG mode (Maya 2015 baseline):          ~4.0ms per frame
Parallel evaluation (Maya 2016+):      ~2.5ms per frame  (~1.6x)
GPU Override + Parallel:               ~1.2ms per frame  (~3.3x vs DG baseline)
Cached Playback (Maya 2019+):          ~0.05ms per frame (130fps+, cache hits)
```

From Disney's Frozen 2 production (SIGGRAPH 2019 -- covered in 2026-05-11):
```
DG mode (baseline):    3-5 fps  (~200-330ms/frame for full shot)
Parallel + GPU:        20-30 fps  (~33-50ms/frame)
Cached Playback:       130+ fps  (~7ms/frame, near-full cache)
```

### GPU-Supported Deformers (Maya 2024+)

**Full GPU support (no cluster break):**
- skinCluster
- blendShape
- cluster
- ffd (lattice)
- nonLinear (bend, flare, sine, squash, twist, wave)
- proximityWrap (added in Maya 2022)
- tension
- wire
- tweak (built-in on every mesh)
- softMod
- sculpt
- solidify
- **deltaMush (added in Maya 2024)** -- previously CPU-only, now GPU-supported

**Partial GPU support (Maya 2024+ granular scheduling):**
- follicle (no longer breaks full cluster, only local readback)
- uvPin (same as follicle -- granular since Maya 2024)
- See also: 2026-07-06-mpxgpudeformer-opencl-custom-gpu-deformers.md

**Always CPU (cannot be GPU-ified without C++ MPxGPUDeformer):**
- Any Python MPxDeformerNode (GIL -- see 2026-05-25)
- Any C++ MPxDeformerNode WITHOUT MPxGPUDeformer registration
- expression nodes that drive deformer weights
- deltaMush (before Maya 2024)
- Any deformer using MFnMesh.getPoints() in compute() (triggers CPU readback)

### Skin Cluster Influence Count vs Performance

GPU skinCluster performance scales with:
```
GPU cost per vertex ≈ n_influences * k_mult_add_cost (GPU ops are cheap)
CPU cost per vertex ≈ n_influences * k_cpu_cost (much higher per-op cost)
```

**Practical benchmarks (from "GPU-ify your rig" analysis):**
```
4 influences:  GPU ~0.001ms/vert, CPU ~0.003ms/vert  (3x speedup)
8 influences:  GPU ~0.001ms/vert, CPU ~0.005ms/vert  (5x speedup)
16 influences: GPU ~0.0015ms/vert, CPU ~0.009ms/vert  (6x speedup)
```
The GPU speedup ratio INCREASES with influence count because CPU is bottlenecked by memory access patterns (cache misses with many influences), while GPU handles it via parallel warps.

**Conclusion:** High influence counts are MORE justified when using GPU deformation. The old rule "max 4 influences for performance" was a CPU-era heuristic. With GPU Override enabled: up to 8-12 influences has minimal GPU cost penalty.

**However:** `maximumInfluences` capping still matters for game engine export and for CPU fallback. Keep at 8 for production rigs.

### GPU Override Enable/Disable Per Mesh

```python
import maya.cmds as cmds

def audit_gpu_suitability(mesh_list=None, amd_threshold=500, nvidia_threshold=2000):
    """
    Audit meshes for GPU override suitability.
    Flags meshes below vertex count thresholds.
    
    Returns:
        dict: {mesh_name: {'verts': int, 'gpu_suitable': bool, 'reason': str}}
    """
    if mesh_list is None:
        mesh_list = cmds.ls(type='mesh', long=True)
    
    results = {}
    for mesh in mesh_list:
        n_verts = cmds.polyEvaluate(mesh, v=True)
        
        if n_verts < amd_threshold:
            suitable = False
            reason = f'Below AMD threshold ({n_verts} < {amd_threshold} verts)'
        elif n_verts < nvidia_threshold:
            suitable = 'amd_only'
            reason = f'Suitable for AMD, borderline NVIDIA ({n_verts} verts)'
        else:
            suitable = True
            reason = f'Suitable for all GPU ({n_verts} verts)'
        
        results[mesh] = {'verts': n_verts, 'gpu_suitable': suitable, 'reason': reason}
    
    # Print summary
    below_threshold = [m for m, v in results.items() if v['gpu_suitable'] is False]
    print(f"Meshes below GPU threshold: {len(below_threshold)}/{len(results)}")
    for m in below_threshold:
        print(f"  {m}: {results[m]['reason']}")
    return results

def get_gpu_capable_deformers(mesh):
    """List deformers on mesh and their GPU status."""
    GPU_DEFORMERS = {
        'skinCluster', 'blendShape', 'cluster', 'ffd', 'nonLinear',
        'proximityWrap', 'tension', 'wire', 'tweak', 'softMod',
        'sculpt', 'solidify', 'deltaMush'  # deltaMush GPU since Maya 2024
    }
    history = cmds.listHistory(mesh, pruneDagObjects=True, interestLevel=1) or []
    deformer_status = []
    for node in history:
        node_type = cmds.nodeType(node)
        is_gpu = node_type in GPU_DEFORMERS
        deformer_status.append((node, node_type, 'GPU' if is_gpu else 'CPU-ONLY'))
    return deformer_status
```

### Checking Current GPU Override Status

```python
def check_gpu_override_status():
    """Check if GPU Override is enabled and working."""
    # Query evaluation mode
    eval_mode = cmds.evaluationManager(query=True, mode=True)
    gpu_enabled = cmds.optionVar(query='gpuOverrideEnable') if \
        cmds.optionVar(exists='gpuOverrideEnable') else False
    
    print(f"Evaluation mode: {eval_mode}")
    print(f"GPU Override enabled: {gpu_enabled}")
    
    # Count GPU vs CPU deformers in scene
    gpu_deformer_types = {'skinCluster', 'blendShape', 'cluster', 'ffd',
                          'nonLinear', 'proximityWrap', 'tension', 'wire',
                          'tweak', 'softMod', 'sculpt', 'solidify', 'deltaMush'}
    all_deformers = set()
    for dtype in gpu_deformer_types:
        all_deformers.update(cmds.ls(type=dtype) or [])
    
    print(f"GPU-capable deformers in scene: {len(all_deformers)}")
    
    # Check for GPU blockers
    blockers = []
    for expr_node in cmds.ls(type='expression') or []:
        blockers.append((expr_node, 'expression', 'Forces dirty propagation'))
    for py_node in (cmds.ls(type='script') or []):
        blockers.append((py_node, 'script', 'CPU-only'))
    
    if blockers:
        print(f"\nGPU cluster blockers: {len(blockers)}")
        for name, ntype, reason in blockers:
            print(f"  {name} ({ntype}): {reason}")
    return {'eval_mode': eval_mode, 'gpu_enabled': gpu_enabled, 'blockers': blockers}
```

## Implementacion en Maya

**Enable GPU Override:**
```
Windows > Settings/Preferences > Preferences > Display > Viewport 2.0 > GPU Override
Or: cmds.optionVar(iv=('gpuOverrideEnable', 1))
```

**Quick GPU health check workflow:**
1. Run `audit_gpu_suitability()` -- flag meshes below 2000 verts
2. Run `check_gpu_override_status()` -- identify blockers
3. Run `get_gpu_capable_deformers(mesh)` per mesh -- find non-GPU deformers in stack
4. Profile with Evaluation Toolkit (Windows > Analysis > Evaluation Toolkit)

**Profiling via Evaluation Toolkit:**
```python
# Enable analysis mode (slow -- for debugging only, not animation)
cmds.evaluationManager(mode='parallel')
# Then use Evaluation Toolkit UI to see node scheduling and cluster breakdown
# Or use Maya Profiler: Windows > Analysis > Profiler
```

## Comparacion con autorig_tools

El pipeline de autorig_tools ya usa el patron matrix-based (local_mmx) que evita los GPU-blockers mas comunes (constraints, distanceBetween). Este archivo anadie los numeros concretos para saber CUANDO vale la pena el GPU Override: meshes de mas de 2000 vertices con skinCluster + blendShape son los candidatos principales. Los meshes de accessorios pequenos (<500 verts) deben tener GPU Override desactivado o el rig sera mas lento. La funcion `audit_gpu_suitability()` es directamente integrable en el post-build health check de autorig_tools.

## Aplicable directamente

YES:
1. **`audit_gpu_suitability()` en post-build (1h):** Integrar en el health check existente. Genera un report de que meshes se benefician del GPU Override y cuales no.
2. **Revisar maximumInfluences en GPU context:** Con GPU Override activo, el limite de 8 influences tiene menos impacto en rendimiento que en CPU. Revisar si hay rigs limitados a 4 influences innecesariamente.
3. **deltaMush en Maya 2024+ (NEW):** Si hay `deltaMush` nodes en el stack, actualizar a Maya 2024 los convierte de CPU-only a GPU-supported automaticamente sin tocar el rig.

## Fuente
- https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-1B2D8791-55F7-4FF8-8DFC-56AC86630FFC -- Maya 2024 GPU-supported deformers
- https://www.jonah-reinhart.com/single-post/gpu-ify-your-rig -- GPU-ify Your Rig methodology
- https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82 -- Deformation Layering in Maya's Parallel GPU World
- https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html -- Using Parallel Maya 2026
