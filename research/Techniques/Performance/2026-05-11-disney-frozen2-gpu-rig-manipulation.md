---
source: https://media.disneyanimation.com/technology/publications/2019/RealTimeRigManip.pdf
found: 2026-05-11
category: performance
priority: 2
tags: [maya, performance, gpu, parallel-evaluation, disney, frozen2, siggraph, production, benchmark]
status: NEW
---

# Disney Animation: Optimizing Rig Manipulation with GPU + Parallel Evaluation (Frozen 2 / SIGGRAPH 2019)

## Descripción
Talk de SIGGRAPH 2019 por John Kahwaty (Disney Animation) documentando cómo optimizaron la performance de rig en producción para Frozen 2, logrando 8× de speedup en manipulación interactiva de personajes. Proporciona números reales de producción: velocidades de viewport, comparativa DG vs Parallel vs GPU, y las técnicas específicas usadas para hacer compatibles los rigs con GPU Override. Es la referencia de benchmarks de producción más citada para Maya rig performance.

## Fundamento matemático / técnico

### Problem Statement
Frozen 2 character rigs had evaluation times of ~200ms/frame in DG mode (~5fps interactive). Animators needed to work with multiple characters on screen simultaneously. Target: 30fps+ interactive evaluation.

### Solution Architecture
Three-layer optimization:

**Layer 1: Parallel Evaluation**
- Converted rig evaluation from serial DG to Parallel Evaluation Graph
- Required auditing all custom nodes for parallel scheduling compatibility
- Replaced any non-parallel-safe nodes with parallel-compatible equivalents
- Result: 3-4× speedup over DG mode alone

**Layer 2: GPU Override Deformers**
- Identified all deformer nodes in the character stack
- Removed or worked around nodes that blocked GPU evaluation (follicles, custom Python deformers)
- Result: additional 2-3× speedup on top of Parallel

**Layer 3: Cached Playback**
- Used Maya's Cached Playback to pre-evaluate a range of frames
- Subsequent playback reads from cache, skipping all DG evaluation
- Result: 130+ fps from cache vs 25fps live evaluation

### Production Benchmarks (Frozen 2 Characters)
| Evaluation Mode | Approx FPS | Notes |
|----------------|-----------|-------|
| DG mode (baseline) | 3-5 fps | Original production mode |
| Parallel mode | 10-15 fps | 3-4× over DG |
| Parallel + GPU Override | 20-30 fps | 6-8× over DG |
| Cached Playback | 130+ fps | Read-only, no live edits |

**8× average improvement** in interactive rig manipulation across all Frozen 2 characters.

### Key Technical Findings
1. **Custom deformer nodes were the biggest blocker.** Disney's proprietary deformers needed C++ rewrites to declare parallel-safe scheduling. Python deformers were completely incompatible with parallel.

2. **follicles on hair and cloth blocked GPU chains.** Before Maya 2024's GPU download feature, any follicle in the deformation chain prevented the entire character from GPU evaluation. Disney worked around this by restructuring the deformation order.

3. **Deformer stack granularity.** Breaking up single large custom deformer nodes into smaller, simpler nodes enabled more granular parallel scheduling. One node that evaluated 10 operations sequentially could be replaced by 10 nodes that the scheduler could distribute across threads.

4. **Expression nodes were completely eliminated.** Any expression node in a rig forced that portion of the DG to serialize. Disney replaced all expressions with DG math nodes before their parallel evaluation migration.

5. **skinCluster influence count had measurable impact.** Reducing from 8 to 4 influences per vertex on secondary characters gave 15-20% additional speedup without noticeable quality loss.

### Evaluation Toolkit Usage in Production
Disney used the Evaluation Toolkit (Windows > Analysis > Evaluation Toolkit) systematically:
- Identified per-node evaluation time contribution
- Found "hotspot" nodes that dominated frame time
- Tracked which nodes were falling back to CPU vs running on GPU
- Used this data to prioritize optimization efforts

## Implementación en Maya

Takeaways directly applicable to rig design:
```python
# 1. Find nodes causing serialization
import maya.cmds as cmds

def find_serial_nodes():
    """Find nodes forcing serial evaluation."""
    nodes = cmds.ls(dag=False)
    serial = []
    for n in nodes:
        sched = cmds.evaluationManager(query=True, schedulingType=n)
        if sched in ('globally_serialize', 'locally_serialize'):
            serial.append((n, cmds.nodeType(n), sched))
    return sorted(serial, key=lambda x: x[2])

# 2. After rig build, invalidate EG and verify parallel mode
cmds.evaluationManager(invalidate=True)
cmds.evaluationManager(mode='parallel')

# 3. Test cached playback
cmds.playbackOptions(loop='once')
# Enable in Timeline > Cache Playback
```

**Disney's parallel compatibility checklist:**
- [ ] No expression nodes anywhere in rig
- [ ] No Python MPxDeformerNode (use C++ or built-in nodes)
- [ ] All custom MPxNode declare `schedulingType = kParallel`
- [ ] No follicles blocking GPU chain (or use GPU download, Maya 2024+)
- [ ] Deformer stack: group GPU-compatible deformers together
- [ ] skinCluster: 4-8 influences max for secondary characters

## Comparación con autorig_tools

Este talk proporciona los benchmarks de referencia más creíbles para rig performance en producción VFX. El target de 20-30fps en manipulación interactiva con GPU+Parallel es el estándar a aspirar. Si autorig_tools genera rigs que van a evaluarse en producción VFX, el checklist de Disney (sin expressions, sin Python deformers, matrix nodes, GPU-compatible stack) es el checklist de producción a seguir. Los números de Frozen 2 validan que las optimizaciones de matrix nodes y GPU tienen impacto real medible.

## Aplicable directamente
YES — Usar el checklist de Disney como audit list para rigs de autorig_tools. El benchmarking con el Evaluation Toolkit es el primer paso. Objetivo inmediato: 0 expression nodes, 0 Python MPxDeformerNode, todo parallel-safe. Los rigs de autorig_tools con el patrón local_mmx ya cumplen la mayoría de estos requisitos.

## Fuente
- Disney Animation SIGGRAPH 2019: https://media.disneyanimation.com/technology/publications/2019/RealTimeRigManip.pdf
- ACM DL: https://dl.acm.org/doi/10.1145/3306307.3328181
- Jonah Reinhart GPU rig article: https://www.jonah-reinhart.com/single-post/gpu-ify-your-rig
