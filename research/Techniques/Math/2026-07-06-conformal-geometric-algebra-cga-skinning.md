---
source: https://link.springer.com/article/10.1007/s00371-016-1270-8
found: 2026-07-06
category: math
priority: 1
tags: [maya, python, rigging, math, cga, geometric-algebra, skinning, dual-quaternions, GPU, opencl]
status: NEW
---

# Conformal Geometric Algebra (CGA) para Character Skinning

## Descripción
Conformal Geometric Algebra (CGA) es un marco matemático unificado que subsume quaterniones, dual quaterniones y matrices en un único álgebra de 5 dimensiones. Su ventaja crítica para rigging es que los *motors* de CGA representan rotación, traslación Y dilatación (escala uniforme) en la misma representación algebraica — algo que DQS no puede hacer. Propuesto para GPU skinning en 2016 (Visual Computer) y ampliado en 2025 con aplicaciones de neural rendering (arxiv 2511.15398). Representa el nivel matemático siguiente a DQS.

## Fundamento matemático / técnico

### Embedding: Espacio Euclidiano en CGA 5D

CGA embeds 3D Euclidean space into a 5D null-cone space:
- **Basis**: {e₁, e₂, e₃, e₀, e∞}
- **e₀**: null vector for the origin (e₀² = 0)
- **e∞**: null vector for point at infinity (e∞² = 0)
- **Cross metric**: e₀ · e∞ = -1

A 3D point **p = (x, y, z)** is encoded as a null vector in CGA:
```
P_cga = x·e₁ + y·e₂ + z·e₃ + ½(x²+y²+z²)·e∞ + e₀
```
This is the "standard embedding" — the extra terms make P_cga a null vector (P·P = 0).

### Motors: rotación + traslación en un objeto algebraico

A **motor** M encodes a rigid body motion (rotation + translation):
```
M = T · R

Rotation rotor:
R = cos(θ/2) - sin(θ/2)·B̂    [B̂ = normalized bivector for rotation axis]
e.g., rotation by θ around Z:  R = cos(θ/2) - sin(θ/2)·(e₁∧e₂)

Translation motor:
T = 1 - (t/2)·e∞    [t = translation vector as te∞ dual]
  = 1 - (tx/2)·e∞e₁ - (ty/2)·e∞e₂ - (tz/2)·e∞e₃
  = 1 + (1/2)·t_vec·e∞    where t_vec = tx·e₁ + ty·e₂ + tz·e₃
```

**Note:** A motor M in CGA has the same 8-float encoding as a dual quaternion:
```
M = (r₀ + r₁·e₂₃ + r₂·e₃₁ + r₃·e₁₂)      [rotation part = quaternion]
  + ε·(t₀ + t₁·e₂₃ + t₂·e₃₁ + t₃·e₁₂)    [translation part × ε = e∞₀]
```
This is why DQS and CGA give identical results for rotation+translation — they are the same algebra in different notation.

### Dilators: escala en CGA (la extensión clave)

A **dilator** D for uniform scale factor s:
```
D = cosh(log(s)/2) + sinh(log(s)/2)·(e∞∧e₀)
  = cosh(σ) + sinh(σ)·e∞₀     where σ = log(s)/2
```

A motor with dilation (Motorized Dilation):
```
M_full = D · T · R
```
Now a single CGA motor encodes rotation + translation + uniform scale in 16 floats.
This is the algebraic reason why squash/stretch can be handled natively without separate scale compensation nodes.

### CGA Skinning Formula

For a vertex p with bone motors {Mᵢ} and weights {wᵢ}:
```
Step 1: Blend motors (like DQS short-path blending)
        M_blend = normalize(Σᵢ wᵢ·Mᵢ)

Step 2: Apply via sandwiching product (versor product)
        P_final = M_blend · P_cga · reverse(M_blend)
```

The `reverse(M)` of a motor is its algebraic inverse: reverse(AB) = reverse(B)·reverse(A).

**Comparison with DQS:**
```
DQS:    q_blend = normalize(Σᵢ wᵢ·q̂ᵢ)
        p_final = q_blend · p · conjugate(q_blend)  [dual quaternion product]

CGA:    M_blend = normalize(Σᵢ wᵢ·Mᵢ)
        P_final = M_blend · P_cga · reverse(M_blend)
```
Mathematically identical for rotation+translation. CGA adds dilators for scaling.

### Motor Interpolation (CGA SLERP equivalent)

```
M(t) = M₁ · exp(t · log(M₁⁻¹ · M₂))    t ∈ [0,1]
```
where exp and log are the GA exponential/logarithm:
```
log(M) = L (a line / screw axis in GA)
exp(L) = cos(|L|) + sin(|L|)/|L| · L   [for rotation part]
       + translation part
```
This is screw interpolation (ScLERP) derived directly from the CGA algebra — no special case needed.

### Performance (from Visual Computer 2016 paper)

| Method | CPU time | GPU time | Notes |
|--------|----------|----------|-------|
| Matrix blending (LBS) | 1.0× (baseline) | — | 100% CPU |
| CGA motor blending | ~2.0× CPU | ~0.33× CPU | 3× GPU speedup vs CPU LBS |
| DQS (dual quat) | ~1.8× CPU | ~0.35× CPU | Similar GPU profile to CGA |
| CGA with dilation | ~2.5× CPU | ~0.40× CPU | Extra 8 floats for scale |

GPU path: CGA runs ~3× faster than CPU LBS baseline — same speedup class as DQS.

### GA-Unity (2024): Production-ready implementation

The GA-Unity package (arxiv 2406.11560) demonstrates production-ready CGA for real-time collaborative XR:
- Motor-based joint transforms replace quaternion+vector pairs
- Unified API: same motor for camera, character, object, and light transforms
- GPU-accelerated using shader-level GA operations (OpenCL/GLSL)

## Implementación en Maya

No native CGA support in Maya. Implementation paths:

### Option A: Python proof-of-concept (CPU)

```python
import numpy as np

def cga_point(x, y, z):
    """Encode a 3D point as a null vector in CGA (5D)."""
    return np.array([x, y, z, 0.5*(x*x+y*y+z*z), 1.0])
    # basis order: [e1, e2, e3, e_inf, e0]

def cga_motor_from_transform(R_quat, t_vec):
    """
    Build CGA motor from quaternion R and translation t.
    Returns 8-float motor (same encoding as dual quaternion).
    """
    # Rotation part (quaternion → rotor)
    qw, qx, qy, qz = R_quat
    r = np.array([qw, qx, qy, qz])
    # Translation motor (T = 1 + 0.5 * t∞)
    tx, ty, tz = t_vec
    d = np.array([0.0, tx/2, ty/2, tz/2])  # dual part
    # Motor = r + ε·d  (dual quaternion encoding)
    return np.concatenate([r, d])

def cga_skin_vertex(pos, motors, weights):
    """
    CGA skinning of a single vertex position.
    motors: (n_bones, 8) float array
    weights: (n_bones,) float array summing to 1.0
    """
    # Blend motors (same as DQS)
    m0 = motors[np.argmax(weights)]  # pivot for anti-podality
    blended = np.zeros(8)
    for i, (m, w) in enumerate(zip(motors, weights)):
        if np.dot(m, m0) < 0:
            m = -m  # anti-podality correction
        blended += w * m
    blended /= np.linalg.norm(blended[:4])  # normalize rotation part
    
    # Apply motor (simplified sandwich product for rotation+translation)
    # For pure rotation+translation: same as dual quaternion apply
    r = blended[:4]  # rotation quaternion
    d = blended[4:]  # dual (translation encoded)
    t = 2 * np.array([
        r[0]*d[1] - d[0]*r[1] - r[2]*d[3] + d[2]*r[3],  # tx
        r[0]*d[2] - d[0]*r[2] + r[1]*d[3] - d[1]*r[3],  # ty
        r[0]*d[3] - d[0]*r[3] - r[1]*d[2] + d[1]*r[2],  # tz
    ])
    # Rotate position using quaternion sandwich product
    q = r  # qw, qx, qy, qz
    p = np.array([0, *pos])  # pure quaternion
    rotated = quat_multiply(quat_multiply(q, p), quat_conjugate(q))[1:]
    return rotated + t
```

### Option B: MPxGPUDeformer (OpenCL)

```opencl
// cga_skinning_kernel.cl
typedef float8 Motor;  // 8-float motor encoding

Motor motor_blend(
    __global const Motor* motors,
    __global const float* weights,
    int bone_start, int num_bones
) {
    Motor blend = (Motor)(0.0f);
    Motor pivot = motors[bone_start];
    for (int b = 0; b < num_bones; b++) {
        Motor m = motors[bone_start + b];
        // Anti-podality: flip if dot product with pivot < 0
        if (dot(m.s0123, pivot.s0123) < 0.0f) m = -m;
        blend += weights[bone_start + b] * m;
    }
    // Normalize rotation part
    float rot_len = length(blend.s0123);
    blend /= rot_len;
    return blend;
}

float4 motor_apply_position(Motor m, float4 p) {
    // Rotation (quaternion sandwich product)
    float4 r = m.s0123;  // rotation quaternion
    float4 d = m.s4567;  // dual part (translation encoded)
    // ... sandwich product implementation ...
    // Same as dual quaternion apply — identical math
    float3 t = 2.0f * cross(r.s123, d.s123 + cross(r.s123, p.s012))
               + 2.0f * (r.s0 * d.s123 - d.s0 * r.s123);
    float3 rot_p = p.s012 + 2.0f * r.s0 * cross(r.s123, p.s012) 
                   + 2.0f * cross(r.s123, cross(r.s123, p.s012));
    return (float4)(rot_p + t, p.w);
}

__kernel void cga_skin(
    __global const float4* bind_positions,
    __global float4* output_positions,
    __global const Motor* bone_motors,
    __global const float* skin_weights,
    __global const int* influence_count,
    __global const int* influence_offset,
    int num_verts
) {
    int vid = get_global_id(0);
    if (vid >= num_verts) return;
    int start = influence_offset[vid];
    int count = influence_count[vid];
    Motor m = motor_blend(bone_motors, skin_weights, start, count);
    output_positions[vid] = motor_apply_position(m, bind_positions[vid]);
}
```

## Comparación con autorig_tools

autorig_tools usa skinCluster nativo con LBS y opcionalmente DQS (`skinningMethod=2`). CGA representa el siguiente paso: mismo rendimiento que DQS en GPU, pero con soporte nativo de dilators (escala). Para el ribbon spine de autorig_tools, esto significa que los nodos de compensación de volumen (`multiplyDivide` con power=0.5) podrían eliminarse si el ribbon usara un motor CGA con dilator — la escala está encodada en el propio motor. El `local_mmx` pattern actual es conceptualmente un motor CGA truncado (solo rotación + traslación).

## Aplicable directamente

PARTIAL — La matemática es idéntica a DQS para rigs sin escala (ya cubierto). El valor añadido es para:
1. **Squash/stretch de personajes cartoon**: reemplazar el stack de nodos de compensación de volumen con un motor CGA con dilator. Requiere MPxGPUDeformer en C++ (~1 semana de trabajo).
2. **Corto plazo**: implementar `cga_motor_from_transform()` en Python como alternativa a `decomposeMatrix` para representar transforms internamente en autorig_tools — más limpio algebraicamente.
3. **Investigación**: revisar si el ribbon spine puede beneficiarse de representar los joints como dilating motors para eliminar los `multiplyDivide` de stretch compensation.

## Fuente
- https://link.springer.com/article/10.1007/s00371-016-1270-8 (Visual Computer 2016 — GPU CGA animation skinning)
- https://arxiv.org/abs/2511.15398 (arxiv nov 2025 — One Algebra for All: CGA for XR/animation/neural rendering)
- https://arxiv.org/pdf/2406.11560 (GA-Unity 2024 — production CGA package)
- https://arxiv.org/abs/2007.04464 (CGA for cut/tear of skinned models, 2020)
- https://projectivegeometricalgebra.org/ (PGA reference — subalgebra of CGA)
