---
source: https://github.com/serguei-k/maya-math-nodes
found: 2026-05-18
category: tool
priority: 3
tags: [maya, python, C++, math-nodes, expression-replacement, performance, rigging, nodes, plugin, github]
status: NEW
---

# Maya Math Nodes (Serguei Kalentchouk) — Nodos Matemáticos C++ para Reemplazar Expressions

## Descripción
maya-math-nodes es un plugin C++ open-source para Autodesk Maya que provee más de 100 nodos matemáticos atómicos de alto rendimiento, diseñados específicamente para reemplazar expression nodes en rigs y eliminar el overhead de Python/MEL en el grafo de evaluación. Desarrollado por Serguei Kalentchouk (Apple Research, autor de papers sobre Delta Mush adaptativo). La versión v1.3 añadió un lenguaje de expresiones inline que genera automáticamente el grafo de nodos desde una cadena matemática, resolviendo el problema de que los nodos son poderosos pero tediosos de conectar manualmente.

## Fundamento matemático / técnico

### Design Philosophy
Each node performs **exactly one operation** and has **exactly one output attribute**. This makes the node graph:
- Maximally parallelizable (each node is an independent computation unit)
- Debuggable at any intermediate step
- Composable into arbitrarily complex expressions

Contrast with Maya's `multiplyDivide` node which does 3 operations (multiply, divide, power) — less clean scheduling.

### Node Categories

**Arithmetic:**
- `Add`, `Subtract`, `Multiply`, `Divide` — scalar, vector, matrix variants
- `Power`, `Sqrt`, `Absolute`, `Negate`
- `Clamp`, `Remap` — useful for weight clamping and remapping
- `Lerp` — linear interpolation (replaces wtAddMatrix for scalar values)
- `Smoothstep` — S-curve interpolation (replaces complex remapValue setups)

**Trigonometry (the critical category):**
- `Sin`, `Cos`, `Tan` — returns float
- `Asin`, `Acos`, `Atan`, `Atan2` — **inverse trig with proper range handling**
- `DegreesToRadians`, `RadiansToDegrees`
- These are the nodes that allow implementing the analytic 2-bone IK solver entirely in the DG without expressions

**Vectors:**
- `VectorLength`, `VectorNormalize`
- `VectorDot`, `VectorCross`
- `VectorAdd`, `VectorSubtract`, `VectorMultiply`
- `VectorProjection` — projects one vector onto another (useful for pole vector computation)
- `VectorRotateByMatrix`, `VectorRotateByQuat`
- `AngleBetweenVectors` — returns angle in radians (wraps dot product and acos cleanly)

**Quaternions:**
- `QuatAdd`, `QuatMultiply`, `QuatNegate`, `QuatNormalize`, `QuatConjugate`
- `QuatToEuler`, `EulerToQuat`
- `QuatToMatrix`, `MatrixToQuat`
- `QuatSlerp` — pure C++ SLERP in the node graph (no expressions)
- `QuatSwingTwist` — directly extracts swing+twist components (one node vs the 3-node chain)

**Matrices:**
- `MatrixAdd`, `MatrixSubtract`, `MatrixMultiply`
- `MatrixInverse`, `MatrixTranspose`
- `MatrixDecompose` — extract translate/rotate/scale without decomposeMatrix overhead
- `MatrixCompose` — build matrix from TRS

**Conditions / Logic:**
- `Greater`, `Less`, `Equal`, `NotEqual`
- `Condition` — if/else for floats (replaces condition node)
- `Select` — select between two values based on bool

### Expression Language (v1.3)
The expression language allows describing a math node network inline:
```
# Instead of creating 5 nodes manually:
result = "(length - rest_length) / rest_length"  # stretch ratio

# Build the node network from the string:
import maya_math_nodes.expression_builder as eb

graph = eb.build_expression(
    "(length - rest_length) / rest_length",
    variables={'length': 'ik_chain.outputDistance',
               'rest_length': 10.5},  # constant
    output_attr='stretch_node.input'
)
```
The builder parses the expression and creates the minimum node graph needed, connecting inputs and outputs automatically.

**Supported operators in expression language:**
- Arithmetic: `+`, `-`, `*`, `/`, `^` (power)
- Functions: `sin()`, `cos()`, `abs()`, `sqrt()`, `clamp()`, `lerp()`, `smoothstep()`
- Comparison: `>`, `<`, `==`, `!=`, `&&`, `||`
- Vector construction: `[x, y, z]`

### Performance vs Native Maya Nodes

| Operation | maya-math-nodes | Maya built-in |
|-----------|----------------|---------------|
| Scheduling | `parallel` (C++ declared) | Varies — many are `locally_serialize` |
| Expression replacement | C++ speed | Python/MEL: 10-100× slower |
| `Atan2` | Yes, native node | Not available natively; needs expression |
| `Acos` | Yes, native node | Not available natively; needs expression |
| QuatSlerp | Single C++ node | 5+ nodes (decomposeMatrix + custom logic) |
| `Smoothstep` | Single node | remapValue node (heavier) |

**Key advantage over Maya 2024's "36 new math nodes":** maya-math-nodes was designed from scratch for parallel scheduling; Maya 2024's new nodes inherit the legacy attribute evaluation system and may have more overhead per-node.

## Implementación en Maya

```python
# Installation: compile C++ plugin or download binary for your Maya version
# GitHub: https://github.com/serguei-k/maya-math-nodes/releases

import maya.cmds as cmds

# Load plugin (add to userSetup.py for permanent loading)
cmds.loadPlugin('maya_math_nodes')

# ─── EXAMPLE: Analytic elbow angle using law of cosines ───────────────────
# Instead of an expression: cos_B = (L1^2 + L2^2 - D^2) / (2 * L1 * L2)

# Create nodes
sq_l1 = cmds.createNode('Power', n='upper_sq')
cmds.setAttr(f'{sq_l1}.input2', 2.0)  # square

sq_l2 = cmds.createNode('Power', n='lower_sq')
cmds.setAttr(f'{sq_l2}.input2', 2.0)

sq_d = cmds.createNode('Power', n='dist_sq')
cmds.setAttr(f'{sq_d}.input2', 2.0)

# (L1² + L2² - D²)
sum_sq = cmds.createNode('Add', n='sum_squares')
diff = cmds.createNode('Subtract', n='diff_squares')

# 2 * L1 * L2
prod = cmds.createNode('Multiply', n='prod_lengths')
double = cmds.createNode('Multiply', n='double_prod')
cmds.setAttr(f'{double}.input2', 2.0)

# cos_B = numerator / denominator
cos_b = cmds.createNode('Divide', n='cos_elbow')

# theta_B = acos(cos_B)
theta_b = cmds.createNode('Acos', n='theta_elbow')

# ─── EXAMPLE: Expression language for stretch IK ─────────────────────────
# Build the entire stretch ratio computation from one expression string:
from maya_math_nodes.expression_builder import build_expression

# Stretch factor: max(1.0, current_length / rest_length)
expr = "max(1.0, ik_length / 10.5)"
# build_expression would create: Divide + Max nodes, connected to ik_length attr

# ─── EXAMPLE: QuatSwingTwist replacing 3-node pattern ────────────────────
# Old way: decomposeMatrix → zero Y/Z → quatNormalize → quatToEuler (3 nodes)
# New way: single QuatSwingTwist node
swing_twist = cmds.createNode('QuatSwingTwist', n='forearm_swingTwist')
cmds.connectAttr('forearm_jnt.worldMatrix[0]', f'{swing_twist}.inputMatrix')
cmds.setAttr(f'{swing_twist}.twistAxis', 0)  # 0=X, 1=Y, 2=Z
# Output: swingTwist.outputTwistAngle directly gives the twist in radians
```

**Key replacement table for autorig_tools:**

| Current pattern | maya-math-nodes replacement |
|----------------|---------------------------|
| expression `${A} = ${B} * ${C}` | `Multiply` node |
| expression with `sin(X)` | `Sin` node |
| expression with `atan2(y, x)` | `Atan2` node (not available in vanilla Maya) |
| 3-node swing-twist extract | `QuatSwingTwist` node |
| `remapValue` for soft clamping | `Smoothstep` node |
| `condition` node | `Condition` node (cleaner API) |
| `vectorProduct` dot + `acos` for angle | `AngleBetweenVectors` node |

## Comparación con autorig_tools
autorig_tools usa matrix nodes nativos de Maya (multMatrix, decomposeMatrix, etc.) como patrón base — exactamente la filosofía de maya-math-nodes aplicada a matrices. El gap está en que para operaciones trigonométricas y condicionales complejas, autorig_tools probablemente usa expresiones o nodos multiplyDivide encadenados de formas subóptimas. Instalar maya-math-nodes como dependencia del pipeline permitiría eliminar todas las expresiones restantes y tener acceso a Acos, Atan2, y QuatSwingTwist como nodos nativos declarados parallel-safe.

## Aplicable directamente
PARTIAL — Requiere compilar o descargar el binario para la versión de Maya del equipo (no es un script Python puro). Una vez instalado, el impacto más inmediato para autorig_tools es: (1) reemplazar cualquier expression restante con nodos Multiply/Divide/Add de maya-math-nodes, (2) usar `QuatSwingTwist` en el ribbon y el extractor de twist, (3) usar `AngleBetweenVectors` para cálculos de ángulos en el poser de pole vector.

## Fuente
- GitHub: https://github.com/serguei-k/maya-math-nodes
- Documentation: https://maya-math-nodes.readthedocs.io/en/stable/
- Expression language blog: https://medium.com/@k_serguei/creating-a-simple-expression-language-9c2aa981f4ca
- Expression builder reference: https://maya-math-nodes.readthedocs.io/en/latest/expression_language.html
