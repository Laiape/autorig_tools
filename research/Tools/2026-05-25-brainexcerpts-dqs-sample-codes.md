---
source: https://github.com/brainexcerpts/Dual-Quaternion-Skinning-Sample-Codes
found: 2026-05-25
category: tool
priority: 3
tags: [maya, C++, dual-quaternion, skinning, DQS, LBS, tutorial, math, implementation, github]
status: NEW
---

# Dual-Quaternion-Skinning-Sample-Codes (brainexcerpts) — Tutorial C++ de DQS

## Descripción
Repositorio de referencia en C++ para implementar Dual Quaternion Skinning (DQS) desde cero, incluyendo los cuatro algoritmos principales: LBS clásico, DQS estándar (Kavan 2007), DQS sin bulging (bulge-free variant), y DQS con soporte de escala. Con 71 estrellas y licencia MIT, es el recurso de referencia más citado para entender la matemática de implementación de DQS en código real (más accesible que los PDFs de SIGGRAPH). La base matemática cubre: álgebra de cuaterniones duales, blending DLB, comparación con LBS, y el artifact de bulging.

## Fundamento matemático / técnico

### Dual Quaternion Mathematics

A dual quaternion `q̂` has the form:
```
q̂ = q_r + ε·q_d
```
where:
- `q_r` = the **real** part (unit quaternion representing rotation)
- `q_d` = the **dual** part (encodes translation)
- `ε` = dual unit, ε² = 0

Relationship between translation t and the dual part:
```
q_d = (1/2) · t · q_r
where t = (0, tx, ty, tz) treated as a pure quaternion
```

A rigid body transformation (rotation R, translation t) becomes:
```
q_r = rotation quaternion (unit)
q_d = 0.5 * (tx·i + ty·j + tz·k) * q_r
```

**Dual Quaternion Blending (DLB — Direct Linear Blending):**
```
b̂ = Σᵢ wᵢ · q̂ᵢ        (weighted sum of dual quaternions)
b̂ = b̂ / |b̂_r|          (normalize real part to unit length)
```

Then convert `b̂` back to rotation+translation:
```
t_blend = 2 · b̂_d · conjugate(b̂_r)   (translation)
R_blend = from_quaternion(b̂_r)         (rotation)
```

**Antipodality fix (critical):**
```
// Ensure all dual quats are in the same hemisphere as q̂₀
for (int i = 1; i < n_bones; i++) {
    if (dot(q_list[0].real, q_list[i].real) < 0.0f) {
        q_list[i] = -q_list[i];  // negate both real and dual parts
    }
}
```
Without this fix, DLB produces wrong results when two bones have rotations >180° apart.

---

### Repository Contents (from README)

**File structure:**
```
quat_cu.hpp        — quaternion type: struct quat { float w, x, y, z; }
dual_quat_cu.hpp   — dual quaternion: struct dquat { quat real, dual; }
vec3.hpp           — 3D vector operations
mat3.hpp           — 3×3 matrix
transfo.hpp        — transformation: rotation + translation wrapper
usage.cpp          — main examples demonstrating all four algorithms
```

**Implemented algorithms:**

1. **LBS (Linear Blend Skinning)** — baseline:
```cpp
vec3 lbs_point(vec3 p, std::vector<Transfo> bones, std::vector<float> weights) {
    mat3 blend_matrix = mat3::zero();
    vec3 blend_trans  = vec3::zero();
    for (int i = 0; i < bones.size(); i++) {
        blend_matrix += weights[i] * bones[i].rotation_matrix();
        blend_trans  += weights[i] * bones[i].translation;
    }
    // blend_matrix is NOT orthogonal when weights mix multiple rotations
    return blend_matrix * p + blend_trans;  // candy-wrapper artifact here
}
```

2. **DQS standard (Kavan 2007)**:
```cpp
vec3 dqs_point(vec3 p, std::vector<dquat> bone_dquats, std::vector<float> weights) {
    dquat blend = dquat::zero();
    
    // Antipodality check against first bone
    for (int i = 0; i < bone_dquats.size(); i++) {
        float sign = (dot(bone_dquats[0].real, bone_dquats[i].real) >= 0) ? 1.f : -1.f;
        blend += weights[i] * sign * bone_dquats[i];
    }
    
    blend.normalize_real();   // |real| = 1
    return blend.transform_point(p);
}
```

3. **Bulge-free DQS** (handles the shoulder bulging artifact):
```cpp
// The bulging artifact in standard DQS occurs because the blended dual quat
// follows a circular arc (SLERP path) instead of a straight line.
// Fix: project the point onto the linear path, then re-sphere it.
vec3 bulge_free_dqs(vec3 p, ...) {
    vec3 dqs_result = dqs_point(p, bone_dquats, weights);
    vec3 lbs_result = lbs_point(p, bones, weights);
    
    // Blend between DQS and LBS in a way that preserves DQS volume preservation
    // but reduces bulging at joints:
    float correction = compute_bulge_correction(weights, bone_dquats);
    return lerp(dqs_result, lbs_result, correction);
}
```

4. **DQS with scale** — extends DQS to handle non-uniform bone scaling:
```cpp
// Scale is not directly representable in dual quaternions.
// Solution: decompose transform into (scale, rotation+translation),
// apply LBS to scale separately, then DQS to rotation+translation.
```

---

### When to Use Each Algorithm

| Algorithm | Candy wrapper | Bulging | Scale support | Cost |
|-----------|-------------|---------|--------------|------|
| LBS | YES (artifact) | NO | YES | Lowest |
| DQS | NO | YES (artifact) | NO | Low (+~10%) |
| Bulge-free DQS | NO | Reduced | NO | Medium |
| DQS + scale | NO | YES | YES | Medium-high |

Maya's built-in `skinCluster.skinningMethod`:
- `0` = Linear Blend (LBS)
- `1` = Dual Quaternion (DQS standard)
- `2` = Weight Blended (per-vertex blend of LBS and DQS — practical compromise)

Method `2` is the production choice: use LBS weights near folding joints (elbows, knees where DQS bulges) and DQS weights near twist joints (wrist, forearm where LBS candy-wraps).

## Implementación en Maya

The repository is C++ (not a Maya plugin), intended as a reference implementation for understanding the math. For Maya integration, the concepts map to:

```python
import maya.cmds as cmds

def set_skinning_method(mesh, method=2):
    """
    Set skinCluster skinning method.
    0=LBS, 1=DQS, 2=Weight Blended
    """
    skin = cmds.listHistory(mesh, type='skinCluster')
    if skin:
        cmds.setAttr(f'{skin[0]}.skinningMethod', method)
        return skin[0]
    return None

def optimize_skinning_method_by_region(mesh, skin_cluster):
    """
    Set per-vertex blend weights for weight-blended mode (method=2).
    DQS=1.0 near twist joints, LBS=1.0 near fold joints.
    """
    # For wrist/forearm area (twist joints → full DQS)
    wrist_verts = get_vertices_near_joint(mesh, 'wrist_jnt', radius=5.0)
    for v in wrist_verts:
        cmds.setAttr(f'{skin_cluster}.blendWeights[{v}]', 1.0)  # 1.0 = DQS
    
    # For elbow area (fold joint → LBS to avoid bulge)
    elbow_verts = get_vertices_near_joint(mesh, 'elbow_jnt', radius=3.0)
    for v in elbow_verts:
        cmds.setAttr(f'{skin_cluster}.blendWeights[{v}]', 0.0)  # 0.0 = LBS
```

## Comparación con autorig_tools

El repositorio es principalmente material de referencia matemático para entender la implementación de DQS — no es un plugin de Maya. Su valor para Laia es como referencia de implementación cuando se desee añadir soporte explícito de configuración per-zona LBS/DQS en el pipeline de skinning de autorig_tools. El archivo `2026-05-11-dual-quaternion-skinning-math.md` ya cubre la teoría; este repositorio aporta el código de referencia concreto en C++ para cada variante del algoritmo, incluyendo el bulge-free variant que no está en los papers de Kavan de forma tan accesible.

## Aplicable directamente

PARTIAL — **Como referencia de implementación:**
1. La función `set_skinning_method(mesh, method=2)` de arriba es aplicable directamente en autorig_tools para asegurarse de que los personajes hero publiquen con `skinningMethod=2` (Weight Blended) en lugar del LBS por defecto.
2. La lógica de `blendWeights` por región (DQS en zonas de twist, LBS en zonas de pliegue) es un patrón post-skinning que se puede añadir como paso final del `build_skincluster()` en autorig_tools.
3. El código C++ del repo sirve como referencia si se desea implementar DQS en un MPxDeformerNode custom en el futuro.

## Fuente
- https://github.com/brainexcerpts/Dual-Quaternion-Skinning-Sample-Codes
- Paper original DQS (Kavan 2007): https://team.inria.fr/imagine/files/2014/10/skinning_dual_quaternions.pdf
- Geometric Skinning (Kavan 2008, bulge-free): https://users.cs.utah.edu/~ladislav/kavan08geometric/kavan08geometric.pdf
