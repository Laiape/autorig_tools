---
source: https://www.jaredlindquist.com/tips-tutorials/ik-fk-matching-theory/
found: 2026-05-05
category: technique
tags: [maya, ikfk, matching, algorithm, python, rigging, worldMatrix, animation]
status: NEW
---

# IK/FK Matching — Teoría y Algoritmo de Implementación

## Descripción
El IK/FK match permite a los animadores cambiar de modo IK a FK (o viceversa) en mitad de una animación sin que el personaje "salte". Es una funcionalidad crítica en cualquier rig de producción. El algoritmo correcto depende de obtener posiciones/rotaciones en world space desde la cadena fuente y aplicarlas en la cadena destino, teniendo en cuenta las especificidades de cada modo.

## Stack técnico
- Maya Python API: `maya.cmds`, `maya.api.OpenMaya.MMatrix`, `MTransformationMatrix`
- Nodes implicados: worldMatrix, ikHandle, poleVector constraint
- Sin plugins externos; lógica puramente matemática

## Detalles técnicos

### FK → IK Match
Objetivo: mover el IK handle y el pole vector para que la cadena IK coincida con la pose FK actual.

**Paso 1 — Match IK end effector**:
```python
# Obtener worldMatrix del joint final de la cadena FK
wm = cmds.getAttr('fk_wrist.worldMatrix[0]')
# Aplicar posición al IK control
pos = cmds.xform('fk_wrist', q=True, ws=True, t=True)
cmds.xform('ik_ctrl', ws=True, t=pos)
# Aplicar rotación (para wrist/ankle donde el IK ctrl tiene orientación)
rot = cmds.xform('fk_wrist', q=True, ws=True, ro=True)
cmds.xform('ik_ctrl', ws=True, ro=rot)
```

**Paso 2 — Match Pole Vector**:
El pole vector debe estar en el plano definido por el triángulo shoulder-elbow-wrist.
```python
import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

def get_pole_vector_position(root, mid, end, distance=1.0):
    root_pos = om.MVector(*cmds.xform(root, q=True, ws=True, t=True))
    mid_pos  = om.MVector(*cmds.xform(mid,  q=True, ws=True, t=True))
    end_pos  = om.MVector(*cmds.xform(end,  q=True, ws=True, t=True))
    
    # Vector de root a end
    line = end_pos - root_pos
    # Vector de root a mid
    point = mid_pos - root_pos
    # Proyección de point sobre line
    scale_value = (point * line) / (line * line)
    proj = line * scale_value + root_pos
    # Vector desde proyección a mid (dirección del pole vector)
    pole_dir = (mid_pos - proj).normalize()
    
    return mid_pos + pole_dir * distance
```

**Paso 3 — Twist arm correction**:
Si el brazo está torcido (ej. palm hacia abajo), el pole vector básico puede apuntar en dirección incorrecta. Solución: calcular el ángulo de twist actual de la cadena FK y ajustarlo en el IK.

### IK → FK Match
Objetivo: rotar los controles FK para que coincidan con la pose IK actual.

```python
# Para cada joint de la cadena FK, obtener la rotación del bind joint IK
for fk_ctrl, bind_joint in zip(fk_ctrls, ik_joints):
    # Obtener worldMatrix del bind joint (que sigue al IK)
    wm = om.MMatrix(cmds.getAttr(f'{bind_joint}.worldMatrix[0]'))
    # Calcular la matriz local del control FK
    parent_wm_inv = om.MMatrix(cmds.getAttr(f'{fk_ctrl_parent}.worldInverseMatrix[0]'))
    local_matrix = wm * parent_wm_inv
    # Descomponer en rotación
    tm = om.MTransformationMatrix(local_matrix)
    rot = tm.rotation(asQuaternion=False)  # retorna MEulerRotation
    cmds.xform(fk_ctrl, ro=[math.degrees(rot.x), math.degrees(rot.y), math.degrees(rot.z)])
```

### Casos edge — problemas comunes
1. **Gimbal lock en rotaciones**: usar quaternions (`MTransformationMatrix.rotation(asQuaternion=True)`) para la interpolación cuando las rotaciones cruzarán el límite de gimbal.
2. **Cadenas FK de longitud arbitraria** (mGear 5.1 lo mejoró): el algoritmo debe iterar por N joints, no asumir shoulder-elbow-wrist.
3. **IK con twist attribute**: si el IK handle tiene twist, debe calcularse y aplicarse antes del match.
4. **ScriptJob automático**: algunos sistemas ejecutan el match como scriptJob al cambiar el blend IK/FK attribute:
```python
cmds.scriptJob(attributeChange=['ctrl.ikfkBlend', lambda: match_ikfk()])
```

### Universal IK/FK Tool approach
Herramientas como el Universal IK FK Switch (Monika Yellow) almacenan las definiciones de control UNA VEZ en nodos de la escena para reutilización durante toda la animación, evitando que el animador tenga que reconfigurar la herramienta en cada sesión.

## Comparación con autorig_tools
autorig_tools ya tiene IK/FK matching integrado. El valor de esta investigación es el algoritmo explícito del **pole vector position calculation** (que muchos implementan incorrectamente) y el manejo de **cadenas FK de longitud arbitraria** (el fix de mGear 5.1). Confirma que usar `worldMatrix` + `worldInverseMatrix` del padre es el approach correcto.

## Takeaways aplicables
- Revisar la implementación del **get_pole_vector_position** en autorig_tools: ¿usa la proyección sobre el vector root→end o un método diferente? El método de proyección es matemáticamente el más correcto.
- Asegurarse de que el IK/FK match de autorig_tools funciona con cadenas de N joints (no hardcodeado a 3). Refactorizar si es necesario.
- El **scriptJob en attributeChange** para match automático es una UX muy valorada por animadores. Considerar añadirlo como opción en el rig publicado.
- Para evitar gimbal lock en el FK→IK match, usar `MTransformationMatrix` con quaternions en lugar de euler.

## Fuente
https://www.jaredlindquist.com/tips-tutorials/ik-fk-matching-theory/  
https://monikayellow.gumroad.com/l/srTEI  
https://github.com/mgear-dev/mgear/releases (mGear 5.1 IK/FK improvements)
