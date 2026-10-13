---
source: https://arxiv.org/abs/2508.10513
found: 2026-08-31
category: math
priority: 1
tags: [maya, rigging, math, Lie-group, SO3, SE3, splines, ribbon, de-Boor, exponential-map]
status: NEW
---

# POE Splines on Lie Groups: SO(3) and SE(3) — Müller 2025/2026

## Descripción
Paper publicado en *International Journal for Numerical Methods in Engineering* (Wiley) con preprint en arXiv:2508.10513. Andreas Müller formaliza una familia de splines en grupos de Lie (SO(3) para rotaciones, SE(3) para poses rígidas) llamados **POE splines** (Product Of Exponentials), derivados de condiciones de contorno sobre la ecuación de Poisson en el grupo. La limitación de los métodos previos (De Casteljau en Lie groups, Shoemake SLERP) es que cada curva local arranca en la identidad del grupo — este paper elimina esa restricción. Aplicación principal: reconstrucción de varillas Cosserat (colas, tentáculos, columnas flexibles) y splines de rotación libres de gimbal lock.

## Fundamento matemático / técnico

A **k-th order POE spline** on Lie group G is the curve:

```
γ(t) = g_0 · exp(a_1(t)·X_1) · exp(a_2(t)·X_2) · ... · exp(a_k(t)·X_k)
```

where X_i ∈ g (Lie algebra of G), and a_i(t) are scalar coefficient functions satisfying boundary conditions. The local geodesic between two group elements g, h is:

```
γ(t) = g · exp(t · log(g^{-1} · h)),  t ∈ [0,1]
```

The key departure: instead of forcing each local segment to start at identity (the De Casteljau Lie group approach), the Poisson equation formulation allows local curves to have **arbitrary starting points** g_i while preserving the group geometry.

**For SO(3) — 3rd order algorithm:**
Given rotation matrices R_0, R_1 at boundary, with prescribed angular velocities ω_0, ω_1 ∈ ℝ³ (Lie algebra so(3)):

```
a_1(t) = t·ω_0 + t²·α + t³·β          (cubic in t)
a_2(t) = t²·η + t³·μ                   (cubic, vanishes at t=0)

R(t) = R_0 · exp(a_1(t)·Ω_1) · exp(a_2(t)·Ω_2)
```

where Ω_i are skew-symmetric matrices (generators). Coefficients α,β,η,μ are solved from the boundary conditions R(1)=R_1, Ṙ(1)=ω_1.

**For SE(3) — screw motion spline:**
SE(3) element: T = (R, p) — rotation + translation. Lie algebra se(3): (Ω, v) where Ω ∈ so(3), v ∈ ℝ³. The exponential map:

```
exp((Ω, v)·θ) = (exp(Ω·θ), (I - exp(Ω·θ)) · Ω^{-1} · v + θ·v)
```

For zero-rotation (translation only): exp((0, v)·θ) = (I, θ·v).

A 3rd-order SE(3) spline satisfies:
```
T(t) = T_0 · exp(a_1(t)·S_1) · exp(a_2(t)·S_2) · exp(a_3(t)·S_3)
```
where S_i = (Ω_i, v_i) are screw axes. This is the same algebraic structure as ScLERP but extended to cubic Hermite matching at endpoints.

**Cosserat rod reconstruction**: The curve γ(t) ∈ SE(3) encodes both the centerline position p(t) and the cross-section frame R(t) simultaneously. Bending and twisting are captured without coordinate singularities. Discretized with N frames T_0, ..., T_N connected by POE segments.

## Implementación en Maya

**Direct node graph equivalent for SO(3) POE segment:**

```
# At each ribbon point, blend between two frames using POE
# instead of Euclidean parameter on de Boor:

# Step 1: Extract local tangent (Lie algebra element)
decompose0 = cmds.createNode('decomposeMatrix')  # → quaternion at knot 0
decompose1 = cmds.createNode('decomposeMatrix')  # → quaternion at knot 1

# Step 2: quaternionProduct to get relative rotation = log(R0^-1 * R1)
quatProd = cmds.createNode('quatProd')
# inputQuat[0] = conjugate(q0), inputQuat[1] = q1 → relative rotation

# Step 3: quatToAxisAngle → (axis, angle) — this IS the Lie algebra element
# Step 4: Scale angle by t (parameter along segment)
# Step 5: axisAngleToQuat → exp(t·X)
# Step 6: quatProd(q0, exp(t·X)) → R(t)
```

**Python approach for ribbon spine (pure numpy, offline solve):**

```python
import numpy as np
from scipy.spatial.transform import Rotation, Slerp

def poe_segment_SO3(R0, R1, t_arr, omega0=None, omega1=None):
    """
    3rd-order POE spline on SO(3) from R0 to R1.
    If omega0/omega1 are None, uses geodesic (SLERP equivalent).
    Returns array of rotation matrices at parameters t_arr.
    """
    key_rots = Rotation.from_matrix(np.stack([R0, R1]))
    if omega0 is None and omega1 is None:
        # Zero-velocity: reduces to geodesic (SLERP)
        slerp = Slerp([0, 1], key_rots)
        return slerp(t_arr).as_matrix()
    else:
        # Full POE: solve for coefficients from boundary conditions
        # (requires small nonlinear solve per segment — offline)
        raise NotImplementedError("Full POE with tangents: see paper Alg.1")

def build_ribbon_poe(knot_matrices, params):
    """
    knot_matrices: list of 4x4 world matrices at ribbon knots (SE(3))
    params: list of t values (0..1) for joint positions on ribbon
    Returns joint matrices using POE segments instead of de Boor.
    """
    results = []
    for t in params:
        # Find segment
        seg = int(t * (len(knot_matrices) - 1))
        seg = min(seg, len(knot_matrices) - 2)
        local_t = t * (len(knot_matrices) - 1) - seg
        T0 = knot_matrices[seg]
        T1 = knot_matrices[seg + 1]
        # Geodesic on SE(3): T(t) = T0 · exp(t · log(T0^-1 · T1))
        rel = np.linalg.inv(T0) @ T1
        # log via SO(3) part + translation
        R_rel = rel[:3,:3]
        p_rel = rel[:3, 3]
        r = Rotation.from_matrix(R_rel)
        rotvec = r.as_rotvec()  # = Ω·θ in so(3)
        R_t = Rotation.from_rotvec(local_t * rotvec).as_matrix()
        p_t = local_t * p_rel  # linear for geodesic (t=0 approx)
        T_t = np.eye(4)
        T_t[:3,:3] = R_t
        T_t[:3, 3] = p_t
        results.append(T0 @ T_t)
    return results
```

**Node graph for ribbon: replace current de Boor UV parameter with POE-computed parameter:**
- Current: `nurbsSurface.pointOnSurface(u,v)` → matrix decompose → joint
- POE upgrade: pre-solve POE interpolated frames offline → bake into `wtAddMatrix` + `blendMatrix` blend using local_t weight

## Comparación con autorig_tools

Laia usa de Boor (Cox–de Boor recursivo) para el ribbon spine en autorig_tools, operando sobre posiciones Euclidianas de los control points. El problema: al interpolar posiciones Euclidianas en zonas de curvatura alta (columna muy curvada, cola en S), el frame local de cada joint se calcula por derivada numérica → inestabilidad de twist. POE splines operan directamente en SE(3): cada frame del ribbon es una pose rígida interpolada en la variedad, no un punto + derivada. Resultado: twist consistente geométricamente incluso bajo curvas extremas. El ScLERP file ya en Drive (2026-06-29) cubre el caso lineal (grado 1); este paper extiende a grado 3-4 con tangentes prescritas — directamente aplicable a un ribbon spine de calidad VFX.

## Aplicable directamente

PARTIAL — El framework matemático requiere una implementación Python offline (scipy Rotation, numpy) para pre-computar los frames del ribbon, que luego se "hornean" en el rig como weights en nodos wtAddMatrix. El workflow: calcular POE frames en Python al build-time → almacenar en atributos float[] en el ribbon surface → usar `blendMatrix`/`wtAddMatrix` para interpolar en runtime. La implementación completa del solver POE de orden 3 requiere 4-8h para integrar en autorig_tools, pero el ganancia en calidad de twist para colas/spines VFX es significativa.

## Fuente

- Paper principal: https://arxiv.org/abs/2508.10513
- DOI Wiley IJNME: https://onlinelibrary.wiley.com/doi/full/10.1002/nme.70088
- HTML versión: https://arxiv.org/html/2508.10513v1
- Paper SO(3)/SE(3) Lie algebras (fondo): https://arxiv.org/pdf/2205.12572
- Cosserat rods context: https://arxiv.org/pdf/2508.10513
