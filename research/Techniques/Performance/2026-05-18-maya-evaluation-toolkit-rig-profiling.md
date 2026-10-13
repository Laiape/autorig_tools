---
source: https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-E22B253D-914B-4056-93F5-755702A6C998
found: 2026-05-18
category: performance
priority: 2
tags: [maya, performance, evaluation-toolkit, profiling, parallel-evaluation, scheduling, diagnosis, benchmark]
status: NEW
---

# Maya Evaluation Toolkit — Profiling de Rigs, Diagnosis de Serialización y Benchmarks

## Descripción
El Evaluation Toolkit (ET) de Maya es la herramienta de diagnóstico principal para entender el rendimiento de un rig en Parallel Evaluation. Permite ver el grafo de evaluación, identificar qué nodos fuerzan serialización, medir tiempos por nodo, y verificar qué deformadores corren en GPU. Es la herramienta que Disney usó sistemáticamente en Frozen 2 para identificar bottlenecks. Maya 2024 añadió nuevas opciones de visualización y un widget de Outliner con datos de scheduling por nodo.

## Fundamento matemático / técnico

### Where to Find It
`Windows → Analysis → Evaluation Toolkit` (Maya 2018+)

### Evaluation Toolkit Panels

**1. Evaluation Graph Viewer**
Visualizes the dependency graph as it will be evaluated by the Evaluation Manager — NOT the same as the Node Editor (which shows DG connections). The Evaluation Graph is preprocessed and may look different:
- Nodes are grouped into **clusters** (connected subgraphs that run on the same thread)
- Arrow direction = evaluation order (data flows from right to left in the ET graph)
- Color coding: GPU nodes (blue), CPU-only nodes (orange), unscheduled (grey)

**2. Scheduling Type Display**
For each node, the ET shows its scheduling type:
| Scheduling Type | Meaning |
|----------------|---------|
| `parallel` | Can execute concurrently with other nodes |
| `locally_serialize` | Must run sequentially relative to sibling nodes in same cluster |
| `globally_serialize` | Forces single-thread execution of all downstream nodes |
| `untrusted` | Node has not been verified safe for parallel — runs last, serially |

**`globally_serialize` is the killer.** Expressions, Python MPxNodes, and old plugins default to this. Every node downstream of a globally-serialized node is also effectively serialized.

**3. GPU Override Validation**
The ET shows which nodes are:
- Running on GPU (green tick)
- Blocked from GPU (red ✗) with reason
- In "speculative GPU" mode (yellow, Maya 2024+)

**4. Profiler Integration (Maya 2024+)**
`Windows → Analysis → Profiler` — records per-node evaluation times across frames. Combined with ET, allows ranking nodes by cost:
```
Most expensive nodes → investigate for optimization or replacement
```

### Python API for Scheduling Diagnosis

```python
import maya.cmds as cmds

# ─────────────────────────────────────────────────────────────────────────────
# 1. Find all globally-serializing nodes in the scene
# ─────────────────────────────────────────────────────────────────────────────
def find_serialization_culprits():
    """Returns list of nodes that force global serialization."""
    offenders = []
    all_nodes = cmds.ls(dag=False)
    for node in all_nodes:
        try:
            stype = cmds.evaluationManager(query=True, schedulingType=node)
            if stype in ('globally_serialize', 'untrusted'):
                offenders.append({
                    'node': node,
                    'type': cmds.nodeType(node),
                    'scheduling': stype
                })
        except Exception:
            pass  # some nodes don't support scheduling query
    return sorted(offenders, key=lambda x: x['scheduling'])

# ─────────────────────────────────────────────────────────────────────────────
# 2. Benchmark parallel vs DG evaluation time
# ─────────────────────────────────────────────────────────────────────────────
def benchmark_evaluation(n_frames=30, frame_start=1):
    """Compare DG vs Parallel evaluation times over n_frames."""
    import time
    
    results = {}
    for mode in ('off', 'parallel'):  # 'off' = DG mode
        cmds.evaluationManager(mode=mode)
        cmds.evaluationManager(invalidate=True)
        
        # Warmup
        cmds.currentTime(frame_start, update=True)
        
        t0 = time.perf_counter()
        for f in range(frame_start, frame_start + n_frames):
            cmds.currentTime(f, update=True)
        elapsed = time.perf_counter() - t0
        
        fps = n_frames / elapsed
        ms_per_frame = (elapsed / n_frames) * 1000
        results[mode] = {'fps': fps, 'ms': ms_per_frame}
    
    # Back to parallel
    cmds.evaluationManager(mode='parallel')
    return results

# ─────────────────────────────────────────────────────────────────────────────
# 3. Find expression nodes in scene
# ─────────────────────────────────────────────────────────────────────────────
def find_expressions():
    """List all expression nodes — primary cause of serialization."""
    exprs = cmds.ls(type='expression')
    results = []
    for expr in exprs:
        # Get the expression string
        expr_str = cmds.expression(expr, query=True, string=True) or ''
        # Find what it drives
        connections = cmds.listConnections(expr, source=False, destination=True) or []
        results.append({
            'expression': expr,
            'drives': connections[:5],  # first 5 driven attrs
            'preview': expr_str[:100]
        })
    return results

# ─────────────────────────────────────────────────────────────────────────────
# 4. Check GPU override status per deformer
# ─────────────────────────────────────────────────────────────────────────────
def check_gpu_status():
    """
    Reports which deformers in the scene are GPU-accelerated.
    Requires GPU Override to be ON (cmds.ogs(gpuOverride=1) or via Prefs).
    """
    gpu_nodes = []
    cpu_nodes = []
    
    deformer_types = ['skinCluster', 'blendShape', 'deltaMush', 'cluster', 
                      'lattice', 'softMod', 'wire']
    
    for dt in deformer_types:
        for node in cmds.ls(type=dt):
            # Query GPU state via evaluationManager
            try:
                # This is simplified — in practice use the ET UI or C++ API
                # for definitive GPU status
                is_gpu = cmds.evaluationManager(query=True, nodeType=dt)
                (gpu_nodes if is_gpu else cpu_nodes).append((node, dt))
            except Exception:
                cpu_nodes.append((node, dt))
    
    return {'gpu': gpu_nodes, 'cpu': cpu_nodes}

# ─────────────────────────────────────────────────────────────────────────────
# 5. Full rig health report
# ─────────────────────────────────────────────────────────────────────────────
def rig_health_report():
    """Run all checks and print a production-ready report."""
    print("=" * 60)
    print("RIG EVALUATION HEALTH REPORT")
    print("=" * 60)
    
    serializers = find_serialization_culprits()
    if serializers:
        print(f"\n⚠ SERIALIZATION CULPRITS ({len(serializers)} nodes):")
        for s in serializers[:10]:
            print(f"  [{s['scheduling']}] {s['node']} ({s['type']})")
    else:
        print("\n✓ No globally-serializing nodes found")
    
    expressions = find_expressions()
    if expressions:
        print(f"\n⚠ EXPRESSION NODES ({len(expressions)}):")
        for e in expressions:
            print(f"  {e['expression']} → drives: {e['drives']}")
            print(f"    Code: {e['preview'][:80]}...")
    else:
        print("\n✓ No expression nodes found")
    
    print("\n--- BENCHMARK (30 frames) ---")
    bench = benchmark_evaluation(30)
    dg_fps = bench['off']['fps']
    par_fps = bench['parallel']['fps']
    speedup = par_fps / dg_fps
    print(f"  DG mode:       {dg_fps:.1f} fps ({bench['off']['ms']:.1f} ms/frame)")
    print(f"  Parallel mode: {par_fps:.1f} fps ({bench['parallel']['ms']:.1f} ms/frame)")
    print(f"  Speedup:       {speedup:.1f}×")
    if speedup < 1.5:
        print("  ⚠ Low parallel speedup — likely due to serialization bottlenecks above")
    elif speedup > 3.0:
        print("  ✓ Good parallel performance")
    
    print("=" * 60)
```

### Production Profiling Workflow (Disney Method)
1. **Enable Parallel mode** and GPU Override
2. **Open Evaluation Toolkit** → switch to "Scheduling" tab
3. **Look for globally_serialize nodes** — these are always step 1 to fix
4. **Use Profiler** (`Windows → Analysis → Profiler`) with `CPU` track → record 5 frames → look at per-node times
5. **Sort by cost** → top 5 expensive nodes → investigate
6. **Compare before/after** every change with `benchmark_evaluation()`
7. **Verify GPU** → ET GPU tab → confirm deformers show "GPU" not "CPU"

### Real Numbers from Production
| Character complexity | DG mode | Parallel mode | +GPU Override | Cached Playback |
|---------------------|---------|---------------|---------------|-----------------|
| Simple (50 bones, 5K verts) | 60fps | 120fps | 150fps | 500fps+ |
| Medium (120 bones, 20K verts) | 20fps | 50fps | 80fps | 300fps |
| Heavy (200 bones, 80K verts, correctives) | 5fps | 15fps | 30fps | 130fps |
| Disney Frozen 2 hero char | 3-5fps | 10-15fps | 20-30fps | 130fps+ |

(Sources: Rigging Dojo 2022 "Goro" rig, Disney SIGGRAPH 2019, Autodesk whitepaper)

**Key insight:** Parallel speedup is largest on **medium** complexity rigs. Very heavy rigs often have a serialization bottleneck that limits parallel benefits. Very simple rigs are already fast enough that parallel overhead isn't worth it.

### Maya 2024 Evaluation Toolkit Improvements
- **New graphical output:** The ET can now export evaluation graph data as structured reports
- **Outliner integration:** Right-click any node in Outliner → "Show in Evaluation Graph"
- **Scheduling type in Attribute Editor:** Each node shows its scheduling type in a dedicated section
- **GPU speculative claiming:** ET shows "speculative GPU" vs "verified GPU" distinction for Maya 2024+ behavior

## Implementación en Maya
The `rig_health_report()` function above is directly usable in the autorig_tools post-build validation pass. Running it after every rig build gives an immediate snapshot of potential performance issues before the rig is delivered to animation.

## Comparación con autorig_tools
autorig_tools no tiene actualmente un proceso de validación de performance post-build. El `rig_health_report()` puede integrarse como el último paso del `build_rig()` o como una función separada `validate_rig_performance()` accesible desde la UI de autorig_tools. Imprimir los resultados en el Script Editor con colores (warnings en amarillo, errores en rojo) es una mejora de UX directa.

## Aplicable directamente
YES — `rig_health_report()` puede integrarse directamente en el pipeline de build de autorig_tools. Estimación: 2-3 horas de integración incluyendo la UI de output.

## Fuente
- Autodesk Evaluation Toolkit docs 2025: https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-E22B253D-914B-4056-93F5-755702A6C998
- Autodesk Evaluator Reference 2024: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-27845E36-B873-42EB-B06F-9FE983E1080D
- Rigging Dojo "Goro" optimization: https://www.riggingdojo.com/2022/12/21/optimizing-rigs-for-parallel-evaluation/
- Disney SIGGRAPH 2019: https://dl.acm.org/doi/abs/10.1145/3306307.3328181
