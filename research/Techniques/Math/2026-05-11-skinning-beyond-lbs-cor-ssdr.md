---
source: https://studios.disneyresearch.com/wp-content/uploads/2020/04/Real-time-Skeletal-Skinning-with-Optimized-Centers-of-Rotation.pdf
found: 2026-05-11
category: math
priority: 1
tags: [maya, rigging, math, skinning, CoR, SSDR, SBS, deformation, disney-research]
status: NEW
---

# Skinning Algorithms Beyond LBS — CoR, SSDR, SBS

## Descripción
Además de LBS y DQS, existen algoritmos de skinning más avanzados que abordan sus artefactos específicos. Center of Rotation (CoR, Disney Research 2016) minimiza artefactos de LBS y DQS con coste comparable a LBS. Smooth Skinning Decomposition with Rigid Bones (SSDR) aprende automáticamente los bone transforms y pesos de un conjunto de poses ejemplo — útil para capturar deformaciones complejas que no se pueden rigging manualmente. SBS (Spherical Blend Skinning) preserva volumen pero tiene coste elevado.

## Fundamento matemático / técnico

### Center of Rotation (CoR) Skinning — Le & Hodgins, Disney Research 2016
The key insight: instead of blending bone transforms and applying to each vertex, pre-compute an **optimal center of rotation** per vertex, then compute a single rigid transform for that vertex.

**Precomputation (per vertex v, done once at bind pose):**
Given skinning weights wᵢ(v) for bones i:
```
c(v) = Σᵢ Σⱼ wᵢ(v) wⱼ(v) · CoR(i, j)
```
where `CoR(i, j)` is the center of rotation between bone pair (i, j), computed as the point that minimizes the average squared distance to both bone frame origins weighted by w:
```
CoR(i, j) = (wᵢ·pᵢ + wⱼ·pⱼ) / (wᵢ + wⱼ)    (simplified 2-bone case)
```
Full formula accounts for all bone pairs in the influence set.

**Runtime (per frame, per vertex):**
1. For each vertex v, compute a SINGLE rotation matrix using the precomputed c(v):
```
R(v) = Σᵢ wᵢ(v) · Rᵢ    (LBS-style rotation blend, at the CoR)
```
2. Apply: `p'(v) = c(v) + R(v) · (p(v) - c(v))`

This is essentially spherical blending centered at the precomputed CoR, not the naive origin. The CoR is chosen to minimize the deviation from the "correct" deformation.

**Runtime cost:** ~1.1× LBS. Requires one extra vec3 per vertex stored (the CoR). Fully GPU-compatible.

**Artifacts:** Significantly reduced vs LBS and DQS. Small residual bulging for extreme bends (>120°), but far less than DQS. No candy-wrapper. The method largely eliminates the need for corrective blendshapes in many joints.

**Patent note:** Disney Research holds a patent on CoR (non-commercial research use only without license).

### SSDR — Smooth Skinning Decomposition with Rigid Bones (Le & Deng, SA 2012)
SSDR takes a set of **example deformed poses** as input and automatically computes:
- The optimal bone transforms {Rᵢ, tᵢ} per pose
- The optimal skinning weights wᵢ(v) per vertex
- The optimal bone count (or fits to a given count)

**Formulation (constrained optimization):**
```
minimize   Σ_{poses p} Σ_{vertices v} |p_v - Σᵢ wᵢ(v) Tᵢ(p) · r_v|²

subject to:  wᵢ(v) ≥ 0    (non-negative weights)
             Σᵢ wᵢ(v) = 1  (partition of unity)
             Rᵢ ∈ SO(3)    (bone rotations must be valid rotations)
```
where `r_v` is the vertex rest position and `Tᵢ(p) = (Rᵢ(p), tᵢ(p))` is the bone transform in pose p.

**Algorithm (alternating optimization — Block Coordinate Descent):**
1. Initialize: cluster vertices via k-means on displacement vectors
2. **Bone update:** Given fixed weights, solve for each bone transform via Procrustes (SVD): `R = V Σ Uᵀ` from `UΣVᵀ = SVD(Σᵥ wᵢ(v) · outer(r_v, Δpᵥ))`
3. **Weight update:** Given fixed bone transforms, solve for weights via non-negative least squares (NNLS) per vertex — a quadratic program with sum=1 and non-negativity constraints
4. Repeat 2-3 until convergence

**Use cases:**
- Capturing muscle deformation from simulation for real-time approximation
- Automatically weighting skin from a reference simulation cache
- Retargeting skin weights from one rig to another via shared pose space

**Maya implementation (dalton-omens/SSDR on GitHub):** Python implementation that reads pose matrices and mesh deltas, solves SSDR, and writes the result back as a Maya skinCluster with the computed weights and joints.

### SBS — Spherical Blend Skinning (Kavan & Žára 2005)
Blends bone transforms by finding the optimal center of rotation that minimizes the deformation error (related to CoR but computed differently). Preserves volume but:
- ~3× LBS cost
- Visible bulging at extreme bends
- Largely superseded by CoR which achieves similar quality at ~1.1× LBS cost

## Implementación en Maya

**CoR in Maya:** No native support. Can implement as a pre-pass (Python at bind time) that stores per-vertex CoR in a custom attribute, then drives a custom MPxDeformerNode for runtime evaluation:
```python
# Precompute CoR for each vertex from skinCluster weights
def compute_vertex_cor(mesh, skin_cluster):
    # Get weights: (n_vertices × n_influences) matrix
    weights, n_inf = cmds.SkinPercent(skin_cluster, mesh, q=True, value=True, ...
    # Compute CoR per vertex using joint positions in bind pose
    # ... (full implementation requires OpenMaya MFnMesh + MFnSkinCluster)
```

**SSDR in Maya:** GitHub implementation by dalton-omens processes Maya skinCluster data directly.

## Comparación con autorig_tools

autorig_tools usa LBS con correctivos RBF. CoR podría eliminar la mayoría de los correctivos de muñeca, codo y rodilla — los artefactos que estos corrigen son exactamente los que CoR resuelve. La limitación es que CoR requiere un MPxDeformerNode C++ para rendimiento en producción; la implementación Python es demasiado lenta para viewport. SSDR es una herramienta de workflow valiosa para capturar deformaciones de simulación y convertirlas en skin weights.

## Aplicable directamente
PARTIAL — CoR: implementar como herramienta de precompute + análisis (qué correctivos podría eliminar). No directamente como deformador runtime en Python. SSDR: usar el repo de GitHub para extraer skin weights de simulaciones de cloth/muscle y convertirlas en skinClusters. Ambos son investigación valiosa pero requieren más trabajo de integración que DQS.

## Fuente
- CoR paper (Disney Research): https://studios.disneyresearch.com/wp-content/uploads/2020/04/Real-time-Skeletal-Skinning-with-Optimized-Centers-of-Rotation.pdf
- CoR ACM: https://dl.acm.org/doi/10.1145/2897824.2925959
- SSDR paper: https://binh.graphics/papers/2012sa-ssdr/2012_SA_SSDR_preprint.pdf
- SSDR GitHub (Maya): https://github.com/dalton-omens/SSDR
- Disney Research overview: https://la.disneyresearch.com/publication/skinning-with-optimized-cors/
