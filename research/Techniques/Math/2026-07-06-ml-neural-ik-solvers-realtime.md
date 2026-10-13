---
source: https://arxiv.org/html/2507.00792v1
found: 2026-07-06
category: math
priority: 1
tags: [maya, python, rigging, math, inverse-kinematics, machine-learning, neural-network, FABRIK, CCD, DNN, real-time]
status: NEW
---

# ML/DNN para Inverse Kinematics en Tiempo Real — Más Allá de FABRIK y CCD

## Descripción
Los solvers de IK basados en redes neuronales (DNN) representan la frontera actual (2024–2025) que supera a CCD y FABRIK en velocidad de convergencia y manejo de restricciones múltiples. Mientras que FABRIK y CCD son algoritmos iterativos geométricos, los DNN IK solvers aprenden la función IK como regresión en un espacio de poses, permitiendo inferencia de pose completa en una única pasada forward (~0.1ms GPU). La base matemática cubre tanto los algoritmos clásicos (para implementación directa en Python) como los arquitecturas DNN emergentes. Los archivos existentes sobre IK cubren 2-bone analytic (ley de cosenos) y FABRIK/CCD de forma general; este archivo añade la formalización matemática completa y el estado del arte 2025.

## Fundamento matemático / técnico

### Comparativa rendimiento: CCD vs FABRIK vs Jacobian vs DNN

| Solver | Iter. alcanzable | Tiempo alcanzable | Iter. inalcanzable | Multi-EE | Restricciones angulares |
|--------|-----------------|-------------------|--------------------|----------|-------------------------|
| CCD | ~26 iter | ~123ms | ~400 iter / 4s | No | Difícil (ad-hoc) |
| FABRIK | ~3–10 iter | ~5–20ms | Convergencia suave | Parcial | Con extensiones |
| Jacobian J⁺ | ~10–20 iter | ~30–80ms | Estable (DLS) | Sí nativo | Sí (penalty) |
| DNN (2025) | 1 pass | ~0.1ms GPU | N/A (non-iterative) | Sí nativo | Vía training data |

**Key finding from arxiv 2507.00792 (July 2025):**
> "Under realistic boundary conditions, conventional methods such as CCD and FABRIK exhibited significantly higher iteration counts and lower success rates (~60%) vs the DNN solver (~95%)."

### FABRIK — Forward And Backward Reaching IK (full mathematical derivation)

FABRIK (Aristidou & Lasenby, 2011) is a two-pass geometric algorithm with O(n) per iteration.

**Forward pass** (reach toward target, ignore root constraint):
```
p_n = target_position  // snap last joint to target
for i in n-1 downto 0:
    direction = normalize(p_i - p_{i+1})
    p_i = p_{i+1} + direction * bone_length_i
```

**Backward pass** (reattach to root):
```
p_0 = root_position    // snap first joint back to root
for i = 0 to n-1:
    direction = normalize(p_{i+1} - p_i)
    p_{i+1} = p_i + direction * bone_length_i
```

Repeat until `|p_n - target| < ε` (tolerance).

**Convergence guarantee:** FABRIK converges when the target is reachable (total chain length ≥ distance to target). For unreachable targets: all joints align toward target (graceful degradation).

**FABRIK with constraints** (Aristidou et al. extended version):
```
// After each position update, clamp to joint constraint cone
p_i_clamped = clamp_to_cone(p_i, cone_axis_i, cone_angle_i)
```
Cone constraints are applied after each backward pass step, not during — this maintains the geometric clarity of the algorithm.

### Cyclic Coordinate Descent (CCD) — full derivation

CCD minimizes `|end_effector - target|²` one joint at a time:

For joint j (rotating around axis aⱼ to minimize distance):
```
v₁ = normalize(end_effector - joint_j_pos)    // current end-effector direction
v₂ = normalize(target - joint_j_pos)           // desired direction
angle = acos(dot(v₁, v₂))                     // rotation angle
axis = normalize(cross(v₁, v₂))               // rotation axis

Apply rotation: R(axis, angle) to joint j
```

Iterate from end-effector joint back to root, then repeat.

**Weakness:** CCD can generate "coiled" configurations (roll joints before reaching target). No global constraint on pose naturalness. Solution: add regularization term or joint limits.

### Jacobian Pseudoinverse IK — formal treatment

For a kinematic chain of n revolute joints with DOFs θ = [θ₁,...,θₙ]ᵀ ∈ Rⁿ:

**Forward kinematics:** x = FK(θ) ∈ R³ (or R⁶ for position+orientation)

**Jacobian matrix J (3×n):**
```
J_ij = ∂xᵢ/∂θⱼ  =  aⱼ × (xₑₑ - pⱼ)   [for revolute joint j, position only]

where:
aⱼ = rotation axis of joint j (in world space)
pⱼ = position of joint j (in world space)
xₑₑ = current end-effector position
```

**Pseudoinverse update:**
```
Δθ = J⁺ · Δx    where J⁺ = Jᵀ(JJᵀ)⁻¹    [Moore-Penrose, for m < n]
```

**Damped Least Squares (DLS) — avoids singularity:**
```
Δθ = Jᵀ(JJᵀ + λ²I)⁻¹ · Δx

λ: damping coefficient (0.01 to 0.1)
At singularity: J becomes rank-deficient → DLS gives stable near-zero Δθ
Near singularity: λ is increased dynamically (variable damping / SVD-based)
```

**Multiple end-effectors (full-body IK):**
Stack the Jacobians:
```
J_full = [J_EE1; J_EE2; J_EE3; ...]    [3m × n matrix for m end-effectors]
x_full = [x_EE1; x_EE2; x_EE3; ...]

Δθ = J_full⁺ · Δx_full
```
This is why Jacobian IK is the standard for full-body solvers (VR avatars, motion capture retargeting).

### DNN-based IK — architecture and training (2025 state-of-art)

**Supervised regression approach:**
```
Network input:  [θ_current ∈ Rⁿ, x_target ∈ R³, constraint_mask ∈ {0,1}ⁿ]
Network output: θ_solution ∈ Rⁿ

Loss function:
L = α·||FK(θ_output) - x_target||²   // position accuracy
  + β·||θ_output - θ_rest||²           // pose naturalness (stay near rest)
  + γ·max(0, violation(θ_output))       // constraint violation penalty
```

**Training data generation:**
```
for _ in range(10_000_000):
    θ = random_valid_pose()           // FK-valid random joint angles
    x_target = FK(θ)[-1]             // target = end-effector of this pose
    θ_initial = random_valid_pose()  // starting configuration
    dataset.append((θ_initial, x_target, θ))
```

**Architecture (from 2025 paper):**
```
Input(n+3) → FC(256, ReLU) → FC(256, ReLU) → FC(256, ReLU) → Output(n)
+ skip connection from input to second layer
```

Inference: single forward pass, 0.1ms on GPU vs 123ms for CCD.

**Limitation:** Must retrain per skeleton topology. Poor generalization across different joint counts.

## Implementación en Maya

### FABRIK completo en Python con maya.api.OpenMaya

```python
import maya.api.OpenMaya as om
import maya.cmds as cmds

def fabrik_solve(joint_chain, target_pos_world, tolerance=0.001, max_iter=20):
    """
    Solve IK via FABRIK for a chain of N joints.
    
    Args:
        joint_chain: list of joint names (root to end)
        target_pos_world: tuple (x, y, z) world space target
        tolerance: convergence threshold in world units
        max_iter: maximum iterations
    
    Returns:
        list of MVector (new world positions for each joint)
    """
    n = len(joint_chain)
    
    # Get current world positions
    positions = []
    for j in joint_chain:
        pos = cmds.xform(j, q=True, ws=True, t=True)
        positions.append(om.MVector(*pos))
    
    # Compute bone lengths (fixed)
    lengths = [(positions[i+1] - positions[i]).length() for i in range(n-1)]
    total_length = sum(lengths)
    root = om.MVector(positions[0])
    target = om.MVector(*target_pos_world)
    
    # Check reachability
    if (target - root).length() > total_length:
        # Unreachable: stretch full chain toward target
        for i in range(n-1):
            direction = (target - positions[i]).normalize()
            positions[i+1] = positions[i] + direction * lengths[i]
        return positions
    
    # FABRIK iterations
    for _ in range(max_iter):
        # --- Forward pass (end → root) ---
        positions[-1] = om.MVector(target)
        for i in range(n-2, -1, -1):
            direction = (positions[i] - positions[i+1]).normalize()
            positions[i] = positions[i+1] + direction * lengths[i]
        
        # --- Backward pass (root → end) ---
        positions[0] = om.MVector(root)
        for i in range(n-1):
            direction = (positions[i+1] - positions[i]).normalize()
            positions[i+1] = positions[i] + direction * lengths[i]
        
        # Convergence check
        if (positions[-1] - target).length() < tolerance:
            break
    
    return positions

def apply_fabrik_to_joints(joint_chain, target_pos_world):
    """
    Run FABRIK and apply resulting positions to joints via worldMatrix.
    Preserves joint orientations (only moves positions).
    """
    new_positions = fabrik_solve(joint_chain, target_pos_world)
    for joint, pos in zip(joint_chain, new_positions):
        cmds.xform(joint, ws=True, t=[pos.x, pos.y, pos.z])
```

### Jacobian IK in Python (for multi-EE scenarios)

```python
import numpy as np

def jacobian_ik_step(joint_positions, joint_axes, target_pos, 
                     ee_pos, damping=0.05):
    """
    Single DLS Jacobian IK step for a single end-effector.
    Returns delta_theta for each joint.
    """
    n = len(joint_positions)
    J = np.zeros((3, n))
    
    for i in range(n):
        # J[:,i] = axis_i × (ee - joint_i)
        axis = np.array(joint_axes[i])
        r = np.array(ee_pos) - np.array(joint_positions[i])
        J[:, i] = np.cross(axis, r)
    
    # DLS: Δθ = Jᵀ(JJᵀ + λ²I)⁻¹ · Δx
    delta_x = np.array(target_pos) - np.array(ee_pos)
    A = J @ J.T + (damping**2) * np.eye(3)
    delta_theta = J.T @ np.linalg.solve(A, delta_x)
    
    return delta_theta

# Usage: call iteratively until convergence
# for step in range(50):
#     dtheta = jacobian_ik_step(...)
#     apply_joint_rotations(dtheta)
```

### Use cases in autorig_tools

| Use Case | Recommended Solver |
|----------|-------------------|
| Arms/legs (2-bone) | Analytic (law of cosines) — O(1) |
| Finger curl (3-4 bones) | FABRIK — simple, O(n) |
| Spine (5-7 bones) | FABRIK or Jacobian |
| Tail/tentacle (10+ bones) | FABRIK — best for long chains |
| Full body IK (VR/MoCap) | Jacobian DLS — handles multiple EE |
| Procedural foot plant | FABRIK + contact constraint |

## Comparación con autorig_tools

Los archivos existentes `ik-solvers-fabrik-ccd-jacobian.md` y `fabrik-ccd-ik-solvers-iterative.md` cubren los algoritmos de forma general. Este archivo añade: (1) la formalización matemática completa con ecuaciones explícitas y derivaciones, (2) datos de performance de 2025 con benchmarks de CCD vs FABRIK vs DNN, (3) la implementación completa de FABRIK en Python con maya.api.OpenMaya lista para integrar, y (4) la tabla de decisión de qué solver usar en cada módulo de autorig_tools.

## Aplicable directamente

YES (FABRIK Python) / PARTIAL (DNN)
- **FABRIK**: copiar `fabrik_solve()` + `apply_fabrik_to_joints()` directamente en `autorig_tools/utils/ik_solvers.py`. Usar para tail rig, procedural spine pose, y cualquier cadena IK >3 bones. Tiempo: 1-2 horas incluyendo tests.
- **Jacobian**: implementar `jacobian_ik_step()` para el sistema de IK facial (múltiples puntos de contacto de labios) o para pose-assist con múltiples end-effectors. Tiempo: 3-4 horas.
- **DNN**: no aplicable a corto plazo (requiere torch en mayapy + entrenamiento per-skeleton). Referencia para entender la dirección de la industria en pose prediction.

## Fuente
- https://arxiv.org/html/2507.00792v1 (arxiv Jul 2025 — Real-Time IK for Multi-Constrained Movements)
- https://arxiv.org/pdf/2209.02532 (arxiv 2022 — Combined FABRIK with Optimization)
- https://andreasaristidou.com/FABRIK (Andreas Aristidou — FABRIK original paper)
- https://saeed1262.github.io/blog/2025/inverse-kinematics-models/ (CCD vs FABRIK vs Jacobian comparison, 2025)
- https://www.researchgate.net/publication/266600621 (Comparison of Jacobian-based IK methods)
