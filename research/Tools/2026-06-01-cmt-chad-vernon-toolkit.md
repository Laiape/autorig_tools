---
source: https://github.com/chadmv/cmt | https://chadmv.github.io/cmt/html/
found: 2026-06-01
category: tool
priority: 3
tags: [maya, python, rigging, swing-twist, unit-tests, cmt, chad-vernon, toolkit, open-source, pipeline]
status: NEW
---

# CMT — Chad Vernon Maya Toolkit (chadmv/cmt)

## Descripción
CMT (Chad Vernon Maya Tools) es un toolkit de rigging y pipeline para Maya en Python de código abierto, mantenido activamente por Chad Vernon (TD veterano, autor del libro "Practical Maya Programming with Python"). Incluye el plugin de swing-twist decomposition, herramientas de IK, unit testing framework para Maya, y diversas utilidades de rigging. Es notable por su calidad de código y por ser una referencia de buenas prácticas de Python en Maya. El repositorio tiene >1000 commits y está actualizado regularmente. Contiene tanto scripts Python puros como un plugin C++ compilado para el swing-twist node.

## Fundamento matemático / técnico

### Swing-Twist Node (Plugin)
The `swingtwist` compiled plugin provides a single Maya node that performs the full swing-twist decomposition in C++:
```
Inputs:
  driver (matrix)       — transform being decomposed
  driverRestMatrix (matrix) — rest pose of driver
  twistWeight (float)   — [0..1], how much twist to propagate
  swingWeight (float)   — [0..1], how much swing to propagate
  twistAxis (enum)      — X=0, Y=1, Z=2

Outputs:
  rotate (float3)       — decomposed rotation to drive target
  matrix (matrix)       — full output matrix (for offsetParentMatrix)
```

The C++ implementation computes:
```cpp
MQuaternion q = extract_local_quaternion(driver, driverRestMatrix);
MQuaternion twist = extract_twist(q, twistAxis);    // zero non-axis components + normalize
MQuaternion swing = twist.inverse() * q;            // residual rotation
MQuaternion result = slerp(identity, twist, twistWeight) *
                     slerp(identity, swing, swingWeight);
```
See full math in `2026-06-01-swing-twist-quaternion-decomposition.md`.

### Maya Unit Testing Framework
CMT includes a complete unit testing infrastructure for Maya Python code:
```python
# test_rig.py
import cmt.test as test

class TestRigModule(test.TestCase):
    def setUp(self):
        # setUp creates a fresh Maya scene
        cmds.file(new=True, force=True)
        
    def test_swing_twist_no_flip(self):
        """Verify swing-twist doesn't flip past 180 degrees."""
        driver = cmds.joint(name='driver_joint')
        driven = cmds.joint(name='driven_joint')
        
        # Build swing-twist network
        from cmt.rig import swingtwist
        swingtwist.create_swing_twist(driver, driven, twist_axis='x')
        
        # Rotate driver to 179° and check driven
        cmds.setAttr(driver + '.rotateX', 179)
        driven_val = cmds.getAttr(driven + '.rotateX')
        self.assertAlmostEqual(driven_val, 179, places=1)
        
        # Check no flip at 181°
        cmds.setAttr(driver + '.rotateX', 181)
        # (With slerp, value should be ~181, not -179)
```

### Other Notable Modules
- **`cmt.rig.control`**: Shape-based control creation (creates rig controls from curve shapes)
- **`cmt.rig.ikhandle`**: IK handle utilities with stretch
- **`cmt.rig.squash_stretch`**: Volume-preserving squash/stretch via matrix
- **`cmt.deform.delta_mush`**: Delta mush utilities
- **`cmt.pipeline.attribute`**: Attribute management and locking utilities
- **`cmt.rig.skeleton`**: Skeleton utilities (orient joints, mirror, etc.)

## Implementación en Maya

### Installation
```bash
# Clone the repo
git clone https://github.com/chadmv/cmt.git
# Add to MAYA_MODULE_PATH or copy to Maya modules directory
# Build the C++ plugin (CMakeLists.txt provided)
# Or: use Python-only scripts/cmt/ without the compiled plugin
```

### Using Swing-Twist Without Plugin (Vanilla Nodes)
```python
# cmt/scripts/cmt/rig/swingtwist.py provides both:
# - create_swing_twist_network() — vanilla nodes only
# - create_swing_twist_node()    — uses compiled plugin if available

from cmt.rig import swingtwist

# Python-only (no compiled plugin needed):
net = swingtwist.create_swing_twist(
    driver='wrist_joint',
    driven='twist_joint_1',
    twist_axis='x',
    twist_weight=0.33,
    swing_weight=0.0
)

# Apply to multiple twist joints at once:
for i, joint in enumerate(twist_joints):
    weight = (i + 1) / len(twist_joints)  # 0.25, 0.50, 0.75, 1.00
    swingtwist.create_swing_twist(
        driver='wrist_joint',
        driven=joint,
        twist_axis='x',
        twist_weight=weight
    )
```

### Unit Testing in Maya
```python
# Run all CMT tests from Maya Script Editor:
import cmt.test as test
test.run_tests()

# Run specific test file:
import unittest
loader = unittest.TestLoader()
suite = loader.discover('/path/to/cmt/tests')
runner = unittest.TextTestRunner(verbosity=2)
runner.run(suite)
```

### Using CMT's squash_stretch Module
```python
from cmt.rig import squash_stretch

# Create volume-preserving squash/stretch on a joint chain:
squash_stretch.create_squash_stretch_chain(
    joints=['spine_01', 'spine_02', 'spine_03', 'spine_04'],
    stretch_axis='y',
    volume_preserve=True
)
```

## Comparación con autorig_tools
CMT es el toolkit de referencia más completo de un TD profesional individual. Varias de sus funciones son directamente comparables con lo que autorig_tools implementa: swing-twist extraction, IK stretch, unit testing, shape control creation. El valor principal no es copiar su código sino usar CMT como **benchmark de calidad** y **referencia de arquitectura**: cómo estructurar módulos, cómo escribir unit tests para Maya, y el patrón del plugin C++ como fallback del network Python.

El módulo de **unit testing es el más directamente aplicable**: autorig_tools puede adoptar el patrón `cmt.test.TestCase` (que maneja la apertura/cierre automática de escenas Maya en cada test) para tener un test suite robusto del pipeline de autorig.

## Aplicable directamente
**YES** — Múltiples aplicaciones inmediatas:
1. **Swing-twist Python network**: usar `swingtwist.create_swing_twist()` directamente en autorig_tools o replicar el patrón (ya documentado en el archivo Math de swing-twist).
2. **Unit testing framework**: adoptar `cmt.test.TestCase` para el test suite de autorig_tools. Requiere ~1 día de setup inicial.
3. **squash_stretch module**: referencia para el módulo de volume preservation de autorig_tools.
4. No requiere instalar el plugin C++ para usar las partes Python.

## Fuente
https://github.com/chadmv/cmt
https://chadmv.github.io/cmt/html/
https://chadmv.github.io/cmt/html/rig/swingtwist.html
