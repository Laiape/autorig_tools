---
source: https://github.com/duncanskertchly/dm2skin
found: 2026-06-01
category: tool
priority: 3
tags: [maya, skinning, delta-mush, skin-weights, optimization, python, scipy, numpy, workflow]
status: NEW
---

# dm2skin — Convertir Delta Mush a Skin Weights (duncanskertchly)

## Descripción
dm2skin es un script de Python para Maya que convierte los resultados de un deformador delta-mush en skin weights estándar. El flujo de trabajo permite al rigger usar delta-mush como una "guía" de deformación deseada y luego transferir esa información a un skinCluster convencional, obteniendo skin weights de alta calidad sin pintarlos manualmente. Esto es especialmente valioso para personajes con muchas influencias o topologías complejas donde el pintar pesos a mano sería prohibitivamente lento. 62 estrellas en GitHub, activo hasta 2020.

## Fundamento matemático / técnico

### The Core Optimization Problem
Given:
- `V_skin(t)` = vertex positions from a skinned mesh at pose `t`
- `V_dm(t)` = vertex positions from a delta-mushed mesh at pose `t` (the target deformation)
- `w[v, j]` = skin weight of vertex `v` for joint `j` (what we want to solve for)

Find `w` such that:
```
min Σ_t Σ_v ‖V_skin(v, t; w) - V_dm(v, t)‖²
```
Subject to:
- `Σⱼ w[v, j] = 1.0`  (weights sum to 1)
- `w[v, j] ≥ 0`       (non-negative)
- `count(j : w[v,j] > 0) ≤ max_influences`  (sparsity constraint)

This is a **constrained least-squares problem** solved per vertex independently, using NumPy/SciPy's `scipy.optimize.lsq_linear` or NNLS (Non-Negative Least Squares).

### Algorithm Steps
```
1. SETUP:
   a. Create a single-influence-per-vertex skinCluster (rough initial bind)
   b. Apply delta-mush deformer on top
   c. Keyframe a set of N diverse poses (elbows, knees, twists)
   d. Specify max_influences (e.g., 4 or 8)

2. DATA COLLECTION (per frame):
   For each pose t in {1..N}:
     - Record V_skin[t] = all vertex world positions from skinCluster
     - Record V_dm[t]   = all vertex world positions from delta-mush output

3. PER-VERTEX OPTIMIZATION:
   For each vertex v:
     - Build matrix A[t, j] = joint_j_contribution_to_vertex_v_at_pose_t
     - Build target vector b[t] = V_dm[v, t] - V_skin[v, t]  (residual)
     - Solve: min ‖Aw - b‖² s.t. w ≥ 0, Σw = 1, sparsity ≤ max_influences
     - Uses NNLS: w_optimal = scipy.optimize.nnls(A, b)[0]
     - Normalize and enforce sparsity (zero out smallest influences)

4. APPLY: Write w_optimal back to skinCluster weights for each vertex
```

### Why Delta Mush as Target
Delta Mush applies Laplacian smoothing while preserving surface detail (stored as per-vertex tangent-space deltas). The result is smoother deformation than naive LBS — making it an ideal **target** for the skin weight optimization: the optimizer finds LBS weights that best approximate the smooth delta-mush output, effectively "baking" the smoothness into the weights.

### Performance Data
- 10,000 vertex mesh, 5 max influences: ~2 minutes on standard workstation
- 50,000 vertex mesh: ~10-15 minutes
- CPU-bound (NumPy operations); parallelization across vertices is straightforward

## Implementación en Maya

### Basic Workflow
```python
# 1. Create rough bind (1 influence per vertex using closest joint)
cmds.skinCluster('mesh', joints, toSelectedBones=True, maximumInfluences=1)

# 2. Add delta mush on top
cmds.deltaMush('mesh', smoothingIterations=20, smoothingStep=0.5)

# 3. Keyframe diverse poses (elbows at 0, 45, 90, 135 degrees, etc.)
#    Minimum: 8-12 poses. More = better results.

# 4. Run dm2skin
import dm2skin
dm2skin.dm2skin(mesh='mesh', max_influences=4, frames=range(1, 13))
# → Overwrites skinCluster weights with optimized values
# → Removes delta-mush deformer (optional)
```

### Pose Coverage Recommendations
```
For an arm:
  - Elbow at 0° (rest), 45°, 90°, 135° (extreme)
  - Forearm supination 0°, 90°, 180°
  - Wrist flex/extend ±45°
  Total: ~10 poses minimum

For a spine:
  - Bend forward/back ±30°, ±60°
  - Side bend ±30°
  - Twist ±45°
  Total: ~12 poses minimum
```

### Limitations and Workarounds
| Limitation | Workaround |
|---|---|
| Maya 2016+ required (deltaMush introduced then) | N/A for modern pipelines |
| CPU-only, slow for high-res meshes | Run on low-res proxy, transfer weights to hero mesh |
| Results depend heavily on pose coverage | Author ≥10 diverse poses including extremes |
| Max influences capped at `max_influences` arg | Start with 8, reduce to 4 if performance needed |
| Last update: ~2020 (no Python 3 official release) | Fork and update imports for Python 3 / Maya 2022+ |

### Integration with Skinning Workflow
```python
# After dm2skin, clean up with ngSkinTools or custom pruner:
def prune_small_weights(mesh, min_weight=0.001):
    skin = get_skin_cluster(mesh)
    verts = cmds.polyEvaluate(mesh, vertex=True)
    for v in range(verts):
        weights = cmds.skinPercent(skin, f'{mesh}.vtx[{v}]', query=True, value=True)
        inf = cmds.skinPercent(skin, f'{mesh}.vtx[{v}]', query=True, transform=None)
        for w, j in zip(weights, inf):
            if w < min_weight:
                cmds.skinPercent(skin, f'{mesh}.vtx[{v}]', transformValue=[(j, 0.0)])
```

## Comparación con autorig_tools
autorig_tools tiene herramientas de skinning (export/import de skin weights). dm2skin ofrece un flujo complementario: **generar buenos skin weights automáticamente** desde una pose coverage set, en lugar de pintarlos desde cero. Es especialmente útil como herramienta de aceleración para el skinning inicial de personajes nuevos, o para mejorar skin weights en zonas problemáticas (rodillas, hombros, muñecas). La limitación de Python 2 en el repo original requiere una actualización manual para funcionar en Maya 2022+.

## Aplicable directamente
**PARTIAL** — El código original está en Python 2 (no ejecuta en Maya 2022+). Pasos para usar:
1. Forkear el repo y actualizar `print` statements y `range()`/`xrange()` para Python 3.
2. Verificar compatibilidad de `scipy.optimize.nnls` con la versión de NumPy/SciPy bundled en Maya.
3. Integrar como herramienta auxiliar de skinning en autorig_tools — no como reemplazo del flujo principal de skin painting, sino como accelerator para el skinning inicial.
4. Tiempo estimado de adaptación: 3-4 horas.

## Fuente
https://github.com/duncanskertchly/dm2skin
