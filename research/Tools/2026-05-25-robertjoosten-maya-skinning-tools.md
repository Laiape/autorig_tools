---
source: https://github.com/robertjoosten/maya-skinning-tools
found: 2026-05-25
category: tool
priority: 3
tags: [maya, python, skinning, skin-weights, paint, interactive, tools, github]
status: NEW
---

# maya-skinning-tools (robertjoosten) — Herramientas Interactivas de Skinning Paint

## Descripción
Colección de 8 herramientas de skinning para Autodesk Maya desarrolladas por Robert Joosten (TD en producción de animación), centradas en la interacción directa sobre la malla: smooth por pincelada, eliminación de influencias por región, inicialización de weights, mirror por topología, y conversión de soft selection a weights. Son herramientas artesanales de precisión para el skinning manual, complementando (no reemplazando) las herramientas de export/import como Skinner. Con 86 estrellas y licencia MIT.

## Fundamento matemático / técnico

### Tool Inventory

**1. Smooth Weights Context (paint-based)**
Interactive smoothing via paint brush:
```
For each vertex v under the brush stroke:
  neighbors = get_connected_vertices(v, max_distance=brush_radius)
  for each influence i:
    weights[v][i] = average(weights[neighbor][i] for neighbor in neighbors)
  normalize(weights[v])  # ensure sum = 1.0
```
This is iterative Laplacian smoothing applied locally under the brush, equivalent to one pass of the deltaMush algorithm but artist-controlled per region.

**2. Remove Weights Context (selective influence removal)**
Removes a specific influence from vertices under the brush:
```
For each vertex v under brush:
  removed_weight = weights[v][selected_influence]
  weights[v][selected_influence] = 0
  # Redistribute removed_weight proportionally to remaining influences:
  for each other_influence i in weights[v]:
    weights[v][i] += removed_weight * (weights[v][i] / (1.0 - removed_weight))
  # Result: weights still sum to 1.0, influence cleanly removed
```

**3. Initialize Weights**
Assigns initial weights based on closest joint proximity:
```
For each vertex v:
  distances = {joint_i: distance(v, joint_i) for joint_i in all_joints}
  closest_joints = sorted(distances, key=lambda j: distances[j])[:max_influences]
  weights = inverse_distance_weighting(v, closest_joints, power=2)
```
Uses the same IDW formula as Skinner's Closest Neighbors algorithm.

**4. Mirror Weights (topology-based)**
Mirrors weights using mesh topology rather than world position:
```
For each vertex v on the +X side:
  mirror_vertex = find_symmetric_vertex(v, axis='X', method='topology')
  weights[mirror_vertex] = remap_joints(weights[v], mirror_mapping)
```
`mirror_mapping` maps left joints to right joints (e.g. `l_arm_jnt` → `r_arm_jnt`) — requires proper joint naming convention.

**5. Soft Selection to Weights**
Converts Maya soft selection falloff values to skinCluster weights:
```
soft_selection = get_maya_soft_selection()  # returns {vtx: falloff_value}
for vertex, falloff in soft_selection.items():
    set_skin_weight(vertex, target_influence, falloff)
    normalize_remaining_influences(vertex)
```
Extremely useful for creating precise weight falloffs on transition zones (elbow, shoulder capsule).

**6. Tweak Weights**
Fine-grained per-component weight adjustment (like a weight table but interactive):
```
# Click and drag on vertex to increase/decrease weight for selected influence
# Similar to Maya's Paint Skin Weights but more precise per-vertex
```

**7. Delinear Weights**
Applies a curve function to existing weights to break linear falloff patterns:
```
new_weight = curve_remap(old_weight)  # e.g. smoothstep or ease-in curve
```
Creates more organic, non-linear weight distributions from linear initial states.

**8. Projection Plane from Joints**
Creates a plane object aligned to selected joints — useful as a reference for symmetric weight painting.

### Technical Stack
- Language: Python (99.8%) + AMPL (0.2%)
- Platform: Maya (version not explicitly stated; Python 2/3 compatible patterns)
- License: MIT
- Stars: 86 | No recent updates (established tool, complete)
- No external dependencies (pure maya.cmds + maya.api.OpenMaya)

### Key Design: Maya API Paint Context
The paint-based tools implement Maya's `MPxContext` or `MPxSurfaceShadingNodeOverride` to integrate with Maya's artisan painting system:
```python
class SmoothWeightsContext(OpenMayaUI.MPxSelectionContext):
    """Custom paint context that smooths weights under brush stroke."""
    
    def toolOnSetup(self, event):
        # Set up the brush and initialize the tool state
        pass
    
    def doDrag(self, event):
        # Called as the user drags the brush over the mesh
        # Read current vertices under brush → smooth their weights → apply
        pass
```
This is a level of Maya integration beyond simple `cmds` scripting — demonstrates MPxContext usage pattern.

## Implementación en Maya

Installation:
```python
# Add to Maya scripts path
import sys
sys.path.append('/path/to/maya-skinning-tools')

# Launch individual tools via module import
from maya_skinning_tools import (
    smooth_weights,
    remove_weights,
    initialize_weights,
    mirror_weights
)

# Or launch through a shelf button / hotkey
from maya_skinning_tools.ui import SkinningToolsUI
SkinningToolsUI.show()
```

Smooth weights on selected vertices:
```python
import maya.cmds as cmds
from maya_skinning_tools import smooth_weights

# Select vertices to smooth, then:
selected_vtx = cmds.ls(selection=True, flatten=True)
smooth_weights.smooth_selected(selected_vtx, iterations=3)
```

## Comparación con autorig_tools

autorig_tools tiene herramientas de skinning para export/import de weights, pero probablemente carece de las herramientas interactivas de pincelado de esta colección. La herramienta de Soft Selection → Weights es especialmente valiosa en el flujo de trabajo de rigging de Laia: permite crear falloffs precisos en shoulder capsule, hip, y wrist usando la selección blanda de Maya como guía — un flujo mucho más rápido que ajustar weights manualmente en el editor de componentes. El Mirror Weights por topología es más robusto que el mirror por posición para personajes con joint naming conventions claras.

## Aplicable directamente

YES — **Como herramientas complementarias al pipeline de autorig_tools:**
1. **Smooth Weights Context**: añadir a la barra de herramientas de skinning de autorig_tools para suavizado interactivo post-bind.
2. **Soft Selection → Weights**: especialmente útil tras hacer bind inicial — crear transiciones de peso suaves en las zonas de mezcla.
3. **Mirror Weights (topology)**: más fiable que la operación nativa de Maya en personajes con buena nomenclatura L/R de joints.
4. **Delinear Weights**: útil para corregir la distribución demasiado lineal que produce el proximity bind inicial.

## Fuente
- https://github.com/robertjoosten/maya-skinning-tools
