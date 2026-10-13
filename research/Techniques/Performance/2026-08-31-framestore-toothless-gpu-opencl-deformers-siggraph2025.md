---
source: https://dl.acm.org/doi/10.1145/3721239.3734131
found: 2026-08-31
category: performance
priority: 2
tags: [maya, rigging, performance, GPU, OpenCL, MPxDeformer, GPU-override, production, SIGGRAPH2025, Framestore]
status: NEW
---

# Highly Accurate GPU-Accelerated Animation Rigs for Toothless — Framestore / SIGGRAPH 2025

## Descripción
Presentación en SIGGRAPH 2025 Talks (ACM DL: 10.1145/3721239.3734131) por Framestore, describiendo la implementación de deformadores GPU para el personaje Toothless en *How to Train Your Dragon* (live-action, 2025). Toothless tiene ~200K vértices con deformadores complejos (piel, músculos, collisiones, wraps) que no pueden implementarse solo con skinCluster. El problema: los MPxDeformers custom de CPU bloquean el GPU cluster de Maya, forzando a los animadores a usar proxies de baja resolución. La solución: portar los deformadores a kernels OpenCL que corren dentro del GPU Override de Maya, manteniendo precisión CPU-equivalente. Resultado: 13 FPS → 19 FPS de media en el rig completo, eliminando la necesidad de proxy rigs para animación interactiva.

## Fundamento matemático / técnico

**GPU Override Architecture (Maya):**
Maya's Evaluation Manager GPU Override cluster evaluates a connected subgraph of GPU-compatible deformers as a single OpenCL execution unit. A single CPU-only deformer in the chain forces a full round-trip:

```
GPU cluster → [readback to CPU] → CPU deformer → [upload to GPU] → GPU cluster
Round-trip cost: ~4-10ms per deformer break (OpenCL buffer alloc + PCIe transfer)
```

**Framestore's approach — mirrored CPU/GPU deformer:**

```
class MyDeformer(MPxDeformerNode):
    # CPU path: reference implementation, numerically correct
    def deform(self, dataBlock, geoIter, matrix, multiIndex):
        verts = read_input_geometry(geoIter)
        result = cpu_deform_algorithm(verts, weights)
        write_output_geometry(geoIter, result)
    
    # GPU path: OpenCL kernel registered with MPxGPUDeformer
    @staticmethod
    def get_opencl_kernel():
        return """
        __kernel void my_deform(
            __global float4* positions,
            __global float* weights,
            __global float4* output,
            int numVerts
        ) {
            int id = get_global_id(0);
            if (id >= numVerts) return;
            // GPU equivalent of cpu_deform_algorithm
            output[id] = positions[id] + weights[id] * deform_delta(positions[id]);
        }
        """
```

**BVH (Bounding Volume Hierarchy) on GPU:**
Framestore's deformers include collision detection (self-collision, mesh-to-mesh). BVH construction is typically CPU-only. Their approach:
- Build BVH on GPU using parallel prefix scan (inclusive scan of AABB extents)
- Morton code-based spatial sorting on GPU (O(N log N) with radix sort)
- BVH traversal in OpenCL → no PCIe round-trip for collision queries

**Performance measurement methodology:**
```
passthrough_fps = fps with deformer computing identity (zero deformation)
actual_fps = fps with full deformation

efficiency = actual_fps / passthrough_fps
# Framestore achieved: efficiency ≈ 0.9 to 1.0 for most deformers
# (close to theoretical maximum — GPU overhead dominates, not computation)
```

**Automated testing framework:**
```python
# Test mode: CPU deformer runs OpenCL kernel in isolated context
# and compares results to CPU reference

class MyDeformerTestMode:
    def __init__(self, kernel_source):
        self.ctx = cl.create_some_context()
        self.queue = cl.CommandQueue(self.ctx)
        self.program = cl.Program(self.ctx, kernel_source).build()
    
    def run_and_compare(self, input_verts, cpu_result, tolerance=1e-4):
        # Upload to GPU
        buf = cl.Buffer(self.ctx, cl.mem_flags.COPY_HOST_PTR, hostbuf=input_verts)
        out_buf = cl.Buffer(self.ctx, cl.mem_flags.WRITE_ONLY, input_verts.nbytes)
        # Run kernel
        self.program.my_deform(self.queue, (len(input_verts),), None, buf, out_buf)
        gpu_result = np.empty_like(input_verts)
        cl.enqueue_copy(self.queue, gpu_result, out_buf)
        self.queue.finish()
        # Compare
        max_err = np.max(np.abs(gpu_result - cpu_result))
        assert max_err < tolerance, f"GPU/CPU mismatch: {max_err}"
```
This runs in batch mode (no GUI Maya required) and integrates with CI pipelines.

**Real production numbers:**
- Toothless hero rig: ~200K vertices
- Before GPU porting: ~13 FPS interactive (DG mode)
- After GPU porting: ~19 FPS average across deformer stack
- Characters achieving real-time (>24 FPS): subset with lighter deformer stacks
- Proxy rig elimination: animators could work directly on hero rig

**Key insight — GPU deformer dominance by vertex count:**
```
GPU overhead (fixed): ~0.3ms (driver dispatch, buffer management)
GPU compute time: O(N) but massively parallel
Crossover point (NVIDIA): ~2000 vertices — above this, GPU faster
Crossover point (AMD): ~500 vertices
→ At 200K vertices, GPU is 50-100x faster than CPU for same algorithm
```

## Implementación en Maya

**MPxGPUDeformer registration:**
```cpp
// C++ — register GPU counterpart to CPU MPxDeformerNode
MStatus MyDeformer::initialize() {
    // ... normal MPxDeformerNode init ...
    
    // Register GPU evaluator
    MGPUDeformerRegistry::registerGPUDeformerCreator(
        deformerTypeName,
        MyDeformerGPU::creator,
        MyDeformerGPU::validateNodeInGraph
    );
    return MStatus::kSuccess;
}

class MyDeformerGPU : public MPxGPUDeformer {
public:
    static MPxGPUDeformer* creator() { return new MyDeformerGPU(); }
    
    DeformerStatus evaluate(
        MDataBlock& block,
        const MEvaluationNode& evalNode,
        const MPlug& outputPlug,
        unsigned int numElements,
        const MAutoCLMem& inputBuffer,
        const MAutoCLEvent& inputEvent,
        MAutoCLMem& outputBuffer,
        MAutoCLEvent& outputEvent
    ) override {
        // Launch OpenCL kernel on inputBuffer → outputBuffer
        // inputBuffer = float4 positions (from GPU cluster)
        // outputBuffer = float4 deformed positions (stays in GPU)
        return DeformerStatus::kDeformerReturnStatusOK;
    }
};
```

**Python: detect GPU cluster breaks in existing rig:**
```python
import maya.cmds as cmds

def audit_gpu_deformer_chain(mesh):
    """Find deformers that break the GPU cluster."""
    history = cmds.listHistory(mesh, pruneDagObjects=True) or []
    deformers = [n for n in history if cmds.nodeType(n, inherited=True) 
                 and 'geometryFilter' in cmds.nodeType(n, inherited=True)]
    breaks = []
    for d in deformers:
        node_type = cmds.nodeType(d)
        # Check if has GPU counterpart registered
        # (heuristic: known CPU-only types)
        cpu_only_types = {'wrap', 'softMod', 'shrinkWrap', 
                          'proximityWrap', 'tension', 'sculpt'}
        if node_type in cpu_only_types:
            breaks.append((d, node_type, 'no GPU counterpart'))
        # Custom deformers: check for MPxGPUDeformer registration
        elif cmds.nodeType(d, inherited=True)[0] == 'geometryFilter':
            breaks.append((d, node_type, 'possible custom — verify GPU reg'))
    return breaks
```

## Comparación con autorig_tools

El stack de autorig_tools de Laia usa nodos nativos de Maya (skinCluster, blendShape, deltaMush) que ya tienen soporte GPU — esta área está bien cubierta. El gap que llena este paper es el caso de **deformadores custom** para necesidades específicas del personaje: collision-based bulge (cuando el brazo presiona el pecho), wrinkle maps dirigidos por geometría, muscular volume preservation custom. Hasta ahora, estos deformadores en production se escriben como MPxDeformerNode CPU-only y rompen el GPU cluster. El framework de Framestore permite mantener la cadena GPU para deformadores arbitrariamente complejos, con testing automatizado para verificar equivalencia CPU/GPU.

## Aplicable directamente

YES — El patrón de implementar un MPxDeformerNode con su MPxGPUDeformer mirror es directamente implementable en C++ para cualquier deformador custom de autorig_tools. La función de auditoría `audit_gpu_deformer_chain()` en Python es aplicable inmediatamente sobre cualquier rig de producción. Si autorig_tools tiene wraps o custom deformers en Python (que por GIL son always CPU-only), este framework provee la arquitectura para migrarlos a C++ + OpenCL con testing automatizado. Tiempo estimado para un deformador custom sencillo (p.ej., contact-based bulge): 2-4 días con el framework.

## Fuente

- ACM DL paper: https://dl.acm.org/doi/10.1145/3721239.3734131
- SIGGRAPH 2025 Talks proceedings: https://www.siggraph.org/wp-content/uploads/2025/08/Talks.html
- Framestore page: https://www.framestore.com/news/how-train-your-dragon-discovering-toothless
- befores&afters highlights: https://beforesandafters.com/2025/05/22/the-siggraph-2025-program-is-out-heres-some-highlights/
- Disney/Autodesk 2019 foundation (GPU+Parallel for Frozen 2): https://media.disneyanimation.com/technology/publications/2019/RealTimeRigManip.pdf
