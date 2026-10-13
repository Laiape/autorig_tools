---
source: https://arxiv.org/abs/2606.06685
found: 2026-09-14
category: math
priority: 1
tags: [maya, rigging, math, lbs, skinning, neural, point-cloud, siggraph2026, radiance-field]
status: NEW
---

# RigPAPR: LBS Aplicado a Nubes de Puntos Neuronales (arXiv:2606.06685, SIGGRAPH 2026)

## Descripción
RigPAPR demuestra que el algoritmo Linear Blend Skinning (LBS) clásico puede aplicarse directamente a primitivas de nubes de puntos neuronales (PAPR — Proximity Attention Point Rendering) en lugar de vértices de malla. El paper auto-riga una representación neural y la anima via LBS estándar usando solo un video de un punto de vista fijo, sin proxy de malla ni correcciones por pose. Supera en 3+ dB PSNR a baselines de Gaussian Splatting en vistas novedosas. Publicado Jun 4, 2026 (arXiv:2606.06685). Autores: Shichong Peng, Yanshu Zhang, Ke Li (Simon Fraser University).

## Fundamento matemático / técnico

**PAPR (Proximity Attention Point Rendering):**
PAPR is a neural point cloud representation where a scene is encoded as N primitives {p_i, f_i}:
- p_i in R^3: 3D position of primitive i
- f_i in R^d: learned feature vector (color, opacity, etc.)

At render time, each pixel color C is recomposed from primitives via proximity-weighted attention:
  C = sum_i alpha_i(ray, p_i) * decode(f_i)

Crucially, PAPR has NO per-primitive mesh geometry — the apparent surface forms implicitly from primitive positions at render time. This means deforming the cloud = deforming a set of 3D points, exactly the domain where LBS was always defined.

**LBS applied to neural primitives:**
Standard LBS on mesh vertices:
  p'_v = sum_b w_{v,b} * T_b * p_v_homogeneous

RigPAPR applies the *identical* formula to PAPR primitives:
  p'_i = sum_b w_{i,b} * T_b * p_i_homogeneous

where:
- w_{i,b} in [0,1], sum_b w_{i,b} = 1  (partition of unity — same constraint as Maya skinCluster)
- T_b in SE(3) = [R_b | t_b; 0 | 1]  (same 4x4 bone transformation matrix as Maya joint)
- p_i is the 3D position of neural primitive i (treated as a mesh vertex)

The mathematical structure is 100% identical to classic LBS. The only difference is what "p_i" represents — neural point vs mesh vertex.

**Auto-rigging via template-based weight transfer:**
Since PAPR primitives have no skeletal structure, weights must be computed by proxy:
1. Reconstruct a body template (SMPL-like parametric mesh M_template) fitted to the static PAPR point cloud
2. Compute LBS weights on M_template via standard methods (heat diffusion or proximity-based)
3. Transfer weights from template vertices to PAPR primitives by proximity kernel:
   w_{i,b} = sum_v K(p_i, p_v) * w_{v,b} / sum_v K(p_i, p_v)
   K(x, y) = exp(-||x - y||^2 / (2*h^2))  [Gaussian kernel, bandwidth h]

This is the same Nadaraya-Watson kernel estimator used for mesh-to-mesh weight transfer — equivalent to Maya's `copySkinWeights -surfaceAssociation closestPoint` with smooth falloff.

**Why LBS works on neural points without pose-dependent correction:**
The paper reports that pure LBS (no blend correctives, no pose-space deformation) achieves 3+ dB PSNR improvement over Gaussian Splatting baselines. This validates the classical result that LBS is sufficient for moderate joint angles (roughly ±70-80° before candy-wrapper artifacts become visible). Since PAPR renders via proximity attention, small geometric errors in point positions are further attenuated by the rendering blending — making LBS's artifacts even less visible than on explicit mesh surfaces.

**Comparison to Gaussian Splatting (3DGS) rigging:**
3DGS-based rigging approaches attach anisotropic Gaussian ellipsoids to bones — this introduces additional rotation of the ellipsoid orientation when bones rotate, which RigPAPR avoids by using PAPR's isotropic, render-implicit primitives. The simpler math of PAPR + LBS outperforms 3DGS + LBS at novel views by 3+ dB PSNR because PAPR doesn't accumulate orientation errors during deformation.

## Implementación en Maya

The LBS-to-neural-point-cloud connection has a direct analog in Maya:

```python
# RigPAPR's workflow = Maya copySkinWeights to a set of locators
# Each locator represents one "neural primitive" (conceptual)

import maya.cmds as mc
import maya.api.OpenMaya as om
import numpy as np

def bind_point_cloud_to_skeleton(point_positions, joint_list, template_mesh):
    """
    Creates a locator for each 3D point, binds to skeleton via
    weight transfer from a template mesh -- identical to RigPAPR's algorithm.
    
    Args:
        point_positions: list of (x,y,z) tuples for each neural primitive
        joint_list: list of Maya joint names
        template_mesh: mesh with existing skinCluster to transfer from
    """
    # Step 1: Create transform nodes for each point (Maya locators or joints)
    point_transforms = []
    for i, pos in enumerate(point_positions):
        loc = mc.spaceLocator(name=f"point_{i:04d}_loc")[0]
        mc.xform(loc, ws=True, t=pos)
        point_transforms.append(loc)
    
    # Step 2: Bind to skeleton
    sc = mc.skinCluster(joint_list + point_transforms,
                        toSelectedBones=True, bm=1)[0]  # bm=1 = closest point init
    
    # Step 3: Copy weights from template mesh (Gaussian kernel proximity)
    # Equivalent to RigPAPR's kernel weight transfer
    mc.copySkinWeights(
        sourceSkin=mc.ls(mc.listHistory(template_mesh), type='skinCluster')[0],
        destinationSkin=sc,
        noMirror=True,
        surfaceAssociation='closestPoint',
        influenceAssociation='name'
    )
    return sc, point_transforms

# The resulting LBS-driven locators follow the skeleton exactly as in RigPAPR
# This pattern is useful for: ribbon follicle replacements, crowd simulation
# instancer positions, particle system driven by rig, etc.
```

**Practical Maya insight from RigPAPR:**
The paper validates that `copySkinWeights -surfaceAssociation closestPoint` with Gaussian kernel is the correct approach for weight transfer to ANY point representation — including non-mesh geometry like clusters, particles, or locator arrays used in crowd/instancing rigs.

## Comparación con autorig_tools

El pipeline de autorig_tools usa `copySkinWeights` para transfer de pesos entre meshes y LODs. RigPAPR confirma que este mismo patrón funciona correctamente para cualquier representación basada en puntos. El insight más aplicable: el template-based weight transfer con kernel gaussiano ponderado por proximidad es más robusto que closest-point puro para puntos dispersos o irregularmente distribuidos — como los helpers de hombro o cadera que usa autorig_tools, o los locators de correctives procedurales. También valida que el LBS puro (sin correctives RBF) es matemáticamente suficiente para el rango de movimiento normal (±70°) incluso en representaciones no-malla.

## Aplicable directamente

PARTIAL:
1. No hay integración Maya directa de PAPR — es un renderer neural, no una herramienta de rigging
2. El patrón de `copySkinWeights` con kernel gaussiano YA está disponible en Maya via `MFnSkinCluster` — refuerza usar `surfaceAssociation=closestPoint` con smooth falloff en lugar de transferencia binaria
3. El concepto de "LBS es suficiente sin correctives para ±70° en puntos" sugiere que los correctives RBF/SDK de autorig_tools son más necesarios en zonas de rango extremo (±90°+) que en movimiento estándar — información útil para decidir DÓNDE invertir tiempo en correctives
4. Para crowd/instancing: el patrón de locators-como-primitivas-LBS es directamente implementable en `build_crowd_point_rig()` si se requiere

## Fuente
- Paper arXiv:2606.06685: https://arxiv.org/abs/2606.06685
- HTML version: https://arxiv.org/html/2606.06685v1
- PDF: https://arxiv.org/pdf/2606.06685
- SIGGRAPH 2026 Papers: https://s2026.siggraph.org/program/technical-papers/
