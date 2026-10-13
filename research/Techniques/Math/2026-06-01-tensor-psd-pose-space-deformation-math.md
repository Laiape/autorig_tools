---
source: https://dl.acm.org/doi/pdf/10.1145/344779.344862 | https://en.wikipedia.org/wiki/Pose_space_deformation | https://arxiv.org/abs/2401.16496
found: 2026-06-01
category: math
priority: 1
tags: [maya, PSD, pose-space-deformation, RBF, correctives, tensor, scattered-data-interpolation, math, blendshapes]
status: NEW
---

# Pose Space Deformation — Fundamento Matemático Tensor y RBF (Lewis et al. 2000)

## Descripción
Pose Space Deformation (PSD) es el marco matemático formal que subyace a todos los sistemas de correctives basados en pose: mGear RBF Manager, Epic PoseWrangler, y el PSD nativo de Maya. El paper original de Lewis, Cordner y Fong (SIGGRAPH 2000) define una función de deformación `d(p)` que mapea un vector de pose `p` a un vector de desplazamiento de vértice, usando interpolación de datos dispersos vía RBF. El archivo `2026-05-05-mgear-rbf-manager-psd.md` cubre el workflow práctico; este archivo cubre el fundamento matemático del tensor RBF que lo hace funcionar.

## Fundamento matemático / técnico

### Pose Vector Representation
A **pose** is parameterized as a vector `p ∈ ℝⁿ`. Different representations have different properties:

| Representation | Dim per joint | Pros | Cons |
|---|---|---|---|
| Euler angles (rx, ry, rz) | 3 | Intuitive | Gimbal lock, discontinuities |
| Rotation matrix (3×3) | 9 | Continuous, encodes full rotation | Redundant (6 constraints) |
| Quaternion (w,x,y,z) | 4 | Compact, no gimbal | Antipodal ambiguity (q = -q) |
| Exponential map (θ·n̂) | 3 | Minimal, geodesic | Singularity at 2π |

Lewis et al. used the **flattened rotation matrix** (9 components per joint) as the pose vector because it is continuous and avoids gimbal lock — at the cost of redundancy. Modern implementations (mGear, PoseWrangler) typically use exponential maps or normalized quaternions.

### The Deformation Function
For a given pose `p`, the deformation (vertex displacement) is:
```
d(p) = Σᵢ wᵢ(p) · dᵢ
```
Where:
- `dᵢ` = the corrective displacement vector stored for the i-th example pose
- `wᵢ(p)` = the weight of example pose i at the current pose p
- The sum is over all N trained example poses

This is exactly how blendShape weights are computed: `w` drives the weight of a corrective blendShape target.

### Scattered Data Interpolation — RBF Basis
The weight function `wᵢ(p)` is computed via **Radial Basis Function interpolation**:
```
wᵢ(p) = Σⱼ cᵢⱼ · φ(‖p - pⱼ‖)
```
Where:
- `‖p - pⱼ‖` = Euclidean distance in pose space between current pose `p` and j-th example pose
- `φ` = the radial basis function (e.g., Gaussian, thin plate spline, multiquadric)
- `cᵢⱼ` = coefficients solved at setup time (not at runtime)

**Setup phase (offline):** Solve the linear system:
```
Φ · C = W
```
Where `Φ[i,j] = φ(‖pᵢ - pⱼ‖)` is the RBF evaluation matrix between all N example poses, `C` is the coefficient matrix, and `W` is the identity (interpolation passes through all training points exactly).

**Runtime phase:** Given the current pose `p`:
```
for each example pose j:
    r_j = ‖p - p_j‖         # distance in pose space
    f_j = φ(r_j)            # apply basis function
w = C^T · f                  # weights via precomputed coefficients
```
This is an O(N) operation per frame — fast even for many correctives.

### Common RBF Kernels φ(r)
```
Gaussian:           φ(r) = exp(-ε² · r²)          — localized, smooth
Thin Plate Spline:  φ(r) = r² · log(r)            — global support, biharmonic
Multiquadric:       φ(r) = sqrt(r² + ε²)           — global support, unbounded
Inverse Multiquadric: φ(r) = 1/sqrt(r² + ε²)      — localized, bounded
Linear:             φ(r) = r                        — simple, often too sharp
```
**For pose correctives:** Gaussian with ε tuned per-rig is the most common. It ensures that a corrective activates strongly at its training pose and falls off smoothly as the rig moves away.

### Tensor Extension (Multi-Joint Interactions)
When a corrective depends on TWO joints simultaneously (e.g., shoulder internal rotation AND elbow flexion both active), the pose vector `p` is the concatenation of both joint representations:
```
p = [rot_shoulder | rot_elbow]   # ∈ ℝ¹⁸ if using rotation matrices
```
The RBF interpolation works identically in the higher-dimensional space. The "tensor" terminology in some references refers to this multi-joint pose space being isomorphic to a tensor product of individual joint spaces. The distance `‖p - pⱼ‖` naturally captures whether BOTH joints are close to the trained pose simultaneously.

### Comparison with SDK (Set Driven Key)
```
SDK:     d(p) = spline_interpolation(p_driver)    — 1D, no joint interaction
RBF PSD: d(p) = Σᵢ wᵢ(p) · dᵢ                  — N-D, captures joint interactions
```
SDK requires manually authoring separate correctives for each combination of joint poses. RBF PSD automatically interpolates between all trained examples — capturing the interaction between shoulder and elbow without requiring a separate corrective for every combination.

### Multi-Resolution Deep PSD (2024)
A November 2024 paper (ACM TOG 2024, doi:10.1145/3687985) extends PSD to use neural networks for the pose-to-weight mapping, achieving higher frequency correctives at near-realtime speed. The mathematical structure is the same but `φ` is replaced by a learned function.

## Implementación en Maya

### Maya Native PSD (Maya 2020+)
```python
# Maya's native PSD uses the same RBF approach internally
# Access via: Deform > Pose Space Deformation

# Create a PSD node manually:
psd = cmds.createNode('poseReader')
# Alternatively, use the PSD deformer:
cmds.poseSpaceDeformer(mesh, name='psd1')

# Pose space deformer uses exponential map internally for pose parameterization
# Weight function is RBF with Gaussian kernel (ε auto-tuned)
```

### mGear RBF Manager: Under the Hood
```
mGearWeightDriver (C++ plugin):
  - Computes distance ‖p - pⱼ‖ in pose space each frame
  - Applies Gaussian φ to each distance
  - Solves Φ·C = W once at author time (setup call)
  - Runtime: matrix-vector multiply C^T · f — O(N) per frame
  
Pose vector: by default uses joint.worldMatrix rotation components (quaternion-based)
```

### Python Pseudocode (Gaussian RBF Solver)
```python
import numpy as np

def solve_rbf_weights(poses, epsilon=0.1):
    """
    poses: (N, D) array — N example poses, each D-dimensional
    Returns: coefficient matrix C for runtime evaluation
    """
    N = len(poses)
    Phi = np.zeros((N, N))
    for i in range(N):
        for j in range(N):
            r = np.linalg.norm(poses[i] - poses[j])
            Phi[i,j] = np.exp(-epsilon**2 * r**2)  # Gaussian kernel
    # Interpolation condition: Phi @ C = I (each pose activates only its own corrective)
    C = np.linalg.solve(Phi, np.eye(N))
    return C

def evaluate_pose(current_pose, example_poses, C, epsilon=0.1):
    """Runtime evaluation — O(N)"""
    f = np.array([np.exp(-epsilon**2 * np.linalg.norm(current_pose - p)**2) 
                  for p in example_poses])
    return C.T @ f  # weights for each corrective blendshape
```

## Comparación con autorig_tools
El archivo existente `2026-05-05-mgear-rbf-manager-psd.md` cubre el workflow práctico de mGear. Este archivo añade el **porqué matemático**: por qué la distancia en pose space funciona como selector de correctives, por qué el kernel gaussiano localiza la activación, y cómo extender a múltiples joints simultáneamente (el "tensor" del nombre). Es especialmente valioso para entender **cómo tunear el parámetro ε** (radio de influencia) y por qué los correctives no se "contaminan" entre sí cuando están bien separados en pose space.

## Aplicable directamente
**YES/PARTIAL** — No requiere implementar el solver RBF desde cero (mGear lo tiene). Pero el conocimiento matemático es directamente aplicable para:
1. **Tuning de ε en mGear**: un ε grande = corrective más suave pero que activa lejos de la pose; ε pequeño = activación muy localizada pero puede producir artefactos en interpolación.
2. **Debug de correctives que se "activan solos"**: si dos poses entrenadas están demasiado cerca en pose space (‖p_i - p_j‖ ≈ 0), la matriz Φ es mal condicionada. Solución: eliminar poses redundantes.
3. **Multi-joint correctives**: concatenar los vectores de rotación de ambos joints en el pose vector, dando soporte nativo a interacciones shoulder+elbow, etc.

## Fuente
https://dl.acm.org/doi/pdf/10.1145/344779.344862 (Lewis et al., SIGGRAPH 2000 — original PSD paper)
https://en.wikipedia.org/wiki/Pose_space_deformation
https://dl.acm.org/doi/10.1145/3687985 (Deep PSD, ACM TOG Nov 2024)
https://arxiv.org/abs/2401.16496 (Refined Inverse Rigging 2024)
