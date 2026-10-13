---
source: https://www.chadvernon.com/blog/space-switching-offset-parent-matrix/
found: 2026-05-05
category: technique
tags: [maya, matrix, rigging, space-switching, offsetParentMatrix, wtAddMatrix, multMatrix, python, constraints]
status: NEW
---

# Matrix Rigging con offsetParentMatrix — Space Switch sin Constraints

## Descripción
Técnica de rigging basada en matrices nativas de Maya (disponible desde Maya 2020) que reemplaza parentConstraints y extra transform nodes en el space switching. Usa el atributo `offsetParentMatrix` del nodo transform para inyectar directamente una matriz calculada, eliminando nodos de constraint y reduciendo el grafo DG. Es la evolución natural del patrón multMatrix/decomposeMatrix hacia una integración más directa con el transform node.

## Stack técnico
- Maya 2020+ (offsetParentMatrix introducido en 2020)
- Nodes: `wtAddMatrix`, `multMatrix`, `decomposeMatrix`, `inverseMatrix`, `pickMatrix`
- Python: `maya.cmds`, `maya.api.OpenMaya.MMatrix`
- No plugins externos requeridos

## Detalles técnicos

### Flujo básico de matrix constraint (sin offsetParentMatrix)
```
parent.worldMatrix[0]   →─┐
                           ├─ multMatrix → decomposeMatrix → child.translate/rotate/scale
child.parentInverseMatrix →─┘
```
Equivale a un parentConstraint pero usa menos nodos y es más rápido.

### Space switch con wtAddMatrix
El nodo `wtAddMatrix` mezcla N matrices con pesos (no normaliza — la suma de pesos puede ser > 1 o negativa):
```
spaceA.worldMatrix[0]  (weight = 1 - blend) ─┐
spaceB.worldMatrix[0]  (weight = blend)      ─┤─ wtAddMatrix → multMatrix → decomposeMatrix
                                              └─ child.parentInverseMatrix
```
- El atributo de blend del control driving a `wtAddMatrix.wtMatrix[*].weightIn`
- **Importante**: wtAddMatrix no normaliza. Para blends correctos: `weightA + weightB = 1.0`
- Para más de 2 espacios: añadir más entradas al wtAddMatrix

### Space switch con offsetParentMatrix (Maya 2020+)
El `offsetParentMatrix` permite driving directo del transform:
```python
# Conectar la matriz mezclada directamente al offsetParentMatrix
cmds.connectAttr('wtAdd.matrixSum', 'ctrl.offsetParentMatrix')
# CRÍTICO: zerear los canales locales del control para evitar double transform
cmds.setAttr('ctrl.translate', 0, 0, 0)
cmds.setAttr('ctrl.rotate', 0, 0, 0)
cmds.setAttr('ctrl.scale', 1, 1, 1)
```

### Double transform — el problema clave
Si `offsetParentMatrix` ya contiene traslación y los canales locales también tienen valores, hay **double transform**. Solución: zerear los canales locales del nodo después de conectar la offsetParentMatrix. En Python:
```python
import maya.cmds as cmds
# Guardar posición mundo, conectar offsetParentMatrix, zerear locales
world_pos = cmds.xform('ctrl', q=True, ws=True, t=True)
cmds.connectAttr('matrix_network.matrixSum', 'ctrl.offsetParentMatrix')
cmds.setAttr('ctrl.t', 0, 0, 0)
```

### parentInverseMatrix vs parent worldInverseMatrix
- Usar `parentInverseMatrix` puede causar ciclos DG en ciertos grafos
- Alternativa más segura: obtener el `worldInverseMatrix` del nodo padre directamente:
```
ctrl.worldMatrix → multMatrix ← actualParent.worldInverseMatrix
```

### Python: setAttr de matrix
```python
import maya.cmds as cmds
matrix_values = [1,0,0,0, 0,1,0,0, 0,0,1,0, tx,ty,tz,1]  # row-major, 16 floats
cmds.setAttr('node.offsetParentMatrix', *matrix_values, type='matrix')
```

### Beneficios sobre constraints
- Menos nodos en el grafo DG → evaluación más rápida
- Outliner más limpio (sin nodos constraint visibles)
- Más fácil de debugar desde el Node Editor
- Comportamiento idéntico matemáticamente

## Comparación con autorig_tools
El patrón local_mmx de autorig_tools ya usa multMatrix/decomposeMatrix, lo cual es el precursor directo de esta técnica. El paso siguiente natural es adoptar `offsetParentMatrix` como destino final de la cadena de matrices, eliminando el decomposeMatrix → connect to translate/rotate/scale y usando el plug directo. Esto simplifica el código de conexión y reduce nodos. Chad Vernon y Rigging Dojo confirman que es la práctica recomendada para Maya 2020+.

## Takeaways aplicables
- Migrar el destino de las cadenas matrix de autorig_tools de `decomposeMatrix → translate/rotate` a `offsetParentMatrix` directamente. Menos nodos, igual resultado.
- En el sistema de space switch de autorig_tools, reemplazar el blend constraint (si se usa) por `wtAddMatrix` con el blend attribute del control. Patrón mucho más limpio.
- Crear una función utilitaria en autorig_tools: `matrix_space_switch(ctrl, spaces, blend_attr)` que monte el grafo wtAddMatrix automáticamente.
- Documentar el gotcha del **double transform** para el equipo — es el error más común al adoptar offsetParentMatrix.

## Fuente
https://www.chadvernon.com/blog/space-switching-offset-parent-matrix/  
https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-8AE22982-B840-4E7B-A098-B4D15D01CCE4  
https://gist.github.com/Muream/b4255ec4f690222d92fe794be249b7f1
