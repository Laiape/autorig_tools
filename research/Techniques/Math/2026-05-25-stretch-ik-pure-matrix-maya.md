---
source: https://charactersetup.com/tutorials/stretchy_limb.html | https://lesterbanks.com/2017/07/understanding-basics-matrix-math-maya/ | https://www.riggingdojo.com/2025/07/17/mastering-matrices-for-3d-animation-and-rigging/
found: 2026-05-25
category: math
priority: 1
tags: [maya, python, rigging, math, stretch-IK, matrix, distanceBetween, performance, scaleX, volume-preservation]
status: NEW
---

# Stretch IK with Pure Matrix Math — No distanceBetween Node

## Descripción
El Stretch IK clásico en Maya usa el nodo `distanceBetween` para medir la distancia entre el root del IK y el effector, compararla con la longitud en reposo y escalar los joints proporcionalmente. El problema: `distanceBetween` es un nodo CPU-only que no participa en GPU Override y puede causar micro-serialización en el grafo de evaluación. La alternativa matricial pura extrae la distancia directamente de los componentes de traslación de una matriz relativa entre dos objetos, usando únicamente `multMatrix` + `decomposeMatrix` + `vectorProduct` — todos parallel-safe y GPU-friendly downstream.

## Fundamento matemático / técnico

### The Core Problem with distanceBetween

The `distanceBetween` node takes two 3D points and computes their Euclidean distance:
```
d = sqrt((x2-x1)² + (y2-y1)² + (z2-z1)²)
```

While it accepts matrix inputs, it evaluates on CPU. More critically, any node that depends on `distanceBetween.distance` output inherits a CPU scheduling dependency in the evaluation chain.

---

### Matrix-Based Distance Extraction

The key insight: **the translation column of a relative matrix IS the positional offset between two objects in the first object's local space.**

For a 2-bone IK chain with root joint R and IK handle H:
```
relMatrix = H.worldMatrix × R.worldInverseMatrix

relMatrix = | r11  r12  r13  tx |
            | r21  r22  r23  ty |
            | r31  r32  r33  tz |
            | 0    0    0    1  |

where (tx, ty, tz) = position of H in R's local space
```

The stretch distance is simply the magnitude of (tx, ty, tz):
```
d = sqrt(tx² + ty² + tz²)
```

For a chain where joints are aligned to the X axis (standard Maya IK), the stretch is primarily `tx` — so in many production setups:
```
stretch_distance ≈ |tx|   (faster, avoids sqrt)
```

---

### Full Stretch IK Node Graph (Pure Matrix)

```
[IK_Handle.worldMatrix]     [Root_Joint.worldInverseMatrix]
         ↓                              ↓
         └──────── multMatrix ──────────┘
                       ↓ (relMatrix)
               decomposeMatrix
                  ↓         ↓
            outputTX   [outputTY, outputTZ]
                  ↓
         (if X-aligned chain, tx alone)
                  ↓
         vectorProduct (dot with itself) = tx²+ty²+tz²
           (or just use outputTranslate magnitude)
                  ↓
          power(input=dotResult, power=0.5) → distance
                  ↓
          clampOp: max(distance, rest_length)  [prevent negative stretch]
                  ↓
          divideOp: clampedDist / rest_length → stretch_ratio
                  ↓
          condition: if stretch_ratio > 1.0 → apply, else → 1.0
                  ↓         ↓
         upper_joint.scaleX  lower_joint.scaleX
```

---

### Python Build Function

```python
import maya.cmds as cmds

def build_stretch_ik_matrix(root_joint, ik_handle, upper_joint, lower_joint,
                             rest_length, axis='X'):
    """
    Build stretch IK using pure matrix nodes — no distanceBetween.
    
    Args:
        root_joint:   The root of the IK chain (shoulder/hip)
        ik_handle:    The IK handle object (end effector target)
        upper_joint:  First bone to scale (upper arm/thigh)
        lower_joint:  Second bone to scale (forearm/shin)
        rest_length:  Total chain length at rest (upper + lower lengths)
        axis:         Axis along which the chain extends ('X', 'Y', or 'Z')
    """
    name = f'{root_joint}_stretchIK'
    
    # ── Step 1: Relative matrix (IK handle in root space) ──────────────────
    rel_mult = cmds.createNode('multMatrix', name=f'{name}_relMtx')
    cmds.connectAttr(f'{ik_handle}.worldMatrix[0]', f'{rel_mult}.matrixIn[0]')
    cmds.connectAttr(f'{root_joint}.worldInverseMatrix[0]', f'{rel_mult}.matrixIn[1]')
    
    # ── Step 2: Decompose to get translation (= positional offset) ─────────
    dcmp = cmds.createNode('decomposeMatrix', name=f'{name}_dcmpRel')
    cmds.connectAttr(f'{rel_mult}.matrixSum', f'{dcmp}.inputMatrix')
    
    # ── Step 3: Compute distance via dot product ───────────────────────────
    dot = cmds.createNode('vectorProduct', name=f'{name}_dot')
    cmds.setAttr(f'{dot}.operation', 1)      # dot product
    cmds.setAttr(f'{dot}.normalizeOutput', 0)
    cmds.connectAttr(f'{dcmp}.outputTranslate', f'{dot}.input1')
    cmds.connectAttr(f'{dcmp}.outputTranslate', f'{dot}.input2')
    # dot.outputX = tx²+ty²+tz² (squared distance)
    
    pw = cmds.createNode('multiplyDivide', name=f'{name}_sqrt')
    cmds.setAttr(f'{pw}.operation', 3)       # power
    cmds.setAttr(f'{pw}.input2X', 0.5)       # exponent 0.5 = sqrt
    cmds.connectAttr(f'{dot}.outputX', f'{pw}.input1X')
    # pw.outputX = distance
    
    # ── Step 4: Clamp to rest_length (no compression) ─────────────────────
    clamp = cmds.createNode('clamp', name=f'{name}_clamp')
    cmds.setAttr(f'{clamp}.minR', rest_length)
    cmds.setAttr(f'{clamp}.maxR', rest_length * 10)  # generous max
    cmds.connectAttr(f'{pw}.outputX', f'{clamp}.inputR')
    
    # ── Step 5: Stretch ratio ──────────────────────────────────────────────
    ratio = cmds.createNode('multiplyDivide', name=f'{name}_ratio')
    cmds.setAttr(f'{ratio}.operation', 2)    # divide
    cmds.connectAttr(f'{clamp}.outputR', f'{ratio}.input1X')
    cmds.setAttr(f'{ratio}.input2X', rest_length)
    
    # ── Step 6: Drive joint scales ─────────────────────────────────────────
    cmds.connectAttr(f'{ratio}.outputX', f'{upper_joint}.scale{axis}')
    cmds.connectAttr(f'{ratio}.outputX', f'{lower_joint}.scale{axis}')
    
    # ── Step 7: Volume preservation (optional) ────────────────────────────
    # If stretch_ratio > 1, compensate YZ scale: sqrt(1/ratio)
    inv_sqrt = cmds.createNode('multiplyDivide', name=f'{name}_invSqrt')
    cmds.setAttr(f'{inv_sqrt}.operation', 3)  # power
    
    inv = cmds.createNode('multiplyDivide', name=f'{name}_inv')
    cmds.setAttr(f'{inv}.operation', 2)       # divide
    cmds.setAttr(f'{inv}.input1X', 1.0)
    cmds.connectAttr(f'{ratio}.outputX', f'{inv}.input2X')
    # inv.outputX = 1/ratio
    
    cmds.connectAttr(f'{inv}.outputX', f'{inv_sqrt}.input1X')
    cmds.setAttr(f'{inv_sqrt}.input2X', 0.5)  # sqrt(1/ratio)
    
    # Apply to perpendicular axes
    other_axes = [a for a in ['X', 'Y', 'Z'] if a != axis]
    for joint in [upper_joint, lower_joint]:
        for ax in other_axes:
            cmds.connectAttr(f'{inv_sqrt}.outputX', f'{joint}.scale{ax}')
    
    return {
        'rel_matrix': rel_mult,
        'decompose':  dcmp,
        'ratio':      ratio,
        'inv_sqrt':   inv_sqrt
    }
```

---

### X-Axis-Only Optimized Version (Performance)

For chains where the IK extension is entirely along X (standard Maya IK):
```python
def build_stretch_ik_matrix_xonly(root_joint, ik_handle,
                                   upper_joint, lower_joint, rest_length):
    """
    Optimized version: uses |tx| directly, avoiding vectorProduct + power nodes.
    Valid only when chain extends purely along X.
    Saves 2 nodes and removes sqrt from the hot path.
    """
    name = f'{root_joint}_stretchFast'
    
    rel_mult = cmds.createNode('multMatrix', name=f'{name}_relMtx')
    cmds.connectAttr(f'{ik_handle}.worldMatrix[0]',       f'{rel_mult}.matrixIn[0]')
    cmds.connectAttr(f'{root_joint}.worldInverseMatrix[0]', f'{rel_mult}.matrixIn[1]')
    
    dcmp = cmds.createNode('decomposeMatrix', name=f'{name}_dcmp')
    cmds.connectAttr(f'{rel_mult}.matrixSum', f'{dcmp}.inputMatrix')
    
    # |tx| ≈ stretch distance along X axis
    ratio = cmds.createNode('multiplyDivide', name=f'{name}_ratio')
    cmds.setAttr(f'{ratio}.operation', 2)
    cmds.connectAttr(f'{dcmp}.outputTranslateX', f'{ratio}.input1X')
    cmds.setAttr(f'{ratio}.input2X', rest_length)
    
    condition = cmds.createNode('condition', name=f'{name}_cond')
    cmds.setAttr(f'{condition}.operation', 3)  # >=
    cmds.setAttr(f'{condition}.secondTerm', 1.0)
    cmds.connectAttr(f'{ratio}.outputX', f'{condition}.firstTerm')
    cmds.connectAttr(f'{ratio}.outputX', f'{condition}.colorIfTrueR')
    cmds.setAttr(f'{condition}.colorIfFalseR', 1.0)
    
    for joint in [upper_joint, lower_joint]:
        cmds.connectAttr(f'{condition}.outColorR', f'{joint}.scaleX')
    
    return ratio
```

---

### Node Count & Performance

| Approach | Node count | GPU safe | Parallel-safe | Notes |
|----------|-----------|---------|--------------|-------|
| Classic distanceBetween | 4–6 nodes | NO | locally_serialize | CPU bottleneck |
| Full matrix (with sqrt) | 7 nodes | YES (downstream) | parallel | General, any axis |
| X-axis optimized | 4 nodes | YES | parallel | Fastest, chain-aligned |

The distanceBetween node forces a CPU evaluation boundary. In a rig with 4 limbs + spine, replacing 5 distanceBetween instances with matrix alternatives removes 5 CPU-only nodes from the evaluation critical path.

## Implementación en Maya

For autorig_tools integration, both functions above can be called after the IK handle is created. The `rest_length` parameter equals `upper_bone_length + lower_bone_length`, computable from joint positions at rig build time:

```python
import maya.api.OpenMaya as om

def get_chain_rest_length(root_joint, end_joint):
    """Compute rest length from joint positions."""
    def get_pos(jnt):
        sel = om.MSelectionList(); sel.add(jnt)
        dag = sel.getDagPath(0)
        fn = om.MFnTransform(dag)
        return fn.translation(om.MSpace.kWorld)
    
    r = get_pos(root_joint)
    e = get_pos(end_joint)
    return (e - r).length()
```

## Comparación con autorig_tools

autorig_tools probablemente usa `distanceBetween` para el stretch IK de brazos y piernas, que es la implementación estándar de la industria. La versión matricial pura no cambia el comportamiento visible para el animador — el rig se comporta idénticamente — pero elimina nodos CPU-only del grafo y mejora la compatibilidad con Parallel Evaluation y GPU Override. La versión X-axis optimizada reduce el conteo de nodos de ~6 a 4 por extremidad. En un personaje con 4 extremidades, esto es una reducción de ~8 nodos CPU-only, que puede traducirse en 1-3% de mejora en tiempo de evaluación frame a frame.

## Aplicable directamente

YES — **Pasos concretos:**
1. En `build_arm_rig()` y `build_leg_rig()` de autorig_tools, localizar dónde se crea `distanceBetween`.
2. Reemplazar con `build_stretch_ik_matrix_xonly()` si los joints están alineados al eje X (estándar en Maya con joint orient).
3. Pasar el `rest_length` calculado con `get_chain_rest_length()` antes del build del IK handle.
4. El volume preservation (scaleY/Z = sqrt(1/ratio)) es la misma matemática ya usada en autorig_tools para el squash-stretch.

## Fuente
- https://charactersetup.com/tutorials/stretchy_limb.html — Tyler Thornock, Stretchy Limb tutorial
- https://lesterbanks.com/2017/07/understanding-basics-matrix-math-maya/ — Understanding Matrix Math in Maya
- https://www.riggingdojo.com/2025/07/17/mastering-matrices-for-3d-animation-and-rigging/ — Rigging Dojo: Mastering Matrices
- https://rijahkaz.com/2020/10/22/simplest-way-i-know-for-measuring-distances/ — Matrix-based distance measurement
