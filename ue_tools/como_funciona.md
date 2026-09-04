# ue_tools (export a Unreal)

Parent: `como_funciona.md` (raiz).
Contrato de export: `.claude/rules/deformacion-y-skin.md` (solo viajan joints `_ENV` y morphs).
Esqueleto de export: `rig_manager.skeleton_hierarchy` en `maya_tools/scripts/utils/como_funciona.md`.

## 1. Que es y para que existe

Sitio reservado para el codigo y las notas de la parte de Unreal del
pipeline. Hoy solo hay documentacion.

## 2. Como esta montado

| Fichero | Que es |
|---|---|
| `ue_tools/docs/unreal_fest_chicago_2026_rigging_produccion.md` | notas de la charla de Stephane Biava (Epic) en Unreal Fest Chicago 2026: precision de pesos (8 influencias, High Precision Skin Weights, lock por joint en 5.8), optimizacion de asset y de Control Rig (Execution Stack, Preview Nodes, profiling, Construction Event), inline bones, switch IK/FK en Sequencer, Deformer Graph desde Control Rig, Spherical Pose (RBF), modularidad en 3 capas (funciones + variants, Modular Control Rig, data-driven por Data Asset), Control Rig Dynamics, groom, y una seccion final "Ideas aplicables a nuestro pipeline" |
| `ue_tools/scripts/_init_.py` | vacio y MAL NOMBRADO (`_init_` con un guion bajo): Python no lo reconoce como paquete. Renombrar a `__init__.py` en la Fase 4 |

## 3. Datos que lee y escribe

Nada todavia. Lo que llegue a UE sale de Maya como esqueleto `_ENV`
(`skeletonHierarchy_GRP`, raiz `C_freeze_ENV`, correctivas colgadas del `_ENV`
de su padre) mas morphs.

## 4. Estado hoy

Carpeta placeholder. Las ideas ya decididas en las notas: el data-driven de
UE (Data Asset -> Construction Event) es el analogo del `.build` + guias; los
ribbons de Boor se exportan como leaf joints o cadena real + Full Body IK;
Control Rig Dynamics cubre colas sin plugin; morph targets con flip/mirror en
5.8 reducen el round-trip de correctivas faciales.

## 5. Como probarlo

No aplica.

## 6. Do not

- No poner aqui codigo de Maya: eso va en `maya_tools/scripts`.
- No dar por exportable nada que no sea joint `_ENV` o morph.
