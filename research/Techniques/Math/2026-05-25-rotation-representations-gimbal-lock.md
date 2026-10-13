---
source: https://www.compu-tools.com/blog/2026-03-07-gimbal-lock/ | https://arxiv.org/html/2511.04452v1 | https://thenumb.at/Exponential-Rotations/
found: 2026-05-25
category: math
priority: 1
tags: [maya, python, rigging, math, euler, quaternion, axis-angle, exponential-map, gimbal-lock, rotation]
status: NEW
---

# Rotation Representations: Euler vs Quaternion vs Axis-Angle vs Exponential Map — Gimbal Lock & Maya Implications

## Descripción
Hay cuatro maneras principales de representar rotaciones 3D: ángulos de Euler, cuaterniones, eje-ángulo y mapa exponencial. Cada una tiene singularidades, coste computacional y propiedades de interpolación diferentes. En rigging, la elección incorrecta causa gimbal lock en controles FK, flipping de joints en IK/FK matching, y artefactos en el blending de poses. Este documento formaliza las cuatro representaciones y su impacto directo en el flujo de trabajo de Maya.

## Fundamento matemático / técnico

### 1. Euler Angles — The Standard (and its Failure)

A 3D rotation is decomposed into three sequential single-axis rotations. Maya uses ZXY by default for joints, XYZ for transforms (configurable per object).

**Gimbal lock condition:**
In XYZ order, gimbal lock occurs when the middle rotation (Y) reaches ±90°:
```
R_XYZ = Rz(α) · Ry(β) · Rx(γ)

At β = 90°:
Rz(α) · Ry(90°) · Rx(γ) = Rz(α - γ) · Ry(90°)
```
The Z and X axes align → only 2 DOF remain instead of 3. Any value of α and γ that satisfies α - γ = constant produces the same rotation. This is not a "mechanical" problem — it is a mathematical singularity in the parameterization. No change of rotation order eliminates it for all poses; it merely moves where it occurs.

**Storage:** 3 floats. **Singularities:** yes (1 per rotation order). **Interpolation:** linear interpolation of Euler angles produces non-constant-velocity, non-arc paths. Best avoided for animation.

**In Maya:** `joint.rotateOrder` — choose ZXY for biped limbs to push singularity to extreme hyperextension poses.

---

### 2. Axis-Angle — Geometric Clarity

A rotation of angle θ about unit axis n̂ = (nx, ny, nz):
```
R(n̂, θ) — any rotation representable this way
Storage: (nx, ny, nz, θ) = 4 floats

Singularity at θ = 0: axis is undefined (identity rotation)
Singularity at θ = 2π: same as θ = 0
```

Not directly interpolatable (composition is non-trivial). Used as an intermediate form; convert to/from quaternion for blending.

**Rodrigues' rotation formula:**
```
v' = v·cos(θ) + (n̂ × v)·sin(θ) + n̂(n̂·v)(1 - cos(θ))
```

---

### 3. Quaternion — The Production Standard

Unit quaternion: q = w + xi + yj + zk, with |q| = 1.
Represents rotation of angle θ about axis n̂:
```
q = (cos(θ/2), sin(θ/2)·nx, sin(θ/2)·ny, sin(θ/2)·nz)
```

**Key properties:**
- **No gimbal lock** — all orientations representable without singularities
- **Double cover:** q and -q represent the same rotation. This causes the antipodality problem: SLERP between q and -q takes the long arc (>180°). Must check `dot(q1, q2) < 0` and negate q2 if so.
- **Composition:** q_total = q2 * q1 (quaternion multiplication, non-commutative)
- **Storage:** 4 floats with 1 constraint (|q|=1)

**SLERP formula** (key for animation blending):
```
SLERP(q1, q2, t) = q1 · sin((1-t)Ω)/sin(Ω) + q2 · sin(tΩ)/sin(Ω)
where Ω = arccos(q1 · q2)
```
For Ω ≈ 0 (nearly identical rotations), use NLERP instead to avoid division by zero:
```
NLERP(q1, q2, t) = normalize(lerp(q1, q2, t))
```

**Rotation application:**
```
v' = q * (0, v) * q⁻¹  [where (0,v) is a pure quaternion]
```

---

### 4. Exponential Map — The Lie Algebra Approach

The exponential map represents rotation as a 3-vector r = θ·n̂ (axis scaled by angle):
```
r ∈ ℝ³, |r| = θ (rotation angle), r/|r| = n̂ (axis)
Identity = (0,0,0)
```

Convert to quaternion:
```
q = (cos(|r|/2), sin(|r|/2) · r/|r|)
```
Convert from quaternion:
```
θ = 2·arccos(w); n̂ = (x,y,z)/sin(θ/2)
r = θ · n̂
```

**Key property:** The exponential map lives in the Lie algebra so(3) — the tangent space of SO(3) at the identity. This means:
- Interpolation in r-space is geometrically natural (straight line = constant angular velocity arc)
- Differentiation (for IK Jacobians) is straightforward
- **Singularity at θ = 2π**, but in practice poses never reach this

Used in: IK Jacobian computation (angular velocity space), pose blending for correctives, log-space quaternion averaging.

---

### Comparison Table

| Property | Euler | Axis-Angle | Quaternion | Exp Map |
|----------|-------|-----------|-----------|---------|
| Storage | 3 floats | 4 floats | 4 floats | 3 floats |
| Gimbal lock | YES | NO | NO | NO |
| Singularities | at ±90° middle | at θ=0, 2π | at identity (none for unit) | at θ=2π |
| Interpolation quality | Poor (shortest path not guaranteed) | Moderate | Excellent (SLERP) | Excellent |
| Composition | Slow (matrix multiply) | Moderate | Fast (quat mult) | Complex |
| Maya native | YES (default) | Partial | YES (quatToEuler node) | NO |
| Human intuition | HIGH | Moderate | LOW | LOW |

---

### Maya-Specific Implications for Rigging

**Rotation order strategy for FK controls:**
```
Spine/torso controls: YXZ — primary Y (twist) pushed to last, singularity at extreme X
Arm/leg: ZXY — primary Z (flex) first, singularity at extreme Y (hyperextension)
Foot roll: XYZ — match to animation intent
```

**Quaternion extraction without gimbal in Maya DG:**
```
decomposeMatrix.outputQuatX/Y/Z/W → quatToEuler → rotation values without gimbal
```
This pipeline avoids Euler singularities for twist extraction and IK/FK matching.

**Avoid animating joint.rotate directly for non-trivial rotations.** Drive worldMatrix decomposition via quatNormalize → quatToEuler instead.

**Checking for quaternion flip in Python:**
```python
import maya.api.OpenMaya as om

def get_quaternion(node_name):
    sel = om.MSelectionList()
    sel.add(node_name)
    dag = sel.getDagPath(0)
    fn = om.MFnTransform(dag)
    return fn.rotation(om.MSpace.kWorld, asQuaternion=True)

def safe_slerp(q1, q2, t):
    """SLERP with antipodality check."""
    # Antipodality check
    if q1.x*q2.x + q1.y*q2.y + q1.z*q2.z + q1.w*q2.w < 0:
        q2 = om.MQuaternion(-q2.x, -q2.y, -q2.z, -q2.w)
    return om.MQuaternion.slerp(q1, q2, t)
```

## Implementación en Maya

**Practical node setup to avoid gimbal on FK chains:**
```
# Instead of reading joint.rotate (euler):
# joint.worldMatrix[0] → decomposeMatrix.outputQuatX/Y/Z/W → quatToEuler.inputQuatX/Y/Z/W
# Result: rotation values that don't flip/gimbal regardless of pose

import maya.cmds as cmds

def build_gimbal_safe_rotation_reader(joint):
    """Reads joint rotation via quaternion path, avoids gimbal lock."""
    dcmp = cmds.createNode('decomposeMatrix', name=f'{joint}_dcmpMatrix')
    qte  = cmds.createNode('quatToEuler',     name=f'{joint}_quatToEuler')
    
    cmds.connectAttr(f'{joint}.worldMatrix[0]', f'{dcmp}.inputMatrix')
    cmds.connectAttr(f'{dcmp}.outputQuatX', f'{qte}.inputQuatX')
    cmds.connectAttr(f'{dcmp}.outputQuatY', f'{qte}.inputQuatY')
    cmds.connectAttr(f'{dcmp}.outputQuatZ', f'{qte}.inputQuatZ')
    cmds.connectAttr(f'{dcmp}.outputQuatW', f'{qte}.inputQuatW')
    
    # qte.outputRotateX/Y/Z now gives gimbal-free euler values
    return qte
```

**For IK/FK matching across spaces:**
```python
def match_fk_to_ik(fk_joint, ik_joint):
    """Quaternion-based FK→IK match that doesn't flip."""
    sel = om.MSelectionList()
    sel.add(ik_joint)
    dag = sel.getDagPath(0)
    fn = om.MFnTransform(dag)
    q_world = fn.rotation(om.MSpace.kWorld, asQuaternion=True)
    
    # Apply to FK joint in its parent space
    sel2 = om.MSelectionList(); sel2.add(fk_joint)
    dag2 = sel2.getDagPath(0)
    fn2 = om.MFnTransform(dag2)
    
    parent_q = fn2.rotation(om.MSpace.kWorld, asQuaternion=True)
    # Convert world quat to local: q_local = parent_q.inverse() * q_world
    q_local = parent_q.inverse() * q_world
    fn2.setRotation(q_local, om.MSpace.kTransform)
```

## Comparación con autorig_tools

autorig_tools usa ángulos de Euler para los controles FK y el método local_mmx para preservar el espacio local. El gimbal lock es un problema latente en cualquier sistema basado en Euler: si un control de FK de brazo se acerca a ±90° en el eje medio de su rotateOrder, los canales colapsan. La solución no es siempre cambiar el rotateOrder — a veces es añadir el pipeline de lectura por cuaternión (decomposeMatrix → quatToEuler) para sistemas que necesitan leer la rotación de forma estable (IK/FK matching, drivers de correctivos, twist extraction). El mapa exponencial es relevante para la Jacobiana del IK solver analítico.

## Aplicable directamente

YES — **Tres usos directos en autorig_tools:**
1. **IK/FK matching**: usar quaternión para transferir orientación entre cadenas FK e IK sin flipping (reemplaza la comparación de euler.rotate con la multiplicación de cuaterniones inversos).
2. **Rotation order por defecto**: asegurarse de que todos los joints de brazo/pierna usen ZXY y los de columna YXZ en el build — reducir singularidades en poses de producción comunes.
3. **Driver seguro para correctivos RBF**: usar outputQuatX/W del decomposeMatrix como driver en lugar de rotate.X para evitar que el RBF reciba valores con discontinuidades de gimbal.

## Fuente
- https://www.compu-tools.com/blog/2026-03-07-gimbal-lock/
- https://arxiv.org/html/2511.04452v1 — A Quaternionic Approach to Teaching 3D Rotations
- https://thenumb.at/Exponential-Rotations/ — Exponentially Better Rotations
- https://www.cs.cmu.edu/~spiff/moedit99/expmap.pdf — Practical Parameterization of Rotations Using the Exponential Map (CMU)
- https://saeed1262.github.io/blog/2024/quaternion/ — Quaternions, SO(3), and Gimbal Lock (Interactive)
