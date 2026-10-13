---
source: https://github.com/yamahigashi/MayaMeshRetarget
found: 2026-06-01
category: tool
priority: 3
tags: [maya, RBF, mesh-retargeting, skin-weights, deformation, python, scipy, numpy, clustering, maya-2022]
status: NEW
---

# MayaMeshRetarget (yamahigashi) — Retargeting de Mesh con RBF

## Descripción
MayaMeshRetarget es una herramienta Python para Maya que transfiere deformaciones complejas entre meshes de personajes usando Radial Basis Function (RBF) interpolation con clustering basado en skinning. Permite tomar una pose deformada de un mesh fuente y transferir esa deformación a un mesh objetivo, preservando la estructura articular del esqueleto. Útil para: transferir correctives entre variantes del mismo personaje (como la técnica Noa/Ulysse), retargeting de blendshapes entre meshes con diferente densidad, y crear delta correctives a partir de poses sculpted. 42 estrellas, Maya 2022+.

## Fundamento matemático / técnico

### Problem Statement
Given:
- `M_source` = source mesh (reference/rest)
- `M_deformed` = deformed version of source (what we want to replicate)
- `M_target` = target mesh (different mesh, same general shape)

Find transformation `T` such that `T(M_target) ≈ M_deformed_target`.

### RBF Deformation Transfer Algorithm
The system computes a vector field `T: ℝ³ → ℝ³` that maps rest positions to deformed positions:
```
T(x) = Σᵢ cᵢ · φ(‖x - xᵢ‖)  +  polynomial_term
```
Where `xᵢ` are control points derived from the source mesh deformation.

**Step 1 — Control point selection:** Not all vertices of `M_source` are used as control points. The tool clusters vertices based on:
- Joint influence (skinning weights)  
- Topological proximity
Result: a reduced set of representative control points per cluster.

**Step 2 — Deformation vectors:** For each control point `i`:
```
d_i = M_deformed[i] - M_source[i]   (displacement vector)
```

**Step 3 — RBF solve:** Fit the RBF interpolant through all displacement vectors:
```
Φ · c = d    →    c = Φ⁻¹ · d
```

**Step 4 — Evaluate at target vertices:** For each vertex `v` in `M_target`:
```
delta_v = T(M_target[v]) = Σᵢ cᵢ · φ(‖M_target[v] - xᵢ‖)
M_target_deformed[v] = M_target[v] + delta_v
```

### Why Clustering Matters
Without clustering, the RBF would need to invert an N×N matrix (N = vertex count = potentially 100K+). With clustering:
- Reduce control points from 100K to ~500-2000
- RBF solve drops from O(N³) to O(C³) where C << N
- Deformation quality preserved through representative sampling

The clustering uses `scikit-learn` KMeans/spectral clustering weighted by skinning influences — ensuring that cluster boundaries align with joint influences, not arbitrary geometry.

### Supported RBF Kernels
| Kernel | Use case |
|--------|---------|
| `gaussian` | General purpose, localized deformation |
| `thin_plate` | Global smooth deformation, face shapes |
| `multi_quadratic` | Organic deformations with broad influence |
| `inverse_multi_quadratic` | Moderate locality |
| `beckert_wendland` | Sparse problems (fast for large meshes) |

## Implementación en Maya

### Basic Usage — Transfer Blendshape Between Meshes
```python
import ymt_mesh_retarget

# Source: mesh with deformation applied (e.g., blink blendshape sculpt)
# Target: mesh we want to apply the same deformation to
# Objects: joints, geometry, or transforms to retarget

result = ymt_mesh_retarget.retarget(
    source="hero_face_base",          # rest mesh
    target="hero_face_blendshape_01", # deformed mesh (source of deformation)
    objects=["npc_face_base"],        # mesh to receive deformation
    kernel="thin_plate",              # TPS = best for face shape transfer
    apply_rigid_transform=True
)
# Returns delta positions → can be added as blendshape target
```

### Corrective Shape Transfer Between Character Variants
```python
# Use case: Transfer all blendshapes from hero_A to hero_B (same topology)
import ymt_mesh_retarget
import maya.cmds as cmds

def transfer_all_blendshapes(source_mesh, target_mesh, blendshape_node):
    """Transfer all blendshape targets from source to target character."""
    targets = cmds.blendShape(blendshape_node, query=True, target=True)
    
    for target_name in targets:
        # Isolate target shape
        cmds.setAttr(f'{blendshape_node}.{target_name}', 1.0)
        deformed_mesh = cmds.duplicate(source_mesh, name=f'{target_name}_deformed')[0]
        cmds.setAttr(f'{blendshape_node}.{target_name}', 0.0)
        
        # Retarget
        result_positions = ymt_mesh_retarget.retarget(
            source=source_mesh,
            target=deformed_mesh,
            objects=[target_mesh],
            kernel="thin_plate"
        )
        
        # Create new blendshape target
        # ... apply result_positions as blendshape target on target_mesh
        
        cmds.delete(deformed_mesh)
```

### Skin Weight Retargeting (Different Topology)
```python
# Transfer skin weights from high-res mesh to low-res LOD
result = ymt_mesh_retarget.retarget(
    source="hero_hires",
    target="hero_hires_posed",  # any deformed version for reference
    objects=["hero_lowres_LOD1"],
    kernel="gaussian",
    apply_rigid_transform=False
)
```

### Requirements
```
Maya 2022+ (Python 3 environment)
Python packages (bundled with Maya or via pip into mayapy):
  numpy
  scipy        # for RBF solve and NNLS
  scikit-learn # for clustering
  embreex      # optional: faster ray-casting for registration
```

### Installing Dependencies in Maya
```bash
# Install to Maya's Python environment
/Applications/Autodesk/maya2026/Maya.app/Contents/bin/mayapy -m pip install \
    scipy scikit-learn
```

## Comparación con autorig_tools
autorig_tools tiene herramientas de skin weight export/import. MayaMeshRetarget resuelve un problema diferente: **transferir deformaciones entre meshes** (no solo skin weights de misma topología). Los casos de uso más directamente aplicables son: (1) transferir blendshapes faciales entre variantes del personaje (técnica usada en Noa/Ulysse del proyecto Spanner ASWF), (2) crear correctives en un personaje hero y aplicarlos automáticamente a las versiones LOD, y (3) retargeting de meshes clothes/hair entre distintos cuerpos del mismo personaje base.

## Aplicable directamente
**YES** — Maya 2022+, Python 3, activo y funcional. Pasos concretos:
1. Instalar `scipy` y `scikit-learn` en el entorno Python de Maya (`mayapy -m pip install`).
2. Usar para transferir corrective blendshapes faciales entre variantes de personaje.
3. Evaluar `kernel="thin_plate"` para deformaciones de cara (suavidad global) y `kernel="gaussian"` para correctives de cuerpo (localidad).
4. La función `transfer_all_blendshapes()` del pseudocódigo de arriba es directamente implementable como utilidad de pipeline.

## Fuente
https://github.com/yamahigashi/MayaMeshRetarget
