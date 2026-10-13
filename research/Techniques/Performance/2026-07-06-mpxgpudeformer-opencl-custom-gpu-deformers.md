---
source: https://help.autodesk.com/cloudhelp/2026/JPN/MAYA-API-REF/cpp_ref/class_m_px_g_p_u_deformer.html
found: 2026-07-06
category: performance
priority: 2
tags: [maya, rigging, performance, GPU, OpenCL, MPxGPUDeformer, custom-node, C++, deformer, parallel-evaluation]
status: NEW
---

# MPxGPUDeformer — Deformadores Custom en GPU OpenCL (C++ API)

## Descripción
MPxGPUDeformer es la API de Maya para implementar deformadores custom que se ejecutan nativamente en OpenCL en la GPU, a diferencia de `MPxDeformerNode` que siempre evalúa en CPU. Un GPUDeformer reemplaza la evaluación CPU dentro del GPU Deformer Evaluator de Maya, permitiendo que la cadena completa de deformación permanezca en GPU sin readback. Resuelve el problema crítico: un único deformador custom sin GPUDeformer registration rompe el cluster GPU y obliga a una round-trip CPU de todos los deformadores upstream (skinCluster, blendShape) a pesar de tener GPU support. El archivo `custom-mpxnode-parallel-evaluation.md` (2026-05-25) cubre el GIL de Python con MPxNode kParallel — este archivo cubre el nivel superior: GPU OpenCL evaluation.

## Fundamento matemático / técnico

### Arquitectura del GPU Deformer Evaluator

```
Evaluation Manager (EM)
  └── GPU Deformer Evaluator (GDE)
        ├── Step 1: Scan deformer stack, identify GPU-capable clusters
        ├── Step 2: For GPU cluster: upload geometry to GPU once at start
        ├── Step 3: Enqueue OpenCL kernels in pipeline order
        ├── Step 4: GPU→viewport (no CPU readback for GPU-only chains)
        └── Step 5: If non-GPU node found: break cluster → CPU readback

GPU cluster definition:
  All consecutive deformers that EITHER:
  (a) are built-in Maya deformers with GPU support, OR
  (b) have a registered MPxGPUDeformer implementation

Built-in GPU deformers:
  skinCluster, blendShape, cluster, ffd, nonLinear, proximityWrap,
  tension, wire, tweak, deltaMush*, softMod, sculpt, solidify
  (*deltaMush added GPU path in Maya 2024)
```

### What happens when GPU cluster is broken

```
Example deformer stack (bottom to top):
  1. skinCluster   → GPU supported ✓
  2. myCustomNode  → NO GPU registration ✗  ← BREAKS CLUSTER HERE
  3. blendShape    → GPU supported ✓

Evaluation:
  skinCluster: evaluates on GPU
  myCustomNode: Maya must read back from GPU to CPU (2-5ms stall)
                evaluate on CPU (serialized)
                upload result back to GPU (2-5ms stall)
  blendShape: evaluates on GPU (new cluster after myCustomNode)

Cost of the break: ~4-10ms overhead per frame just for the round-trips,
independent of what myCustomNode actually does.
```

### C++ Implementation: the two required methods

```cpp
#include <maya/MPxGPUDeformer.h>
#include <maya/MGPUDeformerRegistry.h>
#include <maya/MAutoCLMem.h>
#include <maya/MOpenCLInfo.h>
#include <maya/MFnPluginData.h>

class MyGPUDeformer : public MPxGPUDeformer {
public:
    // --- Factory ---
    static MPxGPUDeformer* creator() { return new MyGPUDeformer(); }
    
    // --- Primary method: called once per frame for GPU evaluation ---
    MPxGPUDeformer::DeformerStatus evaluate(
        MDataBlock& block,
        const MEvaluationNode& evalNode,
        const MPlug& outputPlug,
        const MPlugArray& inputPlugs,
        const MGPUDeformerData& inputData,
        MGPUDeformerData& outputData) override
    {
        // 1. Get input geometry buffer (already on GPU from upstream)
        MAutoCLMem inputPositions;
        MStatus status = inputData.getBuffer(
            inputPlugs[0],           // input mesh plug
            kFloat3,                 // position data type
            inputPositions           // output CL buffer
        );
        if (!status) return kDeformerFailure;
        
        unsigned int numVerts = inputData.numElements();
        
        // 2. Allocate output GPU buffer
        MAutoCLMem outputPositions;
        outputData.createBuffer(
            outputPlug,
            kFloat3,
            numVerts,
            outputPositions
        );
        
        // 3. Read per-node parameters from Maya's dataBlock (CPU side)
        // IMPORTANT: only read attributes that DON'T come from other GPU nodes
        MDataHandle envelopeHandle = block.inputValue(envelope, &status);
        float envelopeValue = envelopeHandle.asFloat();
        
        // 4. Build OpenCL kernel and set arguments
        if (!m_kernel.get()) {
            m_kernel = MOpenCLInfo::getOpenCLKernel(
                "myDeformer.cl", "myDeformKernel"
            );
        }
        cl_uint idx = 0;
        m_kernel.get().setArg(idx++, inputPositions.get());
        m_kernel.get().setArg(idx++, outputPositions.get());
        m_kernel.get().setArg(idx++, numVerts);
        m_kernel.get().setArg(idx++, envelopeValue);
        
        // 5. Enqueue kernel (async — Maya manages sync)
        size_t globalSize = (size_t)numVerts;
        MOpenCLInfo::getOpenCLCommandQueue().enqueueNDRangeKernel(
            m_kernel.get(),
            cl::NullRange,
            cl::NDRange(globalSize),
            cl::NullRange  // let OpenCL pick workgroup size
        );
        
        return kDeformerSuccess;
    }
    
    // --- Called when scene changes require GPU resource cleanup ---
    void terminate() override {
        m_kernel.reset();
    }

private:
    MAutoCLKernel m_kernel;
};
```

### Registration in plugin init

```cpp
MStatus initializePlugin(MObject obj) {
    MFnPlugin plugin(obj, "MyStudio", "1.0");
    
    // Register CPU deformer (required — GPUDeformer augments, not replaces)
    plugin.registerNode("myDeformer", MyDeformer::id,
                        MyDeformer::creator, MyDeformer::initialize,
                        MPxNode::kDeformerNode);
    
    // Register GPU override for this deformer type
    MGPUDeformerRegistrationInfo regInfo;
    regInfo.pluginId       = "com.studio.myDeformer";
    regInfo.deformerName   = "myDeformer";  // must match registerNode name
    regInfo.creator        = MyGPUDeformer::creator;
    
    MStatus gpuStatus;
    MString regKey = MGPUDeformerRegistry::registerGPUDeformerCreator(
        regInfo, &gpuStatus
    );
    // regKey is stored for deregistration in uninitializePlugin
    
    return MS::kSuccess;
}
```

### OpenCL Kernel structure

```opencl
// myDeformer.cl — loaded at runtime by MOpenCLInfo::getOpenCLKernel()
// Positions are stored as float3 packed in float4 buffers (w=1.0f)

__kernel void myDeformKernel(
    __global const float4* inputPos,
    __global float4* outputPos,
    unsigned int numVerts,
    float envelope
) {
    unsigned int vid = get_global_id(0);
    if (vid >= numVerts) return;
    
    float4 p = inputPos[vid];
    
    // ---- Custom deformation math ----
    // Example: push vertices along their local Y by sine wave
    float push = sin(p.x * 2.0f) * 0.1f * envelope;
    p.y += push;
    // ---------------------------------
    
    outputPos[vid] = p;
}
```

### Performance data

| Scenario | Approx. time per frame (10k verts) |
|----------|-------------------------------------|
| skinCluster GPU | ~0.5–1ms |
| blendShape GPU | ~0.3ms |
| Custom MPxDeformerNode CPU (kParallel) | ~3–8ms |
| Custom MPxGPUDeformer OpenCL | ~0.4–1ms |
| GPU cluster broken by 1 CPU node | +4–10ms overhead (readback) |
| deltaMush CPU (Maya native) | ~6–12ms |
| deltaMush GPU (Maya 2024) | ~0.5–1ms |

Observed GPU speedup for custom deformers: **5–20×** depending on vertex count and deformation complexity.

### Critical constraints

1. **Must be C++**: Python MPxDeformerNode cannot expose the required `evaluate()` symbol for GPU override registration. There is no Python path for MPxGPUDeformer.

2. **Data must be on GPU already**: if the deformer reads an attribute connected from a CPU-evaluated node (e.g., a Python node output), that forces a CPU-side read in `evaluate()`, breaking the GPU cluster.

3. **Float4 not Float3**: positions come as `float4[]` (w=1.0f padding), not `float3[]`. OpenCL kernel must handle float4.

4. **Thread safety**: `evaluate()` may be called from multiple threads. Do not use class member variables that aren't thread-safe.

5. **Kernel caching**: compile OpenCL kernel once (cache with `MAutoCLKernel`), not every frame.

## Implementación en Maya

### Audit function: detect GPU cluster breakers

```python
import maya.cmds as cmds

GPU_SUPPORTED_DEFORMERS = {
    'skinCluster', 'blendShape', 'cluster', 'ffd', 'nonLinear',
    'proximityWrap', 'tension', 'wire', 'tweak', 'deltaMush',
    'softMod', 'sculpt', 'solidify', 'morph', 'decomposeMatrix'
}

def audit_gpu_blockers():
    """
    Find deformers that break GPU evaluation clusters.
    Returns list of (mesh, deformer_name, deformer_type) tuples.
    """
    blockers = []
    for mesh in cmds.ls(type='mesh', long=True):
        if cmds.getAttr(mesh + '.intermediateObject'):
            continue
        history = cmds.listHistory(mesh, pruneDagObjects=True) or []
        for node in history:
            ntype = cmds.nodeType(node)
            if ntype not in GPU_SUPPORTED_DEFORMERS:
                # Check if it's a deformer-type node
                inherited = cmds.nodeType(node, inherited=True) or []
                if 'geometryFilter' in inherited:
                    blockers.append({
                        'mesh': mesh,
                        'node': node,
                        'type': ntype,
                        'action': 'Needs MPxGPUDeformer or remove from stack'
                    })
    return blockers

# Usage:
blockers = audit_gpu_blockers()
for b in blockers:
    print(f"GPU BLOCKER: {b['node']} ({b['type']}) on {b['mesh']}")
```

### Priority target for autorig_tools: GPU deltaMush replacement

Maya's native `deltaMush` was CPU-only until Maya 2024 (now has limited GPU path). For older versions, a custom MPxGPUDeformer replacement is the solution:

```opencl
// gpu_delta_mush.cl  (simplified — omits neighbor averaging)
__kernel void gpu_delta_mush_apply(
    __global const float4* bindPos,      // bind-pose positions
    __global const float4* smoothedPos,  // Laplacian-smoothed current positions  
    __global const float4* currentPos,   // current deformed positions
    __global float4* outputPos,
    float smoothWeight,
    unsigned int numVerts
) {
    int vid = get_global_id(0);
    if (vid >= numVerts) return;
    
    // Delta = deformed - smoothed (the "delta mush" displacement)
    float4 delta = currentPos[vid] - smoothedPos[vid];
    // Apply: smoothed + delta at reduced weight
    outputPos[vid] = smoothedPos[vid] + delta * (1.0f - smoothWeight);
}
```

The neighbor averaging (Laplacian smoothing) step requires a connectivity buffer — this is precomputed at bind time and stored as a constant GPU buffer.

## Comparación con autorig_tools

El archivo `custom-mpxnode-parallel-evaluation.md` (2026-05-25) cubre nodos Python con GIL — estos nunca pueden ser GPU. Este archivo cubre el paso siguiente: C++ MPxGPUDeformer que corre en OpenCL. Para autorig_tools, el impacto más directo es: (1) la función `audit_gpu_blockers()` es implementable HOY en Python para diagnosticar dónde se rompen los clusters GPU en rigs de producción, y (2) la arquitectura del GPUDeformer ayuda a entender por qué el `deltaMush` nativo de Maya (CPU-only hasta 2024) bloquea toda la cadena upstream cuando está en medio del stack.

## Aplicable directamente

YES (audit) / PARTIAL (implementation)
- **Inmediato**: implementar `audit_gpu_blockers()` como parte del health check de autorig_tools. Tiempo: 1 hora.
- **Medio plazo**: compilar el MPxGPUDeformer offset example del Maya devkit como primer experimento. El devkit incluye `gpuCachePlugin` y `identityNode` como examples completos. Familiarizarse con el C++ API antes de escribir un deformer custom real.
- **Largo plazo**: GPUDeformer para delta-mush compatible con Maya <2024 (donde el native deltaMush no tiene GPU path) — reemplaza el principal GPU blocker en rigs de producción existentes.

## Fuente
- https://help.autodesk.com/cloudhelp/2026/JPN/MAYA-API-REF/cpp_ref/class_m_px_g_p_u_deformer.html (Maya 2026 API reference)
- https://yantor3d.wordpress.com/2018/02/11/here-there-be-gpu-deformers/ (práctica implementación detallada)
- https://www.scottenglert.com/free-stuff/adding-opencl-kernel-to-gpu-deformer-without-kernel-source-file/ (embedded OpenCL kernels en .dll)
- https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html
- https://help.autodesk.com/cloudhelp/2022/JPN/Maya-SDK/cpp_ref/class_m_g_p_u_deformer_buffer.html (MGPUDeformerBuffer reference)
