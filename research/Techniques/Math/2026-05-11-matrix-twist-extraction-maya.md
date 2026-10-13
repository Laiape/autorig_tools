---
source: https://bindpose.com/maya-matrix-nodes-part-2-node-based-matrix-twist-calculator/
found: 2026-05-11
category: math
priority: 1
tags: [maya, rigging, math, matrix, twist, quaternion, swing-twist, decomposition, node-graph]
status: NEW
---

# Matrix Twist Extraction in Maya — Pure Quaternion/Matrix Solution, No Trigonometry

## Descripción
Extraer el twist de una cadena de joints (p.ej. cuánto ha rotado el forearm en su eje longitudinal) sin usar ikHandle ni aimConstraint es un problema clásico de rigging. La solución moderna usa decomposeMatrix + nodos de quaternión para extraer el twist de forma estable y eficiente, evitando nodos trigonométricos lentos (atan2, asin) y flips. Es la base del forearm twist ribbon y del twist distribuido a lo largo de extremidades.

## Fundamento matemático / técnico

### The Problem: Swing-Twist Decomposition
Any 3D rotation R can be decomposed into:
```
R = Swing · Twist
```
- **Twist:** rotation around a specific axis (e.g., the bone's long axis X)
- **Swing:** rotation in the plane perpendicular to the twist axis

For a forearm joint, we want to extract only the Twist component (rotation around X/Y/Z long axis) to drive the roll joints.

### Quaternion Swing-Twist Decomposition
Given quaternion q = (w, x, y, z) and twist axis t̂ = (1,0,0) (bone long axis = X):

1. Project quaternion rotation vector onto twist axis:
```
proj = dot((x,y,z), t̂) · t̂    # project rotation vector onto twist axis
twist_q = normalize( (w, proj) )  # form quaternion with only the twist component
```
For t̂ = (1,0,0): `proj = (x, 0, 0)`, so `twist_q = normalize(w, x, 0, 0)`

2. Extract twist angle:
```
twist_angle = 2 · atan2(x, w)    # if t̂ = X axis
```

3. Swing quaternion: `swing_q = q · twist_q⁻¹`

### Maya Node Graph Implementation
The `bindpose.com` approach uses Maya's native quaternion nodes:

```
Step 1: decomposeMatrix(matrix_A) → outputQuatX, outputQuatY, outputQuatZ, outputQuatW
Step 2: Zero out the Y and Z components of the quaternion:
    quatY = 0
    quatZ = 0
    (Keep quatX and quatW — this is the projection onto the X axis)
Step 3: quatNormalize(quatX, 0, 0, quatW) → normalized twist quaternion
Step 4: quatToEuler(twist_quat) → outputRotateX = twist angle
```

Node connections:
```
joint_A.worldMatrix[0] → decomposeMatrix.inputMatrix
decomposeMatrix.outputQuatX → quatNormalize.inputQuatX
decomposeMatrix.outputQuatW → quatNormalize.inputQuatW
quatNormalize.outputQuatX → quatToEuler.inputQuatX
quatNormalize.outputQuatW → quatToEuler.inputQuatW
quatToEuler.outputRotateX → multiplyDivide.input1X  # for distribution
```

**Why zero out Y and Z?** Those components encode the swing (off-axis rotation). Keeping only X and W isolates the twist around the X axis. Renormalizing ensures it's a valid unit quaternion.

### Python Build Code
```python
import maya.cmds as cmds

def build_twist_extractor(matrix_source, twist_axis='x'):
    """
    Extracts twist from a matrix using quaternion decomposition.
    twist_axis: 'x', 'y', or 'z' — the bone's long axis
    Returns the name of the quatToEuler node (read outputRotateX/Y/Z for twist angle)
    """
    decomp = cmds.createNode('decomposeMatrix', n=f'{matrix_source}_twistDecomp')
    norm   = cmds.createNode('quatNormalize',   n=f'{matrix_source}_twistNorm')
    euler  = cmds.createNode('quatToEuler',     n=f'{matrix_source}_twistEuler')

    cmds.connectAttr(f'{matrix_source}.worldMatrix[0]', f'{decomp}.inputMatrix')

    axis_map = {'x': ('X', 'outputRotateX'),
                'y': ('Y', 'outputRotateY'),
                'z': ('Z', 'outputRotateZ')}
    ax, out_attr = axis_map[twist_axis]

    # Connect only the twist axis quat components (zero the others)
    cmds.connectAttr(f'{decomp}.outputQuat{ax}', f'{norm}.inputQuat{ax}')
    cmds.connectAttr(f'{decomp}.outputQuatW',    f'{norm}.inputQuatW')
    # Y and Z left at 0 (default)

    cmds.connectAttr(f'{norm}.outputQuat{ax}', f'{euler}.inputQuat{ax}')
    cmds.connectAttr(f'{norm}.outputQuatW',    f'{euler}.inputQuatW')

    return euler, out_attr

# Usage: distribute twist across 3 roll joints
euler_node, twist_attr = build_twist_extractor('upper_arm_jnt')
for i, roll_jnt in enumerate(['forearm_roll_01', 'forearm_roll_02', 'forearm_roll_03']):
    mult = cmds.createNode('multiplyDivide', n=f'{roll_jnt}_twistMult')
    factor = (i + 1) / 3.0  # 0.33, 0.66, 1.0
    cmds.connectAttr(f'{euler_node}.outputRotate{twist_attr[-1]}', f'{mult}.input1X')
    cmds.setAttr(f'{mult}.input2X', factor)
    cmds.connectAttr(f'{mult}.outputX', f'{roll_jnt}.rotate{twist_attr[-1]}')
```

### Chad Vernon's Swing-Twist Method (offsetParentMatrix version)
For Maya 2020+, Chad Vernon shows decomposing swing-twist directly into the offsetParentMatrix pipeline:
1. Decompose worldMatrix of wrist → get quaternion
2. Extract swing: `swing_q = q · twist_q⁻¹`
3. Feed swing back through a compose chain to drive shoulder/clavicle follow

### Comparing with aimConstraint / ikHandle approaches
| Method | Stability | Node Count | GPU Compatible | Notes |
|--------|-----------|------------|----------------|-------|
| Quaternion decomp | Excellent | 3 nodes | Yes | No gimbal, no flip |
| aimConstraint | Good | 1 node | No (constraint) | Flips at 90° possible |
| ikHandle trick | Good | 2 nodes | No | Overhead from ik eval |
| atan2 expression | Poor | 1 node | No | Gimbal at 90°, slow |

## Implementación en Maya

Direct node connections (no plugin required):
- `decomposeMatrix` → `quatNormalize` → `quatToEuler` = 3 native nodes
- Works in Maya 2016+
- 100% GPU Override compatible (all nodes are geometry-independent)
- Zero trigonometric expressions

The output `quatToEuler.outputRotateX` gives the twist angle in degrees, stable from -360° to +360°.

## Comparación con autorig_tools

Si autorig_tools usa aimConstraints o ikHandle para extraer el twist del forearm/shin, este patrón es un reemplazo directo con menos nodos y mejor compatibilidad con Parallel Evaluation y GPU Override. El patrón `decomposeMatrix → quatNormalize → quatToEuler` es el approach recomendado por la comunidad de rigging (bindpose.com, Chad Vernon, riggingdojo) como estándar actual.

## Aplicable directamente
YES — Reemplazar cualquier twist extraction basado en aimConstraint o ikHandle en autorig_tools con este patrón de 3 nodos. Implementar como función `build_twist_extractor(source_matrix, axis, targets, distribution_factors)` en el módulo de extremidades. Tiempo estimado: 1-2 horas.

## Fuente
- Bindpose.com (nodo graph detallado): https://bindpose.com/maya-matrix-nodes-part-2-node-based-matrix-twist-calculator/
- Chad Vernon (swing-twist con offsetParentMatrix): https://www.chadvernon.com/blog/swing-twist/
- YouTube demo: https://www.youtube.com/watch?v=Em0eMN4NBBY
- Rijah's Blog (Python snippet): https://rijahkaz.com/2022/08/26/node-based-matrix-twist-calculator-python-snippet/
