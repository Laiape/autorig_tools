---
source: https://en.wikipedia.org/wiki/De_Boor%27s_algorithm | https://coleobrien.medium.com/matrix-splines-in-maya-ec17f3b3741 | https://www.cgcircuit.com/tutorial/advanced-rigging-with-de-boors-algorithm-in-maya
found: 2026-08-17
category: math
priority: 1
tags: [maya, rigging, bspline, bezier, ribbon, spine, de-boor, matrix, spline-math]
status: NEW
---

# B-Spline y Algoritmo de de Boor — Ribbon Spine sin NURBS ni Rivets

## Descripción
Los ribbon spines (spine rigs basados en ribbon/superficie NURBS con follicles o rivets) tienen un problema de performance conocido: los follicles rompen los clusters GPU y los rivets añaden transforms extra. La alternativa es implementar la matemática B-spline directamente: dado un set de control points (guide joints), evaluar la posición Y tangente de cada joint de salida analíticamente, sin ningún nodo de superficie. El algoritmo de de Boor es el estándar para evaluar B-splines de forma numericamente estable, y Cole O'Brien documentó su implementación para Maya con `offsetParentMatrix`.

## Fundamento matemático / técnico

### B-Spline Definition
A B-spline of degree **p** with **n+1** control points **P₀..Pₙ** and knot vector **T = {t₀, t₁, ..., t_{n+p+1}}**:

```
C(u) = Σᵢ₌₀ⁿ Bᵢ,ₚ(u) · Pᵢ
```

Where **Bᵢ,ₚ(u)** are B-spline basis functions (Cox-de Boor recursion):
```
Bᵢ,₀(u) = 1  if  tᵢ ≤ u < tᵢ₊₁,  else 0

Bᵢ,ₚ(u) = (u - tᵢ)/(tᵢ₊ₚ - tᵢ) · Bᵢ,ₚ₋₁(u)
          + (tᵢ₊ₚ₊₁ - u)/(tᵢ₊ₚ₊₁ - tᵢ₊₁) · Bᵢ₊₁,ₚ₋₁(u)
```

### de Boor's Algorithm (numerically stable evaluation)
Given parameter **u** in knot span [tₖ, tₖ₊₁):

```python
def de_boor(k, p, t, c, u):
    """
    k: knot span index (where u lives)
    p: degree
    t: knot vector (list of floats)
    c: control points (list of MVector or numpy array)
    u: parameter to evaluate
    Returns: point on curve C(u)
    """
    d = [c[j] for j in range(k - p, k + 1)]  # p+1 control points

    for r in range(1, p + 1):
        for j in range(p, r - 1, -1):
            i = j + k - p
            alpha = (u - t[i]) / (t[i + p - r + 1] - t[i])
            d[j] = (1 - alpha) * d[j - 1] + alpha * d[j]

    return d[p]  # The evaluated point
```

**Complexity**: O(p²) operations — very fast for degree 3 splines used in rigging.

### Uniform Knot Vector for Spine Rigging
For a clamped uniform B-spline (curve starts/ends at first/last control point):
```
# 4 control points, degree 3:
# Knot vector: [0, 0, 0, 0, 1, 1, 1, 1]
# (p+1 repeated at start and end = "clamped")

n_ctrl = len(control_points)  # e.g. 4
p = 3  # cubic
n_knots = n_ctrl + p + 1
knots = [0]*p + list(range(n_ctrl - p + 1)) + [n_ctrl - p]*p
# Normalize to [0, 1]:
knots = [k / knots[-1] for k in knots]
```

### Tangent Computation (for joint orientation)
The derivative C'(u) (tangent vector) is itself a B-spline of degree p-1:
```
C'(u) = p · Σᵢ (Pᵢ₊₁ - Pᵢ)/(tᵢ₊ₚ₊₁ - tᵢ₊₁) · Bᵢ,ₚ₋₁(u)
```
This gives an exact analytical tangent at any parameter — no finite differences needed.

### NURBS vs B-Spline for Rigging
| Feature | NURBS ribbon + follicle | Pure B-Spline (DG node) |
|---------|------------------------|------------------------|
| GPU cluster | Follicle breaks GPU | No follicle, stays in DG |
| Node count | High (surface + follicle + rivet) | Minimal (multMatrix chain) |
| Offset parent | Works via offsetParentMatrix | Direct: matrix output = offsetParentMatrix |
| Tangent access | No (must aim at neighbor) | Exact analytic tangent |
| Parameterization | Arc-length optional | Uniform or chord-length |

## Implementación en Maya

### Matrix Spline Approach (Cole O'Brien method)

Build the spine as a **pure DG computation** using Python on rig build:
```python
import maya.api.OpenMaya as om2

def build_bspline_spine(guide_joints, output_joints, degree=3):
    """
    guide_joints: list of joint names (control points)
    output_joints: list of joint names to position along spline
    No NURBS surface, no follicle, no rivet.
    """
    # Get control point positions (world space)
    ctrl_pts = [get_world_position(j) for j in guide_joints]
    
    # Build knot vector (clamped uniform)
    n = len(ctrl_pts)
    p = degree
    knots = [0]*p + list(range(n - p + 1)) + [n - p]*p
    max_k = knots[-1]
    knots = [k / max_k for k in knots]
    
    # Evaluate output joints along parameter [0, 1]
    n_out = len(output_joints)
    for i, jnt in enumerate(output_joints):
        u = i / (n_out - 1)
        
        # Find knot span
        k = find_knot_span(u, knots, p, n)
        
        # Evaluate position via de Boor
        pos = de_boor(k, p, knots, ctrl_pts, u)
        
        # Evaluate tangent (finite diff or analytic)
        eps = 0.001
        tan_pos = de_boor(find_knot_span(min(u+eps, 0.999), knots, p, n),
                           p, knots, ctrl_pts, min(u+eps, 0.999))
        tangent = (tan_pos - pos).normal()
        
        # Build aim matrix (tangent = X axis)
        up = om2.MVector(0, 1, 0)
        side = tangent ^ up; side.normalize()
        up_corrected = side ^ tangent; up_corrected.normalize()
        
        mat = build_matrix(tangent, up_corrected, side, pos)
        
        # Apply via offsetParentMatrix (zero out joint transforms)
        set_offset_parent_matrix(jnt, mat)

def find_knot_span(u, knots, p, n):
    """Binary search for knot span index."""
    if u >= knots[n+1]:
        return n
    lo, hi = p, n + 1
    mid = (lo + hi) // 2
    while u < knots[mid] or u >= knots[mid+1]:
        if u < knots[mid]:
            hi = mid
        else:
            lo = mid
        mid = (lo + hi) // 2
    return mid
```

### Arc-Length Parameterization (for even joint spacing)
Uniform parameter u doesn't give even joint spacing on curves with varying curvature. For even spacing:
1. Sample curve at N points (e.g. N=1000)
2. Build cumulative arc-length table: s(uᵢ) = Σ |C(uᵢ) - C(uᵢ₋₁)|
3. For each output joint i: find u where s(u) = i · total_length / (n_out - 1) via binary search

### Why de Boor vs Maya's NURBS
Maya's NURBS uses the same algorithm internally, but exposes it via surface nodes. By implementing de Boor directly in Python:
- No NURBS surface in DG = no follicle = no GPU cluster break
- Exact tangent access (needed for proper joint orientation)
- Full control over parameterization (arc-length vs uniform)
- Can be computed entirely at rig build time → baked into `offsetParentMatrix` = zero runtime cost

## Comparación con autorig_tools

autorig_tools implementa ribbons via NURBS surface + follicles según se documenta en el código. Esto es correcto y robusto, pero los follicles rompen el GPU cluster upstream. Migrar a B-spline analítico haría el ribbon spine 100% GPU-compatible: los joints de salida se posicionan en build time vía `offsetParentMatrix` (si es un spine no animado) o via Python node custom (si requiere evaluación dinámica). Para spines que se doblan interactivamente, la solución más limpia es el `aimMatrix` + `pickMatrix` + `multMatrix` chain — más simple que de Boor completo pero menos suave con muchos joints de salida.

## Aplicable directamente

PARTIAL — La función `build_bspline_spine()` es directamente aplicable como alternativa al ribbon NURBS en builds donde el spine no requiere deformación GPU (p.ej. el ribbon para blendshapes de volume). Para spines con deformación dinámica (animación de cuerpo), la migración es más profunda. Inmediatamente útil: el `find_knot_span()` + `de_boor()` como utilidad de diagnóstico para visualizar la curvatura del spine en cualquier pose.

## Fuente
- de Boor's algorithm (Wikipedia): https://en.wikipedia.org/wiki/De_Boor%27s_algorithm
- Matrix Splines in Maya (Cole O'Brien): https://coleobrien.medium.com/matrix-splines-in-maya-ec17f3b3741
- CGCircuit tutorial: https://www.cgcircuit.com/tutorial/advanced-rigging-with-de-boors-algorithm-in-maya
- YouTube trailer: https://m.youtube.com/watch?v=RlYfOgAvRmA
