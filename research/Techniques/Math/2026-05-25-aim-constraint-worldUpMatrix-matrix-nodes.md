---
source: https://bindpose.com/maya-matrix-based-functions-part-1-node-based-matrix-constraint/ | https://www.tech-artists.org/t/maya-aim-matrix-vs-aim-constraint-whats-missing/14770 | https://lesterbanks.com/2018/09/maya-constraint-system-matrix-nodes/
found: 2026-05-25
category: math
priority: 1
tags: [maya, python, rigging, math, matrix, aimConstraint, worldUpMatrix, vectorProduct, aimMatrix, nodes, performance]
status: NEW
---

# Aim Constraint Replacement with Matrix Nodes — worldUpMatrix Patterns & aimMatrix Node

## Descripción
El nodo aimConstraint de Maya es funcional pero lento: calcula muchas cosas innecesarias (múltiples targets, offset, maintain offset stack) y no está declarado como parallel-safe en versiones antiguas. Existe una alternativa matricial pura que usa VectorProduct, fourByFourMatrix (o la nueva aimMatrix introducida en Maya 2020) para replicar exactamente el comportamiento del aim constraint con mejor rendimiento y compatibilidad con Parallel Evaluation. Este documento cubre la matemática del aim constraint y su implementación como grafo de nodos puro.

## Fundamento matemático / técnico

### The Math of an Aim Constraint

An aim constraint orients an object so that a local axis (usually +Z or +X) points toward a target position, while a second "up" axis aligns to a reference direction (worldUpVector/worldUpMatrix).

**Given:**
- `S` = source object world position (the object being constrained)
- `T` = target world position (the object to aim at)
- `U` = world up reference (from worldUpMatrix or worldUpVector)

**Step 1: Compute the aim vector**
```
aim = normalize(T - S)
```

**Step 2: Compute the up vector**

For `worldUpType = "object"` (worldUpMatrix):
```
# Extract the world position of the up object from its worldMatrix
U_world = worldUpMatrix.column[3]  # 4th column = translation
up_dir = normalize(U_world - S)    # direction from source to up object
```

For `worldUpType = "objectrotation"`:
```
# Take the Y axis of the worldUpMatrix
up_dir = normalize(worldUpMatrix.column[1])  # 2nd column = Y axis
```

**Step 3: Compute the third axis (side vector)**
```
side = normalize(aim × up_dir)
```

**Step 4: Recompute up (orthogonalize)**
```
up_ortho = normalize(side × aim)
```
This ensures the three axes are perfectly orthogonal even if aim and up were not perpendicular.

**Step 5: Build the rotation matrix**
```
# Assuming aimAxis = +X, upAxis = +Y:
M = | side.x   up_ortho.x   aim.x   S.x |
    | side.y   up_ortho.y   aim.y   S.y |
    | side.z   up_ortho.z   aim.z   S.z |
    | 0        0            0       1   |

# Then: object.offsetParentMatrix = M * parentInverseMatrix
# (to drive in local space)
```

---

### Maya Node Implementations

#### Method 1: aimMatrix Node (Maya 2020+) — Recommended

Maya 2020 introduced the `aimMatrix` node which handles this computation natively with parallel-safe scheduling:

```
aimMatrix inputs:
  .inputMatrix       ← source.worldMatrix[0]
  .primaryTargetMatrix  ← target.worldMatrix[0]
  .primaryMode       ← 1 (aimAt = "target")
  .primaryInputAxis  ← (1, 0, 0)  # which local axis aims at target
  .secondaryTargetMatrix ← upObject.worldMatrix[0]
  .secondaryMode     ← 4 (worldUpObject)
  .secondaryInputAxis ← (0, 1, 0)  # which local axis aligns to up

aimMatrix outputs:
  .outputMatrix  ← connect to object.offsetParentMatrix
                   (or decompose for rotate channels)
```

Python build:
```python
import maya.cmds as cmds

def build_aim_matrix(source, target, up_object,
                     aim_axis=(1,0,0), up_axis=(0,1,0)):
    """
    Replaces aimConstraint with matrix node approach.
    Returns the aimMatrix node name.
    """
    aim = cmds.createNode('aimMatrix', name=f'{source}_aimMtx')
    
    # Source worldMatrix (where the object is)
    cmds.connectAttr(f'{source}.worldMatrix[0]', f'{aim}.inputMatrix')
    
    # Target (what to aim at)
    cmds.connectAttr(f'{target}.worldMatrix[0]', f'{aim}.primaryTargetMatrix')
    cmds.setAttr(f'{aim}.primaryMode', 1)  # aim at target
    cmds.setAttr(f'{aim}.primaryInputAxis', *aim_axis, type='double3')
    
    # Up object
    cmds.connectAttr(f'{up_object}.worldMatrix[0]', f'{aim}.secondaryTargetMatrix')
    cmds.setAttr(f'{aim}.secondaryMode', 4)  # objectrotation up
    cmds.setAttr(f'{aim}.secondaryInputAxis', *up_axis, type='double3')
    
    # Drive rotation in local space via offsetParentMatrix
    # Zero out the object's local rotate to avoid double transform
    mult = cmds.createNode('multMatrix', name=f'{source}_aimLocalMtx')
    cmds.connectAttr(f'{aim}.outputMatrix',  f'{mult}.matrixIn[0]')
    cmds.connectAttr(f'{source}.parentInverseMatrix[0]', f'{mult}.matrixIn[1]')
    
    dcmp = cmds.createNode('decomposeMatrix', name=f'{source}_aimDcmp')
    cmds.connectAttr(f'{mult}.matrixSum', f'{dcmp}.inputMatrix')
    
    cmds.connectAttr(f'{dcmp}.outputRotateX', f'{source}.rotateX')
    cmds.connectAttr(f'{dcmp}.outputRotateY', f'{source}.rotateY')
    cmds.connectAttr(f'{dcmp}.outputRotateZ', f'{source}.rotateZ')
    
    return aim
```

---

#### Method 2: VectorProduct + fourByFourMatrix (Pre-2020 or Custom Control)

For Maya 2018/2019 or when fine-grained control over axis assignment is needed:

```
Node graph:
  1. decomposeMatrix(source.worldMatrix) → sourcePos (translate)
  2. decomposeMatrix(target.worldMatrix) → targetPos (translate)
  3. decomposeMatrix(upObj.worldMatrix)  → upPos (translate)

  4. vectorProduct(mode=subtract): targetPos - sourcePos → rawAim
  5. vectorProduct(mode=normalize): rawAim → aimVec

  6. vectorProduct(mode=subtract): upPos - sourcePos → rawUp
  7. vectorProduct(mode=normalize): rawUp → upVec

  8. vectorProduct(mode=crossProduct): aimVec × upVec → sideVec (normalize)
  9. vectorProduct(mode=crossProduct): sideVec × aimVec → upOrtho (normalize)

  10. fourByFourMatrix:
      row0 = sideVec  (X axis of output)
      row1 = upOrtho  (Y axis of output)
      row2 = aimVec   (Z axis of output)
      row3 = sourcePos (translation)
  
  11. multMatrix: fourByFourMatrix × parentInverseMatrix → local matrix
  12. decomposeMatrix → connect to source.rotate
```

VectorProduct node modes:
- `mode=0` (noOperation)
- `mode=1` (dotProduct) → scalar
- `mode=2` (crossProduct) → vector
- `mode=3` (vectorMatrixProduct)
- `mode=4` (pointMatrixProduct)

Note: VectorProduct does NOT have a subtract/normalize mode — use separate nodes:
```python
# Subtract: plusMinusAverage with operation=subtract (mode 2)
sub = cmds.createNode('plusMinusAverage')
cmds.setAttr(f'{sub}.operation', 2)  # subtract

# Normalize: vectorProduct with normalizeOutput=True on crossProduct
```

---

#### Method 3: worldUpMatrix Pattern for Eye Rigs

A common use case in facial rigs: eye joint aims at a pupil target, up direction from a forehead transform:

```python
def build_eye_aim(eye_joint, pupil_target, forehead_up):
    """Matrix-based eye aim rig."""
    aim = cmds.createNode('aimMatrix', name=f'{eye_joint}_aimMtx')
    
    cmds.connectAttr(f'{eye_joint}.worldMatrix[0]', f'{aim}.inputMatrix')
    cmds.connectAttr(f'{pupil_target}.worldMatrix[0]', f'{aim}.primaryTargetMatrix')
    cmds.setAttr(f'{aim}.primaryMode', 1)
    cmds.setAttr(f'{aim}.primaryInputAxis', 0, 0, 1, type='double3')  # Z aims forward
    
    cmds.connectAttr(f'{forehead_up}.worldMatrix[0]', f'{aim}.secondaryTargetMatrix')
    cmds.setAttr(f'{aim}.secondaryMode', 4)
    cmds.setAttr(f'{aim}.secondaryInputAxis', 0, 1, 0, type='double3')  # Y is up
    
    # Output directly to offsetParentMatrix (cleanest approach)
    # This requires zeroing eye_joint.rotate and translate
    mult = cmds.createNode('multMatrix')
    cmds.connectAttr(f'{aim}.outputMatrix', f'{mult}.matrixIn[0]')
    cmds.connectAttr(f'{eye_joint}.parentInverseMatrix[0]', f'{mult}.matrixIn[1]')
    cmds.connectAttr(f'{mult}.matrixSum', f'{eye_joint}.offsetParentMatrix')
    
    # Zero out local transforms so offsetParentMatrix drives everything
    cmds.setAttr(f'{eye_joint}.rotate', 0, 0, 0)
    cmds.setAttr(f'{eye_joint}.translate', 0, 0, 0)
    
    return aim
```

---

### Performance Comparison

| Approach | Scheduling | Node count | GPU safe |
|----------|-----------|-----------|---------|
| aimConstraint | locally_serialize | 1 node, high overhead | NO |
| aimMatrix + multMatrix + decomposeMatrix | parallel | 3 nodes, minimal overhead | YES (downstream) |
| VectorProduct chain (pre-2020) | parallel | ~10 nodes | YES |

`aimConstraint` nodes are the top complaint in Maya performance audits — one per eye, per ribbon joint, per foot-roll axis adds up quickly in production rigs.

## Implementación en Maya

Direct drop-in replacement for `aimConstraint`:
```python
def replace_aim_constraint_with_matrix(constrained, target, up_object):
    """
    Remove existing aimConstraint and replace with matrix-based aim.
    Safe to call on rigs already built with aimConstraints.
    """
    # Find and remove existing aim constraints
    constraints = cmds.listRelatives(constrained, type='aimConstraint') or []
    for c in constraints:
        cmds.delete(c)
    
    # Also check for constraint node connected via message
    aim_cons = cmds.listConnections(f'{constrained}.rotateX',
                                     type='aimConstraint', source=True) or []
    for c in aim_cons:
        cmds.delete(c)
    
    # Build matrix replacement
    return build_aim_matrix(constrained, target, up_object)
```

## Comparación con autorig_tools

autorig_tools usa aimConstraints en el rig facial (ojos, eyelids) y potencialmente en helper joints de hombro/cadera. Reemplazar estos por aimMatrix + multMatrix eliminaría ~6-10 nodos serializadores por personaje. El patrón de worldUpMatrix es especialmente valioso en el rig de ojos donde el forehead_up control define el "arriba" del ojo — un uso exactamente equivalente al worldUpType="objectrotation" del aimConstraint clásico. El nuevo aimMatrix node (Maya 2020+) es una solución de una sola línea comparada con el grafo de 10 nodos de la alternativa VectorProduct.

## Aplicable directamente

YES — **Específicamente:**
1. En el módulo `build_eye_rig()` de autorig_tools: reemplazar el `aimConstraint` del eye joint por `aimMatrix` con `secondaryMode=4` (worldUpObject apuntando al forehead_up control).
2. En cualquier helper joint de shoulder/hip que use aimConstraint para orientarse al IK pole vector.
3. La función `replace_aim_constraint_with_matrix()` del código anterior se puede añadir directamente como herramienta de conversión en el pipeline.

## Fuente
- https://bindpose.com/maya-matrix-based-functions-part-1-node-based-matrix-constraint/
- https://www.tech-artists.org/t/maya-aim-matrix-vs-aim-constraint-whats-missing/14770
- https://lesterbanks.com/2018/09/maya-constraint-system-matrix-nodes/
- https://www.dominikhaase.com/post/matrix-aim-constraint-rotatehelper
- https://www.linkedin.com/pulse/how-create-aim-constraint-maya-2020-using-matrix-kevin-borjon-piron
