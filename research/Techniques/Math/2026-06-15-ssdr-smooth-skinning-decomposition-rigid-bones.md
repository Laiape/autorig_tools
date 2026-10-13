---
source: http://graphics.cs.uh.edu/ble/papers/2012sa-ssdr/index.html | https://dl.acm.org/doi/10.1145/2366145.2366218 | https://github.com/electronicarts/dem-bones | https://github.com/dalton-omens/SSDR
found: 2026-06-15
category: math
priority: 1
tags: [maya, skinning, SSDR, decomposition, LBS, optimization, NNLS, block-coordinate-descent, SIGGRAPH2012, rigging, math, dem-bones]
status: NEW
---

# SSDR — Smooth Skinning Decomposition with Rigid Bones (Le & Deng, SIGGRAPH Asia 2012)

## Descripción
SSDR (Smooth Skinning Decomposition with Rigid Bones), publicado por Binh Huy Le y Zhigang Deng en ACM Transactions on Graphics (SIGGRAPH Asia 2012), es un algoritmo que invierte el problema de skinning: en lugar de tomar un rig y calcular los pesos, toma un conjunto de poses de malla animada y calcula automáticamente los joints virtuales y los pesos de skin que mejor aproximan esas deformaciones. Permite convertir cualquier animación (captura de movimiento, simulación de tela, blend shapes) en un rig LBS compatible con hardware. EA Open Source publicó **DEM Bones** como implementación de producción de este algoritmo.

## Fundamento matemático / técnico

### Problem Formulation

Given:
- T example poses: V^1, V^2, ..., V^T, each V^t ∈ ℝ^{V×3} (vertex positions)
- V_rest ∈ ℝ^{V×3} = rest pose mesh
- B = number of desired virtual bones (hyperparameter)

Find:
- **W** ∈ ℝ^{V×B} = weight matrix (w_vi ≥ 0, Σ_i w_vi = 1 per vertex)
- **{T_b^t}** = B rigid bone transformations per pose t (rotation R_b^t ∈ SO(3) + translation t_b^t ∈ ℝ³)

Minimize:
```
E(W, {T_b^t}) = Σ_t Σ_v || V_v^t - Σ_b w_vb · (R_b^t · v_v_rest + t_b^t) ||²

Subject to:
  w_vb ≥ 0  ∀v,b       (non-negative weights)
  Σ_b w_vb = 1  ∀v    (partition of unity)
  R_b^t ∈ SO(3)  ∀b,t  (rigid rotations: det=1, R^T·R = I)
```

This is a **constrained non-linear optimization** (jointly over W and rotations) — not convex globally. Solved via **Block Coordinate Descent (BCD)**.

---

### Block Coordinate Descent Algorithm

BCD alternates between two simpler sub-problems:

#### Sub-problem 1: Fix W, Solve for Bone Transformations {T_b^t}

For fixed weights W, the optimization over T_b^t decomposes over bones and poses independently:

For each bone b and each pose t:
```
min_{R_b^t, t_b^t} Σ_v w_vb · || V_v^t - (R_b^t · v_v_rest + t_b^t) ||²
```

This is a **weighted rigid point registration** problem. Closed-form solution via SVD:

```python
# For bone b, pose t:
# Weighted centroid
W_b = weights[:, b]        # shape (V,) — weights for bone b
centroid_rest = (W_b @ V_rest) / W_b.sum()
centroid_posed = (W_b @ V_posed) / W_b.sum()

# Centered point clouds
P_rest  = V_rest  - centroid_rest   # (V, 3)
P_posed = V_posed - centroid_posed  # (V, 3)

# Weighted covariance matrix
H = (W_b * P_rest.T) @ P_posed     # (3, 3)

# SVD to find best rotation
U, S, Vt = np.linalg.svd(H)
d = np.linalg.det(Vt.T @ U.T)
D = np.diag([1, 1, d])             # ensures det=+1 (proper rotation)
R_b = Vt.T @ D @ U.T              # optimal rotation

# Compute translation
t_b = centroid_posed - R_b @ centroid_rest
```

**Cost:** O(V · B · T) — linear in all three dimensions. For each of B bones and T poses, one SVD of a 3×3 matrix (fixed cost).

#### Sub-problem 2: Fix {T_b^t}, Solve for W

For fixed bone transforms, each vertex v can be solved independently:

```
min_{w_v} Σ_t || V_v^t - Σ_b w_vb · T_b^t · v_v_rest ||²
Subject to: w_vb ≥ 0, Σ_b w_vb = 1
```

Let `A_vb^t = T_b^t · v_v_rest` (precomputed position of vertex v if it belonged 100% to bone b, at pose t).

The problem becomes: minimize ||A · w_v - b_v||² with w_v ≥ 0, 1^T w_v = 1.

This is a **Non-Negative Least Squares (NNLS)** problem with simplex constraint. Solved via:
1. Lagrangian relaxation of Σ_b w = 1
2. NNLS (scipy.optimize.nnls or active-set method)
3. Normalize result to sum to 1

```python
from scipy.optimize import nnls

def solve_weights_vertex(v_rest, bone_transforms_all_poses, vertex_positions_all_poses):
    """
    v_rest: (3,) — rest position of vertex v
    bone_transforms_all_poses: list of T dicts {R: (3,3), t: (3,)}
    vertex_positions_all_poses: (T, 3) — target positions
    Returns: w (B,) — optimized weights
    """
    T_poses = len(bone_transforms_all_poses[0])
    B = len(bone_transforms_all_poses)
    
    # Build system matrix A (T*3 rows, B cols)
    # Each row: position of vertex if it belonged to one bone
    rows = []
    rhs = []
    for t in range(T_poses):
        for b in range(B):
            R = bone_transforms_all_poses[b][t]['R']
            tr = bone_transforms_all_poses[b][t]['t']
            rows.append(R @ v_rest + tr)  # predicted position from bone b
        rhs.append(vertex_positions_all_poses[t])
    
    A = np.array(rows).T.reshape(3 * T_poses, B)  # (3T, B)
    b = np.array(rhs).flatten()                     # (3T,)
    
    # NNLS solve
    w, _ = nnls(A, b)
    
    # Normalize (simplex constraint)
    w_sum = w.sum()
    if w_sum > 1e-8:
        w /= w_sum
    else:
        w = np.ones(B) / B  # fallback: uniform
    
    return w
```

#### Sparsity Enforcement

Production rigs need sparse weights (≤ 4-8 influences per vertex). Two strategies:

**Hard sparsity:** After each BCD iteration, zero out all but k largest weights per vertex, renormalize:
```python
k = 4  # max influences
for v in range(V):
    top_k = np.argsort(W[v])[-k:]
    mask = np.zeros(B)
    mask[top_k] = W[v][top_k]
    W[v] = mask / mask.sum()
```

**Soft sparsity (L1 regularization):** Add λ·||W||_1 to the NNLS objective. This shrinks small weights toward zero.

---

### Initialization Strategy

BCD is sensitive to initialization. Standard approaches:

1. **K-means on vertex positions:** Cluster vertices into B groups based on rest position → assign one bone per cluster as initial transform.

2. **PCA on motion:** Apply PCA to the stacked vertex positions across all poses (V×3T matrix) → first B PCA modes capture main motion directions → initialize bones along those.

3. **Skeleton-guided:** If a skeleton exists, initialize bone transforms from existing joint data.

---

### Full BCD Loop

```python
def ssdr(V_rest, V_poses, B, max_iter=100, k_influences=4, tol=1e-4):
    """
    V_rest: (Verts, 3)
    V_poses: list of T arrays, each (Verts, 3)
    B: number of virtual bones
    """
    T = len(V_poses)
    V = len(V_rest)
    
    # Initialize weights (random + normalize)
    W = np.random.rand(V, B)
    W /= W.sum(axis=1, keepdims=True)
    
    prev_error = np.inf
    
    for iteration in range(max_iter):
        # Step 1: Solve for bone transforms (fix W)
        transforms = []
        for b in range(B):
            bone_t = []
            for t in range(T):
                R, tr = solve_rigid_transform(V_rest, V_poses[t], W[:, b])
                bone_t.append({'R': R, 't': tr})
            transforms.append(bone_t)
        
        # Step 2: Solve for weights (fix transforms)
        for v in range(V):
            W[v] = solve_weights_vertex(V_rest[v], transforms, 
                                         [V_poses[t][v] for t in range(T)])
        
        # Enforce sparsity
        for v in range(V):
            top_k = np.argsort(W[v])[-k_influences:]
            mask = np.zeros(B)
            mask[top_k] = W[v][top_k]
            W[v] = mask / mask.sum() if mask.sum() > 1e-8 else np.ones(B)/B
        
        # Check convergence
        error = compute_reconstruction_error(W, transforms, V_rest, V_poses)
        if abs(prev_error - error) < tol:
            break
        prev_error = error
    
    return W, transforms
```

**Convergence:** BCD is guaranteed to decrease the objective at each step. Convergence to a local minimum in ~10-50 iterations typically.

---

### Applications in Production

| Application | How SSDR is Used |
|-------------|-----------------|
| Cloth/simulation → LBS rig | Convert nCloth sim to skinned mesh for games/RT |
| Blend shape compression | Replace N blend shapes with M-bone SSDR rig (lossy) |
| Motion retargeting | Decompose source animation into bones, retarget bone motion |
| Crowd asset optimization | Convert hero simulation to LBS for crowd playback |
| Weight initialization | Use SSDR weights as starting point, then manual refinement |

---

### DEM Bones (EA Open Source)

Electronic Arts released **DEM Bones** (github.com/electronicarts/dem-bones) as their production SSDR implementation:
- Written in C++ (Eigen library)
- Supports alembic/FBX input
- Implements the full SSDR algorithm with EA extensions
- Maya and Houdini plugins available in the repo
- License: BSD-3-Clause
- Actively maintained (2024+)

```bash
# Build DEM Bones
git clone https://github.com/electronicarts/dem-bones
cd dem-bones && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j8

# Run on FBX animation:
./DemBones --nBones=20 --nInitIters=10 input_animated.abc output_rig.fbx
```

## Implementación en Maya

SSDR/DEM Bones workflow in Maya:
1. Simulate or create the target animation (nCloth, blend shapes, etc.)
2. Export as Alembic cache (all frames)
3. Run DEM Bones: input = alembic, output = FBX with joints + skinCluster
4. Import FBX into Maya → apply skinCluster weights
5. Optionally: manually refine weights using Maya's Paint Weights

```python
import maya.cmds as cmds

def apply_ssdr_weights_to_skincluster(mesh, skin_cluster, weight_matrix, influences):
    """
    Apply SSDR-computed weights to an existing skinCluster.
    weight_matrix: (V, B) numpy array
    influences: list of B joint names matching bone order
    """
    V = cmds.polyEvaluate(mesh, vertex=True)
    
    for vid in range(V):
        weight_dict = {}
        for b, inf in enumerate(influences):
            w = float(weight_matrix[vid, b])
            if w > 1e-4:
                weight_dict[inf] = w
        
        # Set weights for this vertex
        cmds.skinPercent(skin_cluster, f'{mesh}.vtx[{vid}]',
                        transformValue=list(weight_dict.items()))
```

## Comparación con autorig_tools

autorig_tools realiza el skinning de forma tradicional: el rigger pinta pesos manualmente o los transfiere desde otro personaje. SSDR abre un workflow diferente: si el estudio tiene simulaciones de tela, músculo, o capturas de movimiento complejas, SSDR puede convertir esas simulaciones en un skinCluster compatible con el pipeline de autorig_tools. La clave es que el output de DEM Bones es un skinCluster Maya estándar, compatible con todos los sistemas de autorig_tools (correctives, space switch, etc.). Valor directo: para personajes con ropa simulada, pasar la sim por DEM Bones y usar el resultado como punto de partida para el skinning manual ahorraría horas de trabajo.

## Aplicable directamente

YES — DEM Bones es open-source, tiene plugin para Maya, y su output es un skinCluster estándar. Workflow inmediato: (1) exportar animación de referencia como ABC, (2) correr DEM Bones con B=20-40 huesos, (3) importar pesos en Maya, (4) refinar manualmente. La función Python `apply_ssdr_weights_to_skincluster()` de arriba es directamente integrable en autorig_tools como herramienta de importación de pesos SSDR.

## Fuente
- Paper original: http://graphics.cs.uh.edu/ble/papers/2012sa-ssdr/index.html
- ACM ToG: https://dl.acm.org/doi/10.1145/2366145.2366218
- Binh Le's page: https://binh.graphics/papers/2012sa-ssdr/
- DEM Bones (EA Open Source): https://github.com/electronicarts/dem-bones
- Maya Python SSDR: https://github.com/dalton-omens/SSDR
- C++ SSDR (Mukai): https://github.com/TomohikoMukai/ssdr
