---
source: https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2026/MayaCachedPlaybackWhitePaper.pdf
found: 2026-05-18
category: performance
priority: 2
tags: [maya, performance, cached-playback, caching-points, evaluation-cache, viewport-cache, rig-topology, invalidation]
status: NEW
---

# Maya Cached Playback — Arquitectura, Caching Points y Topología de Rig

## Descripción
Maya Cached Playback (introducido en Maya 2018, mejorado significativamente en 2022-2026) permite alcanzar 100-200+ fps reproduciendo animaciones desde caché en memoria, eliminando la reevaluación del DG frame a frame. La arquitectura de Cached Playback es ortogonal a Parallel Evaluation: mientras la evaluación paralela optimiza la velocidad de evaluación live, el caché elimina la evaluación por completo durante playback. Entender qué estructura de rig maximiza la efectividad del caché y qué la invalida es crítico para un pipeline de animación eficiente.

## Fundamento matemático / técnico

### Three Cache Modes

| Mode | What is cached | Performance | Limitations |
|------|----------------|-------------|-------------|
| **Evaluation Cache** | All node output values in the DG | Good, flexible | More memory; fallback for unsupported cases |
| **Viewport Software Cache** | Final deformed mesh CPU data | Better than Eval Cache | Some geometry types force fallback to Eval Cache |
| **Viewport Hardware Cache** | Deformed mesh in GPU memory | Best (fastest playback) | Requires GPU, limited to supported geometry |

**Default:** Evaluation Cache. Viewport caches provide faster playback but may fall back to Evaluation Cache for:
- Animated visibility attributes
- Topology-changing deformers (blend shapes targeting different vertex counts)
- Unsupported node types

### Caching Points — The Key Architecture
A **Caching Point** is a node in the DG that acts as a "memo-ize" boundary. When a Caching Point has valid cached data for a frame, all nodes upstream of it do NOT need to be re-evaluated for that frame — the cached output is read directly.

**How Caching Points are selected:**
1. Maya identifies the "leaves" of the Evaluation Graph that produce the final output (usually the mesh shapes connected to viewport).
2. It walks upstream to find suitable caching points.
3. For **Viewport Software Cache:** caching points are placed at the output of the topmost deformer stack node.
4. For **Evaluation Cache:** caching points are placed throughout the graph at major computation boundaries.

**Example:** If the deformer stack is:
```
blendShape → skinCluster → deltaMush → (viewport)
```
The Evaluation Cache caches the output of deltaMush (and all nodes it depends on). During cached playback, no node in the stack re-evaluates.

### What Invalidates the Cache

**Full cache invalidation (entire sequence must re-bake):**
- Adding or removing a node from the scene
- Adding the first keyframe to an attribute
- Changing the topology of any mesh (adding/removing vertices)
- Loading/unloading a plugin
- Changing playback range

**Partial cache invalidation (affected frames re-bake, rest unchanged):**
- Editing a keyframe value or tangent
- Changing a static attribute value
- Moving a control in one frame (that frame + dependent frames)

**Automatic re-evaluation (per frame, without invalidating):**
- Nodes marked as "always dirty" (e.g., some expressions)
- Dynamic simulations (nCloth, nParticles, Bullet) — time-dependent state
- Nodes connected to time that don't track properly

**Rig topology design for cache efficiency:**
```
GOOD (wide, independent branches):
  time → animCurve_A → joint_A → skinCluster (chain 1)
  time → animCurve_B → joint_B → skinCluster (chain 2)
  Both chains cached independently — partial edit only re-bakes affected chain

BAD (deep sequential chain):
  time → animCurve → spine → chest → shoulder → arm → wrist → skinCluster
  Editing spine invalidates ALL downstream cache — re-bakes entire sequence
```

### Caching and Parallel Evaluation Interaction
Cached Playback **requires** Parallel Evaluation to be ON. The cache fill pass (first play-through) runs in parallel mode. Subsequent playbacks read from cache and skip evaluation entirely.

**Cache fill speed:** Directly proportional to parallel evaluation speed. A rig that evaluates at 25fps in parallel mode fills its cache at 25fps → a 10-second shot at 24fps takes ~9.6 seconds to fill cache.

**Production numbers (Disney Frozen 2, SIGGRAPH 2019):**
- DG mode: 3-5fps (interactive)
- Parallel + GPU: 20-30fps (interactive)
- Cached Playback: **130+ fps** (read-only)
- Cache fill: ~1-2 minutes for a 10-second shot

**Maya 2026 Cached Playback improvements:**
- Smarter topology tracking: minor rig edits no longer trigger full cache invalidation
- Background cache fill: cache fills during idle time while animator works
- Cache invalidation scope narrowing: point-level edits invalidate fewer frames

### Rig Topology vs Cache Effectiveness

**Topology changes during animation = worst case:**
Anything that changes the vertex count, face count, or connection topology of a mesh forces the viewport cache to fall back to Evaluation Cache (or fully invalidate). This includes:
- `wrap` deformer with driver mesh changing topology
- `blendShape` targets with different vertex counts
- Dynamic constraint addition/removal per-frame

**Animated deformer weights = partial impact:**
An `animCurve` driving a `blendShape` weight → that blendShape's cached output is invalidated at every edited frame, but the skinCluster below it is NOT invalidated if it doesn't depend on the blendShape result changing.

**Expression nodes in the chain = always dirty:**
Expression nodes evaluate every frame regardless of whether their inputs changed. Nodes downstream of expressions are never cached effectively. This is why expressions should be replaced with DG math nodes (see `2026-05-11-rig-optimization-patterns-maya.md`).

### Python: Cache Control

```python
import maya.cmds as cmds

# Enable/disable Cached Playback
cmds.cacheEvaluator(cachingPoints='modelDependencies')  # evaluation cache mode
cmds.cacheEvaluator(cachingPoints='gpuDynamics')        # viewport cache mode

# Query current cache mode
mode = cmds.cacheEvaluator(query=True, cachingPoints=True)

# Flush the cache (force re-evaluation)
cmds.cacheEvaluator(flushCache='destroy')   # destroy all cache data
cmds.cacheEvaluator(flushCache='implicit')  # flush but keep allocations

# Check if a specific frame is cached
# (only via Evaluation Manager API in C++ plugin; no direct cmds equivalent)

# Practical workflow: fill cache in background
cmds.playbackOptions(loop='once')
cmds.play(forward=True)  # this triggers cache fill in parallel

# Turn off cached playback for debugging:
cmds.evaluationManager(mode='parallel')  # parallel without cache
# vs:
cmds.evaluationManager(mode='off')       # pure DG, no cache, no parallel
```

### Memory Footprint
The Evaluation Cache stores the **output values** of all caching-point nodes for every cached frame.
- Approximate memory per frame per character: mesh data (N verts × 3 floats × 4 bytes) = `N × 12 bytes`
- For a 10K-vert mesh: 120 KB/frame
- For a 10-second shot at 24fps (240 frames): 28.8 MB per mesh
- A full character with 5 meshes: ~144 MB per shot

**Viewport Hardware Cache** is more memory efficient — stores compressed GPU representation instead of raw CPU vertex arrays.

## Implementación en Maya

```python
def check_cache_blocking_nodes(scene_nodes=None):
    """
    Find nodes in the scene that block effective caching.
    Returns: dict of {node_name: reason}
    """
    import maya.cmds as cmds
    
    issues = {}
    if scene_nodes is None:
        scene_nodes = cmds.ls(dag=False)
    
    for node in scene_nodes:
        nt = cmds.nodeType(node)
        
        # Expressions are always dirty
        if nt == 'expression':
            issues[node] = 'expression node — always dirty, blocks caching downstream'
        
        # Python deformers cannot be scheduled parallel
        elif nt == 'unknown':  # unloaded plugin nodes
            issues[node] = 'unknown node type — plugin may not be loaded'
        
        # Check scheduling type
        try:
            sched = cmds.evaluationManager(query=True, schedulingType=node)
            if sched == 'globally_serialize':
                issues[node] = f'global serialization — forces single-thread eval'
        except:
            pass
    
    return issues
```

## Comparación con autorig_tools
Los rigs construidos con autorig_tools se benefician del Cached Playback automáticamente si están en Parallel Evaluation. Los problemas más comunes que reducen la efectividad del caché en rigs de autorig_tools serían: (1) cualquier nodo expression que haya quedado de iteraciones tempranas, (2) wrap deformers para ropa que cambien topología, (3) nCloth o simulaciones dinámicas conectadas al rig principal (no a capas separadas). La separación del rig de simulaciones dinámicas en layers independientes maximiza el caché del rig estático.

## Aplicable directamente
YES — Añadir `check_cache_blocking_nodes()` como función de validación en el proceso de build de autorig_tools (junto a las validaciones de parallel evaluation existentes). Documentar para Laia y el equipo: cualquier nodo expression en el rig = pérdida de caché efectivo.

## Fuente
- Maya 2026 Cached Playback Whitepaper: https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2026/MayaCachedPlaybackWhitePaper.pdf
- Maya 2025 Cached Playback: https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2025/MayaCachedPlaybackWhitePaper.html
- Disney Frozen 2 SIGGRAPH 2019: https://media.disneyanimation.com/technology/publications/2019/RealTimeRigManip.pdf
- Autodesk Cached Playback preferences: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-3CB35662-DB1D-4CF3-9135-E09B973635DE
