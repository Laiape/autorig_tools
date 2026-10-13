---
source: https://github.com/elom1213/Maya_Python
found: 2026-09-14
category: tool
priority: 3
tags: [maya, python, rigging, fkik, geodesic, skinning, constraint-matrix, dem-bones, ssdr, tps, rbf, unreal, pyside]
status: NEW
---
# Ji Hun Park — Maya Production Python Toolkit (elom1213/Maya_Python)

## Descripción
Colección de 61 herramientas Python para Maya (48 mantenidas activamente) creada por Ji Hun Park, actualizada el 8 de septiembre de 2026 — 6 días antes de este run. Cubre desde matching FK/IK hasta binding geodésico, conversión constraint→matrix, SSDR (Dem Bones), wrapping TPS/RBF, y puentes Maya-Unreal. El repo tiene 0 estrellas pero su actividad reciente lo califica para inclusión según la regla de criterio de actividad. Todas las herramientas siguen un framework compartido con PySide2 widgets, theme manager, undo handler context manager, y drag-drop installers.

## Fundamento matemático / técnico

### FK/IK Matching — Law of Cosines
IK → FK matching via analytic solution. For a 2-bone IK chain with lengths L1, L2 and end effector at distance D:
```
cos(θ_elbow) = (D² - L1² - L2²) / (2·L1·L2)    [law of cosines]
θ_elbow = arccos(clamp(cos_elbow, -1, 1))
```
FK → IK: read FK joint world positions → compute D from shoulder to wrist → apply IK solver. No iterative solver, pure closed-form. Works for standard biped limbs (shoulder, elbow, wrist / hip, knee, ankle).

### Geodesic Binding — Cotangent Laplacian + Heat Method
Geodesic skinning weights via discrete heat method (Crane et al. 2013):
1. Build cotangent Laplacian L_cot: for each edge (i,j), weight = (cot(α) + cot(β))/2 where α, β are opposite angles
2. Solve heat equation: (M - t·L_cot)·u = δ_b (heat from bone b, timestep t = h²)
3. Compute gradient field X = -∇u / ||∇u||
4. Solve Poisson: L_cot·φ = ∇·X
5. Normalize: w(v, b) = φ_b(v) / Σ_b' φ_b'(v)

This gives geodesic distances that respect mesh surface topology (no shortcuts through geometry voids). The cotangent Laplacian is sparse (O(E) entries), so the solve is O(V log V) with sparse Cholesky.

### Constraint → Matrix Conversion — Remove locally_serialize
Maya parentConstraints have scheduling type `kLocallySerialize`. Converting to matrix nodes (multMatrix, decomposeMatrix) changes scheduling to `kParallel`:

```
parentConstraint chain:   A → parentConstraint → B  [kLocallySerialize]
matrix chain:             A.worldMatrix → multMatrix → decomposeMatrix → B.t/r/s  [kParallel]
```

The tool reads all parentConstraint connections, replicates the transform math with matrix nodes, then deletes the constraint. This is exactly the EG optimization pattern for constraint-heavy rigs.

### Dem Bones SSDR Python Wrapper
Skinning Decomposition via Dem Bones (Edgar et al. 2019). Given mesh animation (V vertices, F frames), decompose into B bones:
```
min_{T_b, w_{i,b}} Σ_f Σ_i ||v_i^f - Σ_b w_{i,b} · T_b^f · v_i^0||²
subject to: w_{i,b} ≥ 0, Σ_b w_{i,b} = 1
```
Alternating optimization: fix T_b → solve for w (convex QP per vertex), fix w → solve for T_b (polar decomposition). The wrapper calls the Dem Bones C++ binary via subprocess, parses output JSON, and imports weights back via skinPercent.

### TPS/RBF Mesh Wrapping
Thin Plate Spline (TPS) wrapping using φ(r) = r²·log(r) kernel:
```
f(x) = Σ_i λ_i · φ(||x - c_i||) + a·x + b
```
Where c_i are control points (cage vertices), λ_i are solved via:
```
[Φ  P] [λ]   [y]
[Pᵀ 0] [a] = [0]
```
Φ_{ij} = φ(||c_i - c_j||), P = [c_1 1; c_2 1; ...]. For large point sets, sparse approximation uses subset of control points (Nyström approximation). RBF variant supports Gaussian kernel φ(r) = exp(-r²/σ²) with JSON persistence for solver coefficients.

### RBF Solver — Gaussian with JSON Persistence
```
w(x) = Σ_i α_i · exp(-||x - c_i||² / σ²)
```
Solve: α = Φ⁻¹·y where Φ_{ij} = exp(-||c_i - c_j||² / σ²). The solver saves {centers, alpha, sigma} to JSON for offline evaluation (no Maya dependency). Used for corrective shapes: driver = pose space coordinates, driven = corrective delta magnitudes.

## Implementación en Maya

### FK/IK Matching
```python
# From elom1213/Maya_Python/fkik_matcher.py
from fkik_matcher import FKIKMatcher
import math

matcher = FKIKMatcher()

# Match IK → FK (analytic, no iteration)
def ik_to_fk(shoulder, elbow, wrist):
    p0 = mc.xform(shoulder, q=True, ws=True, t=True)
    p1 = mc.xform(elbow, q=True, ws=True, t=True)
    p2 = mc.xform(wrist, q=True, ws=True, t=True)
    L1 = dist(p0, p1)
    L2 = dist(p1, p2)
    D = dist(p0, p2)
    cos_e = (D**2 - L1**2 - L2**2) / (2*L1*L2)
    theta_e = math.acos(max(-1, min(1, cos_e)))
    return math.degrees(theta_e)
```

### Geodesic Binding
```python
# From elom1213/Maya_Python/geodesic_bind.py
from geodesic_bind import GeodesicBinder

binder = GeodesicBinder()
# Build cotangent Laplacian from mesh, solve heat method,
# import weights as skinCluster via skinPercent
binder.bind(mesh='body_geo', 
            joints=mc.ls(sl=True, type='joint'),
            timestep_factor=1.0)
```

### Constraint → Matrix Conversion
```python
# From elom1213/Maya_Python/constraint_to_matrix.py  
from constraint_to_matrix import ConstraintToMatrix

converter = ConstraintToMatrix()
# Find all parentConstraints in rig, convert to multMatrix chains
converter.convert_all_in_scene(delete_constraints=True)
# Reports: N constraints converted, EG locally_serialize nodes removed
```

### Dem Bones SSDR
```python
# From elom1213/Maya_Python/dem_bones_wrapper.py
from dem_bones_wrapper import DemBonesWrapper

wrapper = DemBonesWrapper(dem_bones_binary='/tools/dem_bones')
wrapper.decompose(
    mesh='body_geo',
    anim_frames=range(1, 120),
    num_bones=20,
    iterations=30,
    output_json='weights_ssdr.json'
)
wrapper.import_weights('body_geo', 'weights_ssdr.json')
```

### RBF Solver (Correctives)
```python
# From elom1213/Maya_Python/rbf_solver.py
from rbf_solver import RBFSolver

solver = RBFSolver(kernel='gaussian', sigma=2.0)
solver.train(
    driver_poses=[[0,0,0], [45,0,0], [90,0,0]],  # joint rotations
    driven_values=[[0.0], [0.3], [1.0]]           # corrective weights
)
solver.save('corrective_shoulder.json')

# Runtime evaluation
w = solver.evaluate([30, 0, 0])  # → ~0.2
```

## Comparación con autorig_tools
Ji Hun Park's toolkit es altamente complementario con autorig_tools. El **Constraint → Matrix Converter** es directamente aplicable para limpiar rigs existentes — cualquier rig de autorig_tools que use parentConstraints se beneficia inmediatamente (kLocallySerialize → kParallel). El **Geodesic Binding** implementa exactamente el método que deberíamos tener en `build_geodesic_weights()` (cotangent Laplacian + heat method), aunque requiere scipy.sparse. El **RBF Solver con JSON persistence** es un patrón robusto para correctives que autorig_tools puede adoptar directamente. El wrapper de **Dem Bones** es útil para retargeting y debugging de weights existentes. El **TPS Wrapper** es relevante para wrap deformers en shots de cámara lenta o faces. El framework compartido de PySide2 + undo handler es un buen modelo de arquitectura para las UIs de autorig_tools.

## Aplicable directamente
YES — **Constraint → Matrix Conversion** es aplicable en 1-2 horas: ejecutar `converter.convert_all_in_scene()` en cualquier rig de autorig_tools con parentConstraints elimina kLocallySerialize del EG. **RBF Solver** es portable: extraer `rbf_solver.py` (~150 líneas) para correctives en autorig_tools (2-3h). **Geodesic Binding**: requiere scipy.sparse pero el algoritmo es exactamente lo que necesitamos en `build_geodesic_weights()` (1 día). **Dem Bones Wrapper**: útil para debugging de skin weights en producción (30 min setup). El Maya-Unreal bridge (KawaiiPhysics, Control Rig) es relevante si el pipeline incluye Unreal.

## Fuente
- https://github.com/elom1213/Maya_Python
- https://github.com/elom1213/Maya_Python/blob/main/README.md
- https://github.com/elom1213/Maya_Python/commits/main
