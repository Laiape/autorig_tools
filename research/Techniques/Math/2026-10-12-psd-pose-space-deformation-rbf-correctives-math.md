---
source: https://dl.acm.org/doi/10.1145/344779.344862
found: 2026-10-12
category: math
priority: 1
tags: [maya, python, rigging, math, psd, rbf, correctives, pose-space-deformation, blendshape]
status: NEW
---

# Pose Space Deformation (PSD): Unified Math for RBF Corrective Shapes

## Descripción
Lewis, Cordner & Fong (SIGGRAPH 2000) formalizan Pose Space Deformation como un marco unificado donde los correctives blendshapes son interpolados por funciones RBF en el espacio de pose del esqueleto. Es el fundamento matemático completo del sistema de correctives que usan studios AAA/VFX: en lugar de "empujar vértices en poses concretas", se define un mapeo continuo f: Pose → Δvértice usando RBF multidimensional. Maya lo expone como Pose Deformer / Pose Interpolator node.

## Fundamento matemático / técnico

### Problem Statement
Given N sample poses p₁…pN, each with an associated sculpted correction Δᵢ (per-vertex displacement), define a smooth function:

```
Δ(p) = Σᵢ wᵢ · φ(||p - pᵢ||)    for all i=1..N
```

where φ is a radial basis function (kernel), and weights wᵢ are solved from the interpolation conditions:

```
Δ(pⱼ) = Δⱼ  for j=1..N
→ [φ(||pⱼ - pᵢ||)]·w = Δ    (matrix equation)
```

This gives an N×N linear system (one per vertex, or solved once for the weight matrix and applied per-vertex).

### Pose Space Definition
The pose p is typically a vector of joint DOF values. For a single joint with 3 rotational DOF:

```
p = (θx, θy, θz) ∈ ℝ³   (Euler angles)
```
or better:
```
p = log(q) ∈ ℝ³   (exponential map — geodesically correct, see companion file)
```

For multiple joints: concatenate DOF vectors → pose is in ℝ^(3k) for k joints.

### RBF Kernels Used in Practice

| Kernel | φ(r) | Properties |
|--------|-------|------------|
| Gaussian | exp(-r²/σ²) | Smooth, local support with σ |
| Thin plate spline | r² log(r) | Exact interpolation, global |
| Linear | r | Simple, less smooth |
| Multiquadric | sqrt(r² + c²) | Smooth, always positive |

For correctives, Gaussian is most common: local influence decays with distance from sample pose.

### The Weight System Solves per Vertex
```
For each vertex v:
  solve: Φ · α_v = δ_v
  where Φ[i,j] = φ(||pᵢ - pⱼ||)  (kernel matrix — same for all vertices)
       δ_v[i] = Δᵢ[v]             (sculpted correction at sample i)
       α_v[i] = RBF coefficients  (unique per vertex)

At runtime:
  Δ(p)[v] = Σᵢ α_v[i] · φ(||p - pᵢ||)
```

The kernel matrix Φ is computed once at bind time — O(N²) per rig build, not per frame.

### Localized PSD (per-joint weighting)
To limit a corrective's influence to the geometric region driven by a joint:

```
Δ_localized(p)[v] = sk_weight(joint, v) · Δ(p)[v]
```

where sk_weight is the skinCluster influence weight for that joint on vertex v. This prevents shoulder correctives from bleeding into the torso.

### Combination Shapes (Product Interaction)
For correctives that activate only when TWO conditions are true simultaneously (e.g., both elbow bent AND shoulder raised):

```
w_combination = w_A · w_B   (product of individual RBF outputs)
```

This is the "tensor product" extension: the driver space is factored into independent axes, and combinations activate at the intersection. In Maya's Pose Interpolator this is handled via the "neutral", "combination" pose type settings.

### Maya Pose Interpolator Architecture
```
joint → poseInterpolator → blendShape weights
  └─ pose samples (quaternion snapshots)
  └─ RBF kernel type (linear, gaussian, etc.)
  └─ smoothing falloff
→ drives corrective blendShape targets
```

Python query:
```python
import maya.cmds as mc

def list_pose_interpolators():
    return mc.ls(type='poseInterpolator')

def get_pose_count(node):
    return mc.poseInterpolator(node, query=True, poseCount=True)

def add_corrective_pose(node, name):
    mc.poseInterpolator(node, edit=True, addPose=name)
```

### Performance Note
Each `poseInterpolator` node evaluates O(N·k) per frame where N = number of poses, k = number of driven attributes. For a full-body rig with 50+ correctives, the evaluation time can be significant. Optimize by:
1. Limiting N (trim redundant poses near each other in pose space)
2. Using one poseInterpolator per joint region (parallelization)
3. Replacing low-N correctives with SDK/animCurve (faster for 1-2 sample cases)

## Implementación en Maya

```python
import maya.api.OpenMaya as om
import numpy as np
from scipy.spatial.distance import cdist

def build_rbf_corrective_system(poses, deltas, kernel='gaussian', sigma=0.5):
    """
    poses: (N, D) array of pose vectors (N samples, D DOF)
    deltas: (N, V, 3) array of vertex corrections (N samples, V vertices, xyz)
    Returns: coefficients alpha of shape (N, V, 3)
    """
    N = len(poses)
    # Build kernel matrix
    dists = cdist(poses, poses)
    if kernel == 'gaussian':
        Phi = np.exp(-dists**2 / sigma**2)
    elif kernel == 'thin_plate':
        Phi = np.where(dists > 0, dists**2 * np.log(dists + 1e-12), 0)
    
    # Solve for each vertex: Phi @ alpha = delta
    # alpha shape: (V, 3, N)
    deltas_flat = deltas.reshape(N, -1)   # (N, V*3)
    alpha_flat = np.linalg.solve(Phi, deltas_flat)  # (N, V*3)
    return alpha_flat.reshape(N, -1, 3)

def evaluate_rbf(current_pose, sample_poses, alpha, kernel='gaussian', sigma=0.5):
    """Evaluate correction at current_pose."""
    dists = np.linalg.norm(sample_poses - current_pose, axis=1)
    if kernel == 'gaussian':
        phi = np.exp(-dists**2 / sigma**2)
    return np.einsum('i,ivx->vx', phi, alpha)
```

## Comparación con autorig_tools
El sistema de correctives de autorig_tools probablemente usa SDKs o poseInterpolator nativo de Maya. La ventaja del PSD math explícito en Python es la capacidad de ajustar el kernel (Gaussian vs thin-plate), normalizar los pesos vía softmax, y usar exponential maps como espacio de pose en vez de Euler. Si el facial rig tiene más de 30-40 correctives, evaluar si Maya's poseInterpolator está siendo el cuello de botella con el profiler antes de reimplementar.

## Aplicable directamente
PARTIAL — Para correctives existentes en autorig_tools:
1. Auditar el kernel type usado en los poseInterpolators existentes (accesible via `mc.poseInterpolator(node, q=True, kernelFalloff=True)`)
2. Si se usan Euler angles como pose drivers: comparar con exp-map distances en un shoulder rig para ver si hay diferencia en interpolación a poses > 60°
3. Para casos de combination shapes (codo + hombro juntos): implementar `w_A * w_B` producto explícito como nodo `multiplyDivide` conectado antes del blendShape

## Fuente
- Lewis, J.P., Cordner, M., Fong, N. (2000). "Pose Space Deformation: A Unified Approach to Shape Interpolation and Skeleton-Driven Deformation." SIGGRAPH 2000. https://dl.acm.org/doi/10.1145/344779.344862
- ResearchGate PDF: https://www.researchgate.net/publication/220720724_Pose_Space_Deformation_A_Unified_Approach_to_Shape_Interpolation_and_Skeleton-Driven_Deformation
- Maya Pose Interpolator docs: https://knowledge.autodesk.com/support/maya/learn-explore/caas/CloudHelp/cloudhelp/2018/ENU/Maya-CharacterAnimation/files/GUID-45D389D6-B8E4-4225-B27B-9927BB61C28D-htm.html
