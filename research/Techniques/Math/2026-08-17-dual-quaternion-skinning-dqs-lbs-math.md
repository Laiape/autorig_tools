---
source: https://users.cs.utah.edu/~ladislav/kavan07skinning/kavan07skinning.html | https://dl.acm.org/doi/10.1145/1409625.1409627 | http://rodolphe-vaillant.fr/?e=29
found: 2026-08-17
category: math
priority: 1
tags: [maya, rigging, skinning, dual-quaternion, LBS, deformation, math]
status: NEW
---

# Dual Quaternion Skinning (DQS) vs Linear Blend Skinning — Matemática y Artefactos

## Descripción
DQS (Dual Quaternion Skinning, Kavan et al. 2007/2008) resuelve el artefacto más grave de LBS: el "candy-wrapper" (colapso volumétrico en twists). La causa raíz de LBS no es un fallo de rigging sino matemático — la interpolación lineal de matrices de rotación no preserva la rigidez. DQS reemplaza la mezcla de matrices por mezcla de dual quaterniones, que sí representan transformaciones rígidas exactas. El coste adicional es mínimo (~5% sobre LBS en GPU), y la integración en pipelines LBS existentes es directa.

## Fundamento matemático / técnico

### Dual Quaternions
A dual quaternion is: **q̂ = q_r + ε·q_d** where ε² = 0 (dual unit).

- **q_r** (real part): unit quaternion representing rotation
- **q_d** (dual part): encodes translation as q_d = ½·t·q_r, where t = (0, tx, ty, tz)

A rigid body transform T = (R, t) maps to dual quaternion:
```
q_r = rotation quaternion of R
q_d = 0.5 * (0, tx, ty, tz) * q_r   (pure quaternion product)
```

### LBS Failure — Why Candy-Wrapper Happens
LBS computes: **v' = Σᵢ wᵢ · Mᵢ · v**  (weighted sum of matrices)

Matrix interpolation is NOT a valid operation on SO(3) — the weighted average of two rotation matrices is not a rotation matrix. For a 180° twist, the blended matrix approaches zero (determinant → 0), collapsing volume to near-zero. This is the candy-wrapper artifact.

### DLB — Dual quaternion Linear Blending (Kavan 2007)
```
q̂_blend = Σᵢ wᵢ · q̂ᵢ                    # Linear blend (non-unit result)
q̂_norm  = q̂_blend / ‖q̂_blend‖_r          # Normalize (divide by real-part norm)
v' = q̂_norm · v · q̂_norm*                # Apply transform to vertex
```

Where `q̂·v·q̂*` is the dual quaternion sandwich product applied to v as a pure dual quaternion (0 + εv).

### DLB Normalization
For unit dual quaternions: ‖q̂‖_r = ‖q_r‖ = 1, and normalization becomes:
```
q̂_norm = q̂_blend / ‖q_r_blend‖
```
This is a 2D normalization in the 8D dual quaternion space.

### Geometric Dual Quaternion Blending (Kavan 2008 — DQB)
DLB produces bulging artifacts at joints (opposite problem to candy-wrapper). DQB fixes this:
```
# Scatter: convert each dual quaternion to a 4×4 transformation via:
M_i = reconstruct_matrix(q̂_i)
# Blend matrices normally
M_blend = Σᵢ wᵢ · Mᵢ
# Project back to rigid: Polar decomposition (SVD)
M_rigid = project_to_SO3(M_blend)   # R·S → take R only
```
DQB gives exact rigid motion interpolation but requires SVD per vertex per frame — too expensive for realtime without precomputation.

### Performance Comparison (published benchmarks)
| Method | Vertices | Time (ms) | vs LBS |
|--------|----------|-----------|--------|
| LBS (CPU) | 10k | 0.8 | 1× |
| DQS/DLB (CPU) | 10k | 1.1 | 1.4× |
| LBS (GPU) | 10k | 0.05 | — |
| DQS (GPU) | 10k | 0.06 | ~1.2× GPU LBS |

DQS GPU overhead over LBS is negligible (one extra normalization step).

### DQS Limitations
1. **No non-uniform scale support**: dual quaternions only represent rigid transforms (rotation + translation). Squash/stretch requires separate scale handling.
2. **Bulging at joints** (DLB variant): opposite artifact to candy-wrapper — volume can *increase* at bends. DQB mitigates this.
3. **Antipodal flip**: if wᵢ·q̂ᵢ and wⱼ·q̂ⱼ are on opposite hemispheres, blending can take the long path. Fix: flip q̂ᵢ sign if dot(q_r_i, q_r_0) < 0.

## Implementación en Maya

Maya's native `skinCluster` is LBS-only. No native DQS node exists. Implementation options:

### Option A — Python/OpenMaya MPxDeformerNode (offline or low-vert meshes)
```python
import maya.api.OpenMaya as om2

def dqs_blend(matrices, weights, point):
    """Blend using dual quaternion linear blending."""
    # Convert each matrix to dual quaternion
    dqs = [matrix_to_dual_quat(m) for m in matrices]
    
    # Flip antipodal quaternions
    ref_qr = dqs[0][0]  # reference real part
    for i in range(1, len(dqs)):
        if om2.MQuaternion.dot(dqs[i][0], ref_qr) < 0:
            dqs[i] = (-dqs[i][0], -dqs[i][1])
    
    # Linear blend
    qr_blend = sum(w * dq[0] for w, dq in zip(weights, dqs))
    qd_blend = sum(w * dq[1] for w, dq in zip(weights, dqs))
    
    # Normalize
    norm = qr_blend.length()
    qr_norm = qr_blend / norm
    qd_norm = qd_blend / norm
    
    # Apply: extract rotation and translation from normalized DQ
    return apply_dual_quat(qr_norm, qd_norm, point)

def matrix_to_dual_quat(mat):
    """MMatrix → (qr, qd) dual quaternion pair."""
    mfn = om2.MTransformationMatrix(mat)
    qr = mfn.rotation(asQuaternion=True)
    t = mfn.translation(om2.MSpace.kWorld)
    # qd = 0.5 * t * qr (pure quaternion product)
    qt = om2.MQuaternion(t.x, t.y, t.z, 0.0)
    qd_full = qt * qr
    qd = om2.MQuaternion(qd_full.x * 0.5, qd_full.y * 0.5,
                          qd_full.z * 0.5, qd_full.w * 0.5)
    return (qr, qd)
```

### Option B — MPxGPUDeformer (OpenCL, production quality)
Register a custom GPU deformer that computes DQS in OpenCL kernel. Stays within the GPU cluster — no round-trip CPU cost. Requires C++ plugin.

### Option C — Approximate DQS via wtAddMatrix + normalization
For rigs with limited twist range (<90°), the candy-wrapper is minor. The local_mmx pattern (multMatrix chain) gives near-LBS results. For problematic areas (forearm, wrist) add twist joints to subdivide the rotation — distributing the rotation into smaller steps that LBS handles well.

## Comparación con autorig_tools

El pipeline actual de Laia usa `wtAddMatrix`/`multMatrix` — que es LBS equivalente a nivel de transformaciones de joints. Esto significa que rigs con twists grandes (>90° forearm rotation, shoulder rotation extrema) pueden exhibir el candy-wrapper. La solución de twist joints que ya implementa autorig_tools (distribución del twist en 2-4 joints por zona crítica) es la mitigación estándar de producción, equivalente en calidad visual a DQS para la mayoría de poses. Un MPxGPUDeformer con DQS genuino sería la mejora arquitectural, pero requiere C++ y no es imprescindible si el sistema de twist joints ya cubre los casos problemáticos.

## Aplicable directamente

PARTIAL — La implementación Python de `matrix_to_dual_quat()` es directamente integrable como utilidad de diagnóstico en autorig_tools para auditar qué zonas del rig presentan candy-wrapper potencial (detectar meshes con influencias de ≥2 joints que pueden girar >90° relativamente). Implementar DQS nativo requiere C++ MPxDeformerNode. Alternativa inmediata: auditar si las zonas de twist actuales (forearm, shoulder) tienen suficientes joints de distribución.

## Fuente
- Kavan et al. 2007 (SGP): https://users.cs.utah.edu/~ladislav/kavan07skinning/kavan07skinning.html
- Kavan et al. 2008 (TOG) — Geometric DQB: https://dl.acm.org/doi/10.1145/1409625.1409627
- Tutorial + C++ implementation: http://rodolphe-vaillant.fr/?e=29
- GameDev comparison thread: https://www.gamedev.net/forums/topic/575051-dual-quaternion-skinning-vs-linear-based-quaternion-skinning/
