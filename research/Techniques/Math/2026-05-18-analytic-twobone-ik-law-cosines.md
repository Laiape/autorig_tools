---
source: https://theorangeduck.com/page/simple-two-joint
found: 2026-05-18
category: math
priority: 1
tags: [maya, python, rigging, math, IK, two-bone, law-of-cosines, analytic, pole-vector, RPsolver, arm, leg]
status: NEW
---

# Analytic Two-Bone IK — Ley de Cosenos, Pole Vector y Implementación Maya

## Descripción
El IK de dos huesos (brazo, pierna) tiene una solución analítica (geométrica) exacta basada en la Ley de Cosenos — no iterativa, sin convergencia, O(1). Es la matemática interna del ikRPsolver de Maya. Entenderla permite: implementar el propio IK solver en un node graph puro (sin ikHandle), recrear el comportamiento en Bifrost, depurar flips del pole vector, y construir IK/FK matching exacto. A diferencia de FABRIK/CCD (que se cubren en otro archivo), el solver analítico solo funciona para cadenas de exactamente 2 bones.

## Fundamento matemático / técnico

### Setup: Geometría del Problema
Given:
- `A` = shoulder/hip position (root joint)
- `B` = elbow/knee position (middle joint)
- `C` = wrist/ankle position (IK effector) = **target**
- `L_upper` = bone length AB (upper arm/thigh)
- `L_lower` = bone length BC (forearm/shin)
- `D` = distance from A to C (|AC|)
- `P` = pole vector target (world position that defines bend plane)

### Step 1: Elbow Angle via Law of Cosines
The triangle ABC has sides `L_upper`, `L_lower`, `D`. Law of cosines gives the angle at B:
```
cos(θ_B) = (L_upper² + L_lower² - D²) / (2 · L_upper · L_lower)
θ_B = arccos(clamp(cos(θ_B), -1, 1))    ← angle of bend at middle joint
```
**Interpretation:**
- `D = L_upper + L_lower` → θ_B = 180° (fully extended, arm straight)
- `D = 0` → θ_B = 0° (arm folded completely on itself)
- `D > L_upper + L_lower` → unreachable; clamp cos to -1: arm stretches toward target at max extension

### Step 2: Shoulder Rotation
The shoulder must rotate so B is in the correct position. Using the law of cosines again for angle at A:
```
cos(θ_A) = (L_upper² + D² - L_lower²) / (2 · L_upper · D)
θ_A = arccos(clamp(cos(θ_A), -1, 1))
```
`θ_A` is the angle between the arm direction (A→C) and the upper bone direction (A→B).

### Step 3: Pole Vector — Bend Plane
The angle computations give magnitudes but not direction. The **pole vector** determines which plane the arm bends in.

**Pole vector algorithm:**
```python
def solve_two_bone_ik(A, B, C, P, L_upper, L_lower):
    """
    A, B, C, P: numpy 3D vectors (joint positions + pole vector target)
    Returns new_B position (elbow position)
    """
    import numpy as np
    
    D = np.linalg.norm(C - A)
    D = max(D, 1e-6)  # avoid division by zero
    
    # Step 1: elbow angle
    cos_B = (L_upper**2 + L_lower**2 - D**2) / (2 * L_upper * L_lower)
    theta_B = np.arccos(np.clip(cos_B, -1.0, 1.0))
    
    # Step 2: shoulder angle
    cos_A = (L_upper**2 + D**2 - L_lower**2) / (2 * L_upper * D)
    theta_A = np.arccos(np.clip(cos_A, -1.0, 1.0))
    
    # Step 3: pole vector defines bend plane
    # Direction from A to C (the "spine" of the arm)
    AC = (C - A) / D
    
    # Direction from A to pole vector, projected onto plane perpendicular to AC
    AP = P - A
    AP_perp = AP - np.dot(AP, AC) * AC  # remove component along AC
    AP_perp_len = np.linalg.norm(AP_perp)
    if AP_perp_len < 1e-6:
        # Pole vector is aligned with AC — no well-defined bend direction
        # Fall back: use world Y as up reference
        up = np.array([0.0, 1.0, 0.0])
        AP_perp = up - np.dot(up, AC) * AC
        AP_perp_len = np.linalg.norm(AP_perp)
    AP_perp = AP_perp / AP_perp_len  # normalized "elbow direction"
    
    # Elbow position: rotate AC by theta_A in the bend plane
    # The bend plane basis: AC (along arm) and AP_perp (elbow direction)
    new_B = A + L_upper * (np.cos(theta_A) * AC + np.sin(theta_A) * AP_perp)
    
    return new_B

# Post-solve: set joint rotations from solved positions
def positions_to_rotations(A, B, C, up_hint=None):
    """
    Convert solved positions to joint rotation matrices.
    Each joint's X axis points along the bone.
    Returns rotation matrices for shoulder and elbow.
    """
    import numpy as np
    
    bone_A = (B - A) / np.linalg.norm(B - A)  # upper bone direction
    bone_B = (C - B) / np.linalg.norm(C - B)  # lower bone direction
    
    # Build rotation matrix for shoulder: X along bone, Y up, Z computed
    if up_hint is None:
        up_hint = np.array([0.0, 1.0, 0.0])
    
    def build_frame(forward, up):
        forward = forward / np.linalg.norm(forward)
        right = np.cross(forward, up)
        right /= np.linalg.norm(right)
        true_up = np.cross(right, forward)
        return np.column_stack([forward, true_up, right])  # [X, Y, Z] columns
    
    R_shoulder = build_frame(bone_A, up_hint)
    R_elbow    = build_frame(bone_B, up_hint)
    return R_shoulder, R_elbow
```

### Maya Node Graph Implementation (No ikHandle)
Building a pure node-based 2-bone IK solver. The key challenge: `arccos` is not natively available as a simple DG node, but can be approximated or accessed via specific paths:

**Approach 1 — Maya Bifrost (recommended for modern pipelines):**
Bifrost Graph contains native trig nodes: `acos`, `atan2`, `dot_product`, etc. This is the cleanest implementation.

**Approach 2 — Expression-free using law of cosines approximation:**
```
# Instead of acos, use:
# For the joint rotation from position-space solved positions:
# multMatrix to get local B pos relative to A, then decomposeMatrix for rotation
# This avoids needing acos explicitly — convert to rotation via matrix
```

**Approach 3 — Python custom node (MPxNode):**
```python
import maya.api.OpenMaya as om

class TwoBoneIKNode(om.MPxNode):
    """
    Custom node: inputs = root_pos, effector_pos, pole_pos, upper_len, lower_len
    output = elbow_pos (world position)
    """
    kNodeName = "twoBoneIK"
    kNodeId = om.MTypeId(0x00123456)  # use registered ID range
    
    # Attribute definitions...
    def compute(self, plug, data):
        if plug == self.elbow_output:
            A = data.inputValue(self.root_input).asFloatVector()
            C = data.inputValue(self.effector_input).asFloatVector()
            P = data.inputValue(self.pole_input).asFloatVector()
            L1 = data.inputValue(self.upper_len).asFloat()
            L2 = data.inputValue(self.lower_len).asFloat()
            
            import numpy as np
            A = np.array([A.x, A.y, A.z])
            C = np.array([C.x, C.y, C.z])
            P = np.array([P.x, P.y, P.z])
            new_B = solve_two_bone_ik(A, C, C, P, L1, L2)
            
            out = data.outputValue(self.elbow_output)
            out.setMFloatVector(om.MFloatVector(new_B[0], new_B[1], new_B[2]))
```

### IK/FK Matching (Exact)
The analytic solver enables **exact** IK→FK matching. Given IK bone positions, the FK joint rotations are computed deterministically:
```python
def ik_to_fk_match(shoulder_jnt, elbow_jnt, wrist_jnt):
    """Snap FK chain to match current IK positions."""
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    
    A = cmds.xform(shoulder_jnt, q=True, ws=True, t=True)
    B = cmds.xform(elbow_jnt, q=True, ws=True, t=True)
    C = cmds.xform(wrist_jnt, q=True, ws=True, t=True)
    
    # Get world-space rotation from positions and apply to FK controls
    # (simplified — actual implementation needs parent space conversion)
    cmds.matchTransform('fk_shoulder_ctrl', shoulder_jnt, rot=True)
    cmds.matchTransform('fk_elbow_ctrl', elbow_jnt, rot=True)
    cmds.matchTransform('fk_wrist_ctrl', wrist_jnt, rot=True)
```

### Unreachable Target Handling
When `D > L_upper + L_lower`, the target is out of reach:
- **Hard clamp:** `D_effective = L_upper + L_lower` → arm stretches fully toward target
- **Soft stretch:** `D_effective = L_upper + L_lower + k*(D - (L_upper+L_lower))` for a stretch factor → arm stretches beyond rest length proportionally (the common "stretchy IK" behavior)

The stretch factor computation is the link between this analytic IK and the volume preservation math (see `2026-05-11-volume-preservation-stretch-squash-math.md`).

## Implementación en Maya

**Linking to autorig_tools IK/FK match:**
The current autorig_tools IK/FK matching should use this analytic computation to avoid iterative solutions or Maya's own matching which can drift. The key: when matching FK → IK, extract the pole vector from the current FK chain's elbow position, not from a fixed world position.

```python
def get_pole_vector_from_fk(shoulder, elbow, wrist, multiplier=3.0):
    """Compute ideal pole vector position from FK chain."""
    import numpy as np, maya.cmds as cmds
    
    A = np.array(cmds.xform(shoulder, q=True, ws=True, t=True))
    B = np.array(cmds.xform(elbow, q=True, ws=True, t=True))
    C = np.array(cmds.xform(wrist, q=True, ws=True, t=True))
    
    AC = C - A
    AB = B - A
    # Project B onto AC
    proj = np.dot(AB, AC) / np.dot(AC, AC) * AC
    perp = AB - proj  # component of elbow perpendicular to AC
    
    # Pole vector = midpoint of chain + exaggerated perpendicular
    mid = A + 0.5 * AC
    pole_pos = mid + multiplier * perp
    return pole_pos.tolist()
```

## Comparación con autorig_tools
El solver analítico de 2 bones es la base matemática del IK de brazos y piernas en autorig_tools. Si el pipeline actual usa Maya ikHandle + ikRPsolver, toda esta matemática ocurre implícitamente. Conocerla permite: (1) implementar IK/FK matching exacto sin iteraciones, (2) calcular automáticamente la posición del pole vector control desde la pose FK, y (3) detectar cuándo el elbow flip está a punto de ocurrir (cuando `|perp|` → 0) para advertir al rigger.

## Aplicable directamente
YES — La función `get_pole_vector_from_fk()` puede integrarse en el sistema de IK/FK matching de autorig_tools como utilidad de build. La detección de flip (`perp_length < threshold → warn`) es un check de validación de guía aplicable en el proceso de build del rig.

## Fuente
- The Orange Duck (Daniel Holden) — Simple Two Joint IK: https://theorangeduck.com/page/simple-two-joint
- Ryan Juckett — Analytic Two-Bone IK in 2D: https://www.ryanjuckett.com/analytic-two-bone-ik-in-2d/
- FABRIK paper (iterative complement): https://www.andreasaristidou.com/publications/papers/FABRIK.pdf
- Autodesk Maya IK Solvers: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-952FC4B3-19A6-4055-B034-3A7D15EC66D6
