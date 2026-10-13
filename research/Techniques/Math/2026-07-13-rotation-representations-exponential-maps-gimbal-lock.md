---
source: https://www.cs.cmu.edu/~spiff/moedit99/expmap.pdf | https://arxiv.org/pdf/2511.04452 | https://www.nerd.nintendo.com/files/Working%20With%20Rotations%2020230428.pdf
found: 2026-07-13
category: math
priority: 1
tags: [maya, python, rigging, math, rotation, euler, quaternion, axis-angle, exponential-map, gimbal-lock, interpolation]
status: NEW
---

# Rotation Representations — Euler, Quaternion, Axis-Angle, Exponential Map y Gimbal Lock

## Descripción
Cada representación de rotación 3D tiene propiedades diferentes en términos de singularidades, interpolación y coste computacional. El gimbal lock no es un problema de hardware: es una singularidad matemática intrínseca a los ángulos de Euler que aparece siempre que se usan rotaciones secuenciales por eje. Este archivo cubre las cinco representaciones principales, la matemática del gimbal lock, y por qué los mapas exponenciales son la representación óptima para drivers de IK, RBF correctives y optimización de poses.

## Fundamento matemático / técnico

### 1. Euler Angles (ZYX, XYZ, etc.)

A rotation is decomposed into three sequential rotations around cardinal axes:
```
R = Rz(psi) * Ry(theta) * Rx(phi)   [ZYX convention -- Maya's default for joints]
```

**Gimbal lock mechanism:**
When the middle axis rotation reaches +/-90 deg, the first and third axes become coplanar:
```
Rx(phi)*Ry(90)*Rz(psi) = Rx(phi)*[0,0,-1; 0,0,0; 1,0,0]*Rz(psi)
After reduction: only (phi+psi) is independent -- one DOF is lost.
```
This is a **coordinate singularity**, not a physical constraint. The rotation space SO(3) has no missing DOF -- it is the parameterization that collapses.

**Interpolation problem:**
LERP of Euler angles is not geometrically uniform. Interpolating (0,0,0) to (180,0,0) looks correct, but (90,90,0) to (90,90,90) produces a non-geodesic path due to axis-coupling.

### 2. Axis-Angle

A rotation by angle theta around unit vector n_hat:
```
R(theta, n_hat) = I*cos(theta) + sin(theta)*[n_hat]x + (1-cos(theta))*n_hat(x)n_hat
```
where `[n_hat]x` is the skew-symmetric cross-product matrix.

**Properties:**
- No gimbal lock
- Cannot be directly interpolated (non-linear combination)
- 4 parameters (theta, nx, ny, nz) with |n_hat|=1 constraint

**Relationship to exponential map:** The axis-angle (theta*n_hat) IS the exponential map parameter -- collapsed into one 3-vector.

### 3. Rotation Matrix (SO(3))

A 3x3 orthogonal matrix with det=1. 9 parameters, 6 constraints, 3 DOF.
```
R in SO(3): R^T * R = I, det(R) = 1
```
**LERP is INVALID:** The average of two rotation matrices is NOT a rotation matrix in general:
```
(R1 + R2)/2  -- NOT in SO(3) in general
Fix: SVD of M = U*Sigma*V^T, then R = U*V^T  (projection to SO(3))
```

**Use in rigging:** Maya's decomposeMatrix internally uses SVD to separate rotation from scale/shear in the 4x4 worldMatrix.

### 4. Quaternions (S^3)

Unit quaternion q = w + xi + yj + zk, |q|=1, representing rotation by theta around n_hat:
```
q = cos(theta/2) + sin(theta/2)*(nx*i + ny*j + nz*k)
```

**Double cover:** q and -q represent the SAME rotation. SLERP needs antipodality check:
```
if (q0 dot q1) < 0: q1 = -q1   (take short arc)
```

**No gimbal lock.** Interpolation via SLERP (covered in 2026-05-11-quaternion-interpolation-slerp-squad-log.md).

**Maya nodes:** quatToEuler, eulerToQuat, quatNormalize, quatProd, quatInvert. The decomposeMatrix node computes quaternion internally from the 3x3 rotation submatrix.

### 5. Exponential Map (Grassia 1998) -- The Minimal Representation

The exponential map parameterizes rotations with a **3-vector** v in R^3 where:
```
v = theta * n_hat    (axis-angle collapsed: direction=axis, magnitude=angle)
theta = |v|          (rotation angle)
n_hat = v/|v|        (rotation axis; undefined at v=0 -> identity)
```

**Mapping to rotation matrix (Rodrigues formula):**
```
R = exp([v]x) = I + sin(theta)/theta * [v]x + (1-cos(theta))/theta^2 * [v]x^2

Near theta->0: R ≈ I + [v]x  (first-order approximation, no singularity)
```

**Singularities of the exponential map:**
The exponential map has singularities ONLY at theta = 2*pi*k (k != 0), NOT at theta=0 or pi:
- At theta = 2*pi: exp(2*pi*n_hat) = I for any n_hat
- **Grassia's fix:** When theta crosses 2*pi during IK optimization, "unwrap" by subtracting 2*pi

This makes the exponential map superior to Euler angles for:
1. IK solving (smooth Jacobian near identity)
2. Pose optimization (gradient descent stays in a linear neighborhood)
3. RBF correctives (geodesically correct distance metric in pose space)

**Jacobian (local -> body frame):**
```
dR/dv_i is a closed-form 3x3 matrix, computable without trig
Near theta->0: dR/dv ≈ [e_i]x   (well-defined limit)
```

This is why Grassia (1998) specifically recommends exponential maps for ball-and-socket joint parameterization in IK systems.

### Rotation Representation Comparison Table

| Representation   | DOF | Gimbal Lock          | Interpolation          | Optimization         | Memory    |
|------------------|-----|----------------------|------------------------|----------------------|-----------|
| Euler ZYX        | 3   | YES (at theta_mid=90)| Non-geodesic, order-dep| Discontinuous Jac.   | 3 floats  |
| Axis-Angle       | 3+1 | No                   | Not direct             | Redundant param.     | 4 floats  |
| Quaternion       | 3   | No (double cover)    | SLERP: excellent       | Constrained (S^3)    | 4 floats  |
| Rotation Matrix  | 3   | No                   | LERP invalid           | Over-parameterized   | 9 floats  |
| Exponential Map  | 3   | No (singularity 2*pi)| Log-space: excellent   | Optimal (minimal)    | 3 floats  |

### Practical Gimbal Lock in Maya

Maya joints use **XYZ rotation order by default** for IK joints. The gimbal lock zone is rotateY = +/-90 deg. For a biped spine using XYZ order:
- rotateX = forward/back lean (primary motion)
- rotateY = +/-90 deg -> gimbal lock zone
- rotateZ = lateral tilt

**Solution 1: Change rotation order.** Put the primary motion axis first:
```
Spine:    ZXY  (primary: Z forward-bend, lock zone moved to X@90)
Shoulder: ZYX  (primary: Z abduction)
Elbow:    XZY  (primary: X flex/ext)
Hip:      ZXY
Knee:     XZY
```

**Solution 2: Use quaternion output path.**
The `decomposeMatrix -> quatToEuler` path avoids Euler storage -- the quaternion is intermediate, only the final Euler values go to the joint. But if those Euler values hit gimbal lock, the quaternion is already fine -- the lock is in the display/connection layer.

**Solution 3: Exponential map drivers for RBF correctives.**
Replace Euler angle inputs to RBF pose interpolators with exponential map vectors:
```python
def joint_as_expmap(joint_name):
    """Return joint local rotation as exponential map vector (3D)."""
    import maya.api.OpenMaya as om
    sel = om.MSelectionList()
    sel.add(joint_name)
    fn = om.MFnTransform(sel.getDagPath(0))
    q = fn.rotation(om.MSpace.kTransform, asQuaternion=True)
    angle, axis = q.asAxisAngle()
    return om.MVector(axis) * angle  # exponential map 3-vector

def expmap_geodesic_distance(v1, v2):
    """Geodesic distance between two exp map vectors -- for RBF kernel."""
    import maya.api.OpenMaya as om
    import math
    a1, a2 = v1.length(), v2.length()
    n1 = v1.normal() if a1 > 1e-6 else om.MVector(0, 1, 0)
    n2 = v2.normal() if a2 > 1e-6 else om.MVector(0, 1, 0)
    q1 = om.MQuaternion(a1, n1)
    q2 = om.MQuaternion(a2, n2)
    q_rel = q1.inverse() * q2
    angle, _ = q_rel.asAxisAngle()
    return abs(angle)  # geodesic distance in SO(3)
```

## Implementación en Maya

**Setting optimal rotation orders at rig build time:**
```python
import maya.cmds as cmds

ROTATION_ORDERS = {
    'spine':    'ZXY',
    'neck':     'ZXY',
    'shoulder': 'ZYX',
    'elbow':    'XZY',
    'wrist':    'ZXY',
    'hip':      'ZXY',
    'knee':     'XZY',
    'ankle':    'ZXY',
}
ORDER_INDEX = ['xyz', 'yzx', 'zxy', 'xzy', 'yxz', 'zyx']

def set_rotation_orders(rig_joints_dict):
    """
    rig_joints_dict: {joint_name: joint_type}
    e.g. {'spine_01': 'spine', 'l_shoulder': 'shoulder'}
    """
    for jnt, jnt_type in rig_joints_dict.items():
        order_key = next((k for k in ROTATION_ORDERS if k in jnt_type.lower()), None)
        if order_key and cmds.objExists(jnt):
            idx = ORDER_INDEX.index(ROTATION_ORDERS[order_key].lower())
            cmds.setAttr(f'{jnt}.rotateOrder', idx)
```

**Checking for gimbal lock risk in an existing rig:**
```python
def find_gimbal_risk_joints(threshold_deg=75.0):
    """Find joints near gimbal lock (middle Euler axis close to +/-90 deg)."""
    import maya.cmds as cmds
    results = []
    for jnt in cmds.ls(type='joint'):
        order = cmds.getAttr(f'{jnt}.rotateOrder')
        rot = cmds.getAttr(f'{jnt}.rotate')[0]
        # Middle axis for each rotation order
        middle_axis_idx = [1, 2, 0, 2, 0, 1][order]  # xyz=1, yzx=2, zxy=0, xzy=2, yxz=0, zyx=1
        middle_angle = rot[middle_axis_idx]
        if abs(middle_angle) > threshold_deg:
            results.append((jnt, middle_angle))
    return results
```

## Comparación con autorig_tools

El sistema matrix-based de `autorig_tools` (local_mmx, decomposeMatrix, multMatrix) ya evita el gimbal lock en las cadenas de transform al conducir matrices completas. Sin embargo, el sistema de correctives RBF puede estar usando ángulos de Euler como drivers, lo que introduce distancias no-geodésicas en el espacio de poses. Usar vectores de mapa exponencial como input del solver RBF sería matemáticamente correcto. La función `set_rotation_orders()` arriba es aplicable directamente al biped builder existente.

## Aplicable directamente

PARTIAL:
1. **Rotation orders en el biped builder (30 min):** Añadir `set_rotation_orders()` al build step de joints. Impacto inmediato en estabilidad de spine/neck/shoulder.
2. **Gimbal lock audit (30 min):** Correr `find_gimbal_risk_joints()` en cualquier rig de producción para identificar problemas antes de que los animadores los reporten.
3. **Exponential map para RBF (1-2h):** Si el sistema RBF usa rotateX/Y/Z como driver inputs, sustituir por `joint_as_expmap()`. Mejora la calidad de interpolación de correctives en poses extremas.

## Fuente
- https://www.cs.cmu.edu/~spiff/moedit99/expmap.pdf -- Grassia (1998), Practical Parameterization of Rotations
- https://arxiv.org/pdf/2511.04452 -- Quaternionic approach to gimbal lock resolution (2025)
- https://www.nerd.nintendo.com/files/Working%20With%20Rotations%2020230428.pdf -- Nintendo NERD Working With Rotations (2023)
- https://thenumb.at/Exponential-Rotations/ -- Exponentially Better Rotations
