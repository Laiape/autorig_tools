---
source: https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-2E292C8A-388A-4E77-B42D-165F1C9E1E5F
found: 2026-06-22
category: performance
priority: 2
tags: [maya, python, rigging, performance, skinning, skincluster]
status: NEW
---

# Influences por Vértice — Coste Computacional vs Calidad de Deformación

## Descripción
Cada influencia (joint) que afecta a un vértice en un `skinCluster` añade una multiplicación matriz-vector más a ese vértice por frame. Es un tradeoff directo y cuantificable entre calidad de deformación (más influencias = transiciones más suaves) y coste de evaluación (más influencias = más operaciones por vértice), y es uno de los pocos parámetros de skinning con impacto de performance medible y controlable sin tocar el grafo de nodos.

## Fundamento matemático / técnico
Standard LBS per-vertex cost is O(k) where k is the number of non-zero influences on that vertex: v' = Σ_{i=1}^{k} wᵢ Mᵢ v, each term being a 4×4 matrix times a 4-vector (12 multiply-adds for the linear part, ignoring the homogeneous row). For a mesh with V vertices and average influence count k̄, total skinning cost per frame scales as O(V × k̄) — doubling average influences roughly doubles skinning cost, independent of joint count or topology.

This is why `maxInfluences` (Maya's cap on simultaneous non-zero weights per vertex, commonly set to 4-8 in real-time/game contexts and left unbounded in film/VFX) is the single most direct performance lever in skinning: capping at 4 influences with "Maintain Max Influences" forces the smallest weights to redistribute into the remaining ones (renormalized so Σw=1), trading a small amount of deformation smoothness at the cap boundary for a hard, predictable per-vertex cost ceiling. GPU deformer evaluation parallelizes per-vertex, so the *absolute* k̄ matters less for wall-clock time than for CPU evaluation, but it still determines the per-thread workload and the size of the weight buffer uploaded to the GPU each topology change.

Weight normalization mode interacts with this: "Post" normalization computes normalized values at deform time (extra divide per vertex per frame, but allows weights to not sum to 1 in the stored data — useful for blended layered skinning); "Interactive" normalization bakes the normalization into the stored weights once (no runtime divide, cheaper, but any subsequent paint operation must re-normalize explicitly). For production rigs evaluated thousands of times per playblast/sim, Interactive normalization removes a divide-per-vertex-per-frame that Post mode pays every single evaluation.

## Implementación en Maya
Querying current influence distribution to find performance outliers (vertices with unusually high influence count):
```python
from maya import cmds
sc = cmds.ls(type="skinCluster")[0]
infs = cmds.skinCluster(sc, query=True, influence=True)
verts = cmds.ls(cmds.polyListComponentConversion(mesh, toVertex=True), flatten=True)
for v in verts:
    weights = cmds.skinPercent(sc, v, query=True, value=True)
    nonzero = [w for w in weights if w > 0.0001]
    if len(nonzero) > 8:
        print(v, len(nonzero))  # flag for pruning
```
Pruning low-value weights without visibly changing deformation:
```python
cmds.skinPercent(sc, vertex, pruneWeights=0.01, normalize=True)
```
Set a hard cap going forward:
```python
cmds.skinCluster(sc, edit=True, maximumInfluences=8, maintainMaxInfluences=True, normalizeWeights=1)
```

## Comparación con autorig_tools
Si autorig_tools no impone actualmente un límite de `maxInfluences` ni hace pruning post-paint, es probable que el skinning final (sobre todo tras pasar por correctives RBF que a veces añaden joints de soporte) acumule vértices con 10+ influencias residuales de valor casi nulo — coste sin beneficio de calidad. Esto es independiente del trabajo de pesos automáticos (BBW, dm2skin, MayaMeshRetarget ya investigados en semanas anteriores): sea cual sea el método que genera los pesos iniciales, un paso de pruning + cap es ortogonal y siempre aplicable después.

## Aplicable directamente
YES — Una función `prune_and_cap_skin_weights(mesh, max_influences=8, prune_threshold=0.01)` que recorre todos los skinClusters del personaje al final del pipeline de skinning (antes de export) y aplica `skinPercent(pruneWeights=...)` + `skinCluster(maximumInfluences=...)`. Es directa, sin dependencias externas, y mide el % de vértices afectados como reporte de QA. Estimación: 1-2 horas.

## Fuente
https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-2E292C8A-388A-4E77-B42D-165F1C9E1E5F
https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-99189E9D-237F-471E-A02C-BE6593B4828B
https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82
