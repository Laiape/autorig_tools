---
source: https://github.com/mgear-dev/mgear
found: 2026-05-05
category: technique
tags: [maya, rbf, psd, correctives, pose-space-deformation, mgear, weightdriver, blendshapes, sdk]
status: NEW
---

# RBF / PSD Correctives en Maya — mGear RBF Manager + Epic PoseWrangler

## Descripción
Técnicas de deformación correctiva basadas en Radial Basis Functions (RBF) y Pose Space Deformation (PSD) para corregir artefactos de skinning en poses específicas. El RBF es una evolución del Set Driven Key: en lugar de definir driver/driven manualmente, interpola automáticamente entre N poses usando funciones radiales. Cubre el workflow completo con mGear RBF Manager v2.1 y Epic Games PoseWrangler para pipelines Maya+UE5.

## Stack técnico
- **mGear RBF Manager**: Python + mGearWeightDriver (C++ plugin, fork de SHAPES weightDriver)
- **Epic PoseWrangler**: Python script para Maya; Pose Driver Connect = C++ plugin UE5
- Maya 2020+ (PoseWrangler); Maya 2022+ (mGear RBF Manager v2)
- No requiere SHAPES si se usa mGear (mGearWeightDriver incluido)

## Detalles técnicos

### Concepto RBF
Un solver RBF define:
- **Keys (drivers)**: N-dimensionales — pueden ser rotaciones de joint, posiciones, atributos custom
- **Values (driven)**: M-dimensionales — corrective blendshape weights, rotaciones de joint, atributos

Para cada pose entrenada, el solver define un "radio de influencia". Al interpolar entre poses, las funciones radiales (típicamente gaussianas o multiquadric) ponderan la contribución de cada pose entrenada según la distancia en espacio de parámetros.

**Diferencia con SDK (Set Driven Key)**:
- SDK: 1D → interpolación lineal/spline en una sola dimensión
- RBF: N-D → interpolación multidimensional que maneja interacciones entre parámetros (ej. codo doblado + hombro rotado simultáneamente)

### mGear RBF Manager v2.1 (mGear 5.1, Sept 2024)
- Reemplaza SHAPES weightDriver con **mGearWeightDriver** (fork mantenido por el equipo mGear)
- Nuevo kernel de interpolación con manejo correcto de poses duplicadas
- Usuarios con SHAPES nativo pueden seguir usándolo instalándolo por separado
- Interfaz visual: añadir pose desde pose actual del rig → el manager captura todos los driver values automáticamente
- Soporta: blendshape weights, joint rotations, custom attributes como driven values

### mGear SDK Creator (mGear 5.3, April 2026) — NUEVO
- Genera Set Driven Key setups directamente desde poses en la timeline
- Workflow: posar el personaje en frame X → SDK Creator captura driver/driven → crea las keys automáticamente
- Complementa al RBF Manager para casos donde SDK es suficiente (correctives simples 1D)

### Epic PoseWrangler (Pose Driver Connect)
- Flujo Maya → UE5: autor de correctives en Maya → export JSON + FBX poses → import a UE5 via Pose Driver Connect plugin
- En Maya: PoseWrangler crea solvers RBF que controlan corrective joints; se visualiza y edita en viewport
- Compatibilidad: `Maya 2020+ / UE5.1+`; problemas reportados con Maya 2025 (RBF plugin loading)
- En UE5.6+: Pose Editor (MetaHuman for Maya) reemplaza parte del flujo PoseWrangler

### Pose Space Deformation nativa de Maya (Maya 2025 docs)
- Maya tiene PSD nativo desde versión 2020+
- Usa interpolación RBF internamente para activar blendshapes desde poses de joint
- Accesible desde: `Deform > Pose Space Deformation`
- Limitación: menos flexible que mGear RBF Manager para pipelines custom

### Corrective blendshapes — setup técnico
```
Orden de deformación recomendado: blendShape ANTES del skinCluster
→ blendShape (pre-deformation): Front of Chain
→ skinCluster (bind pose)
→ blendShape (post-deformation): corrige artefactos post-skin
```
Para **post-skin correctives**:
- Extraer la mesh deformada en la pose problemática
- Sculpt la corrección
- Usar `Edit Deformers > Blend Shape > Add` con modo `Post`
- Drivear el weight con SDK, RBF, o el driver nativo de Maya

## Comparación con autorig_tools
autorig_tools ya tiene soporte para RBF/SDK correctives. El valor incremental aquí es el **SDK Creator de mGear 5.3** (captura poses de timeline → SDK automático) y la integración del **mGearWeightDriver** fork como alternativa más estable que SHAPES. El flujo PoseWrangler→UE5 es relevante si el pipeline de Laia incluye entrega para Unreal.

## Takeaways aplicables
- Implementar un **SDK Creator** en autorig_tools: función que capture la pose actual (todos los joints o un subset) y cree automáticamente las driven keys en los targets deseados. Ahorra tiempo significativo en sesiones de correctives.
- Evaluar **mGearWeightDriver** como plugin para el sistema RBF de autorig_tools — es más estable que depender de SHAPES y tiene soporte activo.
- Para **correctives post-skin** (los más comunes en producción): asegurarse de que el orden de deformación en autorig_tools pone los post-correctives DESPUÉS del skinCluster.
- El uso del **RBF multidimensional para correcciones de poses combinadas** (hombro + codo simultáneamente) es el caso de uso donde RBF supera a SDK; documentar esto en autorig_tools como guía de cuándo usar cada sistema.

## Fuente
https://github.com/mgear-dev/mgear/releases  
https://github.com/chrisevans3d/poseWrangler  
https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-45D389D6-B8E4-4225-B27B-9927BB61C28D  
https://dev.epicgames.com/community/learning/tutorials/r04p/unreal-engine-authoring-secondary-animation-in-maya-and-unreal-with-pose-driver-connect
