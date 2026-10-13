---
source: https://adammadej.com/posts/202403-squashstretch/
found: 2026-05-11
category: math
priority: 1
tags: [maya, rigging, math, stretch, squash, volume-preservation, matrix, multiplyDivide, power]
status: NEW
---

# Volume Preservation in Stretch/Squash Rigs — Matemática y Nodo Graph Maya

## Descripción
En rigs con stretch (las extremidades pueden alargarse) y squash (pueden aplastarse), la malla pierde o gana volumen de forma no realista si solo se escala el eje longitudinal. La preservación de volumen asegura que cuando un hueso se alarga (scale Y = n), los ejes laterales (X y Z) se comprimen de forma proporcional para mantener el volumen total. Esta relación es cuadrática (raíz cuadrada inversa) y puede implementarse con pure matrix/node math sin expresiones ni trig.

## Fundamento matemático / técnico

### Volume Preservation Equation
For a bone scaled by factor n along its length axis Y:
```
Volume = scaleX · scaleY · scaleZ = 1.0 (constant, normalized)
```
If `scaleY = n`, then maintaining unit volume requires:
```
scaleX · scaleZ = 1/n
```
For isotropic lateral scaling (same X and Z):
```
scaleX = scaleZ = 1/√n = n^(-0.5)
```

**Proof:** `scaleX · scaleY · scaleZ = n^(-0.5) · n · n^(-0.5) = n^(-0.5+1-0.5) = n^0 = 1 ✓`

### Generalization: Squash Exponent
Artists often want non-physically-accurate volume preservation for stylistic control. Introducing an exponent e:
```
scaleX = scaleZ = n^(-e)
```
- e = 0.0: no volume preservation (pure scale on one axis)
- e = 0.5: perfect physical volume preservation (√)
- e = 1.0: inverse — lateral axes = 1/n (hyper-volume preserving)

This exponent can be exposed as an artist attribute `volume_exponent` on the control.

### Squash/Stretch from Distance
In stretch IK, the stretch factor is derived from the distance between IK root and goal:
```
stretch_factor = current_distance / rest_distance
```
where `rest_distance` is the total chain length in bind pose.

This ratio drives both the joint's translate Y (to physically position bones) and the volume compensation scaling.

**Non-uniform stretch:** For a chain of N joints, the stretch can be distributed non-uniformly (e.g., more stretch near the wrist than the shoulder) using a remap curve:
```
joint_i_stretch = remap_curve(stretch_factor, 0..1 → min..max)
```

### Matrix-Based Stretch (No distanceBetween Node)
Traditional stretch rigs use a `distanceBetween` node (deprecated in favor of matrix approach). Pure matrix version:

1. Get start and end position from their world matrices:
```
start_pos = decomposeMatrix(start_ctrl.worldMatrix).outputTranslate
end_pos   = decomposeMatrix(end_ctrl.worldMatrix).outputTranslate
```
2. Compute length via matrix subtraction + vectorProduct magnitude:
```
delta = end_pos - start_pos             # vector3 subtraction (needs 3 vectorProducts or addDoubleLinear)
length = sqrt(delta.x² + delta.y² + delta.z²)   # vectorProduct in dot mode: √(v·v)
```
Actually in Maya node graph, the cleanest approach is:
```
multMatrix: [end_ctrl.worldMatrix] × [start_ctrl.worldInverseMatrix]
→ decomposeMatrix.outputTranslateX   # X component = distance if on same axis
```
This is the local_mmx pattern: extract the translation of B in A's space. For aligned joints:
```
stretch = decomposeMatrix.outputTranslateX / rest_length
```

### Full Volume-Preserving Stretch Node Graph
```
[stretch_factor: multiplyDivide (stretch / rest_length)]
        │
        ├─→ [joint.scaleY] (stretch along bone axis)
        │
        └─→ [pow node (power = -0.5)] → [joint.scaleX, joint.scaleZ]
```

**Maya 'power' node:** Use `multiplyDivide` with operation = "Power" (3):
```
multiplyDivide.operation = 3 (Power)
multiplyDivide.input1X = stretch_factor
multiplyDivide.input2X = -0.5          # or connect to volume_exponent attr
→ multiplyDivide.outputX = stretch_factor^(-0.5) = 1/√stretch_factor
```

```python
import maya.cmds as cmds

def build_volume_preservation(stretch_attr, joint, volume_exponent=-0.5):
    """
    stretch_attr: plug like 'stretch_node.outputX' (stretch factor value)
    joint: name of joint to apply volume preservation to
    """
    pow_node = cmds.createNode('multiplyDivide', n=f'{joint}_volumePow')
    cmds.setAttr(f'{pow_node}.operation', 3)  # Power
    cmds.connectAttr(stretch_attr, f'{pow_node}.input1X')
    cmds.setAttr(f'{pow_node}.input2X', volume_exponent)

    # Connect to both lateral axes
    cmds.connectAttr(f'{pow_node}.outputX', f'{joint}.scaleX')
    cmds.connectAttr(f'{pow_node}.outputX', f'{joint}.scaleZ')

    # Also connect stretch to the primary axis
    cmds.connectAttr(stretch_attr, f'{joint}.scaleY')

    return pow_node
```

### Clamp for Squash-Only or Stretch-Only
To allow stretch but not squash (common in game rigs), clamp the stretch_factor to ≥ 1.0:
```python
clamp = cmds.createNode('clamp', n=f'{joint}_stretchClamp')
cmds.setAttr(f'{clamp}.minR', 1.0)
cmds.setAttr(f'{clamp}.maxR', 99.0)
cmds.connectAttr(stretch_attr, f'{clamp}.inputR')
# Use clamp.outputR instead of stretch_attr for volume preservation
```

## Implementación en Maya

Nodes used: `multiplyDivide` (divide for ratio + power for √), `clamp` (for stretch/squash limits). No expressions, no mel scripts, no trig.

The only node that doesn't exist natively for this: "vector magnitude" from world positions. The closest is:
- `vectorProduct` in dot mode: `√(v·v)` gives the magnitude
- Or use the local_mmx pattern (decomposeMatrix translate component) if start/end are parent/child

## Comparación con autorig_tools

autorig_tools ya tiene stretch IK. Este documento formaliza la matemática del volume preservation que puede estar implementada informalmente. El patrón `multiplyDivide.power = -0.5` es el estándar. La exposición de `volume_exponent` como atributo en el control (0=off, 0.5=physical, 1.0=hyper) da flexibilidad artística. La versión matrix del cálculo de distancia (sin distanceBetween) mejora compatibilidad con Parallel Evaluation.

## Aplicable directamente
YES — Revisar la implementación actual de stretch en autorig_tools: (1) si usa distanceBetween, reemplazar por decomposeMatrix.translateX del patrón local_mmx; (2) añadir el nodo de volume preservation (multiplyDivide power -0.5) si no está ya; (3) exponer volume_exponent como atributo en el ik_ctrl. Tiempo estimado: 2 horas.

## Fuente
- Adam Madej squash/stretch theory: https://adammadej.com/posts/202403-squashstretch/
- Autodesk realtime rigging squash/stretch: https://www.autodesk.com/learn/ondemand/curated/realtime-rigging-squash-and-stretch
- DapurGrafik volume preservation: https://dapurgrafik.wordpress.com/2014/06/30/volume-preservation-in-squashing-and-strecthing/
