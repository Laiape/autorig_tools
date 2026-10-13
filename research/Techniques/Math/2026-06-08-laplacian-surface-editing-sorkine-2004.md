---
source: https://dl.acm.org/doi/10.1145/1057432.1057456 | https://people.eecs.berkeley.edu/~jrs/meshpapers/SCOLARS.pdf | https://igl.ethz.ch/projects/Laplacian-mesh-processing/Laplacian-mesh-editing/index.php
found: 2026-06-08
category: math
priority: 1
tags: [maya, mesh-deformation, laplacian, surface-editing, correctives, rigging, math, sparse-linear, detail-preservation]
status: NEW
---

# Laplacian Surface Editing — Deformación que Preserva Detalle Superficial

## Descripción
Laplacian Surface Editing (Sorkine, Cohen-Or, Lipman et al., Eurographics/SIGGRAPH SGP 2004) es el framework matemático para deformar mallas poligonales de forma que el detalle superficial se preserve bajo grandes deformaciones. La idea clave: representar cada vértice no por su posición absoluta, sino por su *coordenada diferencial* (Laplacian), que codifica la relación local con sus vecinos. Deformar = imponer constraints → resolver sistema lineal sparse. Está integrado en Blender como "Laplacian Deform Modifier" y es la base teórica de Delta Mush, DDM, y muchos sistemas de rigging de mallas.

## Fundamento matemático / técnico

### Laplacian Coordinates (Differential Coordinates)

Given a mesh M = (V, E) with vertex positions v_i ∈ ℝ³, the **Laplacian coordinate** δ_i is:

```
δ_i = v_i - Σ_{j ∈ N(i)} w_{ij} · v_j
```

where N(i) = 1-ring neighbors of vertex i, and w_{ij} are weights.

**Uniform weights** (simpler): `w_{ij} = 1/|N(i)|`

**Cotangent weights** (geometry-aware, preferred for rigging):
```
w_{ij} = (cot α_{ij} + cot β_{ij}) / (2 · A_i)
```
where:
- `α_{ij}, β_{ij}` = angles opposite to edge (i,j) in the two triangles sharing that edge
- `A_i` = Voronoi area around vertex i

The cotangent weights derive from the **discrete Laplace-Beltrami operator**, the standard discretization of the geometric Laplacian on triangle meshes.

**Matrix form**: defining the Laplacian matrix L ∈ ℝ^{n×n}:
```
L_ii = 1
L_ij = -w_{ij}  (j ∈ N(i))
L_ij = 0        (otherwise)

δ = L · v        [n×3 matrix equation, one column per coordinate]
```

### Properties of Laplacian Coordinates

1. **Translation invariant**: if all vertices move by the same vector t, δ_i is unchanged
2. **NOT rotation invariant**: δ_i transforms with the local rotation — this is the key property that makes them encode "detail direction"
3. **Mean curvature normal**: δ_i ≈ (local mean curvature) × (surface normal) — geometrically meaningful
4. **Linear function of positions**: δ = L·v — this enables efficient linear solves

### The Deformation System

Given:
- A set of **handle vertices** H ⊂ V with prescribed deformed positions v'_H (user-specified constraints)
- A set of **free vertices** F = V \ H

The deformed mesh solves:
```
min_{v'_F} || L·v' - δ' ||²    subject to:  v'_H = prescribed positions
```

where δ' are the **rotated** Laplacian coordinates (to make them rotation-invariant):
```
δ'_i = R_i · δ_i
```
and R_i is estimated from the deformation of vertex i's neighborhood.

**This yields a sparse linear system**:
```
(L^T · L) · v' = L^T · δ'
```

The matrix `L^T · L` is sparse, positive semi-definite, and can be **pre-factored** (Cholesky) — enabling interactive editing (milliseconds per deformation).

### Rotation Estimation (Making it Rotation-Invariant)

Since δ_i is rotation-sensitive, we need to estimate R_i at each free vertex:
```
R_i = argmin_R || R·δ_i - δ'_i ||²   [best-fit rotation from 1-ring deformation]
```
This is solved by SVD of the local Jacobian:
```
J_i = Σ_{j ∈ N(i)} w_{ij} · (v'_j - v'_i)·(v_j - v_i)^T
J_i = U·S·V^T  (SVD)
R_i = V·U^T
```

### Connection to Rigging Systems

| System | Laplacian Use |
|--------|---------------|
| Delta Mush | Laplacian smoothing applied to DEFORMED positions to remove skinning artifacts |
| Direct Delta Mush | L^n precomputed into static matrices at bind time |
| Laplacian Surface Editing | L used as differential coordinates for handle-based deformation |
| Laplacian Deform (Blender) | Same as LSE but integrated as a modifier |

The key difference: in Delta Mush, L is applied to *smooth out* the deformation. In LSE, L is used to *encode detail* so it survives the deformation.

### Python Implementation (Offline Mesh Deformation)

```python
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

def build_laplacian(vertices, faces):
    """Build cotangent-weight Laplacian matrix."""
    n = len(vertices)
    rows, cols, vals = [], [], []
    
    for f in faces:
        for k in range(3):
            i, j, l = f[k], f[(k+1) % 3], f[(k+2) % 3]
            # Cotangent of angle at vertex l (opposite to edge i-j)
            vi, vj, vl = vertices[i], vertices[j], vertices[l]
            cot_l = np.dot(vl - vi, vl - vj) / np.linalg.norm(np.cross(vl - vi, vl - vj))
            rows += [i, j, i]
            cols += [j, i, i]
            vals += [-cot_l / 2, -cot_l / 2, cot_l / 2]
    
    L = sp.csr_matrix((vals, (rows, cols)), shape=(n, n))
    # Normalize rows
    D = sp.diags(np.array(L.sum(axis=1)).flatten())
    return D - L  # Standard Laplacian (positive semi-definite)

def laplacian_deform(vertices, faces, handles, handle_positions):
    """
    handles: list of vertex indices (pinned points)
    handle_positions: new positions for handle vertices (3D)
    """
    n = len(vertices)
    L = build_laplacian(vertices, faces)
    
    # Compute Laplacian coordinates (rest pose)
    delta = L @ vertices  # (n, 3)
    
    # Build system: free vertices F = all non-handle vertices
    free = [i for i in range(n) if i not in handles]
    
    # Augmented system: L·v' = delta for free, v'_i = handle_pos for handles
    A = L.copy().toarray()
    b = delta.copy()
    
    for idx, h in enumerate(handles):
        A[h, :] = 0
        A[h, h] = 1
        b[h] = handle_positions[idx]
    
    # Solve sparse system (Cholesky factorization for speed)
    v_new = np.linalg.solve(A, b)
    return v_new
```

**Production note**: for interactive editing, pre-factorize `A` using `scipy.sparse.linalg.splu` or `cholmod` — solve time drops to <10ms for meshes up to 100K verts.

## Implementación en Maya

Maya has no native Laplacian Surface Editing node, but the technique appears in:
- `deltaMush` deformer: uses iterative Laplacian (not the full LSE solver, but related)
- `smoothSkin` operations: some use Laplacian smoothing
- Custom MPxDeformerNode: full LSE implementable as a C++ deformer

**Practical rigging application — corrective shape creation:**
```python
# Use offline LSE to create a detail-preserving corrective blendshape
# 1. Take the skinned mesh at a problematic pose
# 2. Define "handle" vertices (the correct positions you want)  
# 3. LSE fills in the rest, preserving surface detail
# 4. Result becomes a corrective blendshape target
import maya.cmds as cmds

def create_lse_corrective(mesh, handle_verts, target_positions, n_smooth_iters=10):
    """Offline tool: compute LSE corrective shape."""
    import numpy as np
    verts = np.array(cmds.xform(mesh + '.vtx[*]', q=True, ws=True, t=True)).reshape(-1, 3)
    faces = get_mesh_faces(mesh)
    corrective = laplacian_deform(verts, faces, handle_verts, target_positions)
    # Apply to mesh (create blendshape target)
    apply_positions_to_mesh(corrective, mesh + '_lse_corrective')
```

**As a rigging deformer**: Laplacian deformation can be used for real-time "handle-based" secondary animation — e.g., muscle surface following underlying joint. Each "muscle joint" is a handle; the skin surface solves to preserve volume detail. Requires precomputed Cholesky factorization stored in the deformer.

## Comparación con autorig_tools

autorig_tools crea correctives mediante blendshapes esculpidos manualmente y sistemas RBF/SDK para activarlos. Laplacian Surface Editing ofrece una alternativa matemática para *generar* la forma del corrective de forma automática: dado un handle en la posición correcta, el resto de la malla se deforma preservando el detalle. Esto podría acelerar la creación de correctives de ropa, músculos secundarios, y deformaciones de volumen — en lugar de esculpir todo manualmente, se esculpen solo las posiciones de control (handles) y LSE propaga la deformación de forma coherente. No reemplaza el sistema RBF/SDK de activación, sino que complementa la *creación* de shapes.

## Aplicable directamente

PARTIAL — El sistema completo requiere implementar el solver LSE (Python/C++). Sin embargo:
- **Aplicable inmediatamente en Python** como herramienta offline de creación de correctives: `laplacian_deform()` en ~50 líneas de Python con scipy.sparse. No requiere plugin.
- Workflow: usar en post-build de autorig_tools para generar correctives de volumen automáticos (ej. deltoids al levantar brazo, cuádriceps en flexión de rodilla) desde posiciones de control editadas a mano.
- La función `build_laplacian()` + Cholesky factorization es reutilizable en otros sistemas (incluyendo DDM precompute).

## Fuente
- Paper original: https://dl.acm.org/doi/10.1145/1057432.1057456
- PDF libre (Berkeley): https://people.eecs.berkeley.edu/~jrs/meshpapers/SCOLARS.pdf
- Página del proyecto (ETH): https://igl.ethz.ch/projects/Laplacian-mesh-processing/Laplacian-mesh-editing/index.php
- Blender Laplacian Deform: https://docs.blender.org/manual/en/latest/animation/armatures/posing/bone_constraints/deformation/laplacian_deform.html
