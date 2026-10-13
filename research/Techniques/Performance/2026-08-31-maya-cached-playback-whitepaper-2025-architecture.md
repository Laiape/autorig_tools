---
source: https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2025/MayaCachedPlaybackWhitePaper.pdf
found: 2026-08-31
category: performance
priority: 2
tags: [maya, performance, cached-playback, cache, evaluation, GPU, Caching-Point, topology, rig-optimization]
status: NEW
---

# Maya Cached Playback White Paper 2025 — Arquitectura Completa

## Descripción
Documento técnico oficial de Autodesk (PDF) que detalla la arquitectura interna de Cached Playback en Maya 2025. Orientado a riggers, TDs y autores de plugins. Cubre los tres modos de caché, la mecánica de invalidación por topología (no por valor), la colocación de Caching Points, y las reglas que determinan si un nodo o deformador puede participar en el caché. Complementa la cobertura general de Parallel Evaluation ya en el Drive — este documento va al detalle de implementación del sistema de caché específicamente.

## Fundamento matemático / técnico

**Three cache modes (2025):**

```
Mode 1: Evaluation Cache (default, most compatible)
├── Stores: output attribute values of nodes at Caching Points
├── Location: RAM (system memory)
├── What's cached: any node that can be serialized (float, matrix, mesh, etc.)
├── Playback speedup: eliminates node re-evaluation on unchanged frames
└── Limitation: VP2 still re-renders from CPU data each frame

Mode 2: Viewport Software Cache  
├── Stores: VP2-ready geometry (vertex buffers) in CPU memory
├── Location: RAM (VP2 buffer format)
├── What's cached: geometry after all deformers, ready for GPU upload
└── Speedup: eliminates VP2 consolidation + deformer re-evaluation on playback

Mode 3: Viewport Hardware Cache (fastest)
├── Stores: geometry directly in GPU VRAM
├── Location: GPU memory (OpenGL/DX buffers)
├── Playback: zero CPU overhead — GPU reads directly from cache
├── Requirement: GPU Override must be active for deformation chain
└── Blocker (≤2024): animated .visibility attribute in the cache chain
   (Maya 2026: dynamic GPU reclamation resolves most visibility blockers)
```

**Cache invalidation mechanism — Topology Tracking:**
```
"Topology" in Maya cache = the GRAPH STRUCTURE of dependencies, not values.
A cache is invalidated when:
  1. A node is added/removed from the evaluation graph
  2. An attribute connection changes (plug connection)
  3. A node's evaluation type changes (DG → parallel → GPU)

A cache is NOT invalidated when:
  - Attribute values change (frame advance, control moved)
  - This means: moving a control on a cached frame → cache hit (no re-eval)
```

**Caching Points — placement rules:**
```
Auto-placed Caching Points: Maya inserts at:
  - skinCluster output
  - blendShape output  
  - Deformation chain terminus (last deformer before shape)
  - Root of output-only subtrees

Author-placed Caching Points (via cacheEvaluator command):
  cmds.cacheEvaluator(cacheName='myCache', 
                      nodeTypes=['skinCluster', 'blendShape'],
                      waitForCache=1)
```

**"always dirty" node types — cache killers:**
```
Nodes that mark themselves always-dirty (never cache):
  - expression nodes (arbitrary MEL dependency → cannot be analyzed)
  - Python MPxNode without proper dirty propagation declaration
  - Any node calling MDataBlock.setClean() incorrectly
  
Effect: ALL downstream nodes of an always-dirty node are excluded from cache.
Measurement: A single expression in a facial rig can exclude 50-200 downstream
             nodes from caching → cache provides zero speedup for those paths.
```

**Custom shape caching requirements:**
```cpp
// For a custom MPxSurfaceShape to be cacheable:
MTypeId MyShape::typeId() { return MY_TYPE_ID; }

// Must declare geometry data type:
MStatus MyShape::initialize() {
    // Register as geometry producer for caching
    MFnPlugin::registerShape(
        "myShape", 
        MY_TYPE_ID, 
        MyShape::creator,
        MyShape::initialize,
        MyShapeUI::creator,
        &MyShapeGPUDeformer::creator  // ← GPU deformer = cacheable
    );
}
// Without MPxGPUDeformer: shape falls back to Evaluation Cache only
// With MPxGPUDeformer: eligible for Viewport Hardware Cache
```

**Caching effectiveness formula:**
```
Actual speedup = (frames_served_from_cache / total_frames) × max_speedup

Typical max_speedup values:
  Evaluation Cache:      5-10x  (eliminates node computation)
  VP Software Cache:    10-20x  (eliminates VP2 consolidation)  
  VP Hardware Cache:   20-130x  (Disney Frozen 2: 5fps → 130fps)

cache_hit_rate degraders:
  - expression nodes: exclude large subgraph → hit_rate drops sharply
  - animated visibility: blocks VP Hardware Cache (pre-2026)
  - custom plugin dirty issues: false invalidations → hit_rate → 0
```

**Maya 2026 additions (referenced in 2025 white paper appendix):**
- Dynamic GPU Node Reclamation: nodes previously classified as `globally_serialize` are re-evaluated frame-by-frame for GPU eligibility
- Animated visibility no longer blocks VP Hardware Cache (separate path)
- follicle + uvPin: local readback only, not full cluster break

## Implementación en Maya

**Python: audit rig for cache compatibility:**
```python
import maya.cmds as cmds
from maya import OpenMaya as om

def audit_cache_blockers(rig_root):
    """
    Returns dict of cache-breaking issues found in rig.
    Categories: always_dirty, missing_gpu, topology_risk
    """
    issues = {'always_dirty': [], 'missing_gpu': [], 'topology_risk': []}
    all_nodes = cmds.listHistory(rig_root, allFuture=False) or []
    
    for node in all_nodes:
        ntype = cmds.nodeType(node)
        
        # Always-dirty nodes
        if ntype == 'expression':
            downstream = len(cmds.listHistory(node, future=True) or [])
            issues['always_dirty'].append({
                'node': node,
                'type': ntype,
                'downstream_count': downstream,
                'severity': 'HIGH' if downstream > 20 else 'MEDIUM'
            })
        
        # Deformers without GPU support
        gpu_supported = {
            'skinCluster', 'blendShape', 'deltaMush', 
            'wire', 'cluster', 'nonLinear', 'morph'
        }
        inherited = cmds.nodeType(node, inherited=True) or []
        if 'geometryFilter' in inherited and ntype not in gpu_supported:
            issues['missing_gpu'].append({'node': node, 'type': ntype})
        
        # Topology risk: outMesh→inMesh direct connections
        if ntype in ('mesh', 'nurbsSurface'):
            outputs = cmds.listConnections(f'{node}.outMesh', 
                                           destination=True, type='mesh') or []
            for out in outputs:
                if cmds.attributeQuery('inMesh', node=out, exists=True):
                    issues['topology_risk'].append({
                        'source': node, 'dest': out,
                        'fix': 'Replace with blendShape passthrough'
                    })
    
    return issues

def print_cache_report(rig_root):
    issues = audit_cache_blockers(rig_root)
    print(f"\n=== CACHE AUDIT: {rig_root} ===")
    print(f"Always-dirty nodes: {len(issues['always_dirty'])}")
    for i in sorted(issues['always_dirty'], 
                    key=lambda x: x['downstream_count'], reverse=True)[:5]:
        print(f"  [{i['severity']}] {i['type']} '{i['node']}' "
              f"→ {i['downstream_count']} downstream")
    print(f"\nDeformers without GPU: {len(issues['missing_gpu'])}")
    for i in issues['missing_gpu'][:5]:
        print(f"  {i['type']} '{i['node']}'")
    print(f"\nTopology breaks: {len(issues['topology_risk'])}")
    for i in issues['topology_risk']:
        print(f"  {i['source']} → {i['dest']}: {i['fix']}")
```

**Enable caching modes programmatically:**
```python
# Evaluation Cache (safest, always try this first):
cmds.evaluationManager(mode='parallel')
cmds.cacheEvaluator(cachingPoints='auto', waitForCache=0)

# Check current cache mode:
print(cmds.evaluationManager(query=True, mode=True))
# → ['parallel'] or ['serial'] or ['off']

# Viewport Hardware Cache: enable from Time Slider > Cache > VP Cache
# No direct Python command — requires user action in GUI
# Or via optionVar:
cmds.optionVar(intValue=('vpCacheState', 1))  # 0=off, 1=evaluation, 2=vp2
```

## Comparación con autorig_tools

El log de 2026-07-20 ya menciona los tres modos de caché y la VP2 Hardware Cache. Este white paper 2025 añade el detalle de implementación que falta: las reglas exactas de colocación de Caching Points (auto vs. manual), la mecánica exacta de "topology tracking" vs. "value tracking", y el código Python para `audit_cache_blockers()`. El rig matrix-based de autorig_tools (multMatrix, decomposeMatrix, local_mmx pattern) está bien posicionado: ninguno de estos nodos es always_dirty. El riesgo principal es el rig facial, que puede tener expressions para correctives lip-sync legacy. Esta auditoría Python es el primer paso para cuantificar el impacto.

## Aplicable directamente

YES — `audit_cache_blockers(rig_root)` es implementable en 30 minutos y aplicable hoy sobre cualquier rig de autorig_tools. La función identifica exactamente qué expressions, custom deformers sin GPU, y outMesh→inMesh connections están degradando el cache hit rate. Combinar con `audit_expression_nodes()` del log 2026-07-27 para una auditoría completa de salud del rig. El white paper PDF completo documenta casos edge de caching para plugin authors — relevante si autorig_tools incluye MPxNode C++ custom.

## Fuente

- White Paper PDF 2025: https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2025/MayaCachedPlaybackWhitePaper.pdf
- White Paper PDF 2026: https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2026/MayaCachedPlaybackWhitePaper.pdf
- HTML (2024 version): https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2024/MayaCachedPlaybackWhitePaper.html
- Using Parallel Maya 2026: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html
