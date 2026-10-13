---
source: https://arxiv.org/abs/2605.08086
found: 2026-08-10
category: math
priority: 1
tags: [maya, rigging, math, rotation, quaternion, euler, neural-networks, differentiable, 6d-representation, SO3, continuity]
status: NEW
---

# 6D Continuous Rotation Representations — Matemática para Pipelines Diferenciables de Rigging

## Descripción
Cuando se usan rotaciones como input o output de sistemas diferenciables (redes neuronales para IK, optimizadores de RBF, sistemas de correctives ML), la elección de la representación de rotación afecta la convergencia del gradiente. El paper de Zhou et al. 2019 (arxiv 1812.07035) demostró que Euler, quaterniones y exponential maps tienen discontinuidades que cortan el flujo del gradiente. La representación 6D (primeras dos columnas de la matriz de rotación + Gram-Schmidt de reconstrucción) es la representación continua mínima para SO(3) en espacio Euclidiano. Aiersilan et al. 2025 (arxiv 2605.08086) sintetiza todas las representaciones con análisis comparativo completo.

## Fundamento matemático / técnico

### Por qué las representaciones estándar fallan en sistemas diferenciables

**Theorem (Zhou et al. 2019):** No continuous surjective mapping f: ℝⁿ → SO(3) exists for n < 5. Therefore, 3D representations (Euler, axis-angle, exponential map) and 4D representations (quaternion) must have discontinuities.

**Consequence for gradient-based optimization:** At discontinuity points, the gradient ∂loss/∂θ is either undefined or points away from the correct minimum. A neural network or optimizer that crosses a discontinuity boundary will exhibit training instability or poor convergence.

### Comparison of rotation representations

| Representation | Dim | Continuous | Unique | Gimbal Lock | Interp |
|---|---|---|---|---|---|
| Euler (ZYX, etc.) | 3 | NO | NO | YES | BAD |
| Axis-angle | 3 | NO | NO | NO | OK |
| Exponential map | 3 | NO (at 2π) | NO | NO | OK |
| Quaternion | 4 | NO (±q same R) | NO | NO | GOOD (SLERP) |
| Rotation matrix (full) | 9 | YES | YES | NO | OK (via SVD) |
| **6D representation** | **6** | **YES** | **NO** | **NO** | **GOOD** |
| 9D (matrix + project) | 9 | YES | YES | NO | OK |

### The 6D Continuous Representation (Zhou et al. 2019)

**Encoding:** Given rotation matrix R = [r₁ | r₂ | r₃] (columns r₁, r₂, r₃ ∈ ℝ³), encode as:
```
x = (r₁, r₂) ∈ ℝ⁶
```
Only the first two columns are needed — r₃ is discarded.

**Decoding (Gram-Schmidt orthogonalization):**
```
Given x = (a₁, a₂) ∈ ℝ⁶:

b₁ = normalize(a₁)
b₂ = normalize(a₂ - (a₂·b₁)b₁)     # Gram-Schmidt step
b₃ = b₁ × b₂                         # cross product

R = [b₁ | b₂ | b₃]
```

**Why this is continuous:** The mapping f: ℝ⁶ → SO(3) defined by (a₁, a₂) → R is continuous everywhere (the only degeneracy is when a₁ = 0 or a₂ is parallel to a₁, a set of measure zero). For any sequence xₙ → x in ℝ⁶, f(xₙ) → f(x) in SO(3) almost everywhere.

**Why n=6 is minimal for even dimensions:** The 5D constraint is tight — for ℝ⁴ (quaternions), the antipodality constraint (q ≡ -q) creates a 2:1 covering of SO(3), introducing a topological discontinuity. For ℝ⁶, the Gram-Schmidt map avoids this.

### The 9D Representation

**Encoding:** Use the full rotation matrix as a 9D vector.

**Decoding:** Project to SO(3) via polar decomposition (SVD):
```
M = U Σ Vᵀ  (SVD of M ∈ ℝ³ˣ³)
R = U diag(1, 1, det(UVᵀ)) Vᵀ    (ensures det = +1)
```

The 9D representation is over-parameterized (6 constraints: Rᵀ R = I, det R = 1) but fully continuous and differentiable. Useful when you want direct matrix supervision but is redundant — 6D is sufficient.

### Implications for rotation interpolation quality

For SLERP (quaternion) vs 6D-based interpolation:
- **SLERP** minimizes geodesic distance on S³, equivalent to minimizing geodesic distance on SO(3)
- **6D linear interpolation + renormalize:** NOT equivalent to SLERP, but for small angles (< 30°) the error is negligible (< 0.5°)
- For rigging applications with large rotations (shoulder, hip > 90°), SLERP via quaternion is still preferred for pure interpolation
- 6D is preferred as **input/output format** for differentiable systems — SLERP remains preferred for **pure interpolation**

### Application: RBF correctives with differentiable optimization

When fitting RBF kernel widths via gradient descent:
```python
import numpy as np

def rotation_to_6d(R):
    """Convert rotation matrix to 6D continuous representation."""
    return R[:, :2].flatten()  # first 2 columns, 6 values

def sixd_to_rotation(x):
    """Decode 6D representation to rotation matrix via Gram-Schmidt."""
    a1, a2 = x[:3], x[3:]
    b1 = a1 / np.linalg.norm(a1)
    b2 = a2 - np.dot(a2, b1) * b1
    b2 = b2 / np.linalg.norm(b2)
    b3 = np.cross(b1, b2)
    return np.column_stack([b1, b2, b3])

# For RBF training: use 6D as joint rotation features
# instead of euler angles, to avoid gradient discontinuities
def get_joint_6d_features(joint_name):
    import maya.api.OpenMaya as om
    import maya.cmds as cmds
    wm = cmds.getAttr(joint_name + '.worldMatrix[0]')
    R = np.array(wm).reshape(4, 4)[:3, :3]
    return rotation_to_6d(R)  # 6 continuous values
```

## Implementación en Maya

For traditional rigging (no ML), keep using:
- `decomposeMatrix → outputRotate` (Euler XYZ) for animator-readable rotations
- `quatNormalize → quatToEuler` for gimbal-safe extraction

For differentiable/ML contexts (RBF optimization, neural correctives, SSDR fitting):
```python
# Maya API → 6D representation for ML input
import maya.api.OpenMaya as om

def joint_worldmatrix_to_6d(joint_name):
    sel = om.MSelectionList()
    sel.add(joint_name)
    dag = sel.getDagPath(0)
    mat = dag.inclusiveMatrix()
    # Extract upper 3x3 rotation block
    R = [[mat[i*4+j] for j in range(3)] for i in range(3)]
    # First 2 columns = 6D representation
    col0 = [R[0][0], R[1][0], R[2][0]]
    col1 = [R[0][1], R[1][1], R[2][1]]
    return col0 + col1  # 6 floats, continuous
```

**When NOT to use 6D:** In Maya's DG graph with native nodes, there is no 6D node. For pure node-graph rigging (multMatrix, decomposeMatrix), continue using quatNormalize/quatToEuler. 6D is only relevant when interfacing with Python optimization or ML inference.

## Comparación con autorig_tools

El stack actual de autorig_tools usa `decomposeMatrix → outputRotate` (Euler) y `quatToEuler` para extracción de rotaciones — correcto para rigging interactivo y GPU-compatible. La representación 6D es relevante para autorig_tools únicamente en los componentes diferenciables: el optimizador de RBF (si usa gradient descent para ajustar kernels), cualquier integración futura con UniRig/SkinTokens, y si se implementa un neural corrective system. La mayor aplicación inmediata es como formato de input features cuando se entrena un modelo de correctives con datos de producción.

## Aplicable directamente

PARTIAL — En el pipeline Maya estándar, no hay nada que cambiar. En el sistema RBF de autorig_tools, si el optimizador de kernel widths usa gradient descent (scipy.optimize con jacobian), reemplazar los Euler angles de entrada por 6D features mejora convergencia en poses con rotaciones > 90°. Implementación: `rotation_to_6d()` wrapper de 3 líneas aplicable inmediatamente. Impacto: evita discontinuidades en el fitting de correctives para hombros y caderas.

## Fuente
- Paper comprensivo 2025: https://arxiv.org/abs/2605.08086 (Aiersilan, Liu, Hahn)
- Paper original 6D: https://arxiv.org/abs/1812.07035 (Zhou, Barnes, Lu, Yang, Li, CVPR 2019)
- Paper gimbal lock y quaterniones docencia: https://arxiv.org/abs/2511.04452
