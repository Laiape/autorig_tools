---
source: https://bindpose.com/maya-matrix-nodes-part-2-node-based-matrix-twist-calculator/ | https://www.chadvernon.com/blog/swing-twist/ | https://lesterbanks.com/2017/07/maya-native-matrix-nodes-constraints/
found: 2026-08-17
category: math
priority: 1
tags: [maya, rigging, matrix, twist, swing-twist, decomposeMatrix, quatToEuler, forearm]
status: NEW
---

# Matrix Twist Extraction en Maya — Swing-Twist Decomposition sin Gimbal Lock

## Descripción
Extraer el ángulo de twist de un joint (p.ej. forearm roll) directamente desde matrices es el problema central del sistema de twist joints en rigs de producción. La solución naive — usar `decomposeMatrix.outputRotateX` — es frágil ante cambios de orden de rotación y sufre gimbal lock. La solución correcta es la descomposición swing-twist: separar la rotación total en un componente swing (perpendicular al eje de twist) y un componente twist (alrededor del eje de twist), extraído directamente desde el quaternión de rotación.

## Fundamento matemático / técnico

### Swing-Twist Decomposition
Given a rotation quaternion **q** and a twist axis **a** (unit vector), decompose q into:
- **q_twist**: rotation around axis a
- **q_swing**: rotation perpendicular to a (q = q_swing * q_twist)

**Algorithm:**
```
q = (x, y, z, w)  # rotation quaternion
a = (ax, ay, az)  # twist axis (normalized), e.g. (1, 0, 0) for X

# Project quaternion onto twist axis
proj = dot((x, y, z), a)  # = ax*x + ay*y + az*z

# Twist component quaternion (rotation around a)
q_t_xyz = proj * a   # = (proj*ax, proj*ay, proj*az)
q_twist = normalize(MQuaternion(q_t_xyz.x, q_t_xyz.y, q_t_xyz.z, w))

# Swing component (remove twist from total rotation)
q_swing = q * q_twist.inverse()

# Extract twist angle
twist_angle = 2 * atan2(|q_twist.xyz|, q_twist.w)
# = 2 * atan2(proj, w)  (when a = X axis: proj = q.x)
```

For X-axis twist specifically:
```
twist_angle = 2 * atan2(q.x, q.w)   # exact, no gimbal lock, no euler order issues
```

### Why Euler Extraction Fails
`decomposeMatrix.outputRotateX` computes Euler angles in the node's rotation order (XYZ by default). At ~90° bend (shoulder, knee), the Euler representation passes near singularity — other axes "steal" rotation from the twist axis, producing jump artifacts. Swing-twist decomposition works in SO(3) directly and never has this issue.

### Relative Matrix for Twist Between Two Objects
To get the twist of bone B relative to bone A (both oriented along the same axis):
```
M_rel = M_A_inv * M_B       # B in A's local space
q_rel = quaternion(M_rel)   # extract quaternion from relative matrix
twist = swing_twist_decompose(q_rel, twist_axis)
```
In Maya node network:
```
inverseMatrix(A.worldMatrix) → multMatrix → decomposeMatrix → quatToEuler
```

## Implementación en Maya

### Node Network (pure DG, no scripting required)
```
# Goal: extract forearm twist from wrist relative to elbow

[elbow_joint.worldMatrix]
         │
         ▼
[inverseMatrix]──────────────────────┐
                                     │
[wrist_joint.worldMatrix]            │
         │                           │
         ▼                           ▼
              [multMatrix] → [decomposeMatrix]
                                     │
                          .outputQuatX, .outputQuatW
                                     │
                                     ▼
                    2 * atan2(quatX, quatW) = twist angle
```

Maya node breakdown:
1. `inverseMatrix` on the reference bone (elbow)
2. `multMatrix`: [wrist.worldMatrix, inverseMatrix_output] → relative transform
3. `decomposeMatrix`: extract quaternion components (outputQuatX, outputQuatW)
4. Use `quatToEuler` or manual `2*atan2(quatX, quatW)` via expression/animCurve

### Maya's Built-in: poseInterpolator for Swing-Twist
Maya's `poseInterpolator` node has a built-in "twist" and "swing" output mode that does exactly this decomposition. Connect joint.worldMatrix → poseInterpolator with twist axis set → drive roll joints from `outputTwist`.

### Python Implementation (om2)
```python
import maya.api.OpenMaya as om2
import math

def extract_twist(matrix_a, matrix_b, twist_axis=om2.MVector(1, 0, 0)):
    """Extract twist angle of B relative to A around twist_axis."""
    # Get relative matrix
    inv_a = matrix_a.inverse()
    m_rel = inv_a * matrix_b  # Note: MMatrix multiplication order
    
    # Extract quaternion from relative matrix
    tfm = om2.MTransformationMatrix(m_rel)
    q = tfm.rotation(asQuaternion=True)
    
    # Project onto twist axis for swing-twist decomposition
    ax, ay, az = twist_axis.x, twist_axis.y, twist_axis.z
    proj = ax * q.x + ay * q.y + az * q.z
    
    # Twist quaternion (component around twist_axis)
    # For X axis: just use q.x and q.w
    twist_angle = 2.0 * math.atan2(proj, q.w)
    return math.degrees(twist_angle)

def get_joint_world_matrix(joint_name):
    sel = om2.MSelectionList()
    sel.add(joint_name)
    dag = sel.getDagPath(0)
    fn = om2.MFnTransform(dag)
    return fn.transformation().asMatrix()

# Usage:
m_elbow = get_joint_world_matrix('elbow_L_jnt')
m_wrist = get_joint_world_matrix('wrist_L_jnt')
twist = extract_twist(m_elbow, m_wrist)
print(f'Forearm twist: {twist:.2f}°')
```

### Driving Twist Roll Joints
```python
def build_twist_joints(start_joint, end_joint, num_rolls=3, twist_axis='x'):
    """Create roll joints driven by matrix twist extraction."""
    # Build: start → [roll_00, roll_01, roll_02] → end
    # Each roll joint gets: twist_total * (i / num_rolls) degrees
    # Connection: decomposeMatrix.outputQuatX → multiplyDivide → joint.rotateX
    pass
```

### worldUpMatrix Pattern as aimConstraint Replacement
Twist extraction naturally pairs with aim matrix construction:
```
# Build an aim matrix without aimConstraint:
# 1. Compute aim vector: v_aim = normalize(target_pos - source_pos)
# 2. Compute up vector from worldUpMatrix
# 3. Cross product: v_side = cross(v_aim, v_up)
# 4. Re-cross: v_up_corrected = cross(v_side, v_aim)
# Assemble 4×4 matrix from these 3 vectors + position
# Connect to offsetParentMatrix — no constraint node, fully parallel-safe
```
Node implementation: `aimMatrix` node (Maya 2020+) does this directly with `primaryTargetVector`, `secondaryTargetVector` inputs.

## Comparación con autorig_tools

El patrón `local_mmx` de autorig_tools ya usa matrices para los transforms. La extracción de twist es el siguiente paso lógico para el sistema de twist joints (forearm, upper arm, thigh, calf). Si actualmente autorig_tools usa `jointOrient` o `decomposeMatrix.outputRotateX` directo para los roll joints, migrar a swing-twist decomposition via quaternión eliminaría cualquier flip o inestabilidad a >45° de rotación. El `poseInterpolator` nativo de Maya es la opción más rápida de implementar sin Python custom.

## Aplicable directamente

YES — Directamente aplicable en el builder de twist joints de autorig_tools:
1. Reemplazar `decomposeMatrix.outputRotateX → roll_joint.rotateX` por el patrón swing-twist via quaternión (≤30 min por zona)
2. Para forearm roll: `inverseMatrix(elbow) → multMatrix(wrist) → decomposeMatrix.outputQuatX/W → 2*atan2 → roll_joints`
3. Función Python `extract_twist()` lista para usar como validator/debugger del rig

## Fuente
- bindpose.com tutorial: https://bindpose.com/maya-matrix-nodes-part-2-node-based-matrix-twist-calculator/
- Chad Vernon swing-twist decomposition: https://www.chadvernon.com/blog/swing-twist/
- Matrix nodes overview: https://lesterbanks.com/2017/07/maya-native-matrix-nodes-constraints/
- YouTube tutorial (matrix + quaternion twist): https://www.youtube.com/watch?v=Em0eMN4NBBY
