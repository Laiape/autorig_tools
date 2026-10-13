---
source: https://github.com/TrevisanGMW/gt-tools
found: 2026-08-17
category: tool
priority: 3
tags: [maya, python, rigging, animation, pipeline, skinning, tools, github, open-source]
status: NEW
---

# GT Tools — Free Maya Python Scripts Collection (TrevisanGMW)

## Descripción
GT Tools es una colección gratuita y activamente mantenida de scripts Python/MEL para Autodesk Maya, desarrollada por Guilherme Trevisan. Cubre rigging, animación, mocap, pipeline y utilidades generales. Con 174 estrellas y soporte verificado en Maya 2025/2026/2027, es una de las colecciones de tools gratuitas más completas disponibles. Relevante para autorig_tools como referencia de organización de herramientas, UI patterns (PySide2/Qt), y funciones de rigging de propósito general.

## Fundamento matemático / técnico

GT Tools does not expose novel rigging math, but covers practical implementations of production-quality workflows:

### Key Rigging-Relevant Tools
- **Auto Rigger**: Biped auto-rigging system with IK/FK switching, stretchy limbs, space switching
- **Control Shape Manager**: Create, import, export control curves with custom shapes
- **Influence Map Tool**: Visualize and manage skin cluster influence sets — useful for debugging weight paint
- **Skin Weight Utilities**: Mirror, copy, prune, cap influences
- **Corrective Blendshape Tools**: Create deltas, mirror correctives, manage targets
- **Joint Tools**: Orient joints, create joint chains, chain alignment utilities
- **Ribbon Spine Builder**: NURBS ribbon spine with follicle-based joints

### Architecture Patterns
The toolkit follows a module-per-tool pattern with a unified PySide2 UI framework:
```
gt_tools/
├── tools/
│   ├── auto_rigger/
│   │   ├── module.py      # Biped/quadruped rig builder
│   │   ├── ui.py          # PySide2 UI
│   │   └── core/          # Limb modules (arm, leg, spine, finger)
│   ├── skin_utils/
│   │   ├── mirror_skin.py
│   │   ├── export_skin.py
│   │   └── copy_skin.py
│   └── control_utils/
│       ├── control_shapes.json  # Library of control curve shapes
│       └── shape_manager.py
├── utils/
│   ├── math_utils.py      # Vector/matrix helpers
│   ├── attr_utils.py      # Attribute management
│   └── node_utils.py      # Node creation/query helpers
└── ui/
    └── base_window.py     # Shared PySide2 base window class
```

### Skin Export/Import Format
GT Tools exports skin weights as JSON (similar approach to autorig_tools):
```python
# Export format:
{
    "mesh_name": "body_geo",
    "skinCluster": "skinCluster1",
    "influences": ["jnt_hip", "jnt_knee", "jnt_ankle"],
    "weights": {
        "0": [0.8, 0.2, 0.0],   # vertex index: [weights per influence]
        "1": [0.6, 0.4, 0.0],
        ...
    },
    "blend_weights": {...}
}
```

### Testing Infrastructure
GT Tools includes a test suite using Python `unittest`:
```python
# Tests cover: node creation, attribute setting, math utilities, weight operations
# Run via: python -m pytest gt_tools/tests/
# Tested on Maya 2025, 2026, 2027 (Windows 11)
```

## Implementación en Maya

Install via one-line drag-and-drop `.mel` installer or manual `sys.path.append()`. Menu appears as "GT Tools" in Maya's menu bar.

Key tools accessible from menu:
- `GT > Rigging > Auto Rigger` — full biped setup
- `GT > Skinning > Copy Skin Weights` — topology-invariant weight transfer
- `GT > Skinning > Export/Import Skin Weights` — JSON-based persistence
- `GT > Rigging > Create Control Curve` — shape library with PySide2 UI

### Math Utilities Worth Studying
```python
# From gt_tools/utils/math_utils.py (reconstructed from patterns):
import maya.api.OpenMaya as om2

def aim_matrix(aim_point, up_point, origin, aim_axis='x', up_axis='y'):
    """Build an aim matrix without aimConstraint."""
    aim_vec = (aim_point - origin).normalize()
    up_vec  = (up_point - origin).normalize()
    side_vec = aim_vec ^ up_vec; side_vec.normalize()
    up_corrected = side_vec ^ aim_vec; up_corrected.normalize()
    # Assemble matrix
    mat = om2.MMatrix()
    # ... fill rows based on aim_axis/up_axis mapping
    return mat
```

## Comparación con autorig_tools

GT Tools es una referencia útil para comparar architecture decisions:
- **Similitudes**: PySide2 UI, Python modular, skin export JSON, IK/FK builds
- **Diferencias clave**: GT Tools usa constraints y aimConstraint nativos en muchos módulos (no el patrón local_mmx/matrix puro de autorig_tools). La arquitectura de autorig_tools es más moderna desde la perspectiva de Parallel Evaluation.
- **Lo más útil de GT Tools**: la organización del repositorio (módulos independientes por herramienta), el sistema de testing, y la librería de control shapes en JSON — tres áreas donde autorig_tools podría inspirarse.

## Aplicable directamente

PARTIAL — No hay math nuevo directamente aplicable. El valor está en:
1. Estudiar la arquitectura de módulos (aplicable en 2-3h de refactoring si autorig_tools quiere modularizarse más)
2. Copiar el patrón de test suite para añadir tests a autorig_tools
3. El formato JSON de skin export es compatible con el enfoque de autorig_tools — revisar si hay diferencias en el manejo de `blend_weights`

## Fuente
- GitHub repo: https://github.com/TrevisanGMW/gt-tools
- Documentation site: https://trevisangmw.github.io/gt-tools/
- HighEnd3D listing: https://www.highend3d.com/maya/script/gt-tools-for-maya
