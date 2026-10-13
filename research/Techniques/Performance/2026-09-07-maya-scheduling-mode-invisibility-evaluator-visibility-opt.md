---
source: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.pdf
found: 2026-09-07
category: performance
priority: 2
tags: [maya, performance, parallel-evaluation, scheduling-mode, visibility, evaluation-graph, optimization, cached-playback]
status: NEW
---

# Maya Scheduling Mode — Optimización Dinámica de Visibilidad sin Repartición (Maya 2023+/2026)

## Descripción
Scheduling Mode (también llamado "Invisibility Evaluator") es una funcionalidad introducida en Maya 2023 y refinada en los whitepapers de 2025/2026 que aplica optimizaciones de visibilidad dinámicamente sobre el Evaluation Graph (EG) existente, sin necesidad de una repartición completa. Cuando objetos del rig están fuera de cámara, hidden, o en LOD bajo, el evaluador suspende los nodos del EG que sólo alimentan esos objetos — ahorrando su tiempo de evaluación sin reconstruir el grafo. Especialmente potente en scenes con múltiples personajes donde 30-60% están fuera de cámara en cada frame.

## Fundamento matemático / técnico

### El problema: repartitioning cost

En Parallel Evaluation, cuando la visibilidad de un objeto cambia (show/hide), Maya normalmente necesita reparticionar: descartar el EG completo y reconstruirlo con sus clusters paralelos desde cero. En rigs complejos este proceso toma 200 ms – 2 s → freeze perceptible en viewport.

### Scheduling Mode: scheduling dinámico sin rebuild del EG

El EG se mantiene intacto. Los nodos adoptan estados dinámicos por frame:

```
Estados de un nodo en el EG:
  ACTIVE                 → se evalúa normalmente (CPU o GPU)
  INVISIBLE_SUSPENDED    → omitido este frame; output = "last valid value"
  GLOBALLY_SERIALIZE     → evaluado single-thread (expressions, Python nodes)
```

El `invisibilityEvaluator` corre una pre-pasada O(|EG|) antes de la evaluación del frame:

```
for each node N in EG (topological order):
    if all outputs of N only feed objects where .visibility = False:
        mark N as INVISIBLE_SUSPENDED
    else:
        mark N as ACTIVE

Coste de la pre-pasada: O(|EG nodes|) per frame
Coste típico: 1–5 ms en rigs de producción (400–1000 nodos en EG)
```

Si `.visibility` cambia frame-to-frame, el evaluador re-marca en el siguiente frame sin rebuild del EG.

### Ganancia de rendimiento (datos Autodesk 2025/2026 whitepaper)

| Escenario | Reducción tiempo evaluación |
|---|---|
| 4 personajes, 2 off-screen en promedio | 15–25% |
| 10 NPCs crowd, 60% off-screen en promedio | 30–40% |
| Hero character siempre on-screen | ~0% (overhead de pre-pasada: 1–5 ms) |

Interacción con las otras capas de optimización:
```
Scheduling Mode   → suspende nodos invisibles dinámicamente
GPU Override      → los nodos ACTIVE van a GPU normalmente
Cached Playback   → cachea los frames evaluados (estado ACTIVE)

Los tres son ortogonales y aditivos.
```

### ¿Qué bloquea Scheduling Mode?

**Blocker 1: `.visibility` driven por expression**
El evaluador no puede analizar el output de una expression estáticamente → mantiene el nodo ACTIVE aunque el objeto esté hidden.

```python
# PROBLEMA: expression que devuelve visibility
# expression: "pCube1.visibility = (ikfk_blend > 0.5) ? 1 : 0;"

# SOLUCIÓN: condition node (analizable estáticamente)
cond = cmds.createNode('condition')
cmds.setAttr(f'{cond}.operation', 2)  # greater than
cmds.connectAttr('ctrl.ikFkBlend', f'{cond}.firstTerm')
cmds.setAttr(f'{cond}.secondTerm', 0.5)
cmds.setAttr(f'{cond}.colorIfTrue', 1, 1, 1)
cmds.setAttr(f'{cond}.colorIfFalse', 0, 0, 0)
cmds.connectAttr(f'{cond}.outColorR', 'pCube1.visibility')
```

**Blocker 2: Nodos globally_serialized (Python MPxNode sin scheduling declaration)**
Interrumpen la pre-pasada de visibilidad — el evaluador no puede razonar sobre sus outputs.

**Blocker 3: `.visibility` animada (animCurve keyed en .visibility)**
El evaluador ve un animCurve → no puede saber el valor sin evaluarlo → mantiene ACTIVE.

```python
# SOLUCIÓN: IK/FK switch via attribute enum, no via keyed visibility
# En vez de keyear .visibility de ctrl_ik vs ctrl_fk:
cmds.addAttr('master_ctrl', longName='ikFkSwitch',
             attributeType='enum', enumName='IK:FK:', keyable=True)
# El blend_attr controla matrices de IK/FK, no .visibility directamente
```

## Implementación en Maya

### Activar Scheduling Mode

```python
import maya.cmds as cmds
import maya.mel as mel

# Verificar que Parallel Evaluation está activo
if cmds.evaluationManager(q=True, mode=True)[0] != 'parallel':
    cmds.evaluationManager(mode='parallel')

# Activar Scheduling Mode:
mel.eval('evaluationManager -schedulingMode "dynamicVisibility"')

# Verificar:
print(mel.eval('evaluationManager -q -schedulingMode'))  # → "dynamicVisibility"
```

### Audit de blockers de Scheduling Mode

```python
import maya.cmds as cmds

def audit_scheduling_mode_blockers(rig_root=None):
    """
    Identifica los tres tipos de blockers de Scheduling Mode.
    rig_root: transform raíz del rig (None = escena completa)
    """
    results = {
        'expression_driven_visibility': [],
        'animated_visibility': [],
        'globally_serialized_nodes': []
    }
    
    # 1. Visibilidades driven por expressions
    expressions = cmds.ls(type='expression') or []
    for expr in expressions:
        conns = cmds.listConnections(expr, destination=True, plugs=True) or []
        vis_conns = [c for c in conns if '.visibility' in c]
        if vis_conns:
            results['expression_driven_visibility'].append({
                'expression': expr,
                'drives_visibility': vis_conns
            })
    
    # 2. Visibilidad animada (animCurve -> .visibility)
    if rig_root:
        all_transforms = cmds.listRelatives(
            rig_root, allDescendants=True, type='transform') or []
    else:
        all_transforms = cmds.ls(type='transform') or []
    
    for node in all_transforms:
        vis_src = cmds.listConnections(
            f'{node}.visibility', source=True, type='animCurve') or []
        if vis_src:
            results['animated_visibility'].append({
                'node': node,
                'anim_curve': vis_src[0]
            })
    
    # Reporte
    total = sum(len(v) for v in results.values())
    print(f"\n=== Scheduling Mode Audit: {total} blockers ===")
    
    if results['expression_driven_visibility']:
        print(f"\n[CRITICAL] Expression-driven visibility: "
              f"{len(results['expression_driven_visibility'])} expressions")
        for item in results['expression_driven_visibility']:
            print(f"  - {item['expression']} -> {item['drives_visibility']}")
    
    if results['animated_visibility']:
        print(f"\n[MEDIUM] Animated visibility (keyed): "
              f"{len(results['animated_visibility'])} nodes")
        for item in results['animated_visibility'][:10]:
            print(f"  - {item['node']} (curve: {item['anim_curve']})")
    
    return results
```

## Comparación con autorig_tools

El IK/FK switch de autorig_tools probablemente usa visibilidad para mostrar/ocultar los controles IK vs FK — exactamente el `animated_visibility` blocker principal. Si el animador key-framea el IK/FK blend y eso conecta a `.visibility` de los controles, el evaluador lo ve como animado y no puede suspender ningún nodo relacionado. Convertir ese switch a un atributo enum en el master control (sin keyear .visibility directamente) resuelve el blocker y habilita Scheduling Mode para todo el personaje. El beneficio real es mayor en shots con múltiples personajes: en una escena de crowd o diálogo con 6 personajes, 2-3 siempre están parcialmente fuera de cámara.

## Aplicable directamente

YES — Dos acciones inmediatas: (1) Activar Scheduling Mode desde Evaluation Toolkit (1 click, sin cambio en el rig). (2) Ejecutar `audit_scheduling_mode_blockers(rig_root)` sobre un biped de producción — el sospechoso principal es el IK/FK visibility switch. Corregir los blockers identificados: 3-6h por rig. Resultado esperado en scenes con múltiples personajes: 15-30% de reducción del tiempo de evaluación por frame.

## Fuente
https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.pdf
https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2025/UsingParallelMaya.html
https://knowledge.autodesk.com/support/maya/learn-explore/caas/CloudHelp/cloudhelp/2020/ENU/Maya-Customizing/files/GUID-0FF1BA78-0493-463F-8E66-8014FB0F47BC-htm.html
https://www.riggingdojo.com/2022/12/21/optimizing-rigs-for-parallel-evaluation/
