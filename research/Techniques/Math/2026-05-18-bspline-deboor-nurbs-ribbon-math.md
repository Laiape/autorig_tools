---
source: https://pages.mtu.edu/~shene/COURSES/cs3621/NOTES/spline/B-spline/de-Boor.html
found: 2026-05-18
category: math
priority: 1
tags: [maya, python, rigging, math, bspline, nurbs, de-boor, ribbon, spine, control-points, knot-vector]
status: NEW
---

# B-Splines, Algoritmo de de Boor y NURBS para Ribbon Spine

## Descripción
Laia menciona el algoritmo de de Boor como parte de su pipeline de ribbon spine. Este documento cubre la matemática completa: qué son las B-splines, cómo funciona el vector de nudos (knot vector), la formulación recursiva de las funciones base de B-spline (Cox-de Boor), el algoritmo de evaluación de de Boor, y cómo todo esto se relaciona con las superficies NURBS que Maya usa internamente para los ribbons. Comprender esta base matemática permite manipular los controles del ribbon con precisión y entender por qué ciertos setup de guides producen comportamientos inesperados.

## Fundamento matemático / técnico

### B-Spline Definition
A B-spline curve of degree p with n+1 control points P₀, P₁, ..., Pₙ is defined as:
```
C(u) = Σᵢ₌₀ⁿ Nᵢ,ₚ(u) · Pᵢ    for u ∈ [u_min, u_max]
```
where `Nᵢ,ₚ(u)` are the B-spline basis functions of degree p, and u is the parameter.

### Knot Vector
The knot vector `T = {t₀, t₁, ..., t_{n+p+1}}` is a non-decreasing sequence of real numbers. It controls the domain and continuity of the B-spline:
- **Clamped (open):** first and last knot repeated p+1 times → curve passes through first/last control points
  - Example, degree 3, 6 control points: `T = {0,0,0,0, 0.33, 0.66, 1,1,1,1}`
- **Uniform:** evenly spaced knots (no clamping) → curve does NOT pass through endpoints
- **Non-uniform:** arbitrary knot spacing → local control of smoothness

**Knot multiplicity and continuity:**
- Single knot → C^(p-1) continuity at that parameter (smooth)
- Knot of multiplicity k → C^(p-k) continuity (less smooth)
- Multiplicity p → C^0 (corner, curve passes through knot point)
- Multiplicity p+1 → discontinuity (curve breaks)

### Cox-de Boor Basis Functions (Recursive Definition)
Degree 0 (step function):
```
N_{i,0}(u) = 1   if t_i ≤ u < t_{i+1}
             0   otherwise
```

Higher degrees (recursive):
```
N_{i,p}(u) = [(u - t_i)/(t_{i+p} - t_i)] · N_{i,p-1}(u)
           + [(t_{i+p+1} - u)/(t_{i+p+1} - t_{i+1})] · N_{i+1,p-1}(u)
```
Convention: 0/0 = 0 (whenever denominator is zero, the whole term is zero).

**Local support:** N_{i,p}(u) is nonzero ONLY on the interval [t_i, t_{i+p+1}]. This is the key property giving B-splines their local control — moving control point P_i only affects the curve in the interval [t_i, t_{i+p+1}].

### de Boor's Algorithm — Efficient Evaluation
Given parameter u in [t_k, t_{k+1}), only p+1 control points are active: P_{k-p}, ..., P_k.
The algorithm computes C(u) via triangle scheme:

```
Initialize: d[j][0] = P_{k-p+j}  for j = 0, 1, ..., p

For r = 1, 2, ..., p:
  For j = 0, 1, ..., p-r:
    α = (u - t_{k-p+j+r}) / (t_{k+j+1} - t_{k-p+j+r})
    d[j][r] = (1 - α) · d[j][r-1] + α · d[j+1][r-1]

C(u) = d[0][p]
```

```python
def de_boor(knots, control_pts, degree, u):
    """
    Evaluate a B-spline at parameter u using de Boor's algorithm.
    knots: knot vector (list of floats)
    control_pts: list of control points (each can be 2D, 3D, etc.)
    degree: polynomial degree (p)
    u: parameter value
    Returns: point on the curve
    """
    import numpy as np
    
    n = len(control_pts) - 1
    p = degree
    k = None
    
    # Find knot span [t_k, t_{k+1}) containing u
    for i in range(p, n + 1):
        if knots[i] <= u < knots[i+1]:
            k = i
            break
    if k is None:
        k = n  # handle u == last knot
    
    # Initialize d with relevant control points
    d = [np.array(control_pts[k - p + j], dtype=float) for j in range(p + 1)]
    
    # de Boor triangle
    for r in range(1, p + 1):
        for j in range(p - r + 1):
            i_global = k - p + j + r
            denom = knots[k + j + 1] - knots[k - p + j + r]
            if abs(denom) < 1e-12:
                alpha = 0.0
            else:
                alpha = (u - knots[k - p + j + r]) / denom
            d[j] = (1.0 - alpha) * d[j] + alpha * d[j + 1]
    
    return d[0]

# Example: cubic B-spline with 5 control points (spine setup)
P = [[0,0,0], [1,2,0], [3,3,0], [5,2,0], [6,0,0]]  # 5 control points
T = [0, 0, 0, 0, 0.5, 1, 1, 1, 1]                   # clamped cubic knot vector
degree = 3

# Evaluate at multiple parameters
params = [i/20.0 for i in range(21)]
curve_pts = [de_boor(T, P, degree, u) for u in params]
```

### NURBS — Non-Uniform Rational B-Splines
NURBS extends B-splines with a weight wᵢ per control point:
```
C(u) = Σᵢ wᵢ · Nᵢ,ₚ(u) · Pᵢ  /  Σᵢ wᵢ · Nᵢ,ₚ(u)
```
The denominator normalizes the weights. When all wᵢ = 1, NURBS reduces to a standard B-spline. Non-uniform weights allow exact representation of conics (circles, ellipses) — impossible with polynomial B-splines.

**Maya NURBS curve/surface:** Both are NURBS with degree 1 (linear), 2 (quadratic), or 3 (cubic). A NURBS surface is a tensor product of two B-splines:
```
S(u, v) = Σᵢ Σⱼ Nᵢ,ₚ(u) · Nⱼ,q(v) · Pᵢⱼ
```
The ribbon spine uses a NURBS surface with degree-3 in V (along the spine) and degree-1 in U (across the width).

### Ribbon Spine: The B-Spline Connection
The 4-5 guide controls on a ribbon drive the NURBS surface control points. When you move the chest or hips control:
1. The skinCluster/direct bind of those controls to the NURBS CV positions updates the control point lattice.
2. Maya recomputes the entire NURBS surface using the Cox-de Boor evaluation.
3. `pointOnSurfaceInfo` samples the resulting surface at parameter (u, v) for each joint position.

The **twist behavior** of the ribbon is a direct consequence of how the B-spline basis interpolates the tangent vector: at each evaluated point, the surface tangent U (∂S/∂u) and tangent V (∂S/∂v) form the local frame. Twist artifacts at inflection points are due to the tangent flipping — solvable by adding an extra CV at those points to maintain tangent direction.

### Degree 3 vs Degree 1 Ribbons
| Degree | Continuity | Behavior | Use case |
|--------|-----------|----------|----------|
| 1 (linear) | C⁰ | Sharp kinks at CVs | Technical surfaces, proxies |
| 2 (quadratic) | C¹ | Smooth tangents | Acceptable for real-time |
| 3 (cubic) | C² | Smooth curvature | Production spine, limbs |

The default Maya ribbon uses degree 3 — guaranteeing smooth curvature (C²) everywhere between knots. This matches the visual expectation of organic spine motion.

## Implementación en Maya

```python
import maya.cmds as cmds

def build_ribbon_surface(name, cv_count=4, length=10.0, width=0.5, degree=3):
    """
    Create a NURBS ribbon surface for use as spine ribbon.
    Returns the surface name.
    """
    # Create NURBS plane: spans in V = number of segments
    ribbon = cmds.nurbsPlane(
        name=name,
        width=width,
        lengthRatio=length / width,
        u=1,           # 1 span in U (width direction)
        v=cv_count - 1,  # spans in V (length direction)
        degree=degree,
        axis=[0, 1, 0]
    )[0]
    return ribbon

def sample_ribbon_joint(ribbon, u_param, v_param, joint_name):
    """
    Create a joint driven by a pointOnSurfaceInfo node at (u, v) on the ribbon.
    Uses the matrix rivet pattern to avoid follicles.
    """
    posi = cmds.createNode('pointOnSurfaceInfo', n=f'{joint_name}_posi')
    cmds.connectAttr(f'{ribbon}.worldSpace[0]', f'{posi}.inputSurface')
    cmds.setAttr(f'{posi}.parameterU', u_param)
    cmds.setAttr(f'{posi}.parameterV', v_param)
    cmds.setAttr(f'{posi}.turnOnPercentage', 1)  # percentage mode (0-1 range)

    # Build 4×4 matrix from surface tangents + normal
    fbm = cmds.createNode('fourByFourMatrix', n=f'{joint_name}_fbm')
    # Row 0: tangent U (X axis)
    for i, ch in enumerate('xyz'):
        cmds.connectAttr(f'{posi}.normalizedTangentU{ch.upper()}', f'{fbm}.in0{i}')
    # Row 1: normal (Y axis)
    for i, ch in enumerate('xyz'):
        cmds.connectAttr(f'{posi}.normalizedNormal{ch.upper()}', f'{fbm}.in1{i}')
    # Row 2: tangent V × normal (Z axis) — via vectorProduct cross
    vp = cmds.createNode('vectorProduct', n=f'{joint_name}_cross')
    cmds.setAttr(f'{vp}.operation', 2)  # cross product
    for i, ch in enumerate('XYZ'):
        cmds.connectAttr(f'{posi}.normalizedTangentU{ch}', f'{vp}.input1{ch}')
        cmds.connectAttr(f'{posi}.normalizedNormal{ch}', f'{vp}.input2{ch}')
    for i, ch in enumerate('XYZ'):
        cmds.connectAttr(f'{vp}.output{ch}', f'{fbm}.in2{i}')
    # Row 3: position
    for i, ch in enumerate('XYZ'):
        cmds.connectAttr(f'{posi}.position{ch}', f'{fbm}.in3{i}')

    # Decompose into joint
    dcmp = cmds.createNode('decomposeMatrix', n=f'{joint_name}_dcmp')
    cmds.connectAttr(f'{fbm}.output', f'{dcmp}.inputMatrix')
    
    jnt = cmds.joint(name=joint_name)
    cmds.connectAttr(f'{dcmp}.outputTranslate', f'{jnt}.translate')
    cmds.connectAttr(f'{dcmp}.outputRotate', f'{jnt}.rotate')
    return jnt
```

**Why de Boor matters for production:**
- The `parameterV` range for `pointOnSurfaceInfo` maps directly to the B-spline parameter space `[0, 1]` in percentage mode. Joints placed at `v=0.0, 0.25, 0.5, 0.75, 1.0` are NOT uniformly spaced unless the knot vector is uniform — on a clamped B-spline the end joints will be slightly closer together. This is why evenly-spaced spine joints sometimes produce slightly non-uniform spacing: it's the clamped knot vector effect.

## Comparación con autorig_tools
El algoritmo de de Boor es la matemática que Maya ejecuta internamente cada vez que se evalúa el ribbon spine. Entenderlo explica por qué la distribución de joints a lo largo del ribbon no es perfectamente uniforme con parámetros equidistantes (efecto del knot vector clamped), y por qué el giro (twist) puede tener inflexiones inesperadas en determinados ángulos. Este conocimiento permite ajustar mejor el setup del ribbon en autorig_tools: usar `turnOnPercentage=1` + parámetros adaptados al knot vector real, o usar una curva de retiketing para uniformizar la distribución de joints.

## Aplicable directamente
YES — La función `de_boor()` en Python puede usarse en el proceso de build para calcular posiciones exactas de joints a lo largo del ribbon con distribución paramétrica correcta. La corrección de turnOnPercentage en `pointOnSurfaceInfo` es un cambio de 1 línea en el código de build del ribbon de autorig_tools.

## Fuente
- MTU de Boor's Algorithm: https://pages.mtu.edu/~shene/COURSES/cs3621/NOTES/spline/B-spline/de-Boor.html
- MIT Hyperbook B-spline curves: https://web.mit.edu/hyperbook/Patrikalakis-Maekawa-Cho/node17.html
- CMU B-Spline Curves (CAGD): https://www.cs.cmu.edu/afs/cs/academic/class/15456-f15/Handouts/CAGD-chapter8.pdf
- Wikipedia de Boor's algorithm: https://en.wikipedia.org/wiki/De_Boor's_algorithm
