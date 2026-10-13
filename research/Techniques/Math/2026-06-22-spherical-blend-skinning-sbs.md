---
source: https://users.cs.utah.edu/~ladislav/kavan05spherical/kavan05spherical.pdf
found: 2026-06-22
category: math
priority: 1
tags: [maya, python, rigging, math, skinning]
status: NEW
---

# Spherical Blend Skinning (SBS)

## Descripción
SBS (Kavan & Žára, 2005) es el eslabón histórico entre LBS y DQS: el primer método que sustituyó el promedio de matrices de LBS por un promedio de rotaciones (vía cuaterniones) y centros de rotación esféricos, eliminando el "candy-wrapper" artifact sin el coste de dual quaternions completos. Entender SBS completa el trío de skinning "beyond LBS" del vault (ya cubiertos: CoR y SSDR) y aclara por qué DQS terminó ganando la adopción de la industria.

## Fundamento matemático / técnico
LBS computes a vertex's new position as a linear blend of full affine matrices: v' = Σ wᵢ Mᵢ v. The problem: blending matrices directly blends translation and rotation linearly, which for two bones rotating in opposite directions around a shared joint produces the classic collapse (candy-wrapper / elbow flattening) because matrix interpolation is not rotation-aware.

SBS instead blends only the *rotational* part using quaternions and treats translation differently via per-bone "rotation centers" c_i (points around which each bone's influence rotates, computed once at bind time to minimize deformation error across a set of example poses):

  q_blend = normalize( Σ wᵢ qᵢ )                      (linear quaternion blend, then re-normalize to unit length)
  v' = q_blend · (v − c_blend) · q_blend⁻¹ + t_blend    (rotate around blended center, then translate)

  where c_blend = Σ wᵢ cᵢ  and  t_blend accounts for the bone's translation history.

The critical difference from naive matrix blending: rotating points around a *shared, precomputed pivot* rather than blending translation linearly removes most of the volume-loss artifact, because the joint area genuinely rotates as a rigid unit instead of being pulled toward the average of two disjoint pivots. SBS requires an antipodality check on the quaternions before blending (q and −q represent the same rotation but interpolate to a degenerate result if mixed — same antipodality issue covered in the existing DQS vault entry), and the rotation centers cᵢ must be solved offline (least-squares fit against training poses), which makes SBS a "trained" method, unlike LBS or DQS which require zero precomputation beyond bind weights.

Limitations that led to DQS superseding it: SBS handles only 2 bones cleanly in its original closed form (multi-bone blending needs iterative generalization), the precomputed rotation centers don't generalize to extreme poses outside the training set, and it's still slower than DQS per vertex (quaternion blend + center computation vs DQS's single 8-float blend-and-normalize).

## Implementación en Maya
No native Maya deformer implements SBS specifically (Maya's skinCluster offers `skinningMethod`: 0=Linear/LBS, 1=DQS, 2=Blended — SBS isn't one of the built-in options). To prototype it:
1. Compute per-bone rotation centers offline via least-squares against a set of bind-pose-relative example poses (numpy `lstsq` against the deformation gradient).
2. Implement as a custom `MPxDeformerNode` or GPU-override-compatible compute node: read joint quaternions, blend with `quatSlerp`-like weighted normalize, transform points around the precomputed centers.
3. In pure node-graph terms (no custom node): `quatAdd` (weighted) → `quatNormalize` → use as input to `composeMatrix`'s `inputQuat`, applied around a pivot offset by a `pointMatrixMult` pre/post pair — fully native-node-buildable, GPU-friendly since it avoids any custom C++/Python node.

## Comparación con autorig_tools
SBS en sí no aporta una ventaja directa sobre el `skinningMethod=1` (DQS) ya disponible nativamente en Maya y ya documentado en el vault (2026-05-11-dual-quaternion-skinning-math.md) — DQS es superior y gratis sin entrenamiento. El valor real de este research es de contexto: confirma que la arquitectura "rotación cuaternión + centro de pivote precomputado" es el patrón general detrás de CoR (ya en el vault) y de cómo Laia podría diseñar un corrective de "pivot dinámico" para zonas problemáticas (hombro, cadera) sin recurrir a un deformer completo — solo ajustando el centro de rotación efectivo vía un nodo de offset alimentado por una pose-driven attribute.

## Aplicable directamente
NO — Dado que Maya ya ofrece DQS nativo y superior, implementar SBS desde cero no se justifica en producción. El valor es puramente de comprensión matemática: el patrón de "blend de cuaterniones + pivote precomputado" es reutilizable conceptualmente para diseñar un corrective de pivote dinámico en hombro/cadera, pero como herramienta independiente no aporta sobre lo que ya existe.

## Fuente
https://users.cs.utah.edu/~ladislav/kavan05spherical/kavan05spherical.pdf (paper original, I3D 2005)
https://dcgi.fel.cvut.cz/publications/2005/kavan-i3d-sbs
https://www.researchgate.net/publication/234814042_Spherical_blend_skinning_A_real-time_deformation_of_articulated_models
https://dl.acm.org/doi/10.1145/1230100.1230107 (Skinning with Dual Quaternions — el sucesor directo de SBS)
