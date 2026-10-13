---
source: https://github.com/AKEric/skinner
found: 2026-07-13
category: tool
priority: 3
tags: [maya, python, rigging, skinning, skin-weights, export-import, production, AAA, open-source, github]
status: NEW
---

# skinner (AKEric) -- Skin Weight Export/Import para Maya

## Descripcion
`skinner` es una herramienta Python para Maya que reemplaza el sistema nativo de export/import de skin weights de Maya (Deformer Weights). Fue construida por Eric Pavey para pipelines AAA de produccion (Visceral/EA, Sledgehammer Games/Activision, 31st Union/2K), open-sourced en febrero 2023, y compatible con Maya 2026. Resuelve el problema critico del pipeline nativo: el import de Maya es hasta 5-10x mas lento que skinner, especialmente en meshes de alta densidad con muchas influencias. 205 estrellas, 28 forks.

## Fundamento matematico / tecnico

### Problem: Maya's Native Deformer Weights System

Maya's built-in `File > Export/Import > Deformer Weights` stores skin weights as XML (ASCII, large) or binary. The import process:
1. Reads weight file
2. For each vertex: calls `skinCluster.setWeights()` per-vertex (Python API call overhead)
3. No batching -- N vertices = N individual weight assignments

**Typical import cost (production mesh):**
```
10K verts, 20 influences: Maya native import ~ 8-12 seconds
10K verts, 20 influences: skinner import    ~ 1-2 seconds (5-10x faster)
```

### Skinner's Technical Approach

**Position-based vertex matching (topology-independent):**
Instead of matching by vertex index (fragile to topology changes), skinner matches by world-space position with a configurable tolerance:
```
For each vertex in the weight file:
  Find closest vertex on target mesh (within tolerance)
  Assign weights to matched vertex
```
This means weight files survive:
- Mesh re-topologized with same silhouette
- Vertex index reordering (UV/poly edits)
- Density changes (if using falloff-based matching)

**Weight storage format:** JSON (human-readable, diffable in version control) or binary for production.

**Batch API calls:**
```python
# Instead of per-vertex calls:
# skinFn.setWeights(dagPath, vtxComp, influenceIndices, weights, True)
# ...called once per vertex...

# Skinner builds full weight arrays and calls ONCE:
skin_fn.setWeights(dag_path, all_vertices_component,
                   all_influence_indices, all_weights_flat, True)
# -> massively reduces Python<->Maya API call overhead
```

**Influence lookup optimization:**
Skinner pre-builds an influence name -> index mapping at import start, avoiding repeated `skinCluster.influenceObjects()` queries:
```python
inf_map = {cmds.ls(inf, long=True)[0]: i
           for i, inf in enumerate(cmds.skinCluster(sk, q=True, inf=True))}
```

### File Format Details

**JSON export structure:**
```json
{
  "mesh": "pSphere1",
  "influences": ["joint1", "joint2", "joint3"],
  "vertices": [
    {"pos": [0.0, 1.0, 0.0], "weights": [0.8, 0.2, 0.0]},
    {"pos": [0.1, 0.9, 0.1], "weights": [0.5, 0.4, 0.1]},
    ...
  ],
  "maxInfluences": 4,
  "skinMethod": 0
}
```

Position-based storage means the file is valid even if vertex count changes (missing vertices are skipped, no errors).

## Implementacion en Maya

**Installation:**
```python
# Clone or download from https://github.com/AKEric/skinner
# Add to PYTHONPATH: C:/path/to/skinner/

import skinner.core as sk_core
import skinner.ui as sk_ui
```

**Export skin weights:**
```python
import skinner.core as sk_core

# Export single mesh
sk_core.exportSkin(
    meshes=['pSphere1'],
    filepath='C:/skin_data/pSphere1.json',
    worldSpace=True,   # use world-space positions for position-based matching
    verbose=True
)

# Export all skinned meshes in scene
skinned = [mesh for mesh in cmds.ls(type='mesh')
           if cmds.listHistory(mesh, type='skinCluster')]
sk_core.exportSkin(meshes=skinned, filepath='C:/skin_data/character.json')
```

**Import skin weights:**
```python
import skinner.core as sk_core

# Import with topology-independent matching (recommended)
sk_core.importSkin(
    filepath='C:/skin_data/pSphere1.json',
    meshes=['pSphere1_retopoed'],  # can differ from export mesh name
    matchByPosition=True,           # position-based matching
    positionTolerance=0.001,        # cm tolerance for vertex matching
    verbose=True
)
```

**UI launch:**
```python
import skinner.ui as sk_ui
sk_ui.App()  # Opens the skinner UI panel
```

**Integration in autorig_tools post-build:**
```python
def save_skin_data(character_name, meshes, output_dir):
    """Export skin weights after build. Call in post-build step."""
    import skinner.core as sk_core
    import os
    
    filepath = os.path.join(output_dir, f'{character_name}_skin.json')
    sk_core.exportSkin(meshes=meshes, filepath=filepath, worldSpace=True)
    print(f"Skin data saved: {filepath}")
    return filepath

def load_skin_data(character_name, meshes, data_dir):
    """Import skin weights. Call after geometry rebuild."""
    import skinner.core as sk_core
    import os
    
    filepath = os.path.join(data_dir, f'{character_name}_skin.json')
    if not os.path.exists(filepath):
        print(f"No skin data found at {filepath}")
        return False
    
    sk_core.importSkin(
        filepath=filepath,
        meshes=meshes,
        matchByPosition=True,
        positionTolerance=0.001
    )
    print(f"Skin data loaded from {filepath}")
    return True
```

## Comparacion con autorig_tools

`autorig_tools` tiene su propio sistema de skin data export/import. Skinner es relevante como referencia de implementacion y como alternativa de respaldo para casos donde la topologia ha cambiado pero la geometria es la misma (position-based matching). La ventaja clave de skinner vs el sistema nativo de Maya es el 5-10x speedup en import, que en un personaje hero con 5+ meshes y 20+ influencias puede reducir el rebuild time de skin en varios minutos. El formato JSON es ademas compatible con version control (diffable, mergeable) a diferencia del binario nativo de Maya.

## Aplicable directamente

PARTIAL:
1. **Comparar speedup de import:** Medir el tiempo de import de skin data actual en autorig_tools vs skinner. Si autorig_tools ya usa batched API calls (`setWeights` en batch), la diferencia puede ser menor. Si usa per-vertex calls, hay ganancia directa.
2. **Position-based matching:** Si el pipeline de autorig_tools necesita transferir pesos entre versiones de mesh con diferente topologia, implementar position-based matching equivalente (skinner code es lectura directa -- MIT license).
3. **JSON format:** Si el sistema actual usa formato binario o XML, considerar migrar a JSON para facilitar version control del skin data.

## Fuente
- https://github.com/AKEric/skinner -- repositorio principal (205 estrellas, MIT license)
- Compatibilidad: Maya 2026 Windows 10 documentada en README
- Autor: Eric Pavey (Visceral/EA, Sledgehammer Games/Activision, 31st Union/2K)
