---
source: https://groups.csail.mit.edu/graphics/pubs/thesis_sumner_121905.pdf
found: 2026-05-18
category: math
priority: 1
tags: [maya, python, rigging, math, SVD, polar-decomposition, deformation-gradients, correctives, procrustes]
status: NEW
---

# Polar Decomposition, SVD y Deformation Gradients para Rigging

## Descripción
La descomposición polar y la Singular Value Decomposition (SVD) son la base matemática de varios sistemas avanzados de rigging: el paso de actualización de bones en SSDR, la extracción de la rotación "más cercana" de una matrix deformada, la transferencia de deformaciones entre meshes, y los sistemas de pose-space deformation que usan distancias angulares reales (no Euler). La tesis de Sumner (MIT CSAIL, 2004) sobre deformation gradients es la referencia canónica para transferencia de deformaciones y análisis de diferencias de forma entre meshes.

## Fundamento matemático / técnico

### Singular Value Decomposition (SVD)
Any m×n real matrix M can be factored as:
```
M = U Σ Vᵀ
```
- `U` (m×m): orthogonal matrix — left singular vectors (output directions)
- `Σ` (m×n): diagonal matrix — singular values σ₁ ≥ σ₂ ≥ … ≥ 0 (scaling factors)
- `V` (n×n): orthogonal matrix — right singular vectors (input directions)

**Key property:** `det(U)` and `det(V)` are ±1. For a rotation matrix R ∈ SO(3), `det(R) = +1`. SVD lets us project any matrix onto the nearest rotation matrix.

### Polar Decomposition
Any matrix M decomposes uniquely (if M is invertible) into:
```
M = R · S
```
- `R`: orthogonal rotation matrix (det = +1 for proper rotation)
- `S`: symmetric positive-definite matrix (pure stretch/shear)

**Computing via SVD:**
```
M = U Σ Vᵀ
→ R = U Vᵀ         (nearest rotation — the "orthogonal Procrustes" solution)
→ S = V Σ Vᵀ       (symmetric stretch)
```
**Reflection fix:** If `det(U Vᵀ) = -1` (reflection, not rotation), flip the sign of the smallest singular value:
```
Σ' = diag(σ₁, σ₂, -σ₃)  →  R = U Σ' Vᵀ  (now det(R) = +1)
```

```python
import numpy as np

def polar_decompose(M):
    """Extract rotation R and stretch S from matrix M via SVD."""
    U, sigma, Vt = np.linalg.svd(M)
    # Fix reflection
    if np.linalg.det(U @ Vt) < 0:
        U[:, -1] *= -1
    R = U @ Vt          # nearest rotation matrix
    S = Vt.T @ np.diag(sigma) @ Vt  # symmetric stretch
    return R, S

# scipy alternative (handles degenerate cases better):
from scipy.linalg import polar
R, S = polar(M, side='right')  # M = R @ S
```

### Deformation Gradients (Sumner & Popović 2004)
The **deformation gradient tensor** F captures how an infinitesimal region of a mesh deforms:
```
F = ∂p'/∂p    (Jacobian of deformed positions w.r.t. rest positions)
```
For a triangle with rest vertices v₁, v₂, v₃ and deformed vertices v₁', v₂', v₃':
```
Build edge matrices:
  V = [v₂-v₁ | v₃-v₁ | n_rest]    (3×3, columns are edges + normal)
  V'= [v₂'-v₁'| v₃'-v₁'| n_def]   (3×3 deformed edges + normal)

Deformation gradient:
  F = V' · V⁻¹
```
F encodes all rotation, scale, and shear from rest to deformed.

**Polar decompose F:**
```
F = R · S
  R = pure rotation component of the deformation
  S = stretch/shear component (symmetric)
```
This separates WHAT the surface rotated (R) from HOW it stretched (S) — critical for transferring deformations without transferring pose-dependent rotation.

### Application 1: Corrective Shape Transfer
When transferring a corrective blendshape from character A to character B (same topology):
1. Compute per-triangle deformation gradients `F_i` from A's rest pose to A's corrected pose
2. Polar decompose: `F_i = R_i · S_i`
3. Reconstruct deformation on B: apply `F_i` to B's rest triangles → deformed positions
4. Result: the corrective's *shape change* is transferred without the pose-specific rotation

### Application 2: SSDR Bone Update (Procrustes Problem)
In SSDR, updating bone `i` given fixed weights means finding the rigid transform `{R_i, t_i}` that minimizes:
```
Σ_v w_i(v) · |v'(p) - R_i · v_rest - t_i|²
```
Solution via weighted Procrustes (SVD):
1. Compute weighted centroids: `c_rest = Σ_v w_i(v)·v_rest / Σw`, `c_def = Σ_v w_i(v)·v'(p) / Σw`
2. Build covariance: `C = Σ_v w_i(v) · (v_rest - c_rest)ᵀ ⊗ (v'(p) - c_def)`
3. `U Σ Vᵀ = SVD(C)` → `R_i = V Uᵀ` (with reflection fix), `t_i = c_def - R_i · c_rest`

### Application 3: Rotation Distance for RBF Correctives
Using polar decomposition to compute the angular distance between two poses (instead of Euler difference):
```python
def rotation_distance(M_A, M_B):
    """Geodesic angle between two rotation matrices."""
    R_AB = M_A.T @ M_B   # relative rotation
    # Clamp to valid acos range
    trace = np.trace(R_AB)
    cos_angle = (trace - 1.0) / 2.0
    return np.arccos(np.clip(cos_angle, -1.0, 1.0))
```
This gives a proper, rotation-order-independent distance for use as RBF driver values — much more accurate than Euler angle differences.

## Implementación en Maya

```python
import numpy as np
from scipy.linalg import polar
import maya.api.OpenMaya as om

def get_joint_rotation_matrix(joint_name):
    """Get the 3x3 rotation matrix of a joint in world space."""
    sel = om.MSelectionList()
    sel.add(joint_name)
    path = sel.getDagPath(0)
    fn = om.MFnTransform(path)
    wm = fn.transformation().asMatrix()
    # Extract upper-left 3x3 from MMatrix (row-major)
    rows = [[wm[i*4+j] for j in range(3)] for i in range(3)]
    return np.array(rows)

def extract_rotation_from_deformed_matrix(M_4x4_numpy):
    """Given a 4x4 numpy matrix, extract the pure rotation component."""
    R3 = M_4x4_numpy[:3, :3]
    R, S = polar(R3, side='right')  # R3 = R @ S
    return R  # clean rotation matrix, no scale bleed-through

# Deformation gradient for corrective transfer:
def deformation_gradient(rest_verts_tri, def_verts_tri):
    """
    rest_verts_tri, def_verts_tri: (3,3) arrays, rows are vertex positions
    Returns 3x3 deformation gradient F such that def ≈ F @ rest
    """
    # Build edge matrix + artificial normal (Sumner 2004 approach)
    def edge_matrix(v):
        e1 = v[1] - v[0]
        e2 = v[2] - v[0]
        n = np.cross(e1, e2)
        n_hat = n / (np.linalg.norm(n) + 1e-12)
        return np.column_stack([e1, e2, n_hat])
    
    V_rest = edge_matrix(rest_verts_tri)
    V_def  = edge_matrix(def_verts_tri)
    # F = V_def @ inv(V_rest)
    F = V_def @ np.linalg.inv(V_rest)
    return F
```

**Maya native approach:** `maya.api.OpenMaya.MMatrix` provides `MMatrix.inverse()`, `MMatrix` multiplication, and `MTransformationMatrix` for polar-style decomposition (via `.rotation()` which strips scale). However for corrective transfer workflows requiring full SVD, Python's numpy/scipy are used at build time (not runtime).

## Comparación con autorig_tools
autorig_tools usa RBF correctives con distancias Euler. Adoptar la **distancia geodésica via polar decomposición** como driver del RBF corregiría el problema clásico de que los correctives "se activan" de forma inconsistente según el rotation order del joint. Es un cambio directo en la función de distancia del solver RBF. El deformation gradient transfer también abre la posibilidad de portar correctives sculpted en un personaje hero a variantes de personaje con la misma topología.

## Aplicable directamente
PARTIAL — La función `rotation_distance()` vía SVD como driver para el RBF solver es un cambio de 10-20 líneas en el código RBF de autorig_tools, reemplazando la diferencia de Euler por distancia geodésica. La transferencia de deformation gradients requiere más trabajo pero es un módulo separado, no bloquea el pipeline actual.

## Fuente
- Sumner & Popović 2004 thesis (MIT CSAIL): https://groups.csail.mit.edu/graphics/pubs/thesis_sumner_121905.pdf
- Chalmers skin deformation survey: https://publications.lib.chalmers.se/records/fulltext/251773/local_251773.pdf
- Wikipedia SVD: https://en.wikipedia.org/wiki/Singular_value_decomposition
- Wikipedia Polar Decomposition: https://en.wikipedia.org/wiki/Polar_decomposition
- scipy.linalg.polar: https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.polar.html
