---
source: https://andreasaristidou.com/FABRIK
found: 2026-05-11
category: math
priority: 1
tags: [maya, rigging, math, ik, fabrik, ccd, jacobian, inverse-kinematics, solver]
status: NEW
---

# IK Solvers — FABRIK, CCD y Jacobian Pseudoinversa: Matemática y Comparativa

## Descripción
Los solucionadores de Inverse Kinematics calculan las rotaciones de una cadena de joints para que el end effector alcance una posición/orientación objetivo. Los tres algoritmos principales son CCD (Cyclic Coordinate Descent), FABRIK (Forward And Backward Reaching IK) y el método del Jacobiano (pseudoinversa / Damped Least Squares). Maya usa variantes de estos internamente, pero entender la matemática permite implementar solvers customizados para cadenas secundarias, tentáculos, colas, y sistemas procedurales.

## Fundamento matemático / técnico

### CCD — Cyclic Coordinate Descent
Algoritmo greedy que procesa los joints secuencialmente desde el end effector hacia la raíz, rotando cada joint para minimizar la distancia end-effector → target:

```
For each iteration:
    For joint i from (n-1) downto 0:
        v_end    = end_pos - joint_i_pos    # vector to current end effector
        v_target = target  - joint_i_pos    # vector to target
        axis  = cross(v_end, v_target).normalized()
        angle = arccos(clamp(dot(v_end.norm, v_target.norm), -1, 1))
        Rotate joint_i by angle around axis
        Update all downstream joint world positions via FK
```

**Complexity:** O(n) per joint, O(n²) per full sweep (because each joint rotation requires updating all downstream joints).
**Convergence:** 5-20 iterations for short chains; oscillates/diverges for long chains (n > 10) or overconstrained systems.
**Joint limits:** Add per-joint axis/angle clamping after each rotation step.

### FABRIK — Forward And Backward Reaching IK
Position-based (operates on joint positions, not rotations). Two-pass per iteration:

**Backward pass** (end effector → root, ignoring root pin):
```
p[n] = target                                    # snap end to target
for i = (n-1) downto 0:
    r = length(p[i] - p[i+1])                   # current bone length (should = L[i] after iter)
    λ = L[i] / r                                 # L[i] = rest bone length
    p[i] = (1-λ)·p[i+1] + λ·p[i]               # pull toward new end, maintain bone length
```

**Forward pass** (root → end effector, re-anchoring root):
```
p[0] = root_pos                                  # re-anchor root
for i = 1 to n:
    r = length(p[i] - p[i-1])
    λ = L[i-1] / r
    p[i] = (1-λ)·p[i-1] + λ·p[i]
```

Repeat until `|p[n] - target| < tolerance` (typically 5-10 iterations).

**Key properties:**
- O(n) per full iteration — more efficient than CCD for long chains
- Works in position space; joint rotations extracted post-hoc from solved positions
- Naturally handles unreachable targets (chain straightens toward target)
- Handles branching chains with extensions (simultaneous sub-chain solving)
- No explicit rotation computation during solving — reduces numerical error

```python
def fabrik(positions, lengths, target, root, tol=1e-4, max_iter=30):
    n = len(positions)
    for _ in range(max_iter):
        dist = sum((positions[-1][j]-target[j])**2 for j in range(3))**0.5
        if dist < tol:
            break
        # Backward pass
        positions[-1] = list(target)
        for i in range(n-2, -1, -1):
            d = sum((positions[i+1][j]-positions[i][j])**2 for j in range(3))**0.5
            lam = lengths[i] / d
            positions[i] = [(1-lam)*positions[i+1][j] + lam*positions[i][j] for j in range(3)]
        # Forward pass
        positions[0] = list(root)
        for i in range(1, n):
            d = sum((positions[i][j]-positions[i-1][j])**2 for j in range(3))**0.5
            lam = lengths[i-1] / d
            positions[i] = [(1-lam)*positions[i-1][j] + lam*positions[i][j] for j in range(3)]
    return positions
```

### Jacobian Pseudoinverse (DLS)
Differentiates end-effector position/orientation w.r.t. joint angles. For a chain of n revolute joints:

```
ẋ = J · θ̇
```
where J is the (6×n) Jacobian matrix (3 position rows + 3 orientation rows).

**Column i of J** (revolute joint with axis aᵢ):
```
J_pos_i    = aᵢ × (p_end - pᵢ)   # cross product of axis with lever arm
J_orient_i = aᵢ                   # for full 6-DOF
```

**Solution (pseudoinverse):**
```
θ̇ = J⁺ · ẋ = Jᵀ(JJᵀ)⁻¹ · ẋ    (redundant chain: n > 6)
```
Singularity when det(JJᵀ) → 0 (degenerate config, e.g., fully extended arm).

**Damped Least Squares (DLS) — robust:**
```
θ̇ = Jᵀ(JJᵀ + λ²I)⁻¹ · ẋ
```
λ is the damping factor. Increases near singularities (sacrifices accuracy for stability). Variable λ (Sugihara method): `λ² = max(0, ε - det(JJᵀ)/det_scale)`.

**SVD-based selective dampening:**
```
J = UΣVᵀ  →  J⁺ = VΣ⁺Uᵀ
```
Σ⁺: invert singular values above threshold, zero those below. Cleanest approach for singularity handling.

### Algorithm Comparison
| Property | CCD | FABRIK | Jacobian DLS |
|----------|-----|--------|--------------|
| Per-iter complexity | O(n²) | O(n) | O(n²m) or O(n³) |
| Convergence speed | Medium | Fast (5-10 iters) | Slow (many iters) |
| Singularity handling | Natural | Natural | Needs DLS |
| 6-DOF pose control | Limited | Limited | Full |
| Branching chains | Difficult | Yes (multi-end) | Yes |
| Joint angle limits | Easy clamp | Complex | Via null-space |
| Implementation complexity | Low | Low | High |
| Best for | Simple chains, real-time | Multi-joint chains | Complex robots, full-body IK |

**Maya's ikRPsolver:** Uses a closed-form analytical 2-bone solution (not iterative) — O(1), singularity-free for standard limbs. Always prefer this for biped arm/leg.

## Implementación en Maya

Maya native solvers: `ikRPsolver` (rotate-plane, analytical), `ikSCSolver` (single chain, CCD), `ikSplineSolver` (curve-based).

**Custom FABRIK for secondary chains** (tail, tongue, tentacle):
```python
import maya.cmds as cmds
import maya.api.OpenMaya as om

def apply_fabrik_to_chain(joints, target_pos):
    """After solving, apply positions back as joint translates."""
    positions = [cmds.xform(j, q=True, ws=True, t=True) for j in joints]
    lengths = [om.MVector(*cmds.xform(joints[i+1], q=True, ws=True, t=True) -
                           om.MVector(*cmds.xform(joints[i],   q=True, ws=True, t=True))).length()
               for i in range(len(joints)-1)]
    root = positions[0][:]
    solved = fabrik(positions, lengths, list(target_pos), root)
    # Convert solved positions back to joint rotations via aim vectors
    for i, (j, pos) in enumerate(zip(joints, solved)):
        cmds.xform(j, ws=True, t=pos)
```

## Comparación con autorig_tools

autorig_tools usa `ikRPsolver` para extremidades (correcto — es analítico y O(1)). FABRIK es relevante para módulos secundarios: colas, tentáculos, dedos largos, chains con más de 3 joints. CCD es menos estable que FABRIK para chains largas. El Jacobian DLS es excesivamente complejo para rigging de personaje estándar, pero es la base teórica del full-body IK y del motion retargeting.

## Aplicable directamente
PARTIAL — Implementar FABRIK en Python como módulo de `chain_secondary` en autorig_tools. Para colas de 5-10 joints, FABRIK converge en < 10 iteraciones con tolerancia 0.001 y es 100% Python puro (no requiere plugin). El `ikRPsolver` sigue siendo la mejor opción para arm/leg.

## Fuente
- FABRIK original paper: https://andreasaristidou.com/FABRIK
- FABRIK PDF: https://www.andreasaristidou.com/publications/papers/FABRIK.pdf
- CCD/FABRIK/Jacobian comparison: https://saeed1262.github.io/blog/2025/inverse-kinematics-models/
- IK for Game Programming: https://medium.com/@turtle50vp/inverse-kinematics-for-game-programming-5f9a408e24b2
