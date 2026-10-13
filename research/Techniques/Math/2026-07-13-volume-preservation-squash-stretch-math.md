---
source: https://adammadej.com/posts/202403-squashstretch/ | https://dapurgrafik.wordpress.com/2014/06/30/volume-preservation-in-squashing-and-strecthing/
found: 2026-07-13
category: math
priority: 1
tags: [maya, python, rigging, math, volume-preservation, squash-stretch, IK, scale, matrix, multiplyDivide, GPU]
status: NEW
---

# Volume Preservation en Squash/Stretch -- Matematicas e Implementacion en Maya

## Descripcion
El principio de conservacion de volumen en squash/stretch (principio de animacion de Disney) tiene una formalizacion matematica directa: si un joint se estira a lo largo de su eje primario con factor s, los otros dos ejes deben escalar por 1/sqrt(s) para mantener el volumen constante. En Maya, esto se implementa tipicamente con `multiplyDivide` + `power(-0.5)`, pero la version matrix-based es GPU-compatible y evita el `distanceBetween` CPU-only. Este archivo cubre la matematica de conservacion de volumen, las variantes de implementacion, y por que el enfoque matrix puro es optimo en el contexto del stack de evaluacion paralela.

## Fundamento matematico / tecnico

### Volume Invariance Condition

For a box with dimensions (sx, sy, sz):
```
Volume = sx * sy * sz = constant = 1 (at rest, normalized)
```

If the joint stretches along its primary axis (X, the typical IK bone axis):
```
new_sx = s    (stretch factor, driven by IK handle distance / rest length)
```

Volume preservation requires:
```
s * sy * sz = 1
sy = sz = 1 / sqrt(s)    (isotropic cross-section assumed)
```

**Derivation:**
```
1 / sqrt(s) * 1 / sqrt(s) = 1/s
s * (1/s) = 1    (checked: volume preserved)
```

**General form for any primary axis n in {X, Y, Z}:**
```
s_primary   = s
s_lateral_1 = s^(-1/2)    for first orthogonal axis
s_lateral_2 = s^(-1/2)    for second orthogonal axis

Check: s * s^(-1/2) * s^(-1/2) = s * s^(-1) = 1  (volume preserved)
```

### The Power Relationship

```
s_lateral = s_primary^(-0.5)
```

**Common confusion -- why -0.5 not 0.5:**
- s = 2.0 (stretched to 2x)
- s^(0.5)  = 1.414 -> INCREASES lateral scale -> volume = 2 * 1.414 * 1.414 = 4.0 (WRONG)
- s^(-0.5) = 0.707 -> DECREASES lateral scale -> volume = 2 * 0.707 * 0.707 = 1.0 (CORRECT)

The power node must use **-0.5**, not 0.5.

### Stretch Factor Computation: Two Approaches

**Approach A -- distanceBetween (classic, CPU-only, breaks GPU cluster):**
```
startJoint.worldPosition -> distanceBetween.point1
endJoint.worldPosition   -> distanceBetween.point2
distanceBetween.distance -> multiplyDivide(/ rest_length) -> s
```
Problem: `distanceBetween` is a DAG node that forces CPU evaluation and breaks the GPU deformer cluster.

**Approach B -- matrix-based (GPU-compatible, preferred):**
```
startJoint.worldMatrix -> inverseMatrix -> multMatrix -> decomposeMatrix
endJoint.worldMatrix   -----------------> multMatrix
decomposeMatrix.outputTranslateX -> multiplyDivide(/ rest_length) -> s
```

The `decomposeMatrix.outputTranslateX` gives the distance along the bone's local X axis (the translation component of the relative matrix). This is equivalent to the bone length in local space -- GPU-safe because it reads from the evaluation graph matrix chain.

### Full Volume Preservation Node Graph

**Matrix approach (4 nodes, 0 CPU-blocking in deformer path):**
```
inverseMatrix
multMatrix          -> decomposeMatrix.outputTranslateX
                                      |
                                      v
                        multiplyDivide [op=Divide, input2X=rest_length]
                                      |
                                      v
                        multiplyDivide [op=Power, input2X=-0.5]
                                      |
                              /-------+-------\
                         scaleY              scaleZ
                    (of all IK chain joints)
```

Also connect the stretch factor (before power) to scaleX of joints for the primary axis stretch.

### Segment Scale Compensate (SSC)

Maya joints have `segmentScaleCompensate` (SSC). When ON (default):
- Child joint counter-scales to undo parent scale, preventing double-scaling down the chain
- Required for most game engine exports

**With SSC=OFF on child joints:**
- Parent scale propagates directly to children
- Simpler setup but can cause issues with game engines

**Recommended setup for squash/stretch rigs:**
```
IK root joint:  SSC=ON  (receives volume preserve scale from expression)
IK mid joint:   SSC=OFF (inherit from parent, don't counter-scale)
IK end joint:   SSC=OFF
```
Then ONLY connect the volume preservation nodes to the root/mid joints of the IK chain, not all joints.

### Squash Amount Control Attribute

For animator control, blend between "no squash" and "full volume preserve":
```
s_lateral = lerp(1.0, s^(-0.5), squash_amount)
         = 1.0 + squash_amount * (s^(-0.5) - 1.0)

squash_amount=0 -> s_lateral=1.0 (no squash/stretch compensation)
squash_amount=1 -> s_lateral=s^(-0.5) (full volume preserve)
```

Maya blendWeighted node:
```
blendWeighted.input[0] = 1.0 (constant)
blendWeighted.input[1] = power_node.outputX  (= s^-0.5)
blendWeighted.weight[0] = (1 - squash_amount)
blendWeighted.weight[1] = squash_amount
blendWeighted.output -> scaleY, scaleZ
```

### Non-Uniform Squash (Anatomically Correct)

Real anatomy is not isotropic. An arm is wider in one lateral direction. For a rig with rest scale (1, sy_rest, sz_rest):

If we stretch by s along X:
```
Volume = s * sy * sz = 1 * sy_rest * sz_rest    (preserve initial volume, not unit cube)

One solution (constant ratio y/z):
sy = sy_rest * s^(-0.5)
sz = sz_rest * s^(-0.5)
```

Or with independent control:
```
sy = sy_rest * s^(-py)    // py = y-squash exponent (default -0.5)
sz = sz_rest * s^(-pz)    // pz = z-squash exponent (default -0.5)
// py + pz must = 1 for exact volume preserve
```

This allows an arm to "flatten" preferentially in one direction (anatomically correct for forearm).

## Implementacion en Maya

```python
import maya.cmds as cmds

def build_volume_preserve_ik(start_jnt, end_jnt, mid_joints,
                              rest_length, primary_axis='x',
                              add_squash_attr=True, ctrl_name=None):
    """
    Build GPU-compatible volume preservation for an IK chain.
    
    Args:
        start_jnt:    IK chain start joint (or IK start proxy)
        end_jnt:      IK chain end joint / IK handle position
        mid_joints:   list of joints to receive volume preserve scale
        rest_length:  rest length of bone chain (float, in cm)
        primary_axis: 'x', 'y', or 'z' (bone primary axis)
        add_squash_attr: if True, add squashAmount attr on ctrl_name
        ctrl_name:    control node to add squashAmount attribute to
    
    Returns:
        dict of created node names
    """
    prefix = start_jnt.replace('_jnt', '') + '_volPres'
    
    # 1. Get relative matrix: end in start's local space
    inv_start = cmds.createNode('inverseMatrix', n=f'{prefix}_invStart')
    mm        = cmds.createNode('multMatrix',    n=f'{prefix}_mm')
    dm        = cmds.createNode('decomposeMatrix', n=f'{prefix}_dm')
    
    cmds.connectAttr(f'{start_jnt}.worldMatrix[0]', f'{inv_start}.inputMatrix')
    cmds.connectAttr(f'{inv_start}.outputMatrix',   f'{mm}.matrixIn[0]')
    cmds.connectAttr(f'{end_jnt}.worldMatrix[0]',   f'{mm}.matrixIn[1]')
    cmds.connectAttr(f'{mm}.matrixSum',             f'{dm}.inputMatrix')
    
    # 2. Stretch factor: distance / rest_length
    trans_attr = {'x': 'outputTranslateX', 'y': 'outputTranslateY',
                  'z': 'outputTranslateZ'}[primary_axis]
    div_node = cmds.createNode('multiplyDivide', n=f'{prefix}_div')
    cmds.setAttr(f'{div_node}.operation', 2)  # divide
    cmds.connectAttr(f'{dm}.{trans_attr}', f'{div_node}.input1X')
    cmds.setAttr(f'{div_node}.input2X', rest_length)
    
    # 3. Volume preserve: s^(-0.5)
    pow_node = cmds.createNode('multiplyDivide', n=f'{prefix}_pow')
    cmds.setAttr(f'{pow_node}.operation', 3)  # power
    cmds.connectAttr(f'{div_node}.outputX', f'{pow_node}.input1X')
    cmds.setAttr(f'{pow_node}.input2X', -0.5)
    
    # 4. Optional squash amount blend
    output_attr = f'{pow_node}.outputX'
    if add_squash_attr and ctrl_name and cmds.objExists(ctrl_name):
        if not cmds.attributeQuery('squashAmount', node=ctrl_name, exists=True):
            cmds.addAttr(ctrl_name, ln='squashAmount', min=0, max=1, dv=1, k=True)
        bw = cmds.createNode('blendWeighted', n=f'{prefix}_squashBlend')
        cmds.setAttr(f'{bw}.input[0]', 1.0)
        cmds.connectAttr(f'{pow_node}.outputX', f'{bw}.input[1]')
        cmds.connectAttr(f'{ctrl_name}.squashAmount', f'{bw}.weight[1]')
        cmds.expression(s=f'{bw}.weight[0] = 1 - {ctrl_name}.squashAmount;',
                        n=f'{prefix}_squashWeight_expr')
        output_attr = f'{bw}.output'
    
    # 5. Apply to joints
    other_axes = [a for a in ['x', 'y', 'z'] if a != primary_axis]
    for jnt in mid_joints:
        cmds.connectAttr(f'{div_node}.outputX', f'{jnt}.scale{primary_axis.upper()}')
        for ax in other_axes:
            cmds.connectAttr(output_attr, f'{jnt}.scale{ax.upper()}')
    
    return {'inv': inv_start, 'mm': mm, 'dm': dm, 'div': div_node, 'pow': pow_node}
```

## Comparacion con autorig_tools

`autorig_tools` probablemente tiene volume preservation en arm/leg, implementado con `distanceBetween` o con un setup matrix (cubierto en 2026-05-25-stretch-ik-pure-matrix.md). Este archivo anade: (1) la matematica formal de por que el exponent es -0.5 y no 0.5 -- cuestion que surge frecuentemente al revisar rigs de otros; (2) la funcion `build_volume_preserve_ik()` completa con squash amount attr; (3) la opcion de squash no-isotropico para extremidades anatomicamente correctas. Si hay algun `distanceBetween` en el pipeline actual, la sustitucion por el patron matrix es la mejora de mayor retorno con menor esfuerzo.

## Aplicable directamente

YES -- extension directa del stretch IK matrix existente:
1. **Auditar `distanceBetween` nodes (15 min):** `cmds.ls(type='distanceBetween')` en escena. Si existen en la cadena IK, sustituir por decomposeMatrix.outputTranslateX.
2. **Anadir `squashAmount` attr en IK controls (30 min):** La funcion `build_volume_preserve_ik(..., add_squash_attr=True, ctrl_name='l_arm_IK_ctrl')` anade el attr y el blend automaticamente.
3. **Verificar exponent = -0.5:** En rigs heredados, revisar que el nodo power usa -0.5 y no 0.5 -- error silencioso que duplica el volumen en vez de preservarlo.

## Fuente
- https://adammadej.com/posts/202403-squashstretch/ -- Theory behind building a squash & stretch rig
- https://dapurgrafik.wordpress.com/2014/06/30/volume-preservation-in-squashing-and-strecthing/
- Ver tambien: 2026-05-25-stretch-ik-pure-matrix.md (implementacion base del stretch IK)
