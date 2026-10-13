---
source: https://github.com/AKEric/skinner | https://github.com/AKEric/skinner/releases
found: 2026-06-15
category: tool
priority: 3
tags: [maya, python, skinning, skin-weights, export, import, pipeline, production, numpy, open-source, github]
status: NEW
---

# Skinner (AKEric) — Skin Export / Import Tools para Maya (Production-grade)

## Descripción
Skinner es una herramienta de exportación e importación de skin weights para Autodesk Maya desarrollada por Eric Pavey, con enfoque de producción profesional: UI de usuario completa + API scripteable para pipelines. El diferencial frente a la exportación nativa de Maya es la robustez del formato de archivo (`*.sknr`, basado en numpy), el manejo correcto de múltiples topologías, la selección por componente, y el soporte actualizado hasta Maya 2026. La versión v1.5.1 resolvió un problema crítico de compatibilidad de numpy 1 vs numpy 2 en diferentes versiones de Maya.

## Fundamento matemático / técnico

### Architecture Overview

Skinner stores skin weights in a **numpy-based binary format** (`.sknr` files) rather than Maya's native XML/text format:

```
.sknr file structure:
├── Header: mesh name, vertex count, influence list
├── Weight matrix: float32 numpy array (V × B)
│   - V = vertex count
│   - B = number of influences (bone count)
│   - Row-major: weights[vertex_index, bone_index]
├── Influence metadata: joint names, bind pose matrices
└── Mesh topology hash (for mismatch detection)
```

**Why numpy binary > XML:**
- Load/save speed: 10-50× faster for large meshes (100K+ vertices)
- File size: 3-5× smaller (binary vs text)
- Precision: float32 exact values (no rounding from text representation)
- Atomic: single file per mesh (no scattered XML + pose files)

### numpy 1 vs numpy 2 Compatibility (v1.5.1 Fix)

Maya 2026 ships with numpy 1.26.4. Earlier Maya versions had numpy 2.x. The `.sknr` format uses `numpy.save()` which produces different binary layouts in numpy 1 vs 2:

```python
# The problem: numpy 1 and 2 save() produce non-compatible binary files
# v1.5.1 fix: detect numpy version and handle both formats at load time

import numpy as np

def load_sknr_compat(filepath):
    """v1.5.1 approach: handle both numpy 1 and 2 binary formats."""
    try:
        data = np.load(filepath, allow_pickle=True)
    except ValueError:
        # If numpy 2 cannot read numpy 1 file or vice versa:
        data = np.load(filepath, allow_pickle=True, fix_imports=True)
    return data
```

### Transfer Strategy: Closest Point vs UV-Based

Skinner offers two transfer modes when topology differs:

**Closest Point (default):**
```python
# Map weights from source vertices to target vertices
# by nearest-neighbor in 3D space
# Fast, good for small topology changes
target_weights[v] = source_weights[nearest_source_vertex(v)]
```

**UV-based transfer:**
```python
# Map via UV coordinates
# More accurate when mesh has changed proportions
# Requires both meshes to have UVs in same UV space
```

### API Usage

```python
# Full scriptable API for pipeline integration
import skinner.core as skc

# Export skin weights
skc.exportSkin(
    meshes=['char_body_geo', 'char_face_geo'],
    filePath='/proj/char/skin/char_v002.sknr',
    verbose=True
)

# Import skin weights
skc.importSkin(
    filePath='/proj/char/skin/char_v002.sknr',
    # setToBindPose=True,   # reset to bind pose before importing
    # closestPoint=True,    # use closest point for mismatch topology
)

# Import with topology mismatch handling
skc.importSkin(
    filePath='/proj/char/skin/char_v002.sknr',
    closestPoint=True,    # fallback for vert count mismatch
    verbose=True          # report any vertex count differences
)

# Query what's in a .sknr file without importing
info = skc.getSknrInfo('/proj/char/skin/char_v002.sknr')
print(f"Mesh: {info['meshName']}, Verts: {info['vertCount']}")
print(f"Influences: {info['influences']}")
```

### Pipeline Integration Pattern

```python
import maya.cmds as cmds
import skinner.core as skc
import os

SKIN_CACHE_DIR = '/proj/assets/char/skin_cache'

def save_skin_on_scene_save(scene_path):
    """
    Auto-save skin weights when saving scene.
    Integrate as a Maya pre-save callback.
    """
    scene_name = os.path.splitext(os.path.basename(scene_path))[0]
    skin_dir = os.path.join(SKIN_CACHE_DIR, scene_name)
    os.makedirs(skin_dir, exist_ok=True)
    
    # Find all meshes with skinClusters
    all_meshes = cmds.ls(type='mesh', long=True)
    skinned = []
    for mesh in all_meshes:
        history = cmds.listHistory(mesh, pruneDagObjects=True) or []
        if any(cmds.nodeType(n) == 'skinCluster' for n in history):
            skinned.append(cmds.listRelatives(mesh, parent=True)[0])
    
    if skinned:
        export_path = os.path.join(skin_dir, 'all_skins.sknr')
        skc.exportSkin(meshes=skinned, filePath=export_path)
        print(f'Skin weights saved: {export_path}')

def restore_skin_on_scene_open(skin_file):
    """
    Restore skin weights after scene open.
    """
    if os.path.exists(skin_file):
        skc.importSkin(filePath=skin_file, closestPoint=False)
        print(f'Skin weights restored from: {skin_file}')
    else:
        print(f'WARNING: No skin cache found at {skin_file}')

# Register as callbacks:
# cmds.scriptJob(event=['SceneSaved', lambda: save_skin_on_scene_save(cmds.file(q=True, sn=True))])
```

## Implementación en Maya

**Installation:**
```bash
# Option 1: pip into Maya's Python
mayapy -m pip install skinner

# Option 2: manual
# Download from https://github.com/AKEric/skinner
# Place skinner/ folder in Maya scripts path or PYTHONPATH
```

**Version compatibility:**
- Maya 2020–2026 (tested)
- Python 3 (Maya 2022+)
- Numpy 1.x and 2.x (v1.5.1+)

**Key v1.5.1 change (2025-2026):**
- `.sknr` files saved with numpy 1 can now be loaded in Maya 2026 (numpy 1.26.4)
- Fixes silent corruption that occurred when mixing Maya versions in a pipeline

## Comparación con autorig_tools

autorig_tools ya tiene herramientas de skinning (export/import de skin data). La pregunta es si el formato y la robustez de Skinner aporta algo. Ventajas de Skinner vs solución propia: (1) formato numpy binario es más rápido y compacto que XML; (2) manejo de mismatch de topología incorporado; (3) compatibilidad numpy 1/2 resuelta; (4) API limpia para integración en pipeline. Si el sistema actual de autorig_tools ya tiene estas características, Skinner no aporta mucho. Si usa exportación XML nativa de Maya, migrar al formato .sknr valdría la pena especialmente en meshes con >50K verts donde la diferencia de velocidad es significativa.

## Aplicable directamente

PARTIAL — Si autorig_tools exporta skin weights como XML nativo, evaluar Skinner como reemplazo para meshes grandes. El formato .sknr es especialmente valioso en pipelines con muchos personajes donde se guardan/restauran pesos frecuentemente. La función `save_skin_on_scene_save()` es un patrón de pipeline directamente aplicable como ScriptJob o Hook en autorig_tools.

## Fuente
- GitHub: https://github.com/AKEric/skinner
- Releases (v1.5.1 numpy fix): https://github.com/AKEric/skinner/releases
- Eric Pavey announcement: https://groups.google.com/g/python_inside_maya/c/K_ATtyvFrCg
