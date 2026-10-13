---
source: https://dl.acm.org/doi/10.1145/3306346.3322982 | https://www.ea.com/seed/news/siggraph2019-direct-delta-mush | https://arxiv.org/abs/2101.02798
found: 2026-06-08
category: math
priority: 1
tags: [maya, skinning, delta-mush, laplacian, deformation, precomputed, SIGGRAPH2019, real-time, math]
status: NEW
---

# Direct Delta Mush (DDM) — Laplacian Skinning sin Iteración

## Descripción
Direct Delta Mush (DDM), de Binh Huy Le y JP Lewis (EA SEED / SIGGRAPH 2019, ACM ToG Vol. 38, No. 4, Art. 113), resuelve el problema de rendimiento del Delta Mush original: convierte el algoritmo iterativo de suavizado Laplaciano en una operación directa de una sola pasada, con el mismo coste computacional que LBS. Permite calidad de Delta Mush en tiempo real. En 2021 Apple ML Research publicó Enhanced DDM (EDDM) con correcciones de pose adicionales.

## Fundamento matemático / técnico

### Problem with Iterative Delta Mush

The original Delta Mush (Rhythm & Hues, Joe Mancewicz et al.) runs these steps per frame:

```
1. Compute smoothed rest pose: smooth_rest = L^n * v_rest
2. Compute delta per vertex: δ_i = v_rest_i - smooth_rest_i  (stored in local tangent frame)
3. At runtime: apply LBS → get v_lbs
4. Apply Laplacian smoothing: v_smooth = L^n * v_lbs
5. Re-apply deltas in new tangent frame: v_final = v_smooth + R_i * δ_i
```

Key cost: step 4 runs `n` Laplacian iterations at **every frame**. For n=20 and 100K vertices, this is expensive and cannot run on GPU as a standard deformer.

### The DDM Insight: Laplacian Smoothing is Linear

The cotangent-weight Laplacian operator L ∈ ℝ^{V×V} is a sparse linear matrix:

```
L = I - D^{-1} A
```
where:
- `D` = diagonal degree matrix (D_ii = Σ_j w_{ij})
- `A` = adjacency/weight matrix (A_ij = cotangent weight between vertex i and j)
- `w_{ij} = (cot α_{ij} + cot β_{ij}) / 2` (cotangent of the two angles opposite to edge ij)

After n iterations: `L^n` is still a **linear operator on vertex positions**.

This means:
```
v_smooth = L^n * v_lbs = L^n * (Σ_b w_b * T_b * v_rest)
         = Σ_b w_b * (L^n * T_b * v_rest)    [linearity]
```

### DDM Precomputed Matrices

At **bind time** (one-time offline computation), DDM precomputes for each bone `b` and each vertex `i`:

```
M_{b,i} = L^n * (T_b_rest * v_rest_i)  [4x4 symmetric matrix]
```

The final vertex position at runtime is:

```
v_final_i = Σ_b w_{b,i} * T_b(t) * M_{b,i}
```

where:
- `w_{b,i}` = standard LBS weight (same as LBS, reused)
- `T_b(t)` = bone transform at time t
- `M_{b,i}` = precomputed binding matrix (stored per vertex per bone)

**Computational cost at runtime: O(B) per vertex** — same asymptotic cost as LBS, but with Laplacian-quality results.

### Storage Optimization

Each M_{b,i} is a **symmetric 4×4 matrix** (10 unique floats, not 16), because:
- The cotangent Laplacian is symmetric: L = L^T
- Only the upper (or lower) triangle needs to be stored
- For V vertices and B bones: storage = V × B × 10 floats

For a hero character (50K verts, 4 influences per vertex avg): ~2MB additional storage.

### DDM Variants

Le & Lewis describe multiple variants:
- **Type 0 (basic DDM)**: direct substitution, same quality as iterative DeltaMush
- **Type 1**: decomposes rotational and translational effects independently — allows separate control of bending vs. twisting behavior
- **Type 2 (full)**: includes second-order terms — best quality, higher storage

Type 1 enables a "skin sliding" effect where the surface can translate relative to the underlying skeleton — a feature the original Delta Mush cannot achieve.

### Enhanced Direct Delta Mush (Apple ML Research, 2021)

EDDM (arxiv:2101.02798) adds pose-corrective terms to DDM:
```
v_final_i = DDM(v_i) + Σ_b f_b(pose) * correction_b_i
```
where `f_b(pose)` are pose-dependent blending functions. This reduces the "volume loss" artifact that DDM shares with LBS in extreme bends.

## Implementación en Maya

Maya's native `deltaMush` node runs the **iterative** version (not DDM). There is no native DDM node in Maya as of 2026.

However, DDM is implementable as a custom `MPxDeformerNode` in C++:

```cpp
// Pseudocode for DDM MPxDeformerNode::deform()
MStatus DDMDeformer::deform(MDataBlock& block, MItGeometry& iter,
                             const MMatrix& localToWorld, unsigned int geomIndex)
{
    // Load precomputed M matrices (bound at rig-build time, stored in custom attributes)
    // For each vertex:
    while (!iter.isDone()) {
        MPoint v_final(0, 0, 0, 0);
        int vid = iter.index();
        for (int b = 0; b < numBones; b++) {
            float w = weights[vid][b];          // LBS weight
            MMatrix& M = bindMatrices[vid][b];  // precomputed DDM matrix
            MMatrix T = boneTransforms[b];       // current bone world matrix
            v_final += w * (T * M) * v_rest[vid];
        }
        iter.setPosition(v_final);
        iter.next();
    }
    return MS::kSuccess;
}
```

**Python-side binding computation** (run once at skin-bind time):
```python
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

def compute_ddm_matrices(mesh_vertices, adjacency, bone_weights, bone_rest_transforms, n_iter=20):
    """
    mesh_vertices: (V, 3) rest pose vertices
    adjacency: (V, V) sparse cotangent-weight Laplacian matrix
    bone_weights: (V, B) LBS weights
    bone_rest_transforms: (B, 4, 4) bone rest-pose transforms
    n_iter: number of Laplacian smoothing iterations
    """
    V = mesh_vertices.shape[0]
    B = len(bone_rest_transforms)
    
    # Build Laplacian
    L = sp.eye(V) - adjacency  # simple uniform version; cotangent for production
    
    # Compute L^n
    Ln = L
    for _ in range(n_iter - 1):
        Ln = Ln @ L
    
    # For each bone, compute M_{b,i}
    ddm_matrices = np.zeros((V, B, 4, 4))
    for b in range(B):
        T_rest = bone_rest_transforms[b]
        # Transform rest vertices by bone rest transform
        v_transformed = (T_rest @ np.c_[mesh_vertices, np.ones(V)].T).T  # (V, 4)
        # Apply Ln
        v_smoothed = Ln @ v_transformed[:, :3]
        # Store as per-vertex 4x4 matrix (simplified: actual implementation builds M from v_smoothed)
        for i in range(V):
            ddm_matrices[i, b] = np.outer(v_smoothed[i], [1, 0, 0, 0])  # simplified
    
    return ddm_matrices
```

**GPU implementation:** DDM maps cleanly to a GPU vertex shader — the per-bone weight matrices `M_{b,i}` are precomputed constants, and the per-frame evaluation is just a weighted matrix multiply, identical to LBS in structure.

## Comparación con autorig_tools

autorig_tools usa skinCluster nativo (LBS o DQS) con deltaMush como post-deformador opcional. El problema actual: en characters complejos, deltaMush en modo iterativo bloquea GPU override (es un CPU-only deformer). DDM resolvería esto: la calidad de deltaMush con coste de LBS, GPU-compatible como vertex shader o MPxDeformerNode C++ con `kParallel`. La precomputación de matrices M se puede hacer en Python (scipy.sparse) al momento del bind y almacenar como atributos custom en el nodo deformador. Relevante especialmente para personajes hero donde el deltaMush iterativo causa cuellos de botella.

## Aplicable directamente

PARTIAL — DDM requiere implementación de un MPxDeformerNode en C++ (no trivial) y la precomputación del Laplacian cotangente (scipy). Sin embargo, el concepto es directamente aplicable:
1. **Corto plazo**: documentar que el `deltaMush` nativo de Maya rompe GPU override y usar `deltaMush` con cautela — solo en post-deform cuando sea imprescindible.
2. **Medio plazo (2-4 semanas)**: implementar DDM como C++ deformer usando maya-math-nodes como referencia de estructura de proyecto CMake. Las matrices de precomputing se calculan en Python con scipy.sparse al bind.
3. **Largo plazo**: versión GPU via OpenCL kernel en el evaluador de Maya para integración completa con GPU Override.

## Fuente
- Paper principal: https://dl.acm.org/doi/10.1145/3306346.3322982
- EA SEED overview: https://www.ea.com/seed/news/siggraph2019-direct-delta-mush
- Enhanced DDM (Apple, 2021): https://arxiv.org/abs/2101.02798
- SIGGRAPH 2019 talk: https://www.youtube.com/watch?v=T9mCIwxRG2Q
- DDM compression (SIGGRAPH 2021): https://dl.acm.org/doi/10.1145/3450626.3459779
