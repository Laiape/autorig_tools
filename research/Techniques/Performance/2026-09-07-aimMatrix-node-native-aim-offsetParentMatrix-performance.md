---
source: https://www.tech-artists.org/t/maya-aim-matrix-vs-aim-constraint-whats-missing/14770
found: 2026-09-07
category: performance
priority: 2
tags: [maya, performance, rigging, matrix, aimMatrix, aimConstraint, offsetParentMatrix, nodes, optimization]
status: NEW
---

# aimMatrix Node — Aim Nativo sin aimConstraint (Maya 2020+)

## Descripción
El nodo `aimMatrix` (introducido en Maya 2020) es el reemplazo nativo del sistema de aim constraint implementado como nodo DG puro. A diferencia del `aimConstraint` (que incluye overhead de gestión de targets múltiples, offsets, modos de worldUp, y escritura via el sistema de constraint) y de la alternativa manual pre-2020 (multMatrix + vectorProduct + composeMatrix), `aimMatrix` encapsula la construcción del frame de rotación en un único nodo compilado C++ que se conecta directamente al `offsetParentMatrix` del transform destino — sin overhead de constraint, sin dirty propagation adicional, compatible con Parallel Evaluation y GPU Override scheduling.

## Fundamento matemático / técnico

### Construcción del frame (lo que hace aimMatrix)

Dado un punto objetivo (primaryTargetMatrix) y un punto de referencia "up" (secondaryTargetMatrix):

```
primary_vec          = normalize( target_pos − own_pos )
secondary_vec        = normalize( up_pos − own_pos )
tertiary_vec         = normalize( primary_vec × secondary_vec )
secondary_corrected  = normalize( tertiary_vec × primary_vec )

outputMatrix = compose(primary_vec, secondary_corrected, tertiary_vec, own_pos)
```

El mapping de ejes al espacio local del transform se controla con `primaryInputAxis` y `secondaryInputAxis`.

### Overhead de aimConstraint vs aimMatrix

`aimConstraint` calcula adicionalmente:
- 4 modos de `worldUpType` (branching en C++, siempre activo aunque no se use)
- `offset` attribute (multiplicado siempre)
- `restTranslate` / `restRotate` (para constraint blending)
- Array de targets múltiples con pesos (`multTarget[i].weight`)
- Escritura en `.rotate` vía sistema de constraint (dispara dirty en DAG)
- Scheduling type: puede ser `globally_serialize` en contextos de Parallel Evaluation

`aimMatrix`: sólo los 3 vectores + compose. Scheduling type: `parallel` (DG puro). Escribe en `offsetParentMatrix` → no dispara dirty en cadena DAG.

Diferencia medida (Tech-Artists.org, producción real):
- `aimConstraint`: ~0.05–0.15 ms/nodo
- `aimMatrix`:     ~0.02 ms/nodo
- En un biped con 20 aim setups: ahorro ~0.6–2.6 ms/frame

### Limitaciones conocidas de aimMatrix vs aimConstraint

1. **No tiene `worldUpType = objectRotationUp`** — sólo acepta posición como up target. Para replicarlo: pickMatrix + pointMatrixMult.
2. **No tiene `offset` attribute** — el offset debe pre-multiplicarse externamente (un multMatrix adicional).
3. **No soporta múltiples targets con pesos** — sólo un objetivo. Para blend: usar wtAddMatrix en las matrices de objetivo antes de aimMatrix.

## Implementación en Maya

### Sustitución directa (caso simple: aim con up-target posicional)

```python
import maya.cmds as cmds

def matrix_aim_simple(driver_obj, aim_target, up_target, driven_obj,
                       primary_axis=(1, 0, 0), secondary_axis=(0, 1, 0)):
    """
    Aim constraint sin nodo de constraint, usando aimMatrix + offsetParentMatrix.
    """
    aim_node = cmds.createNode('aimMatrix', name=f'{driven_obj}_aimMtx')
    cmds.connectAttr(f'{driver_obj}.worldMatrix[0]', f'{aim_node}.inputMatrix')
    cmds.connectAttr(f'{aim_target}.worldMatrix[0]', f'{aim_node}.primaryTargetMatrix')
    cmds.connectAttr(f'{up_target}.worldMatrix[0]',  f'{aim_node}.secondaryTargetMatrix')
    cmds.setAttr(f'{aim_node}.primaryInputAxis',   *primary_axis)
    cmds.setAttr(f'{aim_node}.secondaryInputAxis', *secondary_axis)
    cmds.connectAttr(f'{aim_node}.outputMatrix', f'{driven_obj}.offsetParentMatrix')
    for attr in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz'):
        cmds.setAttr(f'{driven_obj}.{attr}', 0)
    return aim_node


def matrix_aim_with_rotation_up(driver_obj, aim_target, up_obj, driven_obj,
                                  up_axis=(0, 1, 0),
                                  primary_axis=(1, 0, 0), secondary_axis=(0, 1, 0)):
    """
    Replica worldUpType=objectRotationUp.
    Extrae el vector up del up_obj con pickMatrix + pointMatrixMult.
    """
    # 1. pickMatrix: sólo rotación del up_obj
    pick = cmds.createNode('pickMatrix', name=f'{driven_obj}_pickUpAxis')
    cmds.connectAttr(f'{up_obj}.worldMatrix[0]', f'{pick}.inputMatrix')
    cmds.setAttr(f'{pick}.useTranslate', False)
    cmds.setAttr(f'{pick}.useScale', False)
    cmds.setAttr(f'{pick}.useShear', False)
    
    # 2. pointMatrixMult: up_axis en espacio local del up_obj → espacio mundo
    pmm = cmds.createNode('pointMatrixMult', name=f'{driven_obj}_upAxisWorld')
    cmds.setAttr(f'{pmm}.inPoint', *up_axis)
    cmds.setAttr(f'{pmm}.vectorMultiply', True)
    cmds.connectAttr(f'{pick}.outputMatrix', f'{pmm}.inMatrix')
    
    # 3. composeMatrix con el vector up como posición (aimMatrix usa posición del origen)
    compose = cmds.createNode('composeMatrix', name=f'{driven_obj}_upPosMtx')
    cmds.connectAttr(f'{pmm}.output', f'{compose}.inputTranslate')
    
    # 4. aimMatrix con el composeMatrix como secondaryTargetMatrix
    aim_node = cmds.createNode('aimMatrix', name=f'{driven_obj}_aimMtx')
    cmds.connectAttr(f'{driver_obj}.worldMatrix[0]', f'{aim_node}.inputMatrix')
    cmds.connectAttr(f'{aim_target}.worldMatrix[0]', f'{aim_node}.primaryTargetMatrix')
    cmds.connectAttr(f'{compose}.outputMatrix',      f'{aim_node}.secondaryTargetMatrix')
    cmds.setAttr(f'{aim_node}.primaryInputAxis',   *primary_axis)
    cmds.setAttr(f'{aim_node}.secondaryInputAxis', *secondary_axis)
    cmds.connectAttr(f'{aim_node}.outputMatrix', f'{driven_obj}.offsetParentMatrix')
    return aim_node


def audit_aim_constraints_in_rig(rig_root):
    """Detecta todos los aimConstraints bajo rig_root para planificar reemplazo."""
    all_aims = cmds.listRelatives(rig_root, allDescendants=True,
                                   type='aimConstraint') or []
    print(f"Found {len(all_aims)} aimConstraint nodes under {rig_root}")
    for node in all_aims:
        targets = cmds.listConnections(f'{node}.target', source=True) or []
        print(f"  {node}: targets={targets}")
    return all_aims
```

## Comparación con autorig_tools

El `local_mmx` pattern de autorig_tools ya eliminó parentConstraints, pero las cadenas de aim (pole vectors, eye aims, ribbon frame orientation) probablemente usan `aimConstraint`. En un biped completo con 6 pole vector aims, 2 eye aims, 8 ribbon frame aims y 4 tweak joint aims (20 nodos total): ahorro promedio ~0.08 ms/nodo = **~1.6 ms/frame** recuperados. Bonus: los `aimMatrix` tienen scheduling `parallel` → no bloquean el EG en Parallel Evaluation como algunos `aimConstraint` nodes.

## Aplicable directamente

YES — Ejecutar `audit_aim_constraints_in_rig(rig_root)` para cuantificar el scope. Prioridad de reemplazo: (1) pole vector aim joints de brazo y pierna, (2) eye aim joints del facial rig, (3) frame orientation nodes del ribbon spine. El caso de `worldUpType=objectRotationUp` requiere el workaround de pickMatrix + pointMatrixMult documentado arriba. Estimado: 2-4h para auditar + reemplazar todos los aimConstraints en un biped completo de autorig_tools.

## Fuente
https://www.tech-artists.org/t/maya-aim-matrix-vs-aim-constraint-whats-missing/14770
https://www.dominikhaase.com/post/matrix-aim-constraint-rotatehelper
https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2025/UsingParallelMaya.html
https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-B98C5BB8-D9DB-40C6-A6C3-A1D92285D327
