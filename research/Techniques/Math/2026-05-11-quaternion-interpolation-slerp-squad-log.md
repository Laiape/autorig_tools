---
source: https://web.mit.edu/2.998/www/QuaternionReport1.pdf
found: 2026-05-11
category: math
priority: 1
tags: [maya, rigging, math, quaternion, slerp, squad, log-quaternion, rotation, gimbal-lock]
status: NEW
---

# Quaternion Interpolation — SLERP, SQUAD y Log-Quaternion Blending

## Descripción
La interpolación de rotaciones es crítica en rigging para IK/FK blending, space switching, correctives RBF, y cualquier sistema que mezcle orientaciones. Los ángulos de Euler tienen gimbal lock y producen interpolaciones no-uniformes. Los cuaterniones permiten SLERP (interpolación esférica suave entre 2 rotaciones), SQUAD (spline de rotaciones para N keyframes), y log-quaternion blending (promedio ponderado de N rotaciones). Este documento cubre la matemática de los tres métodos.

## Fundamento matemático / técnico

### Quaternion Basics
A quaternion `q = w + xi + yj + zk` represents rotation by angle θ around axis n̂:
```
q = cos(θ/2) + sin(θ/2) · (nx·i + ny·j + nz·k)
```
Unit constraint: `w² + x² + y² + z² = 1`. Double cover: q and -q represent the same rotation (the quaternion sphere S³ double-covers rotation space SO(3)).

### SLERP — Spherical Linear Interpolation
Interpolates along the great circle arc between q₀ and q₁ on S³:
```
SLERP(q₀, q₁, t) = sin((1-t)Ω)/sin(Ω) · q₀ + sin(tΩ)/sin(Ω) · q₁
```
where `Ω = arccos(q₀ · q₁)` (quaternion dot product).

**Properties:**
- Constant angular velocity (uniform speed)
- Geodesic path on S³ (shortest arc)
- C¹ continuous

**Anti-podality:** If `q₀ · q₁ < 0`, negate q₁ (take short arc). Without this check, SLERP takes the long way around.

**Near-zero Ω degeneracy:** When q₀ ≈ q₁ (Ω → 0), sin(Ω) → 0 and the formula is undefined. Solution: fall back to normalized LERP when `dot > 0.9995`:
```python
def slerp(q0, q1, t):
    dot = np.dot(q0, q1)
    if dot < 0:            # anti-podality
        q1, dot = -q1, -dot
    if dot > 0.9995:       # nearly identical — use NLERP
        return normalize(q0 + t*(q1 - q0))
    omega = np.arccos(np.clip(dot, -1, 1))
    return (np.sin((1-t)*omega)*q0 + np.sin(t*omega)*q1) / np.sin(omega)
```

### SQUAD — Spherical Quadratic Interpolation
Extends SLERP to produce smooth C¹ curves through a sequence of quaternion keyframes (analogous to cubic Catmull-Rom for positions). Given sequence ..., q_{i-1}, qᵢ, q_{i+1}, q_{i+2}, ...:

**Step 1 — Compute intermediate control points (Shoemake):**
```
sᵢ = qᵢ · exp( -(log(qᵢ⁻¹ · q_{i+1}) + log(qᵢ⁻¹ · q_{i-1})) / 4 )
```

**Step 2 — Evaluate SQUAD (de Casteljau on S³):**
```
SQUAD(qᵢ, q_{i+1}, sᵢ, s_{i+1}, t) = SLERP(
    SLERP(qᵢ,  q_{i+1}, t),
    SLERP(sᵢ,  s_{i+1}, t),
    2t(1-t)
)
```
The `2t(1-t)` factor creates the tangent blending that ensures smoothness at keyframes.

SQUAD is C¹ at keyframes (no kinks) vs piecewise SLERP which is only C⁰ (kinks at keyframe boundaries). Used in animation curves for quaternion joints.

### Log-Quaternion Blending (Averaging N Rotations)
For N > 2 rotations with weights wᵢ (where Σwᵢ = 1), SLERP cannot generalize. Log-space blending converts to a linear space, averages there, then maps back:

```
q_avg = exp( Σᵢ wᵢ · log(qᵢ) )
```

**Quaternion logarithm** (maps from S³ to tangent space at identity):
```
log(q) = log(w + v) = (0, arccos(w) · v̂)    where v̂ = v/|v|, result is a "pure quaternion"
```
If |v| ≈ 0 (near-identity), use Taylor expansion: log(q) ≈ (0, v).

**Quaternion exponential** (inverse map):
```
exp(0, θn̂) = (cos θ, sin θ · n̂)
```

**Why it works:** The logarithm maps S³ to its tangent plane at the origin (a linear space). Weighted averages in this linear space correspond to valid rotation interpolations when mapped back via exp.

**Practical use in rigging:** RBF corrective systems that use joint angles as drivers should use log-quaternion distances (not Euler angle differences) for physically correct interpolation. Avoids spurious interactions between Euler axes.

### Rotation Representation Comparison
| Representation | Gimbal Lock | Interpolation | DOF | Notes |
|---------------|-------------|---------------|-----|-------|
| Euler angles | YES | Non-uniform, order-dep. | 3 | Maya default |
| Axis-angle | No | Can't interpolate directly | 4 | Use via exp/log |
| Quaternion | No | SLERP: excellent | 4 | 4th dim = redundant |
| Rotation matrix | No | LERP invalid (not SO(3)) | 9 | Polar decomp to fix |
| Exponential map | No | Log-space: excellent | 3 | Minimal, no redundancy |

## Implementación en Maya

**API (Python):**
```python
import maya.api.OpenMaya as om

# Get quaternion from joint
def joint_quaternion(joint):
    sel = om.MSelectionList(); sel.add(joint)
    fn = om.MFnTransform(sel.getDagPath(0))
    return fn.rotation(om.MSpace.kWorld, asQuaternion=True)

# SLERP via API
q0 = joint_quaternion('shoulder_jnt')
q1 = joint_quaternion('target_jnt')
q_mid = om.MQuaternion.slerp(q0, q1, 0.5)

# Convert back to Euler for setting on joint
euler = q_mid.asEulerRotation()
cmds.setAttr('ctrl.rotate', 
    math.degrees(euler.x), math.degrees(euler.y), math.degrees(euler.z))
```

**Node-graph SLERP (DG):** No native SLERP node in Maya. Can approximate with:
- `quatAdd` + `quatNormalize` (NLERP, not true SLERP — less accurate but fast)
- `quatToEuler` after decomposeMatrix for extraction (not blending)

For true blending at build time (not runtime), use Python API; at runtime, use a custom MPxNode.

## Comparación con autorig_tools

El IK/FK blend de autorig_tools mezcla rotaciones via constraints o mediante blend de matrices. Si hay flipping en poses extremas, reemplazar la interpolación por SLERP en Python eliminaría el problema. Para el sistema RBF, calcular distancias de pose en log-quaternion space en lugar de distancias euclidianas de ángulos de Euler daría interpolaciones más físicamente correctas, especialmente para hombro y cadera.

## Aplicable directamente
PARTIAL — En el IK/FK matching, verificar si el blend de rotaciones pasa por gimbal en poses extremas y reemplazar con `om.MQuaternion.slerp`. Para RBF correctives, evaluar si el kernel gaussiano usa distancias Euler o quaternion. Bajo coste de cambio, impacto en estabilidad de correctives en poses extremas.

## Fuente
- MIT Quaternion Report: https://web.mit.edu/2.998/www/QuaternionReport1.pdf
- MDPI Log-Quaternion Methods: https://www.mdpi.com/2227-7390/11/5/1131
- EuclideanSpace SLERP: https://www.euclideanspace.com/maths/algebra/realNormedAlgebra/quaternions/slerp/index.htm
- Gabor Makes Games: https://gabormakesgames.com/blog_quats_interpolate.html
