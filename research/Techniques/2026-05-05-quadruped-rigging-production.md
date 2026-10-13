---
source: https://www.cgchannel.com/2024/06/tutorial-creating-a-quadruped-rig-for-production/
found: 2026-05-05
category: technique
tags: [maya, quadruped, rigging, spine, ikfk, stretchy, production, gnomon, vfx]
status: NEW
---

# Quadruped Rigging para Producción en Maya — Técnicas Avanzadas

## Descripción
Técnicas de rigging de cuadrúpedos para producción VFX/film en Maya, sin plugins externos. El workshop del Gnomon (2024) es la referencia más reciente de la industria para este tipo de personaje. Los desafíos específicos del cuadrúpedo son: la columna horizontal (vs vertical del bípedo), los cuatro miembros con comportamientos IK diferentes, y la interacción pecho-pelvis en la columna.

## Stack técnico
- Autodesk Maya (sin plugins requeridos)
- Nodes: `ikHandle` (RP Solver + SC Solver), `splineIK`, `skinCluster`, `blendShape`
- Python: helper scripts para control rig y Spline-IK setup
- Rigging modular con Spline-IK para columna

## Detalles técnicos

### Columna Cuadrúpedo — Spline IK Approach
La columna horizontal del cuadrúpedo requiere un comportamiento push-pull entre pecho y pelvis que no existe en el bípedo vertical:
- **Spline IK** sobre curva NURBS (4-5 CVs) es el estándar de producción para columnas de cuadrúpedo
- CVs de la curva skinned a joints de control: pelvis, hip, back-mid, chest, neck-base
- **Push-pull behavior**: cuando el personaje se agacha, el pecho y la pelvis se acercan; la columna intermedia debe comprimir de forma realista

```
rig hierarchy (conceptual):
pelvis_ctrl → splineIK_curve_cv[0]
hip_ctrl    → splineIK_curve_cv[1]
mid_back_ctrl → splineIK_curve_cv[2]
chest_ctrl  → splineIK_curve_cv[3-4]
```

### Stretchy Spine para cuadrúpedo
```python
# Medir longitud actual de la curva vs longitud en bind pose
curve_info = cmds.createNode('curveInfo')
cmds.connectAttr('spineIK_curve.worldSpace[0]', curve_info + '.inputCurve')

# Normalizar: stretch_factor = current_length / rest_length
normalize = cmds.createNode('multiplyDivide')
cmds.setAttr(normalize + '.operation', 2)  # divide
cmds.connectAttr(curve_info + '.arcLength', normalize + '.input1X')
cmds.setAttr(normalize + '.input2X', rest_length)

# Aplicar stretch_factor a la escala de los joints de columna
for joint in spine_joints:
    cmds.connectAttr(normalize + '.outputX', joint + '.scaleX')  # axis along spine
```

### Twist en Spline IK
- Problema clásico: el spline IK no distribuye el twist automáticamente
- Solución: usar el atributo `roll` del ikHandle + twist distribuido via `multiplyDivide` en joints intermedios
- Alternativa moderna: sustituir spline IK por ribbon matrix-based (ver nota ribbon-spine)

### Patas del cuadrúpedo — particularidades
**Pata delantera** (como brazo humano invertido):
- Scapula → shoulder → elbow → wrist → toe
- FK chain + IK RP solver (wrist como end effector)
- **Reverse foot** con toe pivot y heel pivot

**Pata trasera** (digitigrade vs plantigrade):
- Hip → knee → ankle → ball → toe
- El "ankle" es el equivalente al codo del bípedo — va hacia atrás
- IK RP solver desde hip a ankle; separate IK SC para ball-to-toe
- **Reverse foot lock**: toe/ball/heel rotations en modo IK

### Neck y Head
- FK chain simple (3-5 joints) para cuello largo
- Cabeza: head_ctrl con atributos de follow_body y follow_neck (space switch)
- Blend constraint entre world space y neck tip

### Blended constraints para naturalidad
Usar **blended parentConstraints** (weightA + weightB = 1) en lugar de direct parent para algunos módulos proporciona deformación más natural sin interpenetración en poses extremas. Específicamente útil para escápula y clavícula del cuadrúpedo.

## Comparación con autorig_tools
Si autorig_tools tiene módulos de bípedo, la extensión a cuadrúpedo requiere principalmente: (1) un módulo de spine horizontal con Spline IK o ribbon, (2) reorientar los módulos de extremidades para funcionar en configuración cuadrúpeda (joints rotados), y (3) un módulo de reverse foot configurado para pata digitigrade. La mayoría de los módulos existentes son reutilizables con parámetros de orientación.

## Takeaways aplicables
- Añadir a autorig_tools un parámetro de **orientación de extremidad** en los módulos de brazo/pierna para soportar configuración cuadrúpeda sin duplicar código.
- El módulo de **spine para cuadrúpedo** debe ser Spline IK con stretch (curveInfo + multiplyDivide) y un control de push-pull chest/pelvis — diferente al ribbon más típico de bípedo.
- Implementar el **reverse foot** como módulo separado reutilizable (bípedo plantigrade + cuadrúpedo digitigrade con parámetros).
- El **stretch_factor via curveInfo** es el patrón estándar para stretch en Spline IK — verificar si autorig_tools lo tiene o si usa una implementación diferente.

## Fuente
https://www.cgchannel.com/2024/06/tutorial-creating-a-quadruped-rig-for-production/  
https://www.thegnomonworkshop.com/workshops/creating-a-quadruped-rig-for-production
