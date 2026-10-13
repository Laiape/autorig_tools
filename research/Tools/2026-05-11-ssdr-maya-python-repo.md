---
source: https://github.com/dalton-omens/SSDR
found: 2026-05-11
category: tool
priority: 3
tags: [maya, python, skinning, SSDR, deformation, machine-learning, weights, github]
status: NEW
---

# SSDR Maya Python — Smooth Skinning Decomposition with Rigid Bones (dalton-omens)

## Descripción
Implementación en Python del algoritmo SSDR (Le & Deng, Siggraph Asia 2012) para Autodesk Maya. SSDR toma un conjunto de poses de ejemplo (meshes deformados) y calcula automáticamente las transformaciones de bones y los pesos de skinning que mejor aproximan esas poses. Es especialmente útil para convertir simulaciones (cloth, muscle) a skinClusters ligeros, o para hacer ingeniería inversa de skin weights desde una librería de animaciones de referencia.

## Fundamento matemático / técnico

SSDR solves the following optimization:
```
minimize   Σ_p Σ_v ||deformed_v(p) − Σᵢ wᵢ(v) Tᵢ(p) rest_v ||²
subject to: wᵢ(v) ≥ 0,  Σᵢ wᵢ(v) = 1
```

**Alternating Block Coordinate Descent:**
1. Initialize bone assignments via k-means on per-vertex displacement vectors
2. **Bone transform update (Procrustes problem):** For each bone i and pose p, solve for the rigid transform {Rᵢ, tᵢ} that best explains all vertices assigned to bone i:
   - Build covariance matrix C = Σᵥ wᵢ(v) (rest_v − centroid_rest) ⊗ (deformed_v(p) − centroid_deformed)
   - Solve via SVD: C = UΣVᵀ → R = VUᵀ (with det correction for reflections: det check)
3. **Weight update (Non-negative Least Squares per vertex):** Given fixed bone transforms, find weights that minimize error with constraints (wᵢ ≥ 0, Σwᵢ = 1). Solved as a quadratic program.
4. Iterate until convergence.

## Implementación en Maya

Repository: `github.com/dalton-omens/SSDR`

```python
# Workflow:
# 1. Gather example poses as numpy arrays
import numpy as np
# rest_verts: (n_verts, 3) in rest pose
# posed_verts: (n_poses, n_verts, 3) — deformed positions

# 2. Run SSDR
from ssdr import SSDR
n_bones = 20  # number of bones to decompose into
result = SSDR(posed_verts, rest_verts, n_bones)
# result.weights: (n_verts, n_bones) — skinning weights
# result.transforms: (n_poses, n_bones, 4, 4) — bone transforms per pose

# 3. Apply to Maya skinCluster
import maya.cmds as cmds
skin = cmds.skinCluster(joints, mesh, toSelectedBones=True)[0]
for v_idx in range(n_verts):
    for b_idx in range(n_bones):
        cmds.skinPercent(skin, f'{mesh}.vtx[{v_idx}]',
                         transformValue=[(joints[b_idx], result.weights[v_idx, b_idx])])
```

**Maya data extraction for SSDR input:**
```python
import maya.api.OpenMaya as om

def get_mesh_positions(mesh_name, frame):
    cmds.currentTime(frame)
    sel = om.MSelectionList(); sel.add(mesh_name)
    fn = om.MFnMesh(sel.getDagPath(0))
    pts = fn.getPoints(om.MSpace.kWorld)
    return np.array([[p.x, p.y, p.z] for p in pts])

# Gather all poses
posed = np.array([get_mesh_positions('sim_mesh', f) for f in range(1, n_frames+1)])
rest  = get_mesh_positions('sim_mesh', 0)  # frame 0 = rest
```

**Stars:** 15 | **Language:** Python | **Activity:** low (research code, functional) | **Depends on:** numpy, scipy

## Comparación con autorig_tools

autorig_tools crea skin weights manualmente o por transferencia. SSDR es una herramienta complementaria para capturar automáticamente weights desde simulaciones de tela, músculo o referencias de captura de movimiento. No compite directamente con el autorig — se usa como paso previo o de corrección. Su uso más práctico en el pipeline de Laia: generar skin weights iniciales para personajes complejos (cloth sims → proxy weights).

## Aplicable directamente
PARTIAL — Como herramienta independiente de investigación/workflow. Requiere preparar poses de referencia (simulación o animación de referencia). Para personajes heroes que van a tener simulaciones cloth, puede generar el skin del cloth layer automáticamente. No se integra directamente en el build pipeline de autorig_tools sin adaptación.

## Fuente
- GitHub: https://github.com/dalton-omens/SSDR
- Paper original SSDR: https://binh.graphics/papers/2012sa-ssdr/2012_SA_SSDR_preprint.pdf
- ACM: https://dl.acm.org/doi/10.1145/2366145.2366218
