---
source: https://dl.acm.org/doi/abs/10.1111/cgf.12492 | https://arxiv.org/pdf/2103.01694 | https://igl.ethz.ch/projects/ARAP/
found: 2026-07-13
category: math
priority: 1
tags: [maya, python, rigging, math, polar-decomposition, SVD, deformation-gradient, ARAP, correctives, CoR]
status: NEW
---

# Polar Decomposition y Deformation Gradient para Correctives

## Descripción
La descomposicion polar del gradiente de deformacion F = R*S separa una deformacion local en su componente de rotacion pura (R) y su componente de estiramiento (S). En rigging, esta matematica permite extraer la rotacion local real de cada vertice (no la rotacion del joint mas cercano), activar correctives con mayor precision que con Euler angles de joint, y es la base matematica del algoritmo ARAP (As-Rigid-As-Possible). Diferente del SSDR (cubierto en 2026-06-15): SSDR invierte el problema globalmente para encontrar bones optimos; la descomposicion polar opera localmente per-vertice o per-celda.

## Fundamento matematico / tecnico

### Deformation Gradient F

Given a mesh at rest position X and deformed position x, the **deformation gradient tensor** F at a point describes the local linear mapping from rest to deformed space:
```
x = F * X + t    (locally affine approximation around each vertex)
F = dx/dX        (3x3 matrix -- partial derivatives of deformed wrt rest)
```

**Computing F from mesh triangles:**
For triangle with vertices {p0, p1, p2} at rest and {q0, q1, q2} deformed:
```
D_rest     = [p1-p0 | p2-p0]       (3x2 edge matrix at rest)
D_deformed = [q1-q0 | q2-q0]       (3x2 edge matrix deformed)

F = D_deformed * pinv(D_rest)       (Moore-Penrose pseudo-inverse of D_rest)
```
Result: 3x3 (or 3x2 embedded) matrix describing local affine deformation.

### Polar Decomposition: F = R * S

Every non-singular matrix F decomposes UNIQUELY into:
```
F = R * S

R = rotation matrix (orthogonal, det=+1)     -- the "rigid" component
S = symmetric positive definite matrix        -- the "stretch/shear" component
```

**Computing via SVD (always numerically stable):**
```
SVD: F = U * Sigma * V^T

R = U * V^T                       (rotation -- correct if det(R)=+1)
S = V * Sigma * V^T               (right polar stretch factor)

Edge case -- if det(U*V^T) < 0 (reflection):
  Negate the column of U corresponding to smallest singular value sigma_min
  Then R = U_corrected * V^T
```

```python
import numpy as np

def polar_decomp(F):
    """Polar decomposition F = R * S via SVD.
    Returns (R, S): rotation 3x3, symmetric stretch 3x3.
    """
    U, sigma, Vt = np.linalg.svd(F)
    # Handle reflection: ensure det(R) = +1
    d = np.linalg.det(U @ Vt)
    D = np.diag([1.0, 1.0, d])
    R = U @ D @ Vt
    S = Vt.T @ (D * sigma[:, np.newaxis]) @ Vt
    return R, S

def deformation_gradient_from_triangles(rest_verts, def_verts, tri_indices):
    """
    Compute per-triangle deformation gradient.
    rest_verts, def_verts: Nx3 position arrays
    tri_indices: Mx3 triangle index array
    Returns: Mx3x3 array of deformation gradients
    """
    F_list = []
    for tri in tri_indices:
        p0, p1, p2 = rest_verts[tri]
        q0, q1, q2 = def_verts[tri]
        D_rest = np.column_stack([p1-p0, p2-p0])    # 3x2
        D_def  = np.column_stack([q1-q0, q2-q0])    # 3x2
        # Pseudo-inverse solve: F = D_def * pinv(D_rest)
        F = D_def @ np.linalg.pinv(D_rest)           # 3x2 (embed later)
        # Extend to 3x3 using cross product as third column
        n_rest = np.cross(D_rest[:,0], D_rest[:,1])
        n_rest /= np.linalg.norm(n_rest) + 1e-10
        n_def  = np.cross(D_def[:,0], D_def[:,1])
        n_def  /= np.linalg.norm(n_def) + 1e-10
        F3 = np.column_stack([F, n_def - F @ n_rest.reshape(3,1)[:,0]])  # simplified
        F_list.append(F3 if F3.shape == (3,3) else np.eye(3))
    return np.array(F_list)
```

### Singular Values as Deformation Descriptors

The three singular values sigma_1 >= sigma_2 >= sigma_3 of F describe:
```
sigma_1 * sigma_2 * sigma_3 = det(F) = volume change ratio
    < 1: compression (volume lost)
    > 1: expansion (volume gained)
    = 1: isochoric / volume-preserving

sigma_1 / sigma_3 = anisotropy ratio (large = "candy-wrapper" stretching)

ARAP strain energy = sum((sigma_i - 1)^2) = how far F is from rigid motion
```

### Application 1: ARAP Energy for Corrective Quality Metric

ARAP (As-Rigid-As-Possible, Sorkine & Alexa SIGGRAPH 2007) measures how far a deformation deviates from a rigid body motion:
```
E_ARAP(p) = sum_i sum_{j in N(i)} w_ij * || (p_i - p_j) - R_i*(p_i* - p_j*) ||^2
```
Where:
- `p_i*`, `p_j*` = rest positions
- `p_i`, `p_j`   = deformed positions
- `R_i`          = per-cell rotation from polar decomp of local F
- `w_ij`         = cotangent weights (from mesh Laplacian)

**Two-step alternating solver:**
1. **Local step:** Fix deformed positions p, compute R_i via SVD polar decomp for each 1-ring cell
2. **Global step:** Fix R_i, solve sparse linear system for p (Cholesky factorization, ~3-5 iterations)

**Practical use in rigging:** Use ARAP strain energy `E_ARAP` as a **corrective quality metric** -- high ARAP energy zones = bad skinning that needs correctives most urgently. Run once at bind time to prioritize sculpting effort.

```python
def compute_arap_energy_per_vertex(mesh_rest, mesh_deformed):
    """
    Compute ARAP strain energy per vertex.
    High energy = far from rigid motion = needs corrective shapes.
    Returns: N-length array of strain energies.
    """
    # Get triangles and compute F per triangle
    # ... (mesh query) ...
    F_list = deformation_gradient_from_triangles(rest_verts, def_verts, tri_indices)
    
    energies = np.zeros(len(rest_verts))
    for tri_idx, (tri, F) in enumerate(zip(tri_indices, F_list)):
        R, S = polar_decomp(F)
        strain = np.sum((np.linalg.svd(F, compute_uv=False) - 1.0)**2)
        # Distribute to triangle vertices (area-weighted)
        for vi in tri:
            energies[vi] += strain / 3.0
    return energies
```

### Application 2: Per-Vertex Local Rotation Driver for PSD

Instead of using joint Euler angles as RBF corrective drivers, use the **per-vertex local rotation angle** extracted from polar decomp of the 1-ring deformation gradient:

```python
def local_rotation_angle_at_vertex(mesh_rest, mesh_deformed, vertex_idx):
    """
    Rotation angle (degrees) at a vertex, extracted from deformation gradient.
    Better driver than joint Euler angles for correctives near soft tissue.
    """
    # Get 1-ring triangles of vertex_idx
    # ... mesh connectivity query ...
    F = area_weighted_average_F(mesh_rest, mesh_deformed, vertex_idx)
    R, S = polar_decomp(F)
    
    # Convert R to angle
    trace_R = np.trace(R)
    angle = np.arccos(np.clip((trace_R - 1.0) / 2.0, -1.0, 1.0))
    return np.degrees(angle)
```

This measures "how much has the surface actually rotated here" -- more accurate than joint angle for muscles, fat, soft tissue that deforms non-rigidly.

### Application 3: CoR (Center of Rotation) Skinning

CoR (Le & Hodgins, SIGGRAPH 2016) precomputes a virtual center of rotation per vertex using polar decomposition of relative bone transforms:

```
c_v = (sum_i sum_j w_i(v)*w_j(v) * phi(|b_i - b_j|) * (b_i + b_j)/2) /
      (sum_i sum_j w_i(v)*w_j(v) * phi(|b_i - b_j|))

phi(|b_i - b_j|) = similarity(b_i, b_j) via:
    R_ij, S_ij = polar_decomp(b_i * inverse(b_j))
    phi = 1 - |S_ij - I| / max_stretch  (how "similar" are the two bone transforms)
```

The polar decomp of `b_i * inverse(b_j)` measures how different two bone transforms are in terms of rotation -- joints with similar rotations contribute high phi (good candidates to define a shared CoR), while joints with opposite rotations get low phi.

### Performance Note

3x3 SVD is the computational cost of this approach. For production use:
- **Offline (bind time):** No performance concern. Compute once, store per vertex.
- **Runtime (per-frame):** 3x3 SVD per vertex is expensive in Python (~50µs per vertex). Feasible in C++ with Eigen (< 1µs per vertex with Jacobi SVD).
- For ~10K vertex mesh: Python = ~0.5s per frame (too slow). C++ = ~10ms per frame (acceptable).

## Implementacion en Maya

There is no native Maya node for polar decomposition. Practical approaches:

**Offline Python (bind-time corrective zone detection):**
```python
import maya.cmds as cmds
import numpy as np

def find_high_strain_vertices(mesh_rest_name, mesh_corrected_name, threshold=0.5):
    """
    Find vertices where skinning deviates most from rigid motion.
    These are priority zones for corrective shapes.
    """
    # Get vertex positions
    rest   = np.array([cmds.xform(f'{mesh_rest_name}.vtx[{i}]',    q=True, ws=True, t=True)
                       for i in range(cmds.polyEvaluate(mesh_rest_name, v=True))])
    deform = np.array([cmds.xform(f'{mesh_corrected_name}.vtx[{i}]', q=True, ws=True, t=True)
                       for i in range(cmds.polyEvaluate(mesh_corrected_name, v=True))])
    
    energies = compute_arap_energy_per_vertex(rest, deform)
    high_strain = np.where(energies > threshold * energies.max())[0]
    
    print(f"High-strain vertices: {len(high_strain)}/{len(rest)}")
    print(f"Max strain energy: {energies.max():.4f}")
    
    # Select in Maya for visual inspection
    cmds.select([f'{mesh_rest_name}.vtx[{i}]' for i in high_strain])
    return high_strain, energies
```

**scipy.linalg.polar (recommended for Python):**
```python
from scipy.linalg import polar as scipy_polar

R, S = scipy_polar(F)   # robust for near-degenerate F, uses LAPACK under the hood
```

## Comparacion con autorig_tools

`autorig_tools` usa joint Euler angles como drivers de RBF/SDK correctives. La descomposicion polar permite un nivel de precision superior: el driver seria la deformacion geometrica real de la superficie, no el angulo del joint. La aplicacion mas practica a corto plazo es usar `find_high_strain_vertices()` como herramienta diagnostica al crear correctives nuevos -- indica exactamente donde hay que scultar sin necesidad de iterar a ciegas. El coste de integracion es bajo (funcion Python standalone, sin dependencias de rig).

## Aplicable directamente

PARTIAL:
1. **Diagnostic tool (1-2h):** Implementar `find_high_strain_vertices()` en `autorig_tools/utils/deform_analysis.py`. Correr en cualquier personaje nueva antes de entrar a sesion de correctives sculpting.
2. **ARAP strain energy metric (standalone):** Ya applicable como script offline sobre cualquier par (mesh_skinned_at_problem_pose, mesh_corrected). Sin tocar el rig.
3. **CoR driver (multi-day):** Reemplazar LBS con CoR skinning en zonas problematicas (axila, rodilla) requiere implementacion C++ del CoR precompute. Gran impacto de calidad pero alto coste de implementacion.

## Fuente
- https://dl.acm.org/doi/abs/10.1111/cgf.12492 -- Sparse Localized Decomposition of Deformation Gradients (CGF 2014)
- https://arxiv.org/pdf/2103.01694 -- A Revisit of Shape Editing Techniques
- https://igl.ethz.ch/projects/ARAP/ -- ARAP: Sorkine & Alexa (SIGGRAPH 2007)
- https://binh.graphics/papers/2016s-cor/ -- CoR: Le & Hodgins (SIGGRAPH 2016)
