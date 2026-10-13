---
source: https://arxiv.org/abs/2604.13405
found: 2026-08-03
category: math
priority: 1
tags: [maya, rigging, math, IK, jacobian, singularity, DLS, SDLS, manipulability]
status: NEW
---


# IK Singularity Avoidance — Unified Treatment: DLS, SDLS, Riemannian Manipulability (Apr 2026)


## Descripción
Paper de abril 2026 (arxiv 2604.13405) que proporciona el primer survey que unifica los métodos clásicos y los basados en aprendizaje automático para evitar singularidades en IK. Introduce una taxonomía sistemática: regularización Jacobiana (DLS/SDLS), tracking de manipulabilidad Riemanniana, optimización con restricciones, y métodos data-driven. Evalúa 12 solvers IK en el brazo Franka Panda bajo cuatro protocolos complementarios. Es la referencia más completa actualmente disponible para seleccionar el solver de IK correcto según el caso de uso.


## Fundamento matemático / técnico


### The IK Problem
Given joint angles θ ∈ ℝⁿ and end-effector position/orientation x ∈ ℝᵐ (m ≤ n for redundant chains), solve for:


    Δθ = J† · Δx


where J = ∂x/∂θ is the m×n Jacobian matrix.


### Manipulability Measure
Yoshikawa's manipulability measure:


    w(θ) = sqrt(det(J · Jᵀ))


- w = 0 → kinematic singularity (chain fully extended or folded)
- w → 0 → near-singularity, small Δx causes huge Δθ
- High w → good conditioning, many reachable directions


### Pseudoinverse IK
Standard pseudoinverse (Moore-Penrose):


    J† = Jᵀ(JJᵀ)⁻¹


Problem: (JJᵀ) near-singular when w → 0. Δθ = J† Δx blows up.


### Damped Least Squares (DLS)
Replace the fragile inverse with a Tikhonov-regularized inverse:


    Δθ = Jᵀ(JJᵀ + λ²I)⁻¹ · Δx


Equivalently (via SVD of J = UΣVᵀ):


    Δθ = Σᵢ (σᵢ / (σᵢ² + λ²)) · uᵢᵀΔx · vᵢ


- Away from singularity: λ² ≪ σᵢ², behaves like J†
- At singularity: λ² dominates, clamps joint velocities


**Fixed λ**: simplest, but wastes precision away from singularities.


### Variable Damping (Wampler/Nakamura)
Adapt λ based on proximity to singularity:


    λ(w) = λ_max · (1 - (w / w_threshold)²)   for w < w_threshold
    λ(w) = 0                                     for w ≥ w_threshold


Effect: λ → λ_max near singularity, λ → 0 in well-conditioned regions.


### Selectively Damped Least Squares (SDLS) — Buss & Kim 2004
Per-singular-value damping instead of global λ:


    Δθ = Σᵢ φ(σᵢ) · uᵢᵀΔx · vᵢ


where φ(σᵢ) = σᵢ / (σᵢ² + λᵢ²) with λᵢ chosen per singular value.


This allows the solver to:
- Use full accuracy in non-singular directions (high σᵢ → small λᵢ)
- Heavily damp only the near-singular directions (small σᵢ → large λᵢ)
- Produce less task-error than fixed-λ DLS


### Riemannian Manipulability Tracking
Instead of treating singularity avoidance as a damping problem, formulate it as a secondary objective to MAXIMIZE w(θ):


    Secondary objective: maximize w = sqrt(det(JJᵀ))


Via gradient:


    ∂w/∂θ = w · tr(J⁻ᵀ · ∂J/∂θᵢ)  for each joint i


This secondary task runs in the Jacobian nullspace (doesn't disturb primary task):


    Δθ = J† Δx + (I - J†J) · k · ∇w


The (I - J†J) projects the gradient into the nullspace of J.


### Taxonomy (2026 paper)
1. **Jacobian regularization**: DLS, SDLS, clamped pseudoinverse
2. **Manipulability tracking**: Riemannian gradient, torque-based
3. **Constrained optimization**: QP with joint limits, CLiK
4. **Learning-based**: IKFlow (normalizing flows), HJCD-IK (GPU batch CCD), diffusion-based IK


### Benchmarks (12 solvers, Franka Panda 7-DOF)
- Pseudoinverse: fastest but fails at singularities (Δθ spikes to 50+ rad/s)
- DLS (fixed λ=0.1): stable, ~5% task-error at near-singular configurations  
- SDLS: ~2% task-error, better than DLS at equivalent damping budget
- Variable-λ DLS: near-zero error far from singularity, smooth degradation near it
- IKFlow: ~1ms GPU inference, handles singularities implicitly but requires offline training
- HJCD-IK: 0.1ms GPU (covered 2026-07-20), best speed/accuracy Pareto


## Implementación en Maya


### Python (numpy) DLS implementation:
```python
import numpy as np


def dls_ik_step(J, dx, lam=0.05):
    """Damped Least Squares IK step.
    J:   m×n Jacobian (m=task DOFs, n=joint DOFs)
    dx:  m-vector end-effector error
    lam: damping factor
    Returns: Δθ (n-vector joint increments)
    """
    m, n = J.shape
    # DLS: Jᵀ(JJᵀ + λ²I)⁻¹ dx
    A = J @ J.T + (lam**2) * np.eye(m)
    return J.T @ np.linalg.solve(A, dx)


def sdls_ik_step(J, dx, lam_max=0.1, eps=1e-3):
    """Selectively Damped Least Squares IK step."""
    U, s, Vt = np.linalg.svd(J, full_matrices=False)
    # Per-singular-value damping
    phi = s / (s**2 + (lam_max * np.clip(1 - s/max(s), 0, 1))**2)
    return Vt.T @ (phi * (U.T @ dx))


def manipulability(J):
    """Yoshikawa manipulability measure."""
    return np.sqrt(max(0, np.linalg.det(J @ J.T)))
```


### Maya context:
- J is computed from joint worldMatrix derivatives: column i = ∂x/∂θᵢ
- For a 3-joint chain (shoulder, elbow, wrist), J is 6×3 (position+orientation) or 3×3 (position only)
- `maya.api.OpenMaya.MMatrix` for joint transforms → extract partial derivatives analytically
- Loop: compute J from current pose → compute Δθ via DLS → add to joint rotations → repeat until convergence


## Comparación con autorig_tools


autorig_tools usa ikHandle de Maya (FABRIK-like solver interno) y el FABRIK en Python de los archivos anteriores (2026-07-06, 2026-07-20). DLS/SDLS no está implementado directamente. El valor de este paper es:
- **Fundamentación matemática rigurosa** de por qué el IK nativo de Maya falla en poses extremas (singularidades de cadena extendida al 100%)
- **SDLS como upgrade** al FABRIK Python existente para cadenas con alta redundancia (cola de 10+ joints)
- El **nullspace gradient** (manipulability tracking) es la base matemática del "secondary motion" en colas, tentáculos y spines redundantes


## Aplicable directamente


**PARTIAL** — El concepto de manipulability measure es directamente añadible al solver FABRIK existente como una función de diagnóstico `compute_manipulability(chain)`. Si w < threshold, el solver puede cambiar automáticamente a DLS en lugar de FABRIK (más estable en configuraciones near-singular). Implementable en 3-4 horas sobre el código existente. La implementación completa de SDLS es un reemplazo drop-in de `fabrik_solver()` para cadenas largas (cola, spine > 6 joints).


## Fuente
- https://arxiv.org/abs/2604.13405 (Rudrasamudram & Malaichamee, Apr 2026)
- https://arxiv.org/pdf/2604.13405 (PDF)
- Buss & Kim 2004 (SDLS): https://www.researchgate.net/publication/220494116
- Yoshikawa 1985 (manipulability): original paper on manipulability measure