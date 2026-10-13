---
source: https://github.com/serguei-k/maya-math-nodes | https://maya-math-nodes.readthedocs.io/en/latest/node_reference.html
found: 2026-06-08
category: tool
priority: 3
tags: [maya, python, C++, math-nodes, performance, parallel-evaluation, rigging, expressions, nodes, open-source, github]
status: NEW
---

# maya-math-nodes (serguei-k) — Librería C++ de Nodos Matemáticos para Maya

## Descripción
maya-math-nodes es una librería de nodos matemáticos para Autodesk Maya escrita en C++, mantenida por Serguei Kalentchouk. Proporciona operaciones matemáticas atómicas que los nodos nativos de Maya no incluyen: trigonometría inversa, smoothstep, remap, operaciones de cuaternión, construcción de matrices desde vectores, y lógica booleana. Diseñado para reemplazar expression nodes y Python-driven networks por nodos compilados paralelo-compatibles. La librería incluye además un lenguaje de expresiones que genera automáticamente redes de nodos a partir de texto.

## Fundamento matemático / técnico

### Why Native Maya Nodes Are Insufficient

Maya's built-in math nodes cover basic operations (`multiplyDivide`, `addDoubleLinear`, `clampColors`) but lack:
- Trigonometric inverse functions: `asin`, `acos`, `atan`, `atan2`
- Smooth interpolation: `smoothstep`, `smootherstep`
- Remapping with custom curves: `remap`
- Quaternion arithmetic: `quat_multiply`, `quat_slerp`, `quat_conjugate`, `quat_normalize`
- Matrix construction from vectors: `matrixFromDirection`, `matrixFromRotation`
- Boolean logic: `notBool`, `andBool`, `orBool`, `xorBool`
- Exponential/logarithmic functions: `exp`, `log`, `pow`, `sqrt`

When riggers need these, they typically resort to:
1. **Expression nodes** — MEL/Python at evaluation time, force serialization, break parallel scheduling
2. **Python MPxNodes** — GIL-bound, cannot be scheduled `kParallel`
3. **Approximations** with existing nodes (e.g., `atan2` approximated via lookup table in animCurve)

maya-math-nodes provides all of these as **compiled C++ nodes** declared with `MPxNode::kParallel` scheduling, making them safe for parallel evaluation.

### Node Categories and Types

| Category | Nodes | Operation |
|----------|-------|-----------|
| **Arithmetic** | `AbsoluteFloat/Int`, `AddFloat/Int/Vector/Matrix`, `SubtractFloat/Int/Vector/Matrix`, `MultiplyFloat/Int/Vector/Matrix`, `DivideFloat/Int`, `ModulusFloat/Int` | Basic math |
| **Trigonometric** | `SinFloat`, `CosFloat`, `TanFloat`, `AsinFloat`, `AcosFloat`, `AtanFloat`, `Atan2Float` | Trig + inverse trig |
| **Exponential** | `SqrtFloat`, `PowFloat`, `ExpFloat`, `LogFloat` | Power/exponential |
| **Interpolation** | `SmootstepFloat/Vector`, `Remap`, `ClampFloat/Int/Vector` | Smooth/remap |
| **Logic** | `NotBool`, `AndBool`, `OrBool`, `XorBool`, `ConditionFloat/Int/Vector/Matrix` | Boolean ops |
| **Vector** | `NormalizeVector`, `DotProductVector`, `CrossProductVector`, `LengthVector`, `AngleBetweenVector`, `RotateVector` | Vector ops |
| **Matrix** | `MultiplyMatrix`, `InverseMatrix`, `TransposeMatrix`, `MatrixFromDirection`, `MatrixFromRotation`, `MatrixFromQuaternion` | Matrix ops |
| **Quaternion** | `ConjugateQuaternion`, `MultiplyQuaternion`, `NormalizeQuaternion`, `SlerpQuaternion`, `QuaternionToEuler`, `EulerToQuaternion` | Quat ops |
| **Debug** | `DebugLog` | Print to console |
| **Min/Max** | `MinFloat/Int/Vector`, `MaxFloat/Int/Vector` | Range ops |

### Expression Language

The expression language compiles text math expressions into node networks:

```
# Example: compute the distance between two world positions using only math nodes
distance(pos_a, pos_b) → sqrt((pos_a.x - pos_b.x)^2 + (pos_a.y - pos_b.y)^2 + ...)

# Expression string: "sqrt(pow(a.x - b.x, 2) + pow(a.y - b.y, 2) + pow(a.z - b.z, 2))"
```

Each function call in the expression maps to a node type:
- `abs(x)` → `AbsoluteFloat`
- `sin(x)` → `SinFloat`
- `smoothstep(edge0, edge1, x)` → `SmoothstepFloat`
- `slerp(q1, q2, t)` → `SlerpQuaternion`
- `normalize(v)` → `NormalizeVector`

This eliminates manual node creation for complex math chains.

### Parallel Evaluation Safety

All C++ nodes in maya-math-nodes declare:
```cpp
MPxNode::setMPSafe(true);
// Scheduling type: kParallel
// Thread-safe compute(), no global state, no Maya scene access
```

Contrast with **Python MPxNode**:
- Cannot be `kParallel` because Python's GIL (Global Interpreter Lock) prevents concurrent execution
- Forces the entire DG cluster containing the Python node to serialize
- One Python node in a parallel branch = that branch loses all parallelism

A C++ node from maya-math-nodes in the same position: fully parallel, scheduling overhead only.

### Build and Installation

```bash
# Requirements: CMake 3.x, Maya devkit, C++11 compiler
git clone https://github.com/serguei-k/maya-math-nodes
cd maya-math-nodes
mkdir build && cd build
cmake .. -DMAYA_LOCATION=/usr/autodesk/maya2024 -DCMAKE_BUILD_TYPE=Release
make -j4

# Install: copy plugin + module file to Maya module path
cp maya_math_nodes.so ~/.maya/2024/plug-ins/
cp ../module/maya-math-nodes.mod ~/.maya/modules/
```

**Note**: No distributable binaries — must build from source per Maya version. This is the main adoption barrier.

## Implementación en Maya

```python
import maya.cmds as cmds

# Load plugin (after building from source)
cmds.loadPlugin('maya_math_nodes')

# Example: pure-math aim constraint replacement (no aimConstraint node)
# Goal: compute rotation matrix from "from_pos" to "to_pos" with a given up vector
# Without maya-math-nodes: requires expression node or Python callback
# With maya-math-nodes:

# 1. Compute direction vector: to_pos - from_pos
sub_node = cmds.createNode('SubtractVector')
cmds.connectAttr('target_locator.worldPosition[0]', sub_node + '.input1')
cmds.connectAttr('source_locator.worldPosition[0]', sub_node + '.input2')

# 2. Normalize direction
norm_node = cmds.createNode('NormalizeVector')
cmds.connectAttr(sub_node + '.output', norm_node + '.input')

# 3. Build rotation matrix from direction + world up
aim_matrix = cmds.createNode('MatrixFromDirection')
cmds.connectAttr(norm_node + '.output', aim_matrix + '.forward')
cmds.setAttr(aim_matrix + '.up', 0, 1, 0)  # world Y up

# 4. Decompose and drive joint rotation
dcmp = cmds.createNode('decomposeMatrix')
cmds.connectAttr(aim_matrix + '.outputMatrix', dcmp + '.inputMatrix')
cmds.connectAttr(dcmp + '.outputRotate', 'driven_joint.rotate')

# ── Full aim constraint replacement: 4 nodes, all C++, all kParallel ──

# Example: Smoothstep SDK replacement
# Standard SDK: animCurve node (CPU, not GPU-friendly for complex curves)
# maya-math-nodes smoothstep: compiled, parallel

smooth = cmds.createNode('SmoothstepFloat')
cmds.setAttr(smooth + '.edge0', 0.0)
cmds.setAttr(smooth + '.edge1', 1.0)
cmds.connectAttr('control.bend_attr', smooth + '.input')
cmds.connectAttr(smooth + '.output', 'blend_attr.w')
# Result: smooth S-curve interpolation without animCurve node overhead

# Expression language example
import maya_math_nodes  # hypothetical Python binding
network = maya_math_nodes.build_from_expression(
    "sqrt(pow(pos_a.x - pos_b.x, 2) + pow(pos_a.y - pos_b.y, 2) + pow(pos_a.z - pos_b.z, 2))",
    inputs={'pos_a': 'joint_a.worldPosition', 'pos_b': 'joint_b.worldPosition'},
    output='distance_result.input'
)
```

### Key Use Cases for Rigging

1. **Trig without expression nodes**: `sin`/`cos`/`atan2` for procedural joint orientations
2. **Smoothstep for corrective activation**: smooth S-curve blending without animCurve nodes
3. **Quaternion SLERP in-graph**: `SlerpQuaternion` for in-DG quaternion blending without SDK
4. **MatrixFromDirection**: replaces `aimConstraint` with a pure matrix node
5. **DebugLog**: non-destructive debug output during rig development

## Comparación con autorig_tools

El archivo de Maya 2025-05-25 sobre MPxNode y GIL identificó `maya-math-nodes` como la solución recomendada para reemplazar nodos Python. Este archivo confirma la implementación concreta: la librería provee exactamente las operaciones matemáticas que autorig_tools necesita y que no existen como nodos nativos en Maya. El diferencial crítico frente a expression nodes o Python callbacks: son nodos C++ `kParallel`, por lo que no rompen la evaluación paralela. La barrera es la compilación — requiere devkit de Maya y CMake. Para un pipeline estable, compilar una versión por Maya version y distribuir como .mod es la práctica estándar.

## Aplicable directamente

PARTIAL — Requiere compilación desde fuente (CMake + devkit). Sin embargo:
1. La librería está bien documentada y el proceso de build es estándar
2. Una vez compilado para la versión de Maya de Laia, se integra como cualquier otro plugin
3. **Prioridad alta para autorig_tools**: reemplazar cualquier expression node o Python node de rigging con equivalentes de maya-math-nodes. Elimina `locally_serialize` del grafo de evaluación.
4. Tiempo estimado: medio día para compilar y verificar la build + 1-2 días para migrar los nodos más frecuentes.
5. Nodos más relevantes para autorig_tools: `SmoothstepFloat`, `MatrixFromDirection`, `SlerpQuaternion`, `AtanFloat`, `AsinFloat`

## Fuente
- GitHub: https://github.com/serguei-k/maya-math-nodes
- Documentación: https://maya-math-nodes.readthedocs.io/en/latest/node_reference.html
- Expression language: https://maya-math-nodes.readthedocs.io/en/latest/expression_language.html
- Releases: https://github.com/serguei-k/maya-math-nodes/releases
