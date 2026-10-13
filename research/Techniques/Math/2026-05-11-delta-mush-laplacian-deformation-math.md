---
source: https://media.contentapi.ea.com/content/dam/ea/seed/presentations/le2019-siggraph2019-direct-delta-mush-skinning-and-variants.pdf
found: 2026-05-11
category: math
priority: 1
tags: [maya, rigging, math, delta-mush, laplacian, deformation, smoothing, skinning, EA, siggraph]
status: NEW
---

# Delta Mush y Deformación Laplaciana — Matemática e Implementación

## Descripción
Delta Mush (Joe Mancewicz, Method Studios / Pixar, 2014) es un deformador de post-skinning que suaviza los artefactos del skincluster preservando el detalle superficial del mesh. Usa suavizado Laplaciano para calcular posiciones suavizadas y almacena las diferencias (deltas) en coordenadas de superficie, re-aplicándolas después del suavizado de la pose deformada. EA SEED extendió esto con Direct Delta Mush (DDM) en Siggraph 2019, convirtiéndolo en un algoritmo de skinning directo. Ambos son nativos en Maya.

## Fundamento matemático / técnico

### Laplacian Smoothing
The Laplacian of vertex v is the weighted average of its neighbors minus v itself:
```
L(v) = Σ_{u∈N(v)} w_{vu} · u − v
```
where `N(v)` is the set of neighbors and `w_{vu}` are weights (uniform: `1/|N(v)|`, or cotangent/distance weights for better quality).

**Iterative Laplacian smoothing** (k iterations, step size λ):
```
vᵢ(t+1) = vᵢ(t) + λ · L(vᵢ(t))
         = vᵢ(t) + λ · (Σⱼ∈N(i) wᵢⱼ · vⱼ(t) − vᵢ(t))
         = (1-λ) · vᵢ(t) + λ · Σⱼ∈N(i) wᵢⱼ · vⱼ(t)
```
In matrix form: `V(t+1) = (I − λL) · V(t)` where L is the graph Laplacian matrix.

Multiple iterations → progressive smoothing. More iterations = smoother, more lost detail.

### Delta Mush Algorithm (Mancewicz 2014)
**Pre-computation (bind pose, done once):**
1. Start with rest mesh positions `V_rest`
2. Apply k iterations of Laplacian smoothing → `V_smooth`
3. For each vertex i, compute **delta** in local surface frame:
```
Δᵢ = V_rest[i] − V_smooth[i]        # displacement from smooth to rest
```
4. Store Δᵢ in a local tangent-space frame defined by vertex normal and tangent (or nearest triangle):
```
Δᵢ_local = M_frame[i]ᵀ · Δᵢ         # transform delta to surface-local coords
```

**Deformation (per frame):**
1. Apply skinCluster to rest mesh → deformed mesh `V_def`
2. Apply k iterations of Laplacian smoothing to `V_def` → `V_def_smooth`
3. Reconstruct the surface frame at each vertex in the deformed state → `M_frame_def[i]`
4. Re-apply stored delta in new frame:
```
V_final[i] = V_def_smooth[i] + M_frame_def[i] · Δᵢ_local
```

**Why it works:** Laplacian smoothing removes high-frequency deformation artifacts (candy-wrapper, collapsing skin). The delta re-application restores the original surface detail (wrinkles, muscles) in the correct local orientation for the new pose.

### Direct Delta Mush (DDM) — EA SEED, Siggraph 2019
Converts Delta Mush into a **direct skinning method** — eliminates the per-frame iterative smoothing, making it 10-100× faster:

Key insight: The Laplacian smoothing matrix `(I − λL)^k` can be precomputed as a fixed matrix S. Then the per-vertex deformation becomes a linear blend of bone transforms weighted by **precomputed per-vertex matrices** (not scalar weights):

```
p'(v) = Σᵢ ( Ωᵢ(v) · pᵢ + ωᵢ(v) · Rᵢ · rest(v) )
```
where Ωᵢ(v) are per-vertex 3×3 matrices (precomputed from S and skinning weights), ωᵢ are scalar weights, and Rᵢ is the rotation part of bone i's transform.

**Precomputation cost:** High (requires computing S as a full sparse matrix solve). **Runtime cost:** ~LBS (a single linear combination of precomputed per-vertex matrices per frame). GPU-friendly.

DDM variants include DDM with cotangent weights (better for non-uniform meshes) and DDM-eigen (approximation using top-k eigenvectors of S for further speedup).

### Maya's deltaMush Node (Native)
Maya has had deltaMush built-in since Maya 2016. It implements the original Mancewicz algorithm:

Key attributes:
- `smoothingIterations` (default 10): iterations of Laplacian smoothing applied in precompute and per-frame. Higher = smoother but slower. 10-20 is typical for production.
- `smoothingStep` (default 0.5): step size λ. Higher = faster convergence but potential instability (>1.0 = explodes).
- `distanceWeight` (default 0): if 1.0, uses distance-weighted Laplacian (better quality for non-uniform meshes, slightly slower).
- `pinBorderVertices`: keeps border vertices (seams) from moving.

### Enhanced Delta Mush (Kalentchouk, 2021)
Apple Research paper adds adaptive smoothing: instead of uniform Laplacian, uses a per-vertex anisotropic filter that preserves sharp features (creases, ridges) while still smoothing deformation artifacts. Implementation complexity is higher but quality improvement is significant for characters with fine facial details.

## Implementación en Maya

**Standard Maya deltaMush setup:**
```python
import maya.cmds as cmds

def add_delta_mush(mesh, skin_cluster, iterations=10, step=0.5):
    """Add deltaMush after skinCluster in deformer stack."""
    dm = cmds.deformer(mesh, type='deltaMush')[0]
    cmds.setAttr(f'{dm}.smoothingIterations', iterations)
    cmds.setAttr(f'{dm}.smoothingStep', step)
    # deltaMush must be AFTER skinCluster in deformer stack
    # (it post-processes the skinned result)
    return dm

# Deformer stack order:
# [blendShape (pre)] → skinCluster → [deltaMush] → [blendShape (post)]
```

**GPU Override compatibility:** Maya's native deltaMush IS supported for GPU Override (it's a standard geometry deformer). However, high iteration counts significantly impact GPU performance.

**Performance note:** Delta Mush with 20+ iterations on a 50k+ mesh can drop frame rates even on GPU. DDM would be the upgrade, but it requires a custom plugin (no native Maya DDM). For production, 5-10 iterations is the sweet spot.

## Comparación con autorig_tools

autorig_tools usa correctives RBF/SDK para corregir artefactos de skin. Delta Mush puede reducir la cantidad de correctivos necesarios aplicándolo como una capa de post-skinning. Es especialmente efectivo en zonas donde el skinCluster produce "pinching" en poses extremas. La limitación es el coste computacional adicional por frame. DDM sería ideal pero requiere implementación C++ custom. El nativo Maya deltaMush es una adición de 3 líneas de código a cualquier función de bind skin.

## Aplicable directamente
YES — Añadir un parámetro opcional `use_delta_mush=True` a la función de bind en autorig_tools que aplique deltaMush con iteraciones=10 tras el skinCluster. Evaluar si reduce la necesidad de correctivos RBF en muñeca y hombro. Coste: 1 hora de implementación + tiempo de evaluación de resultados.

## Fuente
- DDM EA SEED Siggraph 2019: https://media.contentapi.ea.com/content/dam/ea/seed/presentations/le2019-siggraph2019-direct-delta-mush-skinning-and-variants.pdf
- Enhanced DDM (Apple, 2021): https://arxiv.org/pdf/2101.02798
- Maya deltaMush docs: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-139B703C-28E7-4787-8FD4-C2991BD6C990
- deltaMush node reference: https://help.autodesk.com/cloudhelp/2023/ENU/Maya-Tech-Docs/Nodes/deltaMush.html
