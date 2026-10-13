---
source: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html
found: 2026-10-12
category: performance
priority: 2
tags: [maya, rigging, performance, profiler, evaluation-toolkit, benchmarking, parallel-evaluation, python]
status: NEW
---

# Maya Profiler & Evaluation Toolkit: Complete Benchmarking Workflow

## Descripción
El Evaluation Toolkit de Maya y el Profiler integrado son las herramientas oficiales para diagnosticar el rendimiento de rigs. Este archivo documenta el workflow completo de auditoría: desde activar el profiler hasta interpretar los resultados y identificar los nodos que serializan el grafo de evaluación. Basado en la documentación oficial de Autodesk Maya 2026 y el whitepaper de Cached Playback.

## Fundamento matemático / técnico

### The Evaluation Graph (EG) and Why It Matters

Maya's evaluation is built on two concepts:
1. **Dependency Graph (DG):** The traditional node graph — attribute dependencies, dirty propagation
2. **Evaluation Graph (EG):** A pre-built execution schedule — built once from the DG, reused per frame

The EG partitions nodes into "evaluation clusters" that can run in parallel. Key insight:
- **Once EG is built, dirty propagation is DISABLED** — the graph re-evaluates using the schedule, not dirty bits
- The EG is invalidated (and rebuilt) when topology changes: connection added/removed, attribute value that affects the graph structure

**Scheduling types (most to least parallel):**
```
kParallel (fully parallel)
kLocallySerialize (waits for other locally-serialized nodes in same cluster)  
kGloballySerialize (global barrier — BLOCKS EVERYTHING)
```

Globally serialized nodes: `expression`, custom Python MPxNode, old-style `scriptNode` animating attributes.

### Maya Profiler: Python API

```python
import maya.utils
import maya.cmds as mc

# --- Step 1: Enable profiler and record ---
def start_rig_profile(output_path='/tmp/rig_profile.txt'):
    mc.profiler(sampling=True, output=output_path)
    mc.profiler(reset=True)

def stop_rig_profile():
    mc.profiler(sampling=False)

# --- Step 2: Time evaluation modes ---
def benchmark_evaluation_modes(scene_path, frame_range=(1, 50)):
    results = {}
    for mode in ['off', 'parallel']:
        mc.evaluationManager(mode=mode)
        mc.currentTime(frame_range[0])
        import time
        t0 = time.perf_counter()
        for f in range(frame_range[0], frame_range[1]+1):
            mc.currentTime(f)
        t1 = time.perf_counter()
        results[mode] = (t1 - t0) / (frame_range[1] - frame_range[0] + 1) * 1000
        print(f"Mode {mode}: {results[mode]:.2f} ms/frame avg")
    return results

# --- Step 3: Identify globally-serialized nodes ---
def audit_node_scheduling(dag_root=None):
    """
    List nodes in scene by their scheduling type.
    globally_serialized nodes are the top priority to fix.
    """
    nodes = mc.ls(dag=False, long=True) if dag_root is None else \
            mc.listRelatives(dag_root, allDescendents=True, fullPath=True) or []
    
    globally_serialized = []
    locally_serialized = []
    
    for node in nodes:
        try:
            sched = mc.evaluator(query=True, nodeType=mc.nodeType(node))
        except:
            continue
        scheduling = mc.getAttr(node + '.schedulingType') if mc.attributeQuery('schedulingType', node=node, exists=True) else 'unknown'
        # Alternative: check via evaluationManager
        if mc.nodeType(node) == 'expression':
            globally_serialized.append(node)
        elif mc.nodeType(node) in ('animExpression', 'script'):
            locally_serialized.append(node)
    
    # More reliable: use evaluationManager to get current scheduling
    global_nodes = mc.evaluationManager(query=True, globallySerializedNodes=True) or []
    return {
        'globally_serialized': global_nodes,
        'expression_count': len(mc.ls(type='expression') or []),
        'python_node_count': len(mc.ls(type='unknown') or [])  # custom python nodes often appear here
    }
```

### Evaluation Toolkit: Cached Playback Python Control

```python
# Check cache compatibility
import maya.plugin.evaluator.cache_preferences as cp

def rig_cache_health_report():
    prefs = cp.CachePreferences()
    report = {
        'cache_mode': prefs.caching_mode,
        'gpu_override_enabled': mc.ogs(query=True, gpuMemoryLimit=True) > 0,
        'eval_mode': mc.evaluationManager(query=True, mode=True)[0],
        'custom_evaluators': mc.evaluator(query=True, enable=True) or []
    }
    
    # Check for cache-breaking patterns
    expressions = mc.ls(type='expression') or []
    report['expression_nodes'] = len(expressions)
    report['expression_names'] = expressions[:10]  # first 10
    
    # Get VP2 cache eligibility
    report['vp2_cache_blocked_by_visibility_anim'] = _check_visibility_animated()
    return report

def _check_visibility_animated():
    """Animated visibility blocks VP2 Hardware Cache."""
    anim_vis_count = 0
    for node in mc.ls(dag=True) or []:
        vis_curves = mc.listConnections(node + '.visibility', 
                                         source=True, type='animCurve') or []
        if vis_curves:
            anim_vis_count += 1
    return anim_vis_count

# Run benchmark with timer output
def full_rig_benchmark(rig_root, frame_range=(1, 100)):
    """Full pipeline benchmark: DG → Parallel → Cache."""
    print("=== RIG PERFORMANCE BENCHMARK ===")
    
    for mode in ['off', 'parallel']:
        mc.evaluationManager(mode=mode)
        import time
        mc.currentTime(1)  # reset
        times = []
        for f in range(*frame_range):
            t0 = time.perf_counter()
            mc.currentTime(f)
            times.append((time.perf_counter() - t0) * 1000)
        avg = sum(times) / len(times)
        print(f"  {mode:10}: {avg:.2f} ms/frame  ({1000/avg:.1f} fps)")
    
    health = rig_cache_health_report()
    print(f"\n  Expression nodes: {health['expression_nodes']}")
    print(f"  Animated visibility nodes: {health['vp2_cache_blocked_by_visibility_anim']}")
    print(f"  GPU Override: {'ON' if health['gpu_override_enabled'] else 'OFF'}")
    return health
```

### Production Benchmark Reference Points (community-sourced)

| Rig Type | DG (ms/f) | Parallel (ms/f) | Cached (ms/f) | Notes |
|----------|-----------|-----------------|---------------|-------|
| Simple biped, 50 joints | 4–8 | 1.5–3 | 0.3–0.8 | Baseline |
| Hero biped + facial | 15–40 | 5–12 | 0.5–1.5 | Expression-free |
| Hero biped + facial (legacy) | 40–120 | 30–80 | N/A (blocked) | With expressions |
| Crowd NPC (stripped) | 1–3 | 0.5–1 | 0.1–0.3 | Minimal features |
| Full body + sim layer | 80–200 | 30–80 | 2–10 | Sim breaks cache |

Source: Autodesk "Using Parallel Maya 2026", Rigging Dojo blog, Disney Frozen 2 SIGGRAPH paper.

## Implementación en Maya

The key Python entry point:
```python
# Invoke from Maya Script Editor or via userSetup.py
full_rig_benchmark('character_root_grp', frame_range=(1, 50))
```

For per-node profiling, use Maya's built-in Profiler window:
- **Windows → Animation → Profiler** (MEL: `profilerTool()`)
- Click "Record" → scrub timeline → "Stop" → read color-coded thread timeline
- Red nodes = globally serialized; Yellow = locally serialized; Green = parallel

## Comparación con autorig_tools
El pipeline de autorig_tools necesita un health check integrado que se ejecute automáticamente al final del build. La función `full_rig_benchmark()` + `audit_node_scheduling()` forman el núcleo de ese check. El objetivo mínimo para un biped hero: < 10ms en modo Parallel, 0 expression nodes en el grafo principal, VP2 Hardware Cache activo (0 animated visibility nodes).

## Aplicable directamente
YES — Las funciones `full_rig_benchmark()` y `rig_cache_health_report()` son directamente añadibles a `autorig_tools/utils/performance.py`. Integrar en el método `post_build_validate()` del rig builder para que cada build genere automáticamente un informe de rendimiento. Tiempo de integración: 1-2h.

## Fuente
- Autodesk Using Parallel Maya 2026: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html
- Maya Cached Playback 2026 Whitepaper: https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2026/MayaCachedPlaybackWhitePaper.pdf
- SPECapc Maya 2023 Benchmark: https://gwpg.spec.org/benchmarks/benchmark/specapc-maya-2023
- Rigging Dojo: "Blazing Fast Character Rigs": https://www.riggingdojo.com/2021/01/22/blazing-fast-character-rigs-with-maya-2016/
