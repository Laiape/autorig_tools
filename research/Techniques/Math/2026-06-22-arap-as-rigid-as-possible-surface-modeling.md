---
source: https://dl.acm.org/doi/10.5555/1281991.1282006
found: 2026-06-22
category: math
priority: 1
tags: [maya, python, rigging, math, deformation, correctives]
status: NEW
---

# As-Rigid-As-Possible (ARAP) Surface Modeling

## Descripción
ARAP (Sorkine & Alexa, Eurographics SGP 2007) es un método de deformación de mallas que minimiza la distorsión local: en lugar de suavizar (como Laplacian/delta mush) o aplicar transformaciones lineales por hueso (LBS), ARAP busca que cada vecindario de vértices se mueva como si fuera "lo más rígido posible" — permitiendo rotación pero penalizando cualquier shear o stretch no deseado. Es la base matemática detrás de muchas herramientas de sculpt-deformation y blendshape-correction modernas (Maya's Shrinkwrap/Wrap, sculpt deformer en otros paquetes, point-cache correctives).

## Fundamento matemático / técnico
The mesh is treated as a set of overlapping local "cells" (each vertex + its one-ring neighbors). For each cell k, ARAP defines an energy that measures deviation from a pure rotation:

  E(V', R) = (1/2) Σ_k Σ_{(i,j)∈cell_k} c_ij · || (v'_i − v'_j) − R_k (v_i − v_j) ||²

where v, v' are original/deformed vertex positions, R_k ∈ SO(3) is the best-fit local rotation for cell k, and c_ij are cotangent edge weights (same cotangent-Laplacian weighting used in Laplacian surface editing and BBW — see vault entries on delta mush math). The key idea: if R_k were fixed, this is a linear least-squares (Poisson) system in V'; if V' were fixed, the optimal R_k per cell is found via SVD of the covariance matrix S_k = Σ (v_i−v_j)(v'_i−v'_j)ᵗ, then R_k = V Uᵗ from the SVD S_k = U Σ Vᵗ (polar-decomposition style — same SVD machinery as the existing vault entry on polar decomposition/SVD for deformation gradients).

The algorithm alternates: (1) fix positions → solve for rotations via per-cell SVD, (2) fix rotations → solve sparse linear system for positions (same Laplacian matrix factored once, refactored only if topology changes). This local/global alternation converges in 3-5 iterations typically and is the prototypical "rotation-fitting" optimization pattern reused across ARAP, shape matching, and corrective-shape solvers.

Why it matters for rigging specifically: ARAP energy is what you want minimized when extracting a "clean" corrective delta from a sculpted pose — it separates genuine shape change from rigid rotation, so correctives don't double-count rotation already handled by the skeleton.

## Implementación en Maya
No native ARAP node exists in Maya. Practical paths:
1. **libigl** Python bindings expose `igl.arap_precomputation` / `igl.arap_solve` directly — same dependency stack as BBW above.
2. As a corrective-extraction tool: take a sculpted high-res target pose, run ARAP against the bind-pose mesh with the skeleton-driven vertices as positional constraints, and the residual local rotation mismatch indicates which areas need true blendshape correction vs which are just unresolved skeletal rotation.
3. Useful as the energy function behind a custom "smart relax" deformer for facial/cloth correctives, callable as a `MPxDeformerNode` wrapping a precomputed sparse Cholesky factorization of the cotangent Laplacian (refactor only on topology change, solve is O(nnz) per frame).

```python
import igl
arap = igl.ARAP(V, F, dim=3, b=constrained_indices)
V_deformed = arap.solve(bc=constrained_target_positions, initial_guess=V)
```

## Comparación con autorig_tools
autorig_tools usa RBF/SDK correctives sobre poses sculpted manualmente — ARAP no sustituye ese flujo, pero puede usarse como paso de limpieza previo: en vez de que el artista esculpa libremente y el corrective capture todo el delta (incluyendo rotación residual mal resuelta), un paso ARAP puede "relajar" la malla esculpida para que solo quede la deformación genuina, mejorando la calidad de los shapes que alimentan al sistema RBF. También es relevante para el ribbon spine (de Boor) si en algún momento se quiere un modo de edición libre de los CVs que preserve rigidez local en vez de solo suavizar.

## Aplicable directamente
PARTIAL — Mismo bloqueo de dependencia que BBW (libigl en mayapy). El caso de uso más concreto y de menor esfuerzo: una función `arap_clean_corrective(base_mesh, sculpted_mesh, joint_constraints)` que se ejecuta una vez por corrective antes de capturarlo como blendShape target, no en tiempo real. Esto la hace más fácil de aislar como script offline (no requiere integrarse en el grafo de Maya en absoluto, solo numpy/igl puro). Estimación: 4-6 horas incluyendo validación visual en personajes existentes.

## Fuente
https://dl.acm.org/doi/10.5555/1281991.1282006 (paper original, Eurographics SGP 2007)
https://www.researchgate.net/publication/221316589_As-Rigid-As-Possible_Surface_Modeling
https://github.com/fanxiaochen/ARAP (implementación de referencia en C++)
https://diglib.eg.org/items/e0b21a71-350e-41e7-a586-3bfa526ed21c
