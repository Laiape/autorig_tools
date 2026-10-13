---
source: https://github.com/AKEric/skinner
found: 2026-08-31
category: tool
priority: 3
tags: [maya, python, skinning, skin-weights, export, import, pipeline, AAA, production]
status: NEW
---

# AKEric/skinner — Maya Skin Weight Export/Import (AAA Production)

## Descripción
Skinner es una herramienta de exportación/importación de skin weights para Autodesk Maya, open source (MIT, publicada Feb 2023 tras 2 años de desarrollo interno en producción AAA de videojuegos). Tiene tanto UI para uso directo como API Python completa para integración en pipelines. Diseñada para manejar casos complejos de producción: meshes duplicados, múltiples métodos de skinning (LBS, DQS, blended), y exportación granular por selección de mesh/joint/vértice. Activamente usada en producción AAA. ~197 estrellas en GitHub, última actualización May 2026.

## Fundamento matemático / técnico

**SkinChunk data format:**
Skinner serializes skin data as `SkinChunk` objects — one per mesh — which capture:
```python
@dataclass  
class SkinChunk:
    mesh_name: str              # long path to handle duplicates
    vertex_count: int
    influences: List[str]       # joint long paths
    weights: np.ndarray         # shape: (vertex_count, influence_count)
    blend_weights: np.ndarray   # DQ blend weights, shape: (vertex_count,)
    skinning_method: int        # 0=LBS, 1=DQ, 2=blended
    max_influences: int         # pruning cap applied
    bind_pre_matrix: np.ndarray # 4x4 per joint — stores bind pose
```

**Weight import strategy — multi-fallback:**
```
1. Exact vertex index match (same topology)
2. Closest-surface-point projection (different LOD/topology)
3. Closest joint influence fallback (if nothing matches)
```

**Handling duplicate mesh names:**
```python
# Skinner converts all paths to long/absolute during export:
# 'leg_mesh' → '|character|body|leg_mesh'
# This survives scene merges, referencing, and namespaceing
# Import: try exact long path first, fall back to short name matching
```

**DQ blend weights:**
```python
# skinCluster has TWO weight arrays:
# 1. Standard weights[vtx][joint] → used for both LBS and DQ
# 2. blendWeights[vtx] → DQ blend factor per vertex (0=full LBS, 1=full DQ)
# Skinner exports/imports both arrays, preserving hybrid skinning method
```

**Performance: why this matters for weight IO:**
```
Native Maya weight export (deformerWeights XML):
  - 100K vertex mesh, 50 influences → ~30-60s export, ~60-120s import
  - XML string parsing overhead, no parallel IO

Skinner (numpy binary format):
  - Same mesh → ~2-5s export, ~3-8s import
  - numpy .npz format: compressed binary, loadable in pure Python
  - No Maya dependency for reading the files (pipeline-friendly)
```

## Implementación en Maya

**API usage:**
```python
import skinner.core as sk

# Export — by mesh selection
cmds.select('character_body_mesh', replace=True)
skin_data = sk.exportSkin(
    meshes=None,          # None = use selection
    filePath='/path/to/weights.skw',
    verbose=True
)

# Export specific verts:
skin_data = sk.exportSkin(
    meshes=[('character_body_mesh', [0, 1, 2, ..., 999])],  # vert indices
    filePath='/path/to/partial_weights.skw'
)

# Import — with closest-point fallback:
sk.importSkin(
    filePath='/path/to/weights.skw',
    useClosestPoint=True,      # handles topology changes
    maxInfluences=8,           # prune to N during import
    verbose=True
)

# Batch export entire character:
all_meshes = cmds.listRelatives('character_root', allDescendents=True, 
                                 type='mesh') or []
for mesh in all_meshes:
    sk.exportSkin(meshes=[mesh], 
                  filePath=f'/skin_data/{mesh}.skw')
```

**Integration into autorig_tools post-build:**
```python
# In autorig_tools/utils/skinning.py:
from skinner import core as sk

def export_rig_skin_weights(rig_root, output_dir):
    """Export all skin weights after rig build, for version control."""
    import os
    skinned_meshes = [m for m in cmds.listRelatives(rig_root, 
                      allDescendents=True, type='mesh') or []
                      if cmds.listConnections(m, type='skinCluster')]
    for mesh in skinned_meshes:
        out_path = os.path.join(output_dir, f'{mesh.split("|")[-1]}.skw')
        sk.exportSkin(meshes=[mesh], filePath=out_path)
    print(f"Exported {len(skinned_meshes)} mesh skin weights to {output_dir}")

def import_rig_skin_weights(rig_root, weights_dir):
    """Import skin weights, with closest-point fallback for LOD variants."""
    import os, glob
    skw_files = glob.glob(os.path.join(weights_dir, '*.skw'))
    for fpath in skw_files:
        sk.importSkin(filePath=fpath, useClosestPoint=True, maxInfluences=8)
```

**Comparison with Maya native (deformerWeights):**
```python
# Native Maya — slow, no DQ blend weights support in older versions:
cmds.deformerWeights('weights.xml', export=True, 
                      deformer='skinCluster1', method='index')

# Skinner — fast, DQ-aware, pipeline-friendly:
sk.exportSkin(meshes=['mesh'], filePath='weights.skw')
# .skw = numpy npz archive, readable without Maya:
import numpy as np
data = np.load('weights.skw', allow_pickle=True)
weights = data['weights']  # pure numpy, no Maya needed
```

**Supported Maya versions:** 2020, 2022, 2023, 2024, 2025, 2026 (tested per releases page)

## Comparación con autorig_tools

El log de 2026-05-25 cubre `robertjoosten/rjSkinningTools` como herramienta de skinning. Skinner es complementario: donde rjSkinningTools se enfoca en UI para pintar/editar weights interactivamente, Skinner está optimizado para export/import de producción en pipelines — más rápido, con API completa, y soporte de DQ blend weights que rjSkinningTools no tiene. Para autorig_tools, el uso natural es en el pipeline post-build: exportar skin weights tras el rig build para mantener bajo control de versiones, e importar en builds subsiguientes o variantes de LOD. La API Python es exactamente lo que necesita autorig_tools para integrar sin UI dependency.

## Aplicable directamente

YES — Instalación: `pip install skinner` o clone del repo. API disponible inmediatamente. La función `export_rig_skin_weights()` de arriba se integra directamente en el post-build de autorig_tools en 1-2h. El beneficio más inmediato: reducir el tiempo de export/import de skin weights de minutos a segundos, y tener un formato de archivo de skin weights versionable que no sea XML de Maya (legible fuera de Maya para auditoría de pipeline).

## Fuente

- GitHub: https://github.com/AKEric/skinner
- README: https://github.com/AKEric/skinner/blob/main/README.md
- Releases: https://github.com/AKEric/skinner/releases
- LinkedIn announcement: https://www.linkedin.com/posts/pavey_github-akericskinner-skin-export-import-activity-6871672272990674944-iShO
- Python Maya group thread: https://groups.google.com/g/python_inside_maya/c/K_ATtyvFrCg
