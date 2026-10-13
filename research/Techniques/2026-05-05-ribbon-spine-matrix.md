---
source: https://www.linkedin.com/pulse/creating-advanced-spine-rigging-system-maya-2020-kevin-borjon-piron
found: 2026-05-05
category: technique
tags: [maya, ribbon, spine, matrix, follicle, nurbs, rigging, twist, production]
status: NEW
---

# Ribbon Spine Rigging — Setup Matrix-Based sin Follicles

## Descripción
La columna ribbon es una técnica de rigging que usa una superficie NURBS como guía para distribuir joints a lo largo de la columna del personaje. La aproximación moderna (Maya 2020+) elimina los follicles tradicionales en favor de nodos matrix nativos, usando vectores normales y tangentes de la superficie NURBS para determinar la orientación de cada joint sin dependencias adicionales. Es el setup estándar en producción para personajes que requieren deformación orgánica de columna.

## Stack técnico
- Maya nodes: `closestPointOnSurface`, `pointOnSurfaceInfo`, `fourByFourMatrix`, `decomposeMatrix`, `multMatrix`, `aimConstraint` (versión clásica)
- Para twist: `multiplyDivide` node para distribuir rotación incremental
- NURBS plane como superficie guía
- Sin plugins externos; sin follicles en el setup moderno

## Detalles técnicos

### Setup clásico con follicles
- NURBS plane → follicle nodes a U=0.5, V=0, 0.25, 0.5, 0.75, 1.0
- Cada follicle da posición y orientación (normal de superficie)
- **Problema**: follicles tienen overhead de evaluación y twist inconsistente en curvaturas extremas

### Setup moderno matrix-based (sin follicles)
Usa vectores de la superficie directamente:
1. `pointOnSurfaceInfo` → `.normalizedNormal` (vector Y/forward del joint)
2. `pointOnSurfaceInfo` → `.normalizedTangentU` (vector up de referencia)
3. Cross product de Normal × Tangent → tercer eje (X o Z del joint)
4. Construir matrix 4x4 con `fourByFourMatrix`:
   - Row 0: tangent vector (X axis del joint)
   - Row 1: normal vector (Y axis)
   - Row 2: cross product (Z axis)
   - Row 3: position from pointOnSurfaceInfo

```
pointOnSurfaceInfo.position → fourByFourMatrix.in30/31/32
pointOnSurfaceInfo.normalizedNormal → fourByFourMatrix.in10/11/12  (Y axis)
pointOnSurfaceInfo.normalizedTangentU → fourByFourMatrix.in00/01/02 (X axis)
vectorProduct(cross) → fourByFourMatrix.in20/21/22  (Z axis)
fourByFourMatrix → decomposeMatrix → joint.translate + joint.rotate
```

### Distribución de twist en ribbon arms (Aaron Holly method)
Para twisting de extremidades tipo forearm twist:
- Conectar rotación del upper arm a joints del ribbon con `multiplyDivide`
- Primer joint del ribbon: multiply = 0.0 (no twist)
- Joints intermedios: multiply = 0.25, 0.50, 0.75
- Último joint: multiply = 1.0 (twist completo)
- Resultado: distribución suave del twist a lo largo del volumen del forearm

### Spine: distribución de controls
Para columna estándar de 5 joints:
- NURBS plane: 5 V patches, Cubic Surface degree
- Controles: pelvis, hips, chest, shoulders (4 controles → deforman el ribbon)
- Ribbon skinned al NURBS plane; joints siguen el ribbon

### Ribbon vs IK Spline — comparación de producción
| Característica | Ribbon | IK Spline |
|---|---|---|
| Control de volume | Muy bueno | Moderado |
| Intuitividad de posado | Alta | Media |
| Weight shift | Excelente | Bueno |
| Whip action | No nativo | Sí (con dynamics) |
| Overlap control | Requiere setup extra | Más natural |
| Performance | Buena | Muy buena |
| Recomendado para | Acción, cartoon, biped | Creatures, tentacles |

### Matrix Splines (Cole O'Brien, Medium)
Técnica que usa matrices para conducir joints a lo largo de una curva NURBS sin follicles ni IK Spline:
- `motionPath` node reemplazado por matrix calculation
- Permite stretch/squash y roll distribuido sin nodos adicionales
- Más limpio que IK Spline para setups dinámicos

## Comparación con autorig_tools
Si autorig_tools usa follicles en el ribbon spine, la migración a `pointOnSurfaceInfo + fourByFourMatrix` es el upgrade más directo: mismo resultado, menos nodos, mejor rendimiento. El método de twist con multiplyDivide para extremidades es compatible con el patrón local_mmx existente. La tabla ribbon vs IK Spline es una guía de decisión útil para documentar en el pipeline de autorig_tools.

## Takeaways aplicables
- Reemplazar follicles por `pointOnSurfaceInfo → fourByFourMatrix → decomposeMatrix` en el ribbon spine de autorig_tools. Implementar como función `build_ribbon_joint(surface, u_param, v_param)`.
- Implementar la **distribución de twist con multiplyDivide** para forearm/shin twist como módulo estándar en autorig_tools.
- Para la spine, parametrizar el número de controles y joints como argumentos del módulo (no hardcodeado a 5).
- Documentar la elección ribbon vs IK Spline como decisión de módulo al inicio del rig (ej. argumento `spine_type='ribbon'|'spline'`).

## Fuente
https://www.linkedin.com/pulse/creating-advanced-spine-rigging-system-maya-2020-kevin-borjon-piron  
https://sites.google.com/site/mayariggingwiki/rigging-notes/rig-fundamentals/ribbon  
https://coleobrien.medium.com/matrix-splines-in-maya-ec17f3b3741
