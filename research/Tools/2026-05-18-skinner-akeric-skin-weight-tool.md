---
source: https://github.com/AKEric/skinner
found: 2026-05-18
category: tool
priority: 3
tags: [maya, python, skinning, skin-weights, export-import, AAA, production, tool, github]
status: NEW
---

# Skinner (AKEric) — Skin Weight Export/Import para Producción AAA

## Descripción
Skinner es una herramienta de exportación e importación de skin weights para Autodesk Maya desarrollada por Eric Pavey, probada en producción AAA y open-sourced en febrero 2023. Resuelve el problema clásico del trabajo de skinning en pipelines donde el mesh cambia continuamente: importar pesos cuando la topología ha cambiado, cuando no hay UVs válidas, o cuando se necesita más velocidad que las herramientas nativas de Maya. Su algoritmo "Closest Neighbors" personalizado es el diferencial técnico principal.

## Fundamento matemático / técnico

### Closest Neighbors Algorithm
Skinner's custom fallback algorithm for topology-mismatched imports:
1. For each vertex `v` in the new mesh, find the N nearest vertices in the old (source) mesh using sphere-based neighbor detection.
2. Compute distance weights: `w_i = 1 / dist_i^2` (inverse square distance), normalize so `Σw_i = 1`.
3. Blend the skinning weights from the N neighbors: `weights_v = Σ w_i · weights_neighbor_i`.
4. Renormalize blended weights so they sum to 1.0 across all influences.

**N=8 by default.** For perfectly matching topologies (zero distance), vertex weights are transferred exactly (no interpolation needed).

This is mathematically equivalent to Inverse Distance Weighting (IDW) interpolation, a standard spatial interpolation method:
```
w_i(x) = (1/||x - x_i||^p) / Σ_j (1/||x - x_j||^p)
```
where p=2 (power=2 for inverse square) and x is the query vertex position.

### File Format: .sknr
Binary pickled Python data structures. Not text/JSON — faster I/O for large meshes. Each `SkinChunk` contains:
- Current worldspace vertex positions (post-deformed pose, for matching)
- Pre-deformed (bind-pose) vertex positions (for matching at rest pose)
- Vertex normals (for vertex normal filtering during fallback import)
- Per-vertex skinning weights array
- Joint name list and hierarchy info
- Skinning method (linear/DQS/blended)

**Multiple meshes** can be stored in a single `.sknr` file.

### Import Fallback Logic
When importing, Skinner tries in order:
1. **Exact topology match** (same vertex count + positions) → direct weight copy
2. **Position-based match** (same positions but different order) → position lookup
3. **Closest Neighbors** (topology changed) → IDW interpolation
4. **Closest Point** (fallback #2) → nearest single vertex weight transfer

The "vertex normal filtering" option: during fallback import, weights from source vertices whose normals face away from the target vertex (angle > 90°) are excluded from the IDW blend. This prevents weight bleeding across surface folds (e.g., finger on one side bleeding to finger on other side).

### Performance
Claims 5-10× faster than Maya's built-in `Deformer Weights` system for import operations. The primary speedup comes from:
- Binary (not text) file format → faster parse
- Batch Maya API calls (`MFnSkinCluster.setWeights()` in batch mode)
- Avoiding Python-level loops on per-vertex weight setting

## Implementación en Maya

```python
# Installation: copy skinner/ folder to Maya scripts path
# Dependencies: Maya 2022+ (Python 3), numpy (bundled in Maya 2025+), scipy

# --- EXPORT ---
import skinner.core as skinCore

# Export all skinned meshes in scene
skinCore.exportSkin(
    meshes=None,           # None = all skinned meshes
    filePath='/path/to/character.sknr',
    setToBindPose=True,    # auto set bindpose before export (recommended)
    verbose=True
)

# Export specific mesh
skinCore.exportSkin(
    meshes=['body_mesh', 'hand_mesh'],
    filePath='/path/to/partial.sknr',
    setToBindPose=False    # mesh is already at bindpose
)

# --- IMPORT ---
skinCore.importSkin(
    filePath='/path/to/character.sknr',
    meshes=None,           # None = match by mesh name
    buildMissingInfluences=True,   # create missing joints (preserves hierarchy)
    useNormalFilter=True,  # prevents normal-facing weight bleed
    postSmoothingIterations=3,     # post-import Laplacian smoothing passes
    verbose=True
)

# Import with topology change (mesh was updated):
skinCore.importSkin(
    filePath='/path/to/character.sknr',
    meshes=['updated_body_mesh'],  # new mesh name
    buildMissingInfluences=True,
    closestNeighborCount=8         # N for IDW interpolation
)

# --- PIPELINE INTEGRATION ---
# Export on rig publish:
def publish_skin_weights(character_name, output_dir):
    import os
    path = os.path.join(output_dir, f'{character_name}_skin.sknr')
    result = skinCore.exportSkin(meshes=None, filePath=path, setToBindPose=True)
    print(f"Exported {len(result['meshes'])} meshes to {path}")
    return path

# Import after mesh update:
def restore_skin_weights(character_name, weights_dir):
    import os
    path = os.path.join(weights_dir, f'{character_name}_skin.sknr')
    skinCore.importSkin(filePath=path, buildMissingInfluences=True)
```

**Key differences from Maya's native `Deformer Weights` export:**

| Feature | Skinner | Maya Deformer Weights |
|---------|---------|----------------------|
| UV dependency | None | Required (UV-based weight transfer) |
| Topology mismatch handling | IDW fallback | Limited, often fails |
| Multi-mesh file | Yes (.sknr) | No (one file per mesh) |
| Import speed | 5-10× faster | Baseline |
| DQS skinning support | Yes | Yes (Maya 2022+) |
| Missing joint creation | Yes (build_missing_influences) | No |
| Vertex normal filtering | Yes | No |
| File format | Binary pickle | Text XML |

**Maya 2025+ note:** Maya 2025 ships with internal numpy. Skinner detects this and uses it automatically. scipy still needs manual installation (pip into Maya's Python).

## Comparación con autorig_tools
autorig_tools tiene herramientas de skinning propias pero puede beneficiarse de Skinner para el flujo mesh-update: cuando llega un mesh actualizado del modelado, Skinner puede restaurar automáticamente los pesos existentes usando el algoritmo IDW. Es especialmente útil en la fase de producción tardía cuando los meshes llegan con correcciones menores. El formato `.sknr` también es un candidato para ser el formato de exportación de skin weights de autorig_tools, sustituyendo el formato JSON/XML propio si existe.

## Aplicable directamente
YES — Integrar Skinner como herramienta de backup/restore de skin weights en el pipeline de autorig_tools para el workflow "mesh changed → restore weights". Añadir a los scripts de build un paso automático de export de skin weights al finalizar el skinning inicial (antes de que lleguen correcciones de modelo).

## Fuente
- GitHub: https://github.com/AKEric/skinner
- README direct: https://github.com/AKEric/skinner/blob/main/README.md
- LinkedIn announcement: https://www.linkedin.com/posts/pavey_github-akericskinner-skin-export-import-activity-7028524746862452736-co0b
- Maya-Python community thread: https://groups.google.com/g/python_inside_maya/c/K_ATtyvFrCg
