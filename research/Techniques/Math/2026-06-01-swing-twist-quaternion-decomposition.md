---
source: https://www.chadvernon.com/blog/swing-twist/ | https://github.com/chadmv/cmt/blob/master/scripts/cmt/rig/swingtwist.py
found: 2026-06-01
category: math
priority: 1
tags: [maya, quaternion, swing-twist, decomposition, twist-extraction, forearm, spine, rigging, math]
status: NEW
---

# Swing-Twist Quaternion Decomposition — Math y Nodos Maya

## Descripción
La descomposición swing-twist separa una rotación de cuaternión en dos componentes independientes: el **twist** (rotación alrededor de un eje específico, ej. el eje largo del forearm) y el **swing** (la rotación restante, perpendicular al eje de twist). Es la técnica matemáticamente correcta para extraer el giro de rotación de un hueso sin que otros ejes contaminen el resultado. Reemplaza completamente el patrón antiguo de usar `ikHandle` + `pointConstraint` para el forearm twist, que produce flipping. Chad Vernon lo implementó como un network de nodos nativos de Maya y como un plugin compilado (`swingtwist.py` / `swingtwist.mll`).

## Fundamento matemático / técnico

### Quaternion Review
A quaternion `q = (w, x, y, z)` represents a rotation. For a rotation of angle `θ` around unit axis `n̂ = (nx, ny, nz)`:
```
q = (cos(θ/2),  nx·sin(θ/2),  ny·sin(θ/2),  nz·sin(θ/2))
w = cos(θ/2)
x = nx·sin(θ/2)
y = ny·sin(θ/2)
z = nz·sin(θ/2)
```

### Twist Extraction Formula
To extract the twist component around axis X (the most common case for forearm/spine twist):

**Step 1 — Project quaternion onto twist axis:**
```
twist_q = normalize(w, x, 0, 0)   # keep only W and X components (for X-axis twist)
twist_q = normalize(w, 0, y, 0)   # for Y-axis twist  
twist_q = normalize(w, 0, 0, z)   # for Z-axis twist
```
This is the key mathematical insight: by zeroing the two components not aligned with the twist axis and renormalizing, you obtain a pure rotation around that axis.

**Step 2 — Derive swing from twist:**
```
swing_q = twist_q_inverse * full_rotation_q
        = conjugate(twist_q) * full_rotation_q
```
Since `full_rotation = swing * twist`, it follows that `swing = full * inverse(twist)`.

**Verification:**
```
twist_q * swing_q ≈ full_rotation_q  (up to floating point error)
```

### Weighted Application
To drive a joint with only partial twist (e.g., 50% of the wrist's twist for a mid-forearm joint):
```
driven_twist = slerp(identity_q, twist_q, weight)   # weight in [0.0, 1.0]
driven_swing = slerp(identity_q, swing_q, swingWeight)
result_q = driven_twist * driven_swing
```

### Flip Warning at 180°
Because `slerp` interpolates along the shortest arc, **when the driver rotates past ±180° the blend will suddenly flip direction.** Negative weight values (-1.0 to 0.0) can counter-rotate — useful for correcting over-rotation artifacts.

## Implementación en Maya

### Node Network (vanilla, no plugin)
```
driver_transform
  └─ multMatrix (driver.worldMatrix * rest_pose_inverse_matrix)
       └─ decomposeMatrix → outputQuatW, outputQuatX, outputQuatY, outputQuatZ
            ├─ [TWIST EXTRACTION]
            │   quatNormalize
            │     in: (W, X, 0, 0)         ← zero non-twist components before normalize
            │     out: twist_q
            │   quatInvert(twist_q)         ← inverse twist
            │   quatProd(quat_full, inv_twist) → swing_q
            │
            ├─ [WEIGHTED BLEND]
            │   quatSlerp(identity, twist_q, twistWeight)  → weighted_twist
            │   quatSlerp(identity, swing_q, swingWeight)  → weighted_swing
            │   quatProd(weighted_twist, weighted_swing)   → result_q
            │
            └─ composeMatrix(result_q)
                 └─ multMatrix(result * driven_rest_matrix)
                      └─ driven_transform.offsetParentMatrix
```

### Python Setup (from cmt)
```python
import maya.cmds as cmds
import maya.api.OpenMaya as om

def create_swing_twist(driver, driven, twist_axis='x', twist_weight=1.0, swing_weight=0.0):
    """
    driver: string — transform driving the rotation
    driven: string — transform receiving decomposed rotation
    twist_axis: 'x', 'y', or 'z' — the axis to extract twist from
    """
    # Store rest matrix
    rest_matrix = cmds.getAttr('{}.worldMatrix[0]'.format(driver))
    rest_inv = om.MMatrix(rest_matrix).inverse()
    
    # multMatrix: driver.worldMatrix * rest_inverse
    mm = cmds.createNode('multMatrix')
    cmds.connectAttr('{}.worldMatrix[0]'.format(driver), mm + '.matrixIn[0]')
    cmds.setAttr(mm + '.matrixIn[1]', list(rest_inv), type='matrix')
    
    # decomposeMatrix -> quaternion components
    dcmp = cmds.createNode('decomposeMatrix')
    cmds.connectAttr(mm + '.matrixSum', dcmp + '.inputMatrix')
    
    # quatNormalize to extract twist (zero non-twist components)
    qnorm = cmds.createNode('quatNormalize')
    axis_map = {'x': ('W', 'X'), 'y': ('W', 'Y'), 'z': ('W', 'Z')}
    w_attr, axis_attr = axis_map[twist_axis]
    cmds.connectAttr(dcmp + '.outputQuatW', qnorm + '.inputQuatW')
    cmds.connectAttr(dcmp + '.outputQuat{}'.format(axis_attr.upper()), 
                     qnorm + '.inputQuat{}'.format(axis_attr.upper()))
    # non-twist components remain 0 (default)
    
    # ... (quatInvert, quatProd for swing, quatSlerp for weighting)
    # ... composeMatrix -> multMatrix(rest_matrix) -> driven.offsetParentMatrix
    
    # Set weights
    cmds.addAttr(driven, longName='twistWeight', defaultValue=twist_weight, min=-1.0, max=1.0)
    cmds.addAttr(driven, longName='swingWeight', defaultValue=swing_weight, min=-1.0, max=1.0)
```

### Practical Setup Patterns
```
# FOREARM TWIST (3 twist joints from wrist rotation):
# wrist.worldMatrix → swing_twist(twist_axis='x')
# twist_joint_1.twistWeight = 0.33
# twist_joint_2.twistWeight = 0.66
# twist_joint_3.twistWeight = 1.00

# SPINE TWIST (chest to pelvis):
# chest_ctrl → swing_twist(twist_axis='y')
# spine_mid.twistWeight = 0.5
```

## Comparación con autorig_tools
El archivo existente `2026-05-11-matrix-twist-extraction-maya.md` cubre el patrón básico `decomposeMatrix → quatNormalize(zero Y/Z) → quatToEuler`. La descomposición swing-twist va más lejos: permite extraer **y ponderar de forma independiente** el twist y el swing, y **propagar ambos a distintos joints con pesos distintos**. Es especialmente útil para sistemas donde el forearm twist debe seguir parcialmente al shoulder (swing) y parcialmente al wrist (twist) simultáneamente. El plugin CMT de Chad Vernon es la implementación de referencia más citada en producción.

## Aplicable directamente
**YES** — Reemplazar el sistema de twist del forearm/shin en autorig_tools con este network. Específicamente:
- El patrón `quatNormalize` (zerear componentes no-twist) ya está en el archivo existente; el paso adicional aquí es la **separación completa swing/twist con pesos independientes** en el joint, no solo extracción de twist.
- Implementar como `build_swing_twist_extractor(driver, driven_joints, twist_axis, weights)` que cree el network completo.
- El uso de `offsetParentMatrix` como destino final (en lugar de `quatToEuler → rotateX/Y/Z`) es el patrón moderno recomendado.
- Tiempo de implementación estimado: 2-3 horas.

## Fuente
https://www.chadvernon.com/blog/swing-twist/
https://github.com/chadmv/cmt/blob/master/scripts/cmt/rig/swingtwist.py
https://chadmv.github.io/cmt/html/rig/swingtwist.html
