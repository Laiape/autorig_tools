---
source: https://users.cs.utah.edu/~ladislav/kavan07skinning/kavan07skinning.pdf
found: 2026-05-11
category: math
priority: 1
tags: [maya, rigging, math, skinning, dual-quaternion, LBS, deformation, siggraph]
status: NEW
---

# Dual Quaternion Skinning (DQS) — Math, Artifacts & LBS Comparison

## Descripción
Técnica de skinning que reemplaza la interpolación lineal de matrices de Linear Blend Skinning (LBS) por interpolación de dual cuaterniones unitarios. Presentada por Kavan et al. (I3D 2007 / Siggraph 2014), resuelve el artefacto candy-wrapper/twisting de LBS sin coste computacional significativo. Es la alternativa más práctica y ampliamente adoptada a LBS en producción en tiempo real.

## Fundamento matemático / técnico

### Dual Quaternion Representation
A unit dual quaternion `q̂ = q₀ + ε·qₑ` encodes a rigid transform (rotation + translation):
- `q₀`: real part — encodes rotation (unit quaternion, |q₀|=1)
- `qₑ`: dual part — encodes translation: `qₑ = (1/2) · t̂ · q₀` where `t̂ = (0, tx, ty, tz)`
- Orthogonality constraint: `q₀ · qₑ* + qₑ · q₀* = 0`
- ε is the dual unit: ε² = 0

### DQS Blending Formula
Given N bones with weights wᵢ and transforms as unit dual quaternions q̂ᵢ:
```
q̂_blend = Σᵢ (wᵢ · q̂ᵢ) / |Σᵢ (wᵢ · q̂ᵢ)|
```
This is DLB (Dual quaternion Linear Blending) — blending in the dual quaternion vector space then normalizing.

**Anti-podality fix (critical):** q̂ and -q̂ represent the same transform. Blending without checking sign produces the zero quaternion. Rule: if `dot(q̂ᵢ.real, q̂₀.real) < 0`, negate q̂ᵢ before blending.

### Why LBS Fails: The Candy-Wrapper Artifact
LBS blends bone matrices linearly: `M_blend = Σᵢ wᵢ · Mᵢ`

At 180° twist between two bones, their matrices average to a rank-deficient projection — the mesh collapses to a plane or a point ("candy wrapper"). This happens because the set of rotation matrices SO(3) is NOT a linear subspace; linear combinations can exit the valid rotation manifold.

DQS interpolates on the unit dual-quaternion manifold (a non-linear space), always producing valid rigid transforms.

### DQS Bulging Artifact
DQS's own failure mode: **bulging near joints** at high bend angles. For a simple 2-bone chain, DQS reduces to spherical blending. The interpolated position traces an arc, causing the mesh to bulge outward. Worse than LBS at elbow-like joints.

**Fix — Geometric DQS (Kavan 2008):** Pre-compute per-vertex optimal blend coefficients that minimize deviation from the "correct" rigid deformation. The correction term is added to the standard DQS result, suppressing bulging. Cost: a precomputation pass per mesh; runtime cost unchanged (~1.05× LBS).

### Algorithm: Matrix → Dual Quaternion Conversion
```python
import numpy as np

def mat4_to_dq(M):
    # M: 4x4 row-major numpy array
    # Extract rotation (upper 3x3) and translation (column 3)
    R = M[:3, :3]
    t = M[:3, 3]
    # Rotation quaternion q0 = [w, x, y, z]
    trace = R[0,0] + R[1,1] + R[2,2]
    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (R[2,1] - R[1,2]) * s
        y = (R[0,2] - R[2,0]) * s
        z = (R[1,0] - R[0,1]) * s
    else:  # ... (handle other cases for numeric stability)
        raise NotImplementedError("use scipy.spatial.transform.Rotation for robustness")
    q0 = np.array([w, x, y, z])
    # Translation dual part: qe = 0.5 * t_pure * q0
    t_quat = np.array([0, t[0], t[1], t[2]])
    qe = 0.5 * quat_mul(t_quat, q0)
    return q0, qe

def blend_dqs(q0s, qes, weights):
    # Anti-podality: flip sign if dot with first quaternion is negative
    ref = q0s[0]
    for i in range(1, len(q0s)):
        if np.dot(q0s[i], ref) < 0:
            q0s[i] = -q0s[i]
            qes[i] = -qes[i]
    q0b = sum(w * q for w, q in zip(weights, q0s))
    qeb = sum(w * q for w, q in zip(weights, qes))
    norm = np.linalg.norm(q0b)
    return q0b / norm, qeb / norm
```

### Relative Performance of Skinning Methods
| Method | Relative Cost | Main Artifact | GPU-friendly |
|--------|--------------|---------------|--------------|
| LBS | 1× (baseline) | Candy-wrapper collapse | Yes |
| DQS | ~1.05× | Joint bulging | Yes (Maya 2022+) |
| Geometric DQS | ~1.1× | Minor residual bulge | Yes |
| Log-matrix | ~2.5× | Slight volume loss | No |
| SBS | ~3× | Bulging | No |
| CoR | ~1.1× | Almost none | Yes |

## Implementación en Maya

Maya's skinCluster has **Skinning Method** (native since Maya 2012):
- `0` = Classic Linear (LBS)
- `1` = Dual Quaternion
- `2` = Weight Blended (per-vertex blend: 0.0=LBS, 1.0=DQS — most useful)

```python
import maya.cmds as cmds

skin = cmds.ls(type='skinCluster')[0]
# Full DQS
cmds.setAttr(f'{skin}.skinningMethod', 1)

# Blended mode — then paint dqBlendWeights attribute:
# 0.0 at flat/planar areas (avoid DQS bulging)
# 1.0 at twist joints (eliminate LBS candy-wrapper)
cmds.setAttr(f'{skin}.skinningMethod', 2)

# Query which vertices have high dqBlendWeight:
weights = cmds.getAttr(f'{skin}.dqBlendWeights[*]')
```

**GPU Override compatibility:** DQS skinCluster is supported for GPU Override in Maya 2022+. Performance comparable to LBS on GPU.

## Comparación con autorig_tools

autorig_tools usa skinCluster LBS estándar. El candy-wrapper en muñeca, hombro y rodilla se corrige actualmente con correctivos RBF. Cambiar a `skinningMethod = 2` (blended) en esas zonas podría reducir la necesidad de correctivos y simplificar el rig. No requiere plugins — es nativo de Maya.

## Aplicable directamente
YES — Añadir parámetro `skinning_method` ('lbs'|'dqs'|'blended') a la función de bind skin en autorig_tools. Probar en forearm twist y shoulder. Tiempo estimado: 2-3 horas para implementar y probar.

## Fuente
- Paper I3D 2007: https://users.cs.utah.edu/~ladislav/kavan07skinning/kavan07skinning.pdf
- Geometric DQS 2008: https://users.cs.utah.edu/~ladislav/kavan08geometric/kavan08geometric.pdf
- Siggraph 2014 Skinning Course: https://skinning.org/direct-methods.pdf
- ACM: https://dl.acm.org/doi/10.1145/1230100.1230107
