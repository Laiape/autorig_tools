---
source: https://www.andreasaristidou.com/publications/papers/FABRIK.pdf | https://www.cs.cmu.edu/~15464-s13/lectures/lecture6/iksurvey.pdf | https://saeed1262.github.io/blog/2025/inverse-kinematics-models/
found: 2026-06-15
category: math
priority: 1
tags: [maya, IK, FABRIK, CCD, iterative-solver, inverse-kinematics, N-joint, multi-chain, convergence, rigging, math]
status: NEW
---

# FABRIK & CCD — Solvers Iterativos de IK para Cadenas N-Joint

## Descripción
FABRIK (Forward And Backward Reaching Inverse Kinematics, Aristidou & Lasenby, 2011) y CCD (Cyclic Coordinate Descent) son los dos solvers iterativos más usados en rigging para cadenas de IK con más de dos huesos, donde la solución analítica de la ley de cosenos no aplica. A diferencia del solver analítico de dos huesos (cubierto en 2026-05-18), estos solvers son genéricos para N joints y soportan múltiples end-effectors. Este archivo cubre sus matemáticas, comparativa de convergencia, y cómo ambos pueden implementarse en Python para usarlos fuera del sistema IK nativo de Maya.

## Fundamento matemático / técnico

### Setup: N-Joint Kinematic Chain

Given a chain of N+1 joints p_0, p_1, ..., p_N with:
- `p_0` = root joint (fixed position)
- `p_N` = end effector
- `l_i` = bone length between p_i and p_{i+1} (constant)
- `t` = target position
- `tol` = tolerance (e.g., 0.001 units)

Goal: find positions p_0, ..., p_{N-1} such that p_N ≈ t, with each bone length preserved.

---

### FABRIK Algorithm

FABRIK finds new joint positions by locating points on line segments — no rotation matrices or angles needed. Each iteration has two passes:

#### Forward Pass (end effector → root):
```
p_N = t                           # move end effector to target
for i = N-1 downto 0:
    r_i  = |p_{i+1} - p_i|       # distance: current joint to its child
    λ_i  = l_i / r_i              # scale factor to preserve bone length
    p_i  = (1 - λ_i) * p_{i+1} + λ_i * p_i  # place joint at bone-length from child
```
This "reaches forward" — the root drifts off its original position.

#### Backward Pass (root → end effector):
```
p_0 = b                           # reset root to original position b
for i = 0 to N-1:
    r_i  = |p_{i+1} - p_i|       # distance: current joint to its child
    λ_i  = l_i / r_i
    p_{i+1} = (1 - λ_i) * p_i + λ_i * p_{i+1}  # push child along bone dir
```

#### Convergence Criterion:
```
while |p_N - t| > tol AND iterations < max_iter:
    forward_pass()
    backward_pass()
    iterations++
```

If the target is unreachable (|t - p_0| > Σ l_i), the chain stretches toward the target without converging — this must be checked before the loop:
```
d = |t - p_0|
if d > sum(l_i):
    # Unreachable: point all joints toward target
    for i = 0 to N-1:
        r = |t - p_i|; λ = l_i / r
        p_{i+1} = (1-λ) * p_i + λ * t
```

**Convergence speed:** FABRIK typically converges in 3-10 iterations for reachable targets. Compare: CCD needs ~26 iterations on average; Jacobian ~15-20.

---

### CCD Algorithm (Cyclic Coordinate Descent)

CCD rotates each joint one at a time to minimize the distance from the end effector to the target. It works with angles, not positions.

#### One CCD Iteration (backward, from end to root):
```
for i = N-1 downto 0:
    # Vector from joint i to end effector (current)
    e_i = normalize(p_N - p_i)
    # Vector from joint i to target
    g_i = normalize(t - p_i)
    
    # Rotation axis to align e to g:
    axis = normalize(cross(e_i, g_i))
    
    # Rotation angle (clamped to joint limits):
    angle = arccos(clamp(dot(e_i, g_i), -1, 1))
    
    # Apply rotation to joint i and update all children:
    R_i = rotation_matrix(axis, angle)
    for j = i+1 to N:
        p_j = p_i + R_i * (p_j - p_i)
```

**Advantages of CCD:**
- Naturally works with joint angle limits (clamp `angle`)
- Easy to add joint constraints (orientation cones, hinge joints)

**Disadvantages:**
- Slower convergence than FABRIK (~26 iterations average)
- Can produce unrealistic oscillating postures
- At singularities (near-linear chain), CCD can stall

---

### Jacobian Pseudoinverse (DLS — Damped Least Squares)

The Jacobian approach models IK as a linear system:
```
Δx = J · Δθ
```
Where:
- `Δx` ∈ ℝ³ = desired end-effector displacement (3D)
- `Δθ` ∈ ℝ^N = joint angle changes (N joints)
- `J` ∈ ℝ^{3×N} = Jacobian matrix (how end effector moves with each joint)

**Jacobian column i** (for revolute joint i with axis n̂_i):
```
J_col_i = cross(n̂_i, (p_N - p_i))   [translational effect]
```

**Pseudoinverse (Moore-Penrose):** When N > 3 (redundant chain):
```
J^+ = J^T * (J * J^T)^{-1}
```

**Damped Least Squares (DLS):** Stable near singularities:
```
Δθ = J^T * (J * J^T + λ² * I)^{-1} * Δx
```
Where λ is the damping factor. When near singularity (det(J*J^T) ≈ 0), DLS makes joints move smoothly through the singularity instead of exploding.

**Convergence:** ~15-20 iterations. Best for redundant chains (6+ DOF) and humanoid IK requiring secondary objectives (minimize joint velocity, avoid obstacles). More complex to implement than FABRIK.

---

### Comparison Table

| Property              | Analytic (2-bone) | FABRIK         | CCD               | Jacobian DLS         |
|-----------------------|-------------------|----------------|-------------------|----------------------|
| Chain length          | Exactly 2 bones   | N bones        | N bones           | N bones              |
| Implementation        | O(1), trivial     | Simple         | Moderate          | Complex (matrix math)|
| Speed (iterations)    | 1 (exact)         | 3-10           | ~26 avg           | ~15-20               |
| Joint constraints     | None native       | Cone/hinge ext | Natural           | Via null space       |
| Multi-end-effector    | No                | Yes            | Separate chains   | Yes (extended J)     |
| Gimbal/flip risk      | None              | None (positional) | Yes (angles)   | Near singular        |
| GPU-friendly          | Yes               | Yes            | Moderate          | No (matrix solve)    |
| Best use              | Arms, legs        | Spines, tails  | Robot IK          | Full-body IK         |

---

### Python Implementation (FABRIK, N-joint):

```python
import numpy as np

def fabrik_solve(positions, bone_lengths, target, max_iter=20, tol=1e-3):
    """
    FABRIK IK solver.
    positions: list of np.array([x,y,z]) — initial joint positions (p_0 to p_N)
    bone_lengths: list of floats (len = len(positions)-1)
    target: np.array([x,y,z])
    Returns: updated positions list
    """
    p = [np.array(pos, dtype=float) for pos in positions]
    root = p[0].copy()
    N = len(p) - 1  # number of bones
    
    # Check reachability
    total_len = sum(bone_lengths)
    dist_to_target = np.linalg.norm(target - root)
    
    if dist_to_target > total_len:
        # Unreachable: point toward target
        for i in range(N):
            d = np.linalg.norm(target - p[i])
            lam = bone_lengths[i] / d
            p[i+1] = (1.0 - lam) * p[i] + lam * target
        return p
    
    for _ in range(max_iter):
        # Forward pass
        p[N] = target.copy()
        for i in range(N-1, -1, -1):
            r = np.linalg.norm(p[i+1] - p[i])
            if r < 1e-8: continue
            lam = bone_lengths[i] / r
            p[i] = (1.0 - lam) * p[i+1] + lam * p[i]
        
        # Backward pass
        p[0] = root.copy()
        for i in range(N):
            r = np.linalg.norm(p[i+1] - p[i])
            if r < 1e-8: continue
            lam = bone_lengths[i] / r
            p[i+1] = (1.0 - lam) * p[i] + lam * p[i+1]
        
        if np.linalg.norm(p[N] - target) < tol:
            break
    
    return p


def apply_fabrik_to_maya_joints(joint_chain, target_pos, max_iter=20):
    """
    Apply FABRIK result to Maya joint chain.
    joint_chain: list of joint names (root to end)
    target_pos: [x, y, z] in world space
    """
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    
    # Collect world positions
    positions = []
    for jnt in joint_chain:
        pos = cmds.xform(jnt, q=True, ws=True, t=True)
        positions.append(np.array(pos))
    
    # Collect bone lengths
    bone_lengths = []
    for i in range(len(positions) - 1):
        bone_lengths.append(np.linalg.norm(positions[i+1] - positions[i]))
    
    # Solve FABRIK
    new_pos = fabrik_solve(positions, bone_lengths, np.array(target_pos), max_iter)
    
    # Apply new positions: compute rotations from position differences
    for i, jnt in enumerate(joint_chain[:-1]):
        bone_dir = new_pos[i+1] - new_pos[i]
        bone_dir_norm = bone_dir / np.linalg.norm(bone_dir)
        # Set world position
        cmds.xform(jnt, ws=True, t=new_pos[i].tolist())
        # NOTE: rotation from direction requires up-vector convention matching rig
```

---

### Joint Constraints in FABRIK

FABRIK extensions for joint limits (Aristidou & Lasenby, 2016):

**Ball-and-socket (cone constraint):**
```
After repositioning joint i, check if the joint-to-child direction 
falls within the allowed cone angle θ_max from the bone's rest axis.
If not: clamp to cone surface.
```

**Hinge joint (planar constraint):**
```
Project the joint position onto the constraint plane 
(defined by the hinge axis and the bone above it).
If the bend angle exceeds min/max: clamp.
```

## Implementación en Maya

Maya's `ikRPsolver` and `ikSCsolver` implement analytic 2-bone IK. For N-joint spline IK, Maya uses `ikSplineSolver`. None of them are FABRIK/CCD.

**When to use FABRIK in a Maya pipeline:**
- N-joint creature tails, tentacles, spine IK alternatives
- Procedural secondary motion (hair strands, feathers)
- Python-driven IK for prototype rigs before committing to a solver architecture

**Note:** A custom FABRIK `MPxIkSolverNode` in C++ would run parallel-safe. In Python, it would be CPU-only (GIL). For production N-joint IK, the `ikSplineSolver` with a ribbon setup is usually faster because it uses GPU-side skinCluster evaluation.

```python
# Prototype: use FABRIK in Python for tail/tentacle procedural rig
import maya.cmds as cmds

def build_fabrik_rig_prototype(root_joint, num_joints, target_ctrl):
    """
    A scriptJob-driven FABRIK rig for prototyping.
    WARNING: Python scriptJob — not parallel-safe. Use for development only.
    """
    chain = [root_joint]
    j = root_joint
    for i in range(num_joints - 1):
        children = cmds.listRelatives(j, type='joint')
        if not children: break
        j = children[0]
        chain.append(j)
    
    def on_target_moved():
        tgt = cmds.xform(target_ctrl, q=True, ws=True, t=True)
        positions = [cmds.xform(j, q=True, ws=True, t=True) for j in chain]
        bone_lengths = [
            np.linalg.norm(np.array(positions[i+1]) - np.array(positions[i]))
            for i in range(len(positions)-1)
        ]
        new_pos = fabrik_solve(positions, bone_lengths, np.array(tgt))
        for i, j in enumerate(chain):
            cmds.xform(j, ws=True, t=new_pos[i].tolist())
    
    cmds.scriptJob(attributeChange=[f'{target_ctrl}.translate', on_target_moved])
```

## Comparación con autorig_tools

autorig_tools usa ikHandle (solver analítico de 2 huesos) para brazos/piernas y ribbon matrix-based para columna. FABRIK es el candidato natural para módulos de cola, tentáculo, o spine procedural con N joints sin usar ikSplineSolver. La implementación Python es correcta para prototipar; para producción habría que portar a C++ MPxIkSolverNode. El foco en FABRIK vs CCD: usar FABRIK en autorig_tools (menos artefactos, más rápido) si se implementa un solver custom.

## Aplicable directamente

PARTIAL — Implementable en Python para módulos procedurales (cola, tentáculo) como scriptJob en fase de prototipado. Para producción necesita C++ MPxIkSolverNode. En el contexto actual de autorig_tools, es más relevante entender la matemática para diseñar ribbon/spline setups que imiten el comportamiento de FABRIK, que implementar el solver desde cero.

## Fuente
- Paper original FABRIK: https://www.andreasaristidou.com/publications/papers/FABRIK.pdf
- Aristidou blog con demo interactivo: https://andreasaristidou.com/FABRIK.html
- FABRIK con constraints: https://onlinelibrary.wiley.com/doi/abs/10.1002/cav.1630
- IK Survey (Jacobian, CCD, FABRIK): https://www.cs.cmu.edu/~15464-s13/lectures/lecture6/iksurvey.pdf
- Comparison blog (2025): https://saeed1262.github.io/blog/2025/inverse-kinematics-models/
