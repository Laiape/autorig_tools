---
source: https://www.cs.cmu.edu/~spiff/moedit99/expmap.pdf
found: 2026-10-12
category: math
priority: 1
tags: [maya, python, rigging, math, rotation, quaternion, euler, exponential-map, gimbal-lock]
status: NEW
---

# Exponential Maps & Rotation Representations: Euler, Quaternion, Axis-Angle, Exp Map

## Descripción
Grassia (1998) "Practical Parameterization of Rotations Using the Exponential Map" es el paper definitivo sobre representaciones de rotación para animación y rigging. Compara Euler angles, quaterniones, axis-angle y exponential maps en términos de singularidades, interpolación y viabilidad para optimizadores IK. La conclusión práctica: los exponential maps son la mejor representación paramétrica para ball-and-socket joints (hombro, cadera).

## Fundamento matemático / técnico

### The Four Representations

**Euler angles (ZYX / XYZ / etc):**
- 3 DOF, minimal representation
- Gimbal lock: when the middle angle = ±90°, the first and third axes align → loss of one DOF
- Not a Lie group morphism: interpolation is non-linear, angular velocity discontinuities
- Maya default: `jointOrient` + `rotate` in XYZ order

**Quaternions q = (w, x, y, z), ||q|| = 1:**
- 4 components, 1 constraint (unit norm) → effectively 3 DOF
- No gimbal lock, smooth interpolation via SLERP
- Double cover of SO(3): q and -q represent the same rotation → antipodality problem
- SLERP: `SLERP(q1, q2, t) = q1 * (q1^-1 * q2)^t`
- Not closed under addition, cannot be directly averaged → use log-mean

**Axis-angle (n̂, θ) where ||n̂|| = 1:**
- Singularity at θ = 0 (axis undefined) and θ = ±π (same issue as antipodality)
- Not useful directly for optimization

**Exponential map v ∈ ℝ³:**
- Encode axis-angle as a single 3-vector: `v = θ * n̂`
- `||v|| = θ` (rotation magnitude), direction = rotation axis
- Map to rotation matrix: `R = exp(v) = I + sin(θ)/θ * [v]× + (1-cos(θ))/θ² * [v]×²`
  where [v]× is the skew-symmetric cross-product matrix
- Inverse (log map): `v = log(R) = θ/(2sin(θ)) * (R - R^T)`, θ = arccos((trace(R)-1)/2)
- Singularity only at θ = ±π (not θ = 0 → use limit: `exp(0) = I`, safe)
- **Dynamic reparameterization trick (Grassia):** When ||v|| approaches π, remap: choose the equivalent rotation with ||v'|| < π to avoid the singularity branch cut. This keeps the map continuous for optimization.

### Why This Matters for IK / RBF Optimizers
- IK with Jacobian: derivative dR/dv is well-defined everywhere except θ=π (vs. Euler where it breaks at θ=90°)
- Exponential map provides a local chart on SO(3): small perturbations in v produce small rotations
- In RBF corrective systems: using exp maps as driver inputs avoids the non-linearity of Euler interpolation — drivers sampled in exp-map space distribute more uniformly on SO(3)

### Log-Mean for N Rotations (the right way to blend)
Instead of averaging quaternions (linear, approximate):
```
v_i = log(q_ref^-1 * q_i)    # bring to tangent space at q_ref
mean_v = Σ w_i * v_i           # linear blend in ℝ³
mean_q = q_ref * exp(mean_v)   # back to SO(3)
```
Error of naive quaternion average: O(θ²) — up to 5-10° at large angles (shoulders/hips at 90°+).

### Nintendo R&D (2023): Working With Rotations
A comprehensive practical guide (Poncet, Nintendo NERD) covers the same taxonomy:
- For FK chains: quaternions with shortest-path SLERP
- For IK optimization: exponential maps
- For interpolation curves: log-Euclidean or SQUAD

## Implementación en Maya

```python
import maya.api.OpenMaya as om
import numpy as np

def rotation_to_expmap(matrix_fn):
    """Extract exponential map from MMatrix (rotation part only)."""
    q = om.MTransformationMatrix(matrix_fn).rotation()
    # Convert to axis-angle
    axis, angle = q.asAxisAngle()  # angle in radians
    # Exponential map vector
    return om.MVector(axis.x * angle, axis.y * angle, axis.z * angle)

def expmap_to_quaternion(v):
    """v is MVector, ||v|| = rotation angle in radians."""
    angle = v.length()
    if angle < 1e-8:
        return om.MQuaternion()  # identity
    axis = v.normal()
    return om.MQuaternion(angle, axis)

# RBF driver: use exp-map distance instead of Euler distance
def expmap_distance(q1, q2):
    """Geodesic distance on SO(3) — correct for RBF kernels."""
    q_rel = q1.inverse() * q2
    axis, angle = q_rel.asAxisAngle()
    return abs(angle)  # geodesic distance in [0, π]
```

**In the DG (no Python):**
Maya has no native exp-map node, but:
- `decomposeMatrix` → `outputQuatX/Y/Z/W` gives quaternion
- `quatNormalize` ensures unit quaternion
- `quatToEuler` for final joint drives (with a known safe decomposition order)
- For twist isolation: zero out two axes of quaternion before converting (swing-twist pattern)

## Comparación con autorig_tools
Los RBF correctives de autorig_tools probablemente usan rotaciones Euler del joint como drivers de entrada. Esto es matemáticamente incorrecto para joints con gran rango de movimiento (hombro, cadera): la distancia Euclidiana en espacio Euler no es la distancia geodésica en SO(3). Reemplazar los drivers de RBF con exponential maps/log-map distance corregirá la interpolación espuria que aparece cuando el animador cruza la singularidad de 90°.

## Aplicable directamente
PARTIAL — La matemática de exponential map no tiene nodo nativo en Maya, pero:
1. En el sistema RBF Python de autorig_tools: reemplazar `driver.rotateX/Y/Z` por distancia geodésica calculada con `om.MQuaternion` como kernel de distancia. Impacto: mejor interpolación de correctives en hombros y caderas a poses extremas.
2. Para el IK Jacobiano: cambiar la representación de estado de Euler a exp-map reduce singularidades durante la optimización (2-4h de implementación).
3. Inmediato: documentar el `expmap_distance()` como util en `autorig_tools/utils/math_utils.py` para usarlo en los próximos RBF builds.

## Fuente
- Grassia, F.S. (1998). "Practical Parameterization of Rotations Using the Exponential Map." Journal of Graphics Tools, 3(3), 29–48. https://www.cs.cmu.edu/~spiff/moedit99/expmap.pdf
- Nintendo NERD (2023). "Working With Rotations." https://www.nerd.nintendo.com/files/Working%20With%20Rotations%2020230428.pdf
- Tandfonline DOI: https://www.tandfonline.com/doi/abs/10.1080/10867651.1998.10487493
