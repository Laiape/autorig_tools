---
source: https://create3dcharacters.com/maya-hive-autorigger/
found: 2026-08-03
category: tool
priority: 3
tags: [maya, rigging, autorig, facial, joints, game-engine, zoo-tools, modular, production]
status: NEW
---


# Hive Auto-Rigger (Zoo Tools 2.12.4) — Joint-Based Facial Rigs for Game Engines (Feb 2026)


## Descripción
Hive es el auto-rigger de producción incluido con Zoo Tools Pro para Maya, desarrollado por Create 3D Characters / Zoo Tools team. La actualización de febrero 2026 (Zoo Tools 2.12.4) añade un sistema de facial rigging completo basado en joints (no blendshapes) optimizado para exportación a Unreal Engine y Unity. El mouth component sale de beta, haciendo los facial joints production-ready para criaturas y humanoides. Notable por su arquitectura modular orientada a game engine pipeline.


## Fundamento matemático / técnico


### Architecture — Component-Based Modular System


Hive operates on "components" — reusable rig modules that can be assembled into full characters:


**Body components:**
- `biped.arm`, `biped.leg`, `biped.spine`, `biped.head`
- `quadruped.front_leg`, `quadruped.back_leg`, `quadruped.spine`
- `freeform_spine`, `twist_seg` (for twist distribution)


**New in 2026 (Zoo Tools 2.12.4) — Facial components:**
- `face.eye` — eyeball aim with stable world-up vector
- `face.eyelid` — upper/lower lid joints with squash/stretch
- `face.brow` — brow joint chain with per-joint controls
- `face.mouth` — full mouth component: lips, jaw, corners (OUT OF BETA)
- `face.cheek` — cheek volume control joints
- Template: `head_face_games` — pre-configured for real-time game export


### Joint-Based Face vs BlendShape-Based


**Joint-based approach (Hive 2026 default):**
```
mouth_corner_L_joint
  ├── upper_lip_mid_joint
  │     └── lip_seal corrective joint (automated)
  └── lower_lip_mid_joint
jaw_joint → rotX (open), rotY (lateral)
```


Advantages for game engines:
- **FBX-exportable**: joints export cleanly to Unreal/Unity; blendshapes require extra setup
- **GPU skinned in engine**: same skinCluster pipeline as body → coherent shader/deformation
- **Control rig mapping**: UE5 Control Rig / Unity Animator can drive joint targets
- **Lower VRAM**: no separate morph target buffers needed


Disadvantages vs blendshapes:
- Fewer unique face shapes (limited by joint count)  
- Wrinkle/aging details need additional texture blending
- Lip seal requires a dedicated "contact" joint or corrective setup


### Spine Offset Control (New 2026)


New `spine_offset` control added:
- Per-vertebra offset that respects the spline IK twist
- Mathematically: applies a local rotation before the ribbon/spline deformation
- Enables squash poses without breaking the uniform twist distribution


### Export Pipeline for Game Engines


```python
# Hive export workflow (simplified)
# 1. Build rig via Hive API
import zoo.libs.maya.cmds.rig.hive as hive
rig = hive.buildRigFromTemplate('biped_with_face_games')


# 2. Configure for game export
hive.setBakeJointsMode(rig, True)  # collapse to deformation skeleton


# 3. Export deformation skeleton + weights
# Result: single skeleton, no extra helper joints
# Compatible with Unreal Mannequin skeleton hierarchy
```


### Spline Joint-Based Facial — Per-Joint Control Math


Unlike a standard joint chain, Hive's facial components support **per-joint falloff weights**:


For N joints along a lip curve (e.g., 5 upper lip joints):
```
weight_j = gaussian(position_j - control_position, sigma)
```


The control (e.g., "upper_lip_mid_ctrl") has a spatial influence radius σ. Moving the control deforms nearby joints with Gaussian-weighted influence:


```
Δrotation_j = Δcontrol_input · exp(-|position_j - control_pos|² / (2σ²))
```


This gives "soft selection" behavior at the control level without extra nodes.


### Modular Template System


Templates are JSON configuration files:
```json
{
  "head_face_games": {
    "components": ["face.eye", "face.eyelid", "face.brow", "face.mouth", "face.cheek"],
    "mouth_config": {"joint_count": 9, "corner_falloff": 0.4},
    "eyelid_config": {"segments": 4, "squash_driver": "eye_aim"}
  }
}
```


This is structurally identical to what autorig_tools does with its Python module architecture.


## Implementación en Maya


**Installation:** Zoo Tools Pro (commercial, $49/yr individual). Included in studio licenses.


**Key Python API:**
```python
# Create facial components via Hive API
from zoo.libs.maya.cmds.rig import hiveapi


# Build from template
char = hiveapi.Rig()
char.buildFromTemplate('biped_face_games_template')


# Add individual facial component
face_comp = char.addComponent('face.mouth', side='center',
                               config={'joint_count': 7})
# Build it
face_comp.buildRig()
# Export deformation skeleton for game engine
char.exportDeformSkeleton('char_deform_skeleton.fbx')
```


**Relevant to autorig_tools:**
- The `joint_count` and `corner_falloff` parameters mirror what autorig_tools would need as config parameters for its facial module
- The `bakeJointsMode` concept (deformation skeleton export) is applicable if autorig_tools supports game engine pipelines


## Comparación con autorig_tools


Hive 2026 representa el estado del arte comercial en facial rigging orientado a game engines. El sistema de autorig_tools de Laia tiene facial rig (jaw, eyes, eyelids, brows, lips) pero probablemente con más dependencia de blendshapes y aimConstraints (el facial existente usa aimConstraint en los ojos, según el archivo de mayo 2026). Hive usa aimMatrix puro y joints distribuidos a lo largo del contorno de los párpados — más similar al nivel de producción AAA. La arquitectura de template JSON es algo a considerar para autorig_tools: parametrizar los módulos faciales vía config file en lugar de hardcodear counts de joints.


## Aplicable directamente


**PARTIAL** — Hive es una herramienta commercial (no open-source) por lo que no se puede integrar directamente en autorig_tools. Sin embargo: (1) la arquitectura de template JSON para configurar módulos es directamente adoptable como patrón; (2) el concepto de `exportDeformSkeleton` es relevante si el pipeline de Laia incluye entrega para Unreal/Unity; (3) el `spine_offset` control para squash sin romper twist es un concepto directamente implementable en el módulo de spine de autorig_tools.


## Fuente
- https://create3dcharacters.com/maya-hive-autorigger/ (Hive landing page)
- https://www.cgchannel.com/2026/02/hive-auto-rigger-for-maya-now-creates-full-joint-based-faces/ (Feb 2026 update news)
- https://create3dcharacters.com/2026/02/17/hive-auto-rigger-massive-update-video/ (update video)
- https://vimeo.com/1155088922 (Hive 2026 demo reel)
- https://digitalproduction.com/2026/02/23/hive-adds-joint-facial-rigs-to-maya/ (press coverage)