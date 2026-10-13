---
source: https://github.com/yamahigashi/MayaMeshRetarget
found: 2026-06-08
category: tool
priority: 3
tags: [maya, python, rbf, mesh-retarget, skin-weights, deformation-transfer, scipy, open-source, github, correctives]
status: NEW
---

# MayaMeshRetarget (yamahigashi) — Retargeting de Deformaciones entre Meshes via RBF

## Descripción
MayaMeshRetarget (yamahigashi, GitHub) es una herramienta Python para Autodesk Maya que transfiere deformaciones de malla entre personajes con topología diferente usando interpolación RBF y clustering de skin weights. El caso de uso principal: dado un personaje A con skin weights maduros y un personaje B con proporciones similares pero topología diferente, transferir los pesos de A a B sin pérdida de rigidez articular. La librería soporta 6 kernels RBF y es notable por su integración con el kernel de Beckert-Wendland para problemas grandes (sparse matrix support). Relacionado directamente con el archivo de matemáticas RBF del 2026-06-01.

## Fundamento matemático / técnico

### Problem: Naive Mesh Deformation Transfer

Standard approaches (e.g., Maya's Transfer Weights, nearest-neighbor vertex copy) fail when:
1. Topology differs between source and target (different vertex count, edge loops)
2. Characters have different proportions (scaling, limb ratios)
3. Articulated areas (joint regions) need to stay rigid — naive transfer "melts" geometry around joints

### Skin Weight-Based Clustering: Rigidity Preservation

MayaMeshRetarget's key innovation: before computing the RBF transformation field, it **clusters vertices by their dominant skinning influence**:

```
For each vertex v:
    dominant_bone(v) = argmax_b(weight_b(v))
    cluster(v) = dominant_bone(v)
```

This creates bone-influenced clusters where vertices within the same cluster are expected to move rigidly together (same bone drives them). During RBF fitting:

```
For each cluster c (bone b):
    - Compute rigid transform R_c, t_c that best fits source cluster → target cluster
    - Use this rigid transform as the "ground truth" for RBF interpolation in cluster c
```

This prevents the "sausage artifact" where high-deformation areas (elbows, knees) get distorted during retargeting — they stay rigid because the RBF is fitted to per-cluster rigid transforms, not raw vertex-to-vertex correspondences.

### RBF Interpolation for Deformation Transfer

Given the per-cluster rigid transforms, the retargeting computes a smooth interpolating field:

```
T(x) = Σ_i c_i · φ(||x - x_i||)
```

where:
- `x` = query position (target mesh vertex)
- `x_i` = source cluster centers (bone positions in source)
- `φ` = RBF kernel
- `c_i` = RBF coefficients (solved from source→target cluster constraints)

The solved field `T(x)` gives the transformation (rotation + translation) for any point in 3D space. Applying it to each target mesh vertex gives the retargeted deformation.

### Supported RBF Kernels

| Kernel | Formula | Best Use |
|--------|---------|----------|
| **Linear** | φ(r) = r | Simple, no parameters, fast |
| **Gaussian** | φ(r) = exp(-ε²r²) | Localized: good for similar proportions |
| **Thin-Plate** | φ(r) = r² log(r) | Smooth global transfer, no parameter needed |
| **Multi-Quadratic** | φ(r) = √(r² + ε²) | Medium-range global influence |
| **Inverse Multi-Quadratic** | φ(r) = 1/√(r² + ε²) | Localized falloff, good for local correctives |
| **Beckert-Wendland** | φ(r) = (1 - r/ρ)₊⁴(4r/ρ + 1) | Compactly supported: sparse matrix → fast for large meshes |

The Beckert-Wendland kernel is particularly important: it has **exactly zero** support beyond radius ρ, producing a sparse coefficient matrix that scipy.sparse can solve efficiently. For large meshes (100K+ verts), this can be the difference between a tractable solve and an out-of-memory failure.

### `radius_coefficient` Parameter

For Gaussian and Beckert-Wendland kernels, the `radius_coefficient` controls the influence radius:
```
effective_radius = radius_coefficient * characteristic_length_of_mesh
```

Typical values:
- `0.001` → very localized (each bone cluster affects only nearby vertices)
- `0.005` → default (balanced local/global)
- `0.05` → very global (similar to Thin-Plate behavior)

### Inpainting

The `inpaint=True` option fills regions where no source deformation data exists (e.g., mesh areas that only exist in target, not in source — new accessories, topology changes). It uses spatial extrapolation from nearby clusters.

## Implementación en Maya

```python
import maya.cmds as cmds

# Installation
# pip install numpy scipy scikit-learn embreex
# Clone repo: git clone https://github.com/yamahigashi/MayaMeshRetarget
# Add to PYTHONPATH

import ymt_mesh_retarget

# ── BASIC USAGE ──
# Transfer deformation from source_char to target_char
ymt_mesh_retarget.retarget(
    source="source_character_mesh",     # mesh with existing skinCluster
    target="target_character_mesh",     # target mesh (different topology)
    objects=["mesh_to_retarget"],       # objects to receive the transferred deformation
    kernel="gaussian",                  # 'linear', 'gaussian', 'thin_plate', 
                                        #  'multi_quadratic', 'inverse_multi_quadratic', 
                                        #  'beckert_wendland'
    radius_coefficient=0.005,           # RBF influence radius (relative to mesh size)
    apply_rigid_transform=True,         # use bone-cluster rigid transforms (RECOMMENDED)
    inpaint=True                        # fill gaps with spatial extrapolation
)

# ── LARGE MESH (100K+ verts): use Beckert-Wendland kernel ──
ymt_mesh_retarget.retarget(
    source="hero_mesh",
    target="lod1_mesh",
    objects=["lod1_mesh"],
    kernel="beckert_wendland",          # sparse matrix → tractable solve
    radius_coefficient=0.01,
    apply_rigid_transform=True,
    inpaint=False                       # faster without inpainting for LODs
)

# ── SCRIPT-BASED PIPELINE INTEGRATION ──
def transfer_skin_weights_to_variant(source_char, target_char, skin_meshes):
    """
    Pipeline tool: transfer mature skin weights from source character to variant.
    Useful when source_char is rigged hero, target_char is costume variant.
    """
    for mesh in skin_meshes:
        source_mesh = f"{source_char}:{mesh}"
        target_mesh = f"{target_char}:{mesh}"
        
        try:
            ymt_mesh_retarget.retarget(
                source=source_mesh,
                target=target_mesh,
                objects=[target_mesh],
                kernel="gaussian",
                radius_coefficient=0.005,
                apply_rigid_transform=True,
                inpaint=True
            )
            cmds.setAttr(target_mesh + '.visibility', 1)
            print(f"  ✓ Retargeted: {mesh}")
        except Exception as e:
            print(f"  ✗ Failed {mesh}: {e}")

# Call from rig post-build
transfer_skin_weights_to_variant(
    source_char="hero_char", 
    target_char="costume_variant_char",
    skin_meshes=["body_mesh", "hand_mesh", "head_mesh"]
)
```

### UI Workflow (from repo)

1. Launch UI: `ymt_mesh_retarget.show_ui()`
2. Set source mesh (with deformation data) and target mesh
3. Select objects to retarget
4. Configure kernel + radius_coefficient + settings
5. Execute → tool builds RBF field and applies transformation

### Dependencies

```bash
# Required (pip install or Maya-bundled)
numpy       # ≥1.20 (bundled in Maya 2025+)
scipy       # ≥1.7  (not bundled — requires pip install in mayapy)
scikit-learn # ≥1.0  (not bundled)
embreex     # Ray casting library (not bundled, requires pip install)
```

Install in Maya's Python:
```bash
mayapy -m pip install scipy scikit-learn embreex
```

**Maya version**: 2022+ (Python 3 required)

## Comparación con autorig_tools

autorig_tools tiene importación/exportación de skin weights (ver archivo de Skinner, mayo 2026). MayaMeshRetarget aborda un problema diferente: no importar pesos entre la *misma* topología, sino *retargetear* pesos entre topologías distintas. Las aplicaciones directas para autorig_tools:

1. **Variantes de personaje**: cuando un personaje tiene múltiples versiones (cuerpo base, cuerpo vestido, variante con accesorios), MayaMeshRetarget transfiere los pesos del personaje hero a cada variante automáticamente.

2. **LOD generation**: transferir pesos del mesh hero (50K verts) al LOD1 (15K verts) o LOD2 (5K verts) sin re-skinning manual.

3. **Correctives transfer**: los corrective blendshapes del personaje A pueden retargetearse al personaje B usando el mismo mecanismo RBF.

El sistema de clustering por bone-influence preserva la rigidez articular — el punto débil de todos los sistemas naive de transferencia de pesos.

## Aplicable directamente

YES — Python puro, Maya 2022+, requiere pip install de scipy/scikit-learn/embreex (estándar en pipelines modernos).

**Caso de uso inmediato para autorig_tools**:
- Si se crean variantes de personaje (muy común en producción AAA), MayaMeshRetarget automatiza la transferencia de weights sin re-skinning
- Integrar como función en el módulo de skinning: `retarget_skin_weights(source, target, kernel='gaussian')`
- Con `apply_rigid_transform=True` + kernel `gaussian`, la calidad es production-ready sin trabajo manual
- Tiempo de setup: 1-2 horas (instalar dependencias, probar en un personaje)

## Fuente
- GitHub: https://github.com/yamahigashi/MayaMeshRetarget
- Relacionado — RBF Kernel Functions: ver `2026-06-01-rbf-kernel-functions-mathematical-basis.md`
