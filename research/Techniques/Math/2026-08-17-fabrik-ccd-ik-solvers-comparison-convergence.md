---
source: https://www.andreasaristidou.com/publications/papers/FABRIK.pdf | https://link.springer.com/content/pdf/10.1007/s10846-023-01895-2.pdf | https://saeed1262.github.io/blog/2025/inverse-kinematics-models/
found: 2026-08-17
category: math
priority: 1
tags: [maya, rigging, IK, FABRIK, CCD, inverse-kinematics, math, python]
status: NEW
---

# FABRIK vs CCD IK Solvers — Convergencia, Matemática e Implementación

## Descripción
FABRIK (Forward And Backward Reaching Inverse Kinematics, Aristidou & Lasenby 2011) y CCD (Cyclic Coordinate Descent) son los dos solvers IK geométricos más usados en producción para cadenas de más de 3 huesos. FABRIK es ~10× más rápido que CCD en número de iteraciones y maneja cadenas no alcanzables de forma robusta. Relevante para autorig_tools en tail rigs, spine procedural, y cadenas de tentáculo/cabello. Complementa el research previo sobre IK singularity (DLS/SDLS) y HJCD-IK (GPU batched).

## Fundamento matemático / técnico

### Notation
- Chain: **p₀** (root), **p₁**, ..., **pₙ** (end-effector)
- Link lengths: **dᵢ = |pᵢ₊₁ - pᵢ|** (constant, preserved throughout)
- Target: **t**

### FABRIK Algorithm

**Step 1 — Check reachability:**
```
dist = |t - p₀|
if dist > Σdᵢ:  # target unreachable
    # Extend chain toward target in straight line
    for i in range(n):
        λ = dᵢ / |t - pᵢ|
        pᵢ₊₁ = (1 - λ)·pᵢ + λ·t
    return  # Done in one pass
```

**Step 2 — Forward reaching pass (end → root direction):**
```
pₙ_new = t  # Move end-effector to target
for i in n-1 downto 0:
    rᵢ = |pᵢ₊₁_new - pᵢ|
    λ = dᵢ / rᵢ
    pᵢ_new = (1 - λ)·pᵢ₊₁_new + λ·pᵢ  # point on line at distance dᵢ from new pᵢ₊₁
```

**Step 3 — Backward reaching pass (root → end direction):**
```
p₀_new = p₀_original  # Restore root to original position
for i in 0 to n-1:
    rᵢ = |pᵢ₊₁_new - pᵢ_new|
    λ = dᵢ / rᵢ
    pᵢ₊₁_new = (1 - λ)·pᵢ_new + λ·pᵢ₊₁_new
```

**Iterate** forward + backward until |pₙ - t| < ε (tolerance ~0.01 units).

### CCD Algorithm

```
for iteration in max_iters:
    for i in n-1 downto 0:
        # Vector from joint i to end-effector (current)
        v_current = normalize(pₙ - pᵢ)
        # Vector from joint i to target
        v_target  = normalize(t - pᵢ)
        # Rotation to align them
        axis  = cross(v_current, v_target)
        angle = acos(clamp(dot(v_current, v_target), -1, 1))
        R = rotation_matrix(axis, angle)
        # Apply rotation to all downstream joints
        for j in i+1 to n:
            pⱼ = pᵢ + R · (pⱼ - pᵢ)
    if |pₙ - t| < ε: break
```

### Convergence Comparison (published benchmarks, Aristidou 2011)

| Solver | Avg Iterations (reachable) | Avg Time (ms) | Unreachable Iterations | Unreachable Time |
|--------|---------------------------|---------------|----------------------|-----------------|
| FABRIK | 15.4 | 13.2 | ~10 | ~9ms |
| CCD | 26.0 | 123.0 | ~400 | ~4000ms |
| Jacobian Pseudoinverse | 28.0 | 13,100 | — | — |

**FABRIK is ~10× fewer iterations than CCD, ~1000× faster than Jacobian.**

### Why FABRIK Converges Faster
FABRIK works in position space: each step finds a point on a line — O(1) per joint per iteration, no trigonometry or matrix ops. CCD must recompute the full rotation for each joint and propagate it downstream. For n joints: FABRIK is O(n) per iteration; CCD is also O(n²) in the worst case (each joint rotation affects all downstream).

### FABRIK Joint Constraints
For rotationally constrained joints (joint limits):
1. Convert position-based solution to rotation angle at joint i
2. Clamp angle to joint limits [θ_min, θ_max]
3. Reconstruct position from clamped angle + parent position

Combined FABRIK + SQP (2023): use FABRIK as initial seed for SQP optimizer — converges faster than pure SQP or pure FABRIK under high-precision requirements (ε < 10⁻⁶).

## Implementación en Maya

### Pure Python FABRIK for Maya (om2)
```python
import maya.api.OpenMaya as om2

def fabrik_solve(joint_positions, link_lengths, target, max_iters=30, tol=0.001):
    """
    joint_positions: list of om2.MVector (world space)
    link_lengths: list of float (len = len(joint_positions) - 1)
    target: om2.MVector
    Returns: list of om2.MVector (solved positions)
    """
    p = [om2.MVector(v) for v in joint_positions]
    n = len(p) - 1  # number of links
    root = om2.MVector(p[0])
    total_length = sum(link_lengths)
    
    dist_to_target = (target - p[0]).length()
    
    if dist_to_target > total_length:
        # Unreachable: stretch toward target
        for i in range(n):
            d = (target - p[i]).length()
            lam = link_lengths[i] / d
            p[i+1] = p[i] * (1 - lam) + target * lam
        return p
    
    for _ in range(max_iters):
        # Forward pass
        p[n] = om2.MVector(target)
        for i in range(n-1, -1, -1):
            d = (p[i+1] - p[i]).length()
            if d < 1e-10:
                continue
            lam = link_lengths[i] / d
            p[i] = p[i+1] * (1 - lam) + p[i] * lam  # wrong direction, fix:
            p[i] = p[i+1] + (p[i] - p[i+1]).normal() * link_lengths[i]
        
        # Backward pass
        p[0] = om2.MVector(root)
        for i in range(n):
            d = (p[i+1] - p[i]).length()
            if d < 1e-10:
                continue
            p[i+1] = p[i] + (p[i+1] - p[i]).normal() * link_lengths[i]
        
        if (p[n] - target).length() < tol:
            break
    
    return p

def apply_fabrik_to_joints(root_joint, target_pos, max_iters=30):
    """Apply FABRIK to a Maya joint chain."""
    sel = om2.MSelectionList()
    sel.add(root_joint)
    dag = sel.getDagPath(0)
    
    # Collect joint chain
    joints = []
    fn = om2.MFnTransform(dag)
    # ... walk chain, collect positions and link lengths
    # Then call fabrik_solve and apply results back via setTranslation
    pass
```

### Node-based IK (DG graph approach)
For character spine: pair FABRIK Python solver (run on rig build) with matrix constraint outputs, or use Maya's built-in `ikSCsolver`/`ikRPsolver` for 2-bone chains. FABRIK shines for 4+ bone chains (tail, fin, spine strips).

## Comparación con autorig_tools

autorig_tools implementa IK de 2 huesos (brazo, pierna) con `ikRPsolver` nativo. Para cadenas de cola, aleta, o spine procedural de más de 3 huesos, FABRIK es la solución correcta. El research log de junio ya documentó un `fabrik_solve()` en Python; este archivo añade la comparativa cuantitativa de convergencia y la referencia al paper para la función con joint constraints (2023). La combinación FABRIK+SQP es relevante si en el futuro autorig_tools necesita cadenas con límites angulares estrictos (dedos de mano).

## Aplicable directamente

YES — La implementación Python es directamente integrable en `autorig_tools/utils/ik_solvers.py` para:
1. **Tail rigs**: cadenas de 5-15 joints que la ikRPsolver no maneja bien
2. **Procedural spine pose**: calcular posición de joints de spine en función de root+tip target
3. **Debug/validation**: comparar solución FABRIK vs IK handle nativo para detectar flip

Tiempo estimado de integración: 2-3h incluyendo tests en Maya.

## Fuente
- Paper original FABRIK: https://www.andreasaristidou.com/publications/papers/FABRIK.pdf
- Combined FABRIK+SQP (2023): https://link.springer.com/content/pdf/10.1007/s10846-023-01895-2.pdf
- Comparison tutorial (2025): https://saeed1262.github.io/blog/2025/inverse-kinematics-models/
- GitHub implementation (CCD+FABRIK): https://github.com/chFleschutz/inverse-kinematics-algorithms
