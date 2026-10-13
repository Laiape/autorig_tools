---
source: https://github.com/TrevisanGMW/gt-tools
found: 2026-05-25
category: tool
priority: 3
tags: [maya, python, rigging, skinning, IK, autorig, biped, tools, pipeline, PySide2, github]
status: NEW
---

# GT Tools (TrevisanGMW) — Colección Completa de Scripts Python para Maya

## Descripción
GT Tools es una colección gratuita y open-source de más de 100 scripts para Autodesk Maya, organizada en submenús temáticos (modeling, rigging, utilities, animation, skinning). Su principal valor es la amplitud de herramientas: desde auto-rigging bípedo con HumanIK hasta exportación FBX para juegos, pasando por herramientas específicas de skinning, ribbon, sine attributes procedurales y retarget de mocap. Desarrollado por Guilherme Trevisan (Brasil), está activamente mantenido con 189 estrellas y 93 releases hasta diciembre 2024.

## Fundamento matemático / técnico

### Architecture & Tech Stack
- **Language:** Python 3 (94.2%) + MEL (5.8%)
- **UI:** PySide2/Qt (pre-Maya 2025); PySide6 compatibility issue in Maya 2025+ (known bug #203)
- **Installation:** drag-and-drop setup script, adds pull-down menu to Maya
- **License:** MIT (2020)
- **Stars:** 189 | **Releases:** 93 | **Latest:** v3.4.1 (December 12, 2024)
- **Tested on:** Maya 2022, 2023, 2024 (Windows 11)

### Rigging Tool Inventory

**GT Biped Auto Rigger**
Full biped rig generator:
- FK/IK switches for arms and legs
- Finger automation with curl/spread attributes
- Foot rolls (heel, ball, toe) with bank
- Stretchy limbs with volume preservation
- Automatic HumanIK character definition for mocap retargeting
- Control shape customization

**GT Biped Rig Interface**
Post-rig automation panel:
- FK/IK switching with matching
- Pose management (mirror, reset, store/recall)
- Animation utilities

**GT Make IK Stretchy**
Standalone stretchy IK tool:
- Adds stretch + squash to existing IK handles
- Includes volume preservation (cross-axis scaling)
- Works on arbitrary IK chains (not only biped)

**GT Ribbon Tool**
Automated ribbon surface creation:
- Configurable joint count and surface resolution
- Follicle-based attachment points
- Used for spine, lip, eyelid ribbons

**GT Create Auto FK**
Forward kinematics control builder:
- Generates FK control hierarchy for selected joint chain
- Maintains transform hierarchy
- Configurable control shape and color

**GT Add Sine Attributes**
Procedural motion attribute generator:
- Creates sine wave attributes without plugins (pure DG)
- Uses Maya expression or node network for wave computation
- Useful for procedural cloth, tail, and breathing overlays

**GT Connect Attributes**
Attribute connection automation:
- Batch source→target attribute connections
- Optional reverse node insertion
- Useful for SDK setups and blend weight wiring

**GT Morphing Utilities**
Blendshape management:
- Creates driver attributes for morphing systems
- Manages blendShape node organization on rig controls

**GT Mirror Cluster Tool**
Cluster mirroring across symmetry axes — used in facial corrective setups.

**GT Extract Bound Joints**
Generates Python code to select all joints in a skinCluster — useful for rig documentation and joint list export.

**GT Retarget Assistant**
HumanIK mocap retargeting patches:
- Handles toes, spine, fingers, leg stabilization
- Applies corrections to retargeted animations from external sources

**GT Game FBX Exporter**
Game engine pipeline export:
- FBX model + animation export from biped rig
- Configurable skeleton hierarchy for UE5/Unity

### Code Patterns
Consistent use of Maya Python API patterns:
```python
# Typical gt-tools pattern: cmds-based with error checking
import maya.cmds as cmds

def gt_make_stretchy(ik_handle, stretch_name='stretch_attr', volume=True):
    """Add stretchy IK to existing handle."""
    # Find root and tip from ik handle
    start_joint = cmds.ikHandle(ik_handle, q=True, startJoint=True)
    end_effector = cmds.ikHandle(ik_handle, q=True, endEffector=True)
    end_joint    = cmds.listConnections(f'{end_effector}.translateX', s=True)[0]
    
    # ... creates distanceBetween + clamp + multiplyDivide chain
    # Note: uses distanceBetween (classic approach, not matrix-based)
```

**Notable gap vs autorig_tools:** GT Tools uses the classic `distanceBetween` approach for stretch IK, not the matrix-based approach covered in `2026-05-25-stretch-ik-pure-matrix-maya.md`. This is a performance improvement opportunity.

## Implementación en Maya

Installation:
```python
# Drag-and-drop gt_tools_setup.py onto Maya viewport
# Or manually:
import sys
sys.path.append('/path/to/gt-tools/python-scripts')
import gt_tools_setup
gt_tools_setup.install()
# Adds "GT Tools" pull-down menu to Maya's main menu bar
```

Individual tool access:
```python
# Direct import pattern
from gt_rigger.gt_rigger_biped import GTBipedRigger
rigger = GTBipedRigger()
rigger.create_biped_proxy()  # guides
rigger.create_biped_rig()    # full rig build
```

## Comparación con autorig_tools

GT Tools es más amplio en categorías (modeling, animation, utilities) pero menos especializado en rigging de producción AAA/VFX que autorig_tools. Sus herramientas de rigging son funcionales y bien mantenidas, pero siguen patrones clásicos (constraints, distanceBetween) en lugar del approach matricial de autorig_tools. El valor principal de GT Tools para Laia es como **referencia de implementación**: cómo estructurar menús, cómo hacer setup install/uninstall drag-and-drop, y cómo implementar HumanIK integration para mocap retargeting. El `GT Retarget Assistant` y el `GT Game FBX Exporter` son funcionalidades que autorig_tools actualmente no cubre.

## Aplicable directamente

PARTIAL — **Tres áreas de referencia útil:**
1. **HumanIK integration**: el `GT Biped Auto Rigger` genera la definición HumanIK automáticamente — código de referencia para añadir soporte mocap a autorig_tools.
2. **FBX export pipeline**: `GT Game FBX Exporter` muestra un patrón limpio de exportación para games que autorig_tools podría adoptar.
3. **Install pattern**: el sistema drag-and-drop setup con menú Maya es un patrón de distribución a considerar para autorig_tools si se plantea publicar.

## Fuente
- https://github.com/TrevisanGMW/gt-tools
- https://trevisangmw.github.io/gt-tools/
- https://www.highend3d.com/maya/script/gt-tools-for-maya
