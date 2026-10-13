---
source: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2025/UsingParallelMaya.html
found: 2026-05-11
category: performance
priority: 2
tags: [maya, performance, parallel-evaluation, scheduling, dirty-propagation, evaluation-manager, rig-optimization]
status: NEW
---

# Maya Parallel Evaluation Architecture — Scheduling, Dirty Propagation & Rig Compatibility

## Descripción
Maya Parallel Evaluation (introducido en Maya 2016, madurado en 2022-2026) permite ejecutar múltiples nodos del Dependency Graph simultáneamente en diferentes threads CPU. Para que un rig se beneficie, su grafo DG debe tener ramas independientes que Maya pueda ejecutar en paralelo. Este documento cubre la arquitectura interna, qué estructuras de nodos son compatibles, y cómo diseñar rigs que maximicen el paralelismo.

## Fundamento matemático / técnico

### The Evaluation Graph (EG)
Maya's DG is a directed acyclic graph (DAG). Parallel Evaluation builds an **Evaluation Graph** — a preprocessed version of the DG that:
1. Topologically sorts the DG into layers (dependency levels)
2. Identifies independent branches (no data dependencies between them)
3. Groups nodes into **clusters** for scheduling

**Cluster scheduling:**
- Nodes in the same cluster execute sequentially on one thread
- Different clusters may execute in parallel on different threads
- Cluster size tradeoff: fewer large clusters = less scheduling overhead but less parallelism; many small clusters = more parallelism but more overhead

**Maya 2024 improvement:** Deformers are scheduled in more granular fashion (smaller clusters) allowing better pruning of the evaluation graph when not all deformers need evaluation in a given frame.

### Dirty Propagation
When a value changes (time or attribute edit), Maya propagates a "dirty" flag through the DG forward from the changed plug:
```
Animation curve → joint rotation → world matrix → downstream nodes
```
Only dirty nodes are re-evaluated. This means:
- Rigs with wide, independent branches = many nodes avoid evaluation
- Rigs with deep chains where everything depends on one root = almost everything re-evaluates every frame

**Design principle:** Minimize the "fan-in" of the dirty propagation. Prefer wide dependency graphs over deep ones.

### What Breaks Parallel Evaluation
1. **Unsupported node types:** Custom MPxNodes must declare parallel-safe scheduling. Legacy plugins default to serial evaluation.
2. **Expression nodes:** MEL/Python expressions run on the main thread → force serialization of all dependent nodes
3. **Script nodes and callbacks:** Any `scriptJob` or `callback` that reads scene state → forces DG to serialize
4. **Cycle detection:** Cyclic connections (even intended "lazy" cycles) → Maya falls back to DG mode
5. **Animated weight attributes on deformers:** Any deformer with `weightFunction` animated → pulled out of GPU evaluation
6. **Python MPxNode:** Python-based custom nodes cannot be scheduled in parallel (GIL). Must be C++.

### Evaluation Modes in Maya
1. **DG mode:** Original single-threaded Maya evaluation. Always available, fully compatible.
2. **Parallel mode:** Multi-threaded CPU evaluation using the Evaluation Graph. Best for complex rigs.
3. **Serial mode:** Similar to DG but uses the Evaluation Graph infrastructure (good for debugging).
4. **GPU Override:** Within Parallel mode, offloads supported deformer computation to GPU VRAM.
5. **Cached Playback:** Records evaluated results in memory; subsequent playbacks skip re-evaluation entirely.

```python
import maya.cmds as cmds
# Query/set evaluation mode
mode = cmds.evaluationManager(query=True, mode=True)
cmds.evaluationManager(mode='parallel')  # 'parallel', 'serial', 'off'

# Check if a node is in a cluster that runs on GPU
cmds.evaluationManager(query=True, nodeType='skinCluster')
```

### Real Performance Numbers from Production
- **Disney Frozen 2 (SIGGRAPH 2019):** GPU + Parallel evaluation achieved 8× speedup in interactive rig manipulation compared to DG mode. Characters went from ~2-5 fps to 15-25 fps interactive.
- **General benchmark (Rigging Dojo, 2022):** After parallelization, a production character rig ("Goro") achieved 70-80 fps in Parallel mode and 130+ fps with Cached Playback. DG mode was 8-12 fps.
- **GPU vs CPU for deformers:** Tests show 5 fps (CPU) → 12 fps (GPU) for meshes under 2K verts — GPU gains are minimal for small meshes. GPU is most beneficial for meshes with 10K+ verts.
- **Maya 2024 data:** Pre-2024, non-GPU nodes (follicle, uvPin) blocked an entire character from GPU. Post-2024, GPU download support allows these to coexist — significant practical improvement.

### Evaluation Toolkit (profiling)
```python
# Open the Evaluation Toolkit
cmds.evaluationManager(query=True, info=True)
# Use Maya's built-in profiler
cmds.profiler(sampling=True, output='/tmp/maya_profile.txt')
# Or via UI: Windows > Analysis > Evaluation Toolkit
```

## Implementación en Maya

**Best practices for rig DG design:**
1. Replace constraint networks with matrix nodes (no cycle risk, parallel-compatible)
2. Avoid expression nodes — use `multiplyDivide`, `condition`, `blendTwoAttr` instead
3. Use `unitConversion` nodes sparingly — they add DG overhead but are parallel-safe
4. Keep deformer stacks simple: fewer deformers, correct stack order
5. Use `cmds.evaluationManager(invalidate=True)` after rig build to force EG rebuild

**Checking a node's scheduling type:**
```python
# Returns 'globally_serialize', 'locally_serialize', 'parallel' etc.
cmds.evaluationManager(query=True, schedulingType='myNode')
```

**Forcing a node to run in parallel** (for custom MPxNode in C++):
```cpp
// In MPxNode::schedulingType():
return MPxNode::kParallel;  // declare parallel-safe
```

## Comparación con autorig_tools

autorig_tools usa matrix nodes (wtAddMatrix, multMatrix, etc.) que son compatibles con Parallel Evaluation. Los puntos de riesgo son: (1) cualquier expresión Python en el grafo en runtime, (2) scriptJobs del rig que lean atributos, (3) nodos custom si existen. El patrón local_mmx (matrix chain) es exactamente lo que Autodesk recomienda para maximizar paralelismo.

## Aplicable directamente
YES — Auditar el grafo de un rig de autorig_tools con el Evaluation Toolkit para verificar qué nodos están forzando serialización. Objetivo: todo el rig en Parallel mode excepto los scriptJobs de UI que son aceptables. Eliminar cualquier expression node restante y reemplazar por nodos DG. Tiempo estimado: 2-4 horas de auditoría.

## Fuente
- Autodesk Using Parallel Maya 2025: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2025/UsingParallelMaya.html
- Autodesk Using Parallel Maya 2026: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.pdf
- Disney Frozen 2 SIGGRAPH 2019 (GPU + Parallel): https://media.disneyanimation.com/technology/publications/2019/RealTimeRigManip.pdf
- Rigging Dojo Goro Case Study: https://www.riggingdojo.com/2022/12/21/optimizing-rigs-for-parallel-evaluation/
