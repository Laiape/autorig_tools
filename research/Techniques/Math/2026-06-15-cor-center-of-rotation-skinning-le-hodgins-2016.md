---
source: https://dl.acm.org/doi/10.1145/2897824.2925959 | https://history.siggraph.org/learning/real-time-skeletal-skinning-with-optimized-centers-of-rotation/ | https://binh.graphics/papers/2016s-cor/
found: 2026-06-15
category: math
priority: 1
tags: [maya, skinning, CoR, center-of-rotation, LBS, DQS, artifacts, candy-wrapper, bulging, SIGGRAPH2016, disney, math]
status: NEW
---

# CoR — Real-Time Skeletal Skinning with Optimized Centers of Rotation (Le & Hodgins, SIGGRAPH 2016)

## Descripción
Center of Rotation (CoR) skinning es un método de deformación de piel desarrollado por Binh Huy Le y James Hodgins (Disney Research / CMU, publicado en ACM Transactions on Graphics Vol. 35, No. 4, SIGGRAPH 2016). Resuelve simultáneamente los dos artefactos principales de los métodos anteriores: el "candy-wrapper" (colapso de volumen) de LBS y el "bulging" (hinchazón artificial) de DQS. El insight fundamental: en lugar de interpolar transformaciones de hueso, se precalcula un centro de rotación óptimo por vértice y se aplica una rotación ponderada directamente. Coste computacional en runtime idéntico a LBS. Nota: Disney Research tiene patente sobre esta técnica (uso comercial requiere licencia).

## Fundamento matemático / técnico

### Problem Review: Why LBS and DQS Fail

**LBS (Linear Blend Skinning):**
```
p_LBS(v) = Σ_i w_i(v) · T_i · v_rest
```
Where T_i = 4×4 transformation matrix of bone i.

**Failure mode — candy-wrapper:** When bone i rotates 180° relative to bone j, the average of T_i and T_j has near-zero determinant. The matrix sum collapses toward zero, shrinking the mesh:
```
At θ=180°: det(w·R(180°) + (1-w)·I) ≈ 0 for w=0.5
→ Volume collapses → "candy wrapper twist" artifact
```

**DQS (Dual Quaternion Skinning):**
```
p_DQS(v) = DQ_blend(v) · v_rest
```
DQS fixes candy-wrapper but introduces **bulging**: the arc path of SLERP between two quaternions is longer than the straight line between the two end positions, causing the mesh to inflate in the middle of a rotation:
```
SLERP arc length > linear interpolation distance
→ Vertex travels on a longer path → volume increase → "bulging"
```

---

### The CoR Insight: Precomputed Rotation Centers

For a rigid body rotating around a fixed axis through point **c**, the deformed position is:
```
p_deformed = R · (v_rest - c) + c
```
Where R is the pure rotation matrix and c is the center of rotation.

**Key observation:** If each vertex v has a precomputed optimal center of rotation c_v, then:
```
p_CoR(v) = R_v · (v_rest - c_v) + c_v
```
Where R_v is a weighted average of bone rotations. This is a pure rotation (no volume loss, no arc inflation).

---

### Computing the Optimized CoR (Offline, per vertex)

Given a vertex v with skinning weights w_i (summing to 1), the optimal CoR is computed from pairs of bones:

**Step 1: For each pair of bones (i, j) — i ≠ j:**

The canonical center of rotation r_{ij} for a two-bone blend (weights w_i, w_j) is the geometric mean point that minimizes rotation artifacts between bones i and j:
```
r_{ij} = center where the "pure rotation" from bone i's pose 
          to bone j's pose appears to originate
```
For pure rotational bones at rest: r_{ij} = weighted midpoint of bone i and bone j pivot points.

**Step 2: Aggregate over all bone pairs:**
```
c_v = Σ_{i<j} w_i(v) · w_j(v) · r_{ij}
      ─────────────────────────────────
         Σ_{i<j} w_i(v) · w_j(v)
```
This is a normalized weighted average of all pairwise "natural rotation centers" for vertex v.

**Intuition:** Vertices with high influence from one dominant bone get their CoR near that bone's pivot. Vertices at a joint seam (equal influence from two bones) get their CoR at the midpoint between the two bone pivots — the natural rotation center for a 50/50 blend.

**Storage:** One 3D vector c_v per vertex = 3 floats × V vertices. For 100K vertex mesh: ~1.2MB. No per-bone-per-vertex storage needed (unlike DDM's precomputed matrices).

---

### Runtime Deformation

At each frame, for vertex v:

**Step 1: Compute blended rotation R_v:**
```
R_v = polar_decomposition(Σ_i w_i(v) · R_i)
```
Where:
- R_i = rotation component of bone i's current transform (3×3 matrix)
- Polar decomposition extracts the pure rotation from the weighted sum
  (avoids the volume-loss problem of directly averaging rotation matrices)

**Polar decomposition via SVD:**
```
M = U · S · V^T  (SVD of weighted rotation sum)
R_v = U · V^T   (drop the singular values S → pure rotation)
```

**Step 2: Apply rotation around precomputed CoR:**
```
p_v = R_v · (v_rest - c_v) + c_v
```

**Total runtime cost:** O(B) per vertex (same as LBS) + one polar decomposition (SVD of 3×3 matrix) per vertex.

**Polar decomposition cost:** SVD of 3×3 ≈ 5-10× more expensive than a matrix-vector multiply. In practice, CoR is approximately 2-3× slower than LBS per vertex, but the quality improvement eliminates the need for costly corrective shapes.

---

### Artifact Comparison

| Artifact            | LBS       | DQS          | CoR           |
|---------------------|-----------|--------------|---------------|
| Candy-wrapper       | YES (severe) | No        | No            |
| Bulging             | No        | YES (moderate) | No          |
| Volume preservation | No        | Approximate  | Yes (polar decomp) |
| Scale support       | Yes       | No (requires workaround) | Yes |
| Shear support       | Yes       | No           | No            |
| Runtime cost        | O(B·V)    | O(B·V)       | O(B·V) + SVD |
| GPU-compatible      | Yes       | Yes (Maya 2022+) | Needs custom deformer |

---

### Maya Implementation Strategy

Maya has no native CoR deformer. Implementation as custom `MPxDeformerNode` in C++:

```cpp
// CoR MPxDeformerNode pseudocode
MStatus CoRDeformer::deform(MDataBlock& block, MItGeometry& iter,
                             const MMatrix& localToWorld, unsigned int geomIndex)
{
    // Load precomputed CoR per vertex (stored as custom attribute array)
    MFloatVectorArray cors = block.inputValue(aCoRs).asFloatVectorArray();
    
    // Load current bone rotations (from skinCluster binding)
    // For each bone b: get worldMatrix → extract R_b (3x3 rotation)
    
    while (!iter.isDone()) {
        int vid = iter.index();
        MPoint v_rest = iter.position();
        MVector cor = cors[vid];
        
        // Compute weighted rotation sum (3x3 matrix)
        MMatrix M = zero_3x3;
        for (int b = 0; b < numBones; b++) {
            float w = weights[vid][b];
            M += w * R[b];  // add weighted rotation of bone b
        }
        
        // Polar decomposition via SVD (use Eigen or custom SVD)
        Matrix3f R_v = polar_decompose(M);  // U * V^T from SVD
        
        // Apply CoR deformation
        MVector d = MVector(v_rest) - cor;
        MPoint p_cor = R_v * d + cor;
        
        iter.setPosition(p_cor);
        iter.next();
    }
    return MS::kSuccess;
}
```

**Build-time computation (Python, offline):**
```python
import numpy as np
import maya.cmds as cmds

def compute_cor_per_vertex(mesh, skin_cluster):
    """
    Compute CoR for each vertex from skinning weights.
    Simplified: CoR = weighted centroid of bone pivot points.
    """
    # Get all bone pivots in world space
    influences = cmds.skinCluster(skin_cluster, q=True, influence=True)
    bone_pivots = []
    for inf in influences:
        pos = cmds.xform(inf, q=True, ws=True, t=True)
        bone_pivots.append(np.array(pos))
    
    # Get skin weights
    num_verts = cmds.polyEvaluate(mesh, vertex=True)
    cors = []
    
    for vid in range(num_verts):
        weights = []
        for inf in influences:
            w = cmds.skinPercent(skin_cluster, f'{mesh}.vtx[{vid}]',
                                 transform=inf, query=True)
            weights.append(w)
        weights = np.array(weights)
        
        # Weighted sum over pairs (simplified: use direct weighted centroid)
        # Full CoR: Σ_{i<j} w_i * w_j * r_ij / Σ_{i<j} w_i * w_j
        pair_cor = np.zeros(3)
        pair_weight = 0.0
        for i in range(len(influences)):
            for j in range(i+1, len(influences)):
                w_pair = weights[i] * weights[j]
                if w_pair < 1e-6: continue
                # r_ij = midpoint of bone i and bone j pivots (simplified)
                r_ij = (bone_pivots[i] + bone_pivots[j]) * 0.5
                pair_cor += w_pair * r_ij
                pair_weight += w_pair
        
        if pair_weight > 1e-6:
            cors.append(pair_cor / pair_weight)
        else:
            # Single-influence vertex: CoR = that bone's pivot
            dominant = np.argmax(weights)
            cors.append(bone_pivots[dominant])
    
    return cors
```

---

### Relationship to Other Algorithms

| Algorithm | Key Trick | Limitation |
|-----------|-----------|------------|
| LBS       | Weighted matrix sum | Volume loss (candy-wrapper) |
| DQS       | SLERP dual quaternions | Bulging |
| CoR       | Precomputed rotation center + polar decomp | No scale/shear; needs custom deformer |
| DDM       | Precomputed Laplacian matrices | Slightly more storage; also no native Maya node |
| SBS (Spherical Blend Skinning) | Blend on sphere | Similar to CoR, older approach |

## Comparación con autorig_tools

autorig_tools usa `skinCluster` nativo con `skinningMethod=0` (LBS) o `skinningMethod=1` (DQS). CoR no tiene nodo nativo en Maya, así que no es un reemplazo drop-in. Su valor en el pipeline de Laia es como referencia académica para entender la matemática del bulging de DQS: si el DQS da artifacts visibles en zonas específicas, la solución CoR indica que hay que ajustar las poses de corrective o usar una mezcla LBS+DQS por zona (`skinningMethod=2`). Para producción en autorig_tools, el tradeoff es: implementar CoR como MPxDeformerNode C++ (2-3 semanas de trabajo) vs usar corrective blendshapes sobre DQS (ya implementado, más rápido de autor).

## Aplicable directamente

NO — No hay nodo nativo en Maya. Implementar CoR como MPxDeformerNode C++ requiere trabajo de plugin sustancial. PARTIAL para el código Python de `compute_cor_per_vertex()`: puede usarse offline para analizar dónde están los centros de rotación de los joints en un personaje, y comparar con dónde el DQS produce bulging — útil como herramienta de diagnóstico de skin weights.

## Fuente
- Paper ACM ToG: https://dl.acm.org/doi/10.1145/2897824.2925959
- SIGGRAPH History listing: https://history.siggraph.org/learning/real-time-skeletal-skinning-with-optimized-centers-of-rotation/
- Binh Le's page: https://binh.graphics/papers/2016s-cor/
- Unity community implementation: https://discussions.unity.com/t/cor-real-time-skeletal-skinning-with-optimized-centers-of-rotation/733353
