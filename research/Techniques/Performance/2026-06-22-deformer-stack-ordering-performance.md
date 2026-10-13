---
source: https://lesterbanks.com/2014/11/changing-maya-deformer-order/
found: 2026-06-22
category: performance
priority: 2
tags: [maya, python, rigging, performance, deformers, blendshape, skincluster]
status: NEW
---

# Deformer Stack Ordering — blendShape vs skinCluster y el coste de GPU

## Descripción
El orden en que los deformadores se apilan sobre una malla (historia de Maya: tweak → blendShape → skinCluster → deformadores extra) no solo afecta el resultado visual, sino directamente si la cadena entera puede ejecutarse en GPU Override o cae a CPU. Es un complemento directo al research previo de "Deformation Layering in Maya's Parallel GPU World" ya en el vault — aquí se detalla específicamente el caso blendShape/skinCluster, el más común en cualquier rig biped/quadruped.

## Fundamento matemático / técnico
Maya's deformer evaluation order is, by default, "Automatic" — but the actual position in the history stack determines both result and cost:
- **Pre-deformation (front of chain)**: blendShape evaluated *before* skinCluster. Targets are defined in bind-pose space; the corrective travels through the same skin matrices as the base mesh. This is the standard setup for corrective shapes (PSD-style) because the blendShape delta is defined in the same space the skin weights were authored against.
- **Post-deformation (end of chain)**: blendShape evaluated *after* skinCluster, i.e. directly modifying already-skinned output. Used for overlay/sculpt-style corrections that should not be re-influenced by skin weights.

The GPU-relevant fact: a **live, animated target mesh** feeding a blendShape (rather than a static target) forces that blendShape, and everything upstream feeding the live target, onto CPU — this is the same `outMesh→inMesh` rule from the deformation-layering research already in the vault, but the failure mode here is specific to corrective rigs: if a corrective blendShape's target is driven by a wrap deformer or another skinCluster (a common "sculpt the corrective live on the mesh" workflow), the entire corrective chain becomes CPU-bound even though the base skinCluster itself is GPU-compatible.

Order also affects *cost*, not just compatibility: Maya evaluates deformers strictly in stack order — each deformer in the chain processes the full vertex array sequentially, so n deformers means n full passes over the point array regardless of how localized each deformer's actual influence is (e.g. a cluster deformer touching 12 vertices still costs a full mesh pass in the chain unless Maya's partial-evaluation optimizations kick in, which they only do for deformers that declare a vertex-set membership, like `deformer -partialUpdate` registered nodes).

## Implementación en Maya
Querying and setting order:
```python
from maya import cmds
# inspect history order
history = cmds.listHistory(mesh, pruneDagObjects=True)
# set blendShape to evaluate before skinCluster (front of chain)
cmds.reorderDeformers(blendshape_node, skincluster_node, mesh)
```
GPU-compatibility check per deformer in the stack:
```python
cmds.evaluator(query=True, name="gpuOverride", supported=True)  # global support check
```
Practical rule for corrective-heavy rigs: keep all PSD/RBF-driven correctives as static-target blendShapes evaluated pre-skinCluster, and audit any deformer whose target/input is itself the output of another deforming chain (the #1 GPU-breaker pattern in facial rigs with layered correctives).

## Comparación con autorig_tools
El rig facial de Laia (jaw, eyes, eyelids, brows, lips) es exactamente el escenario de mayor riesgo: muchos correctives RBF/SDK encadenados sobre la misma malla. Si algún corrective usa como target una malla que a su vez recibe wrap o blendShape de otra fuente (en vez de un target estático guardado), rompe GPU Override para toda la cadena facial — que suele ser la parte más cara de evaluar por su densidad de deformadores. Vale la pena una auditoría específica del orden y la naturaleza (estático vs live) de cada target en el rig facial.

## Aplicable directamente
YES — Extender la función `audit_deformation_architecture()` (ya mencionada en research previo, 2026-06-15) para que además de detectar conexiones `outMesh→inMesh` problemáticas, reporte específicamente: (1) el orden blendShape/skinCluster en cada malla, (2) si algún blendShape target es un mesh "live" (con su propia historia de deformación) en vez de un shape estático congelado. Esto es una extensión de 1-2 horas sobre la función que ya existe, no una herramienta nueva.

## Fuente
https://lesterbanks.com/2014/11/changing-maya-deformer-order/
https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82
https://yantor3d.wordpress.com/2016/12/03/layering-deformers/
https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-C954C197-6D56-4EB8-BEA0-70DD1BBBAD6B
