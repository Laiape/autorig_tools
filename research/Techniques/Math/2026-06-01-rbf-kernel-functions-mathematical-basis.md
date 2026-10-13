---
source: https://binh.graphics/papers/2016s-cor/ | http://graphics.cs.uh.edu/ble/papers/2012sa-ssdr/index.html | https://rodolphe-vaillant.fr/?e=29
found: 2026-06-01
category: math
priority: 1
tags: [maya, RBF, kernel-functions, pose-space, correctives, gaussian, thin-plate-spline, multiquadric, math, interpolation]
status: NEW
---

# RBF Kernel Functions — Matemáticas para Correctives y Mesh Retargeting

## Descripción
Las Radial Basis Functions (RBF) son el motor matemático que impulsa sistemas de correctives como mGear RBF Manager, Epic PoseWrangler, y herramientas de mesh retargeting como yamahigashi/MayaMeshRetarget. La elección del kernel φ(r) determina el "radio de influencia" de cada pose de entrenamiento, la suavidad de la interpolación, y si la función tiene soporte local o global. Este archivo cubre la matemática de los cinco kernels más usados en rigging, con análisis de cuándo elegir cada uno, y la conexión directa con el problema de interpolación en pose space.

## Fundamento matemático / técnico

### Radial Basis Function Interpolation Setup
Given N data points `(xᵢ, fᵢ)` where `xᵢ ∈ ℝᵈ` (e.g., pose vectors) and `fᵢ ∈ ℝ` (e.g., blendshape weights), the RBF interpolant is:
```
s(x) = Σᵢ₌₁ᴺ cᵢ · φ(‖x - xᵢ‖)
```
The coefficients `c = [c₁, ..., cN]` are found by solving the linear system:
```
Φ · c = f
Φ[i,j] = φ(‖xᵢ - xⱼ‖)
```
**Guarantee:** If Φ is non-singular (which it is for most common kernels), the solution interpolates exactly: `s(xᵢ) = fᵢ` for all training points.

### The Five Main Kernels

#### 1. Gaussian (most common for pose correctives)
```
φ(r) = exp(-ε² · r²)
```
- **Shape parameter ε**: controls falloff. Large ε = narrow peak (localized). Small ε = wide activation.
- **Support:** Global (never exactly zero), but effectively local for large ε
- **Interpolation matrix:** Always positive definite → unique solution guaranteed
- **Rigging use:** Best for pose correctives where activation should be confined to poses near the training pose. The standard for mGear RBF Manager.
- **Tuning guideline:** ε ≈ 1/d where d = typical distance between training poses in pose space

#### 2. Thin Plate Spline (TPS)
```
φ(r) = r² · log(r)    (for r > 0;  φ(0) = 0)
```
- **Support:** Global
- **Smoothness:** Minimizes the bending energy `∫|∇²s|² dx` — the interpolant is the "smoothest" possible function passing through all data points
- **No shape parameter:** Self-tuning (no ε to choose)
- **Requires polynomial term:** Full TPS needs `s(x) = Σcᵢ·φ + p(x)` where p is affine polynomial for stability
- **Rigging use:** Excellent for mesh deformation retargeting (yamahigashi/MayaMeshRetarget), face shape deformation, any scenario where global smoothness is more important than locality
- **Problem:** Global support means editing one training pose slightly changes all other outputs

#### 3. Multiquadric
```
φ(r) = sqrt(r² + ε²)
```
- **Support:** Global, unbounded growth
- **Matrix:** Conditionally positive definite (requires polynomial augmentation)
- **Rigging use:** Less common for pose correctives. Used in some mesh retargeting tools.
- **Note:** Can produce overshooting far from training data

#### 4. Inverse Multiquadric
```
φ(r) = 1 / sqrt(r² + ε²)
```
- **Support:** Effectively local (decays to 0 as r→∞)
- **Matrix:** Positive definite, like Gaussian
- **Rigging use:** Similar to Gaussian but with heavier tails — correctives activate slightly more broadly. Good when you want slightly more overlap between adjacent correctives.

#### 5. Compactly Supported (Wendland, Beckert)
```
φ(r) = (1 - r/ρ)₊⁴ · (4r/ρ + 1)     (Wendland C²)
where (·)₊ = max(0, ·)
ρ = support radius
```
- **Support:** Exactly zero for r > ρ (truly local)
- **Matrix:** Sparse (most pairs have Φ[i,j] = 0) → fast solve, memory efficient
- **Rigging use:** Large rigs with many correctives (hundreds of poses). yamahigashi/MayaMeshRetarget supports Beckert-Wendland kernel specifically for this reason — sparse matrix → fast solve for 10K+ vertex retargeting.

### Kernel Comparison Table
| Kernel | Local? | Shape Param? | Smoothness | Best for Rigging |
|--------|--------|---------|----------|-------------------|
| Gaussian | Effectively | ε (falloff rate) | C∞ | Pose correctives (mGear default) |
| Thin Plate Spline | No | None | Minimizes bending energy | Mesh retargeting, face deformation |
| Multiquadric | No | ε | C∞ | Mesh interpolation |
| Inverse Multiquadric | Effectively | ε | C∞ | Broad pose correctives |
| Wendland/Beckert | Yes, exactly | ρ (support radius) | C² | Large sparse problems |

### Distance Metric in Pose Space
The kernel operates on distance `r = ‖p - pⱼ‖`. The choice of distance metric matters:

**Euclidean on rotation matrix (9D per joint):** Standard L2. Works well, symmetric.
**Euclidean on quaternion (4D per joint):** Risk of antipodal ambiguity — `q` and `-q` represent the same rotation but have distance 2. Must ensure consistent sign convention.
**Geodesic on SO(3):** `d(R₁, R₂) = ‖log(R₁ᵀ·R₂)‖_F` (Frobenius norm of the rotation log). Geometrically correct distance on the rotation manifold. Computationally more expensive.
**Exponential map (3D per joint):** Euclidean in exp-map space approximates geodesic for small rotations. Maya's PSD uses this.

### Condition Number and Numerical Stability
```
κ(Φ) = ‖Φ‖ · ‖Φ⁻¹‖
```
If κ(Φ) is very large, the solution is numerically unstable — small changes in training data → large changes in coefficients. This happens when:
- Two training poses are very close in pose space: `‖pᵢ - pⱼ‖ ≈ 0` → `Φ[i,j] ≈ Φ[i,i]` → near-linearly dependent rows
- Fix: Remove redundant training poses, or add Tikhonov regularization: `(Φ + λI)·c = f`

## Implementación en Maya

### Choosing the Kernel in mGear RBF Manager
mGear uses Gaussian kernel internally (mGearWeightDriver C++ plugin). The shape parameter ε is not directly exposed in the UI — it is set at the system level. Knowing the math helps when:
- **Correctives "bleed" into adjacent poses:** ε is too small (Gaussian too wide). Try training more poses closer together.
- **Corrective doesn't activate strongly enough at the training pose:** ε is too large (Gaussian too narrow). The pose may need an additional support pose nearby.

### yamahigashi/MayaMeshRetarget Kernel Selection
```python
import ymt_mesh_retarget

# Gaussian (default, best for organic deformations)
ymt_mesh_retarget.retarget(source="src", target="tgt", objects=["geo"], kernel="gaussian")

# Thin Plate Spline (best for global smooth mesh deformation)
ymt_mesh_retarget.retarget(source="src", target="tgt", objects=["geo"], kernel="thin_plate")

# Beckert-Wendland (best for large meshes, sparse computation)
ymt_mesh_retarget.retarget(source="src", target="tgt", objects=["geo"], kernel="beckert_wendland")
```

### Custom RBF Evaluator in Python (runtime)
```python
import numpy as np

KERNELS = {
    'gaussian':     lambda r, eps=0.5: np.exp(-eps**2 * r**2),
    'tps':          lambda r, eps=None: r**2 * np.log(r + 1e-12),
    'multiquadric': lambda r, eps=0.5: np.sqrt(r**2 + eps**2),
    'inv_mq':       lambda r, eps=0.5: 1.0 / np.sqrt(r**2 + eps**2),
    'wendland':     lambda r, rho=1.0: np.maximum(0, (1 - r/rho))**4 * (4*r/rho + 1),
}

def rbf_solve(poses, epsilon=0.5, kernel='gaussian', regularization=1e-6):
    """Solve for RBF coefficients given example poses."""
    N = len(poses)
    phi = KERNELS[kernel]
    Phi = np.array([[phi(np.linalg.norm(poses[i]-poses[j]), epsilon) 
                     for j in range(N)] for i in range(N)])
    Phi += regularization * np.eye(N)  # Tikhonov regularization
    return np.linalg.solve(Phi, np.eye(N))

def rbf_eval(query_pose, example_poses, coefficients, epsilon=0.5, kernel='gaussian'):
    """Evaluate RBF weights at query_pose — O(N)."""
    phi = KERNELS[kernel]
    f = np.array([phi(np.linalg.norm(query_pose - p), epsilon) for p in example_poses])
    return coefficients.T @ f
```

## Comparación con autorig_tools
El sistema RBF de autorig_tools probablemente usa mGearWeightDriver o el PSD nativo de Maya, ambos con kernel gaussiano. El valor de este documento es entender **cuándo y por qué cambiar de kernel**:
- Para **mesh retargeting** (transferir skin weights entre personajes con distinta pose): usar TPS o Gaussian.
- Para **rigs con muchos correctives** (>50 poses entrenadas): evaluar Wendland para reducir el tiempo de solve.
- Para **debug de correctives que se activan en poses incorrectas**: revisar κ(Φ) y buscar poses redundantes en el training set.

## Aplicable directamente
**PARTIAL** — El conocimiento es inmediatamente aplicable como guía de diagnóstico y tuning del sistema RBF existente. La implementación Python del `rbf_solve` es una herramienta de debugging útil para visualizar la matriz Φ y detectar problemas de condicionamiento antes de que aparezcan en el viewport.

## Fuente
https://la.disneyresearch.com/publication/skinning-with-optimized-cors/ (CoR — Disney Research)
https://rodolphe-vaillant.fr/?e=29 (Dual Quaternion Skinning + RBF context)
http://graphics.cs.uh.edu/ble/papers/2012sa-ssdr/index.html (SSDR — Le & Deng 2012)
https://github.com/yamahigashi/MayaMeshRetarget (kernel options reference)
https://maya-math-nodes.readthedocs.io/en/latest/ (maya-math-nodes kernel documentation)
