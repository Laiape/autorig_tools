---
source: https://igl.ethz.ch/projects/bbw/
found: 2026-06-22
category: math
priority: 1
tags: [maya, python, rigging, math, skinning, optimization]
status: NEW
---

# Bounded Biharmonic Weights (BBW) — Automatic Skinning Weights

## Descripción
BBW (Jacobson, Baran, Popović, Sorkine — SIGGRAPH 2011) es un método para generar pesos de skinning automáticamente a partir de un esqueleto y una malla, sin pintura manual. En lugar de heurísticas como heat diffusion o distancia geodésica, formula el cálculo de pesos como un problema de optimización: minimiza la energía del Laplaciano (biharmónica) sujeta a que los pesos sumen 1 y estén acotados en [0,1]. El resultado es shape-aware — respeta huecos, formas cóncavas y geometría compleja sin que las influencias se "filtren" a través de la malla.

## Fundamento matemático / técnico
For a mesh with vertices V and a skeleton with handles (bones/points/cages) H, BBW computes one weight function w_i per handle by solving:

  minimize  ∫_Ω ||∇²w_i||² dV   (biharmonic / Laplacian energy, not just Dirichlet)
  subject to:
    w_i(p_j) = δ_ij  at handle constraints
    Σ_i w_i(x) = 1   for all x  (partition of unity)
    0 ≤ w_i(x) ≤ 1   for all x  (boundedness — this is the key innovation)

This is a constrained quadratic program. Discretized over the mesh, the biharmonic energy becomes wᵢᵗ L M⁻¹ L wᵢ where L is the cotangent Laplacian and M is the mass (Voronoi area) matrix — same building blocks used in delta mush / Laplacian surface editing (see 2026-05-11-delta-mush-laplacian-deformation-math.md and 2026-06-08-laplacian-surface-editing-sorkine-2004.md already in this vault). The bound constraint 0≤w≤1 is what prevents the negative-weight artifacts that plain biharmonic (unconstrained) or heat-diffusion weights can produce near concave joints (armpit, crotch, elbow pit).

Key result: the QP is convex (Laplacian energy is positive semi-definite), so a global optimum exists and is found via active-set or interior-point solvers. Jacobson's follow-up "Fast Automatic Skinning Transformations" (SIGGRAPH 2012) shows the BBW weight-computation problem is dual to a non-negative least-squares problem, enabling faster iterative solvers (~seconds for a 50k-vertex mesh, production-feasible at bind time, not runtime).

Complexity: weights are precomputed once at bind time (offline), so runtime cost is identical to standard LBS — it's purely a smarter weight-generation algorithm, not a new deformation method.

## Implementación en Maya
There is no native Maya node for BBW — Maya's own "Implicit"/"Heat Map" auto-skin uses a simpler heat-diffusion approximation, not the bounded biharmonic QP. To get true BBW weights in a Maya pipeline:
1. Export mesh + skeleton (OBJ + joint positions) via a Python/numpy bridge.
2. Solve the QP with `libigl` (has Python bindings `igl.bbw`) or `scipy.optimize` against the cotangent Laplacian built from the mesh (`igl.cotmatrix`, `igl.massmatrix`).
3. Import the resulting per-vertex weight matrix back into Maya and feed it directly into `cmds.skinPercent` / `MFnSkinCluster.setWeights` to populate a standard `skinCluster`.

Pseudocode:
```python
import igl, numpy as np
V, F = igl.read_triangle_mesh("body.obj")
b = handle_vertex_indices            # constrained vertex indices per bone
bc = np.eye(len(b))                  # one-hot constraint values
W = igl.bbw(V, F, b, bc)             # returns (n_verts, n_handles) weight matrix
# normalize (BBW already sums to 1, but float drift happens)
W = W / W.sum(axis=1, keepdims=True)
```
The resulting `W` columns map 1:1 to joints and load straight into `MFnSkinCluster.setWeights`.

## Comparación con autorig_tools
Esto ataca un problema real del pipeline de Laia: el peso inicial de skinning en autorig_tools probablemente depende de heat map o copySkinWeights manual + correctives posteriores (RBF/SDK). BBW puede sustituir el primer pase de pintura automática con resultados matemáticamente óptimos y sin necesidad de retocar manualmente las zonas cóncavas problemáticas (axila, ingle, dedos). No reemplaza sus correctives RBF — los complementa, dándoles un punto de partida mejor y reduciendo el trabajo de pintura manual antes de aplicar SDKs.

## Aplicable directamente
PARTIAL — Requiere instalar `libigl` (con bindings Python) en el entorno de `mayapy`, lo cual es viable (`pip install libigl`) pero añade una dependencia externa a numpy/scipy que autorig_tools no tiene actualmente. Una función `bbw_preskin(mesh, joints)` podría integrarse como paso opcional de pre-skinning en el pipeline (similar a como ya usa MayaMeshRetarget/dm2skin de research anteriores), ejecutándose en `mayapy` fuera del proceso de Maya si las dependencias chocan. Estimación: 3-5 horas para wrapping + pruebas de export/import de pesos.

## Fuente
https://igl.ethz.ch/projects/bbw/
https://dl.acm.org/doi/10.1145/2010324.1964973 (paper original SIGGRAPH 2011)
https://igl.ethz.ch/projects/fast/fast-automatic-skinning-transformations-siggraph-2012-compressed-jacobson-et-al.pdf (follow-up con NNLS dual)
https://www.cs.toronto.edu/~jacobson/ (Alec Jacobson — autor)
