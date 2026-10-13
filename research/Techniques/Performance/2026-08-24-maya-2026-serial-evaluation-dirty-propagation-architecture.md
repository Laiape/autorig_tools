---
source: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.pdf
found: 2026-08-24
category: performance
priority: 2
tags: [maya, performance, evaluation-manager, serial-eval, dirty-propagation, 2026]
status: NEW
---

# Maya 2026 — Serial Evaluation Mode & the "No Dirty Propagation" EG Architecture

## Descripción
Maya 2026 introduce (o consolida) un cambio arquitectónico fundamental en el evaluation manager: **una vez construido el Evaluation Graph (EG), Maya deja de propagar dirty flags en cada frame**. En modo DG legacy, cada evaluación propaga dirty a downstream, lo cual era un porcentaje significativo del tiempo de frame en rigs complejos. En 2026, la EG cachea la topología de dependencias y las evaluaciones futuras siguen ese grafo sin re-marcar dirty hasta que la EG se invalide (topology change, connection change, etc). Aparece además el **Serial Evaluation mode** como puente de diagnóstico entre DG legacy y Parallel Evaluation — misma arquitectura no-dirty pero ejecución single-thread, útil para aislar bugs de scheduling vs bugs de multithreading.

## Fundamento matemático / técnico

### El problema del dirty-propagation legacy

En Maya DG clásico, evaluar `time.outTime → *` implicaba:
```
1. mark_dirty(time.outTime)
2. Recursión: para cada plug downstream, mark_dirty y propagar
3. En cada plug consultado (pull), verificar dirty y evaluar si es necesario
```
Costo por frame ≈ `O(N_edges)` de mark + `O(N_evaluated)` de compute. En rigs con 10k+ nodos y millones de edges, el paso 1-2 se comía frecuentemente 20-40% del frame budget.

### Nueva arquitectura: EG estático + forward evaluation

Fases:
1. **Discovery pass** (una vez, o al invalidar EG): Maya simula un "dry-run" de evaluación siguiendo mensajes de dirty. Construye un **directed graph** cuyos nodos son "evaluation units" (nodos DG o clusters) y cuyas aristas son dependencias entre ellos.
2. **Cluster detection:** si hay ciclos entre nodos DG, se colapsan en un cluster (unidad indivisible que se evalúa serialmente en su interior). Los clusters son la razón por la que un cycle warning suele bloquear parallel eval.
3. **Scheduling assignment:** cada nodo/cluster obtiene un scheduling type (`kParallel`, `kSerialize`, `kGloballySerialize`, `kUntrusted`). El scheduler los agrupa en batches paralelizables.
4. **Runtime forward eval:** cada frame, Maya recorre el EG hacia adelante sin verificar dirty por-plug. Solo lee inputs → evalúa → escribe outputs, en el orden topológico del EG.

**Ganancia:** eliminar completamente el overhead de mark_dirty por frame. Autodesk publica ejemplos donde el time.dirty propagation ocupaba 4-8ms por frame → 0ms en EG estática.

### Serial Evaluation mode — el modo de diagnóstico

Serial Evaluation Mode = arquitectura EG sin dirty propagation, PERO single-thread. Uso:
- **Debugging de bugs de multithreading:** si Parallel funciona mal pero Serial funciona bien → problema de scheduling. Si Serial también falla → problema arquitectónico o de expresiones dependientes de orden.
- **Detección de "hidden dependencies":** en Serial Eval hay un debug tool exclusivo que registra cuando un plug se evalúa sin que su dependencia esté declarada en la EG. Esto atrapa el bug más costoso de todos: nodos custom que hacen `getAttr` desde `compute()` sin haber declarado el input attr.
- **Comparación DG vs EG:** benchmark side-by-side para medir cuánto del speedup viene de "no dirty prop" vs "multithread".

### Scheduling types recap

| Tipo | Efecto en EG |
|------|------|
| `kParallel` | Puede correr en paralelo con hermanos independientes. Requiere que `compute()` sea thread-safe (`MPxNode::setMPSafe(true)`). |
| `kSerialize` | Nodos del mismo tipo se serializan entre sí, pero pueden correr en paralelo con otros tipos. |
| `kGloballySerialize` | Serializa contra TODO — barrera de scheduling. Los expression nodes tienen esto. |
| `kUntrusted` | Como `kGloballySerialize` + fuerza fallback a evaluación DG legacy en el subgrafo local. |

**Regla operativa 2026:** un nodo Python custom (`MPxNode` en Python) hereda `kGloballySerialize` por default porque el GIL de Python impide MP-safety. Solución conocida: reescribir en C++, o mejor, evitar custom nodes cuando un `multMatrix`+`decomposeMatrix` cubre el caso.

### Dynamic GPU Node Reclamation (Maya 2026 concreto)

Maya 2026 reclasifica dinámicamente nodos previamente `kGloballySerialize` a `kParallel` cuando el runtime confirma que su compute es thread-safe. Impacto directo: follicles y uvPin dejaron de bloquear la GPU deformer cluster en 2024, y en 2026 varios nodos de constraint también entran en el pool paralelo.

## Implementación en Maya

**Comandos y checks Python:**

```python
import maya.cmds as cmds
import maya.mel as mel

# Cambiar modo de evaluación
cmds.evaluationManager(mode='off')          # legacy DG
cmds.evaluationManager(mode='serial')       # Serial: EG sin dirty prop, single-thread
cmds.evaluationManager(mode='parallel')     # Parallel: EG sin dirty prop, multi-thread

# Query modo actual
mode = cmds.evaluationManager(query=True, mode=True)

# Debug tool en Serial mode: detecta plugs evaluados sin dep declarada
cmds.evaluationManager(invalidate=True)     # forzar rebuild del EG
cmds.dbtrace(keyword='eval', enable=True)   # trace evaluation events

# Inspeccionar clusters
mel.eval('evaluationManager -query -verbose;')
```

**Función de auditoría — detecta blockers de arquitectura EG:**

```python
def audit_eg_health(root=None):
    """
    Detecta nodos que fuerzan kGloballySerialize o rompen la EG estática.
    """
    report = {'blockers': [], 'clusters': [], 'expression_nodes': [], 'python_mpx': []}

    # 1. Expression nodes — kGloballySerialize forzoso
    for e in cmds.ls(type='expression'):
        report['expression_nodes'].append(e)

    # 2. Python MPxNode custom — heredan kGloballySerialize por GIL
    for t in cmds.pluginInfo(query=True, listPlugins=True) or []:
        # Iterate node types registered by python plugins → they force serialize
        try:
            info = cmds.pluginInfo(t, query=True, dependNode=True) or []
            for node_type in info:
                for n in cmds.ls(type=node_type):
                    report['python_mpx'].append((n, node_type, t))
        except: pass

    # 3. Clusters en el EG (cycles → EG force to cluster)
    try:
        info = mel.eval('evaluationManager -query -verbose;') or ''
        # Parse clusters from EM debug output (Maya 2020+)
        report['clusters'] = parse_clusters(info)
    except: pass

    # 4. Nodos con .visibility keyed — bloquea VP2 Hardware Cache
    for n in cmds.ls(dag=True, transforms=True):
        if cmds.keyframe(n + '.visibility', query=True, keyframeCount=True):
            report['blockers'].append((n, 'animated_visibility'))

    return report


def switch_to_serial_and_diagnose():
    """
    Cambia a Serial mode, invalida EG, deja el tracer activo por 30 frames.
    Recomendado para diagnosticar por qué un rig funciona en DG pero rompe en Parallel.
    """
    cmds.evaluationManager(mode='serial')
    cmds.evaluationManager(invalidate=True)
    cmds.dbtrace(keyword='eval', enable=True)
    for f in range(30):
        cmds.currentTime(f)
    cmds.dbtrace(keyword='eval', enable=False)
    print("Check the script editor for 'undeclared dependency' warnings.")
```

**Migración práctica de un rig legacy a EG 2026:**
1. Setear a Serial mode primero. Si el rig visualiza correcto en Serial, la EG está bien; el bug será de scheduling.
2. Activar `dbtrace(keyword='eval')` y reproducir 10 frames. Buscar warnings de "undeclared dependency" — cada uno es un nodo custom con `getAttr` implícito en `compute()`.
3. Fix cada warning: declarar el input attr en `MPxNode.initialize()` con `attributeAffects(input, output)`.
4. Cambiar a Parallel. Medir con Evaluation Toolkit.

## Comparación con autorig_tools
`autorig_tools` ya está diseñado matrix-based (multMatrix / decomposeMatrix / pickMatrix / offsetParentMatrix), lo cual es EG-friendly: todos son `kParallel` y no rompen la EG estática. Los riesgos residuales:
1. **Locators con `.visibility` keyed** en módulos IK/FK switch → bloquea VP2 Hardware Cache. `audit_eg_health()` lo detecta.
2. **Expression nodes** legacy en el rig facial (si quedaban de versiones antiguas) — cada uno es una barrera `kGloballySerialize`.
3. **Custom Python MPxNode** — si algún módulo escribió uno, hereda `kGloballySerialize`. Reescribir a C++ o descomponer en matrix nodes.

`audit_eg_health()` cubre las tres categorías en una llamada. Es integrable en el post-build health check junto con `audit_deformer_stack()` (2026-08-17), `audit_gpu_blockers()` (2026-07-06), y `audit_expression_nodes()` (2026-07-27).

## Aplicable directamente

**YES** — dos acciones inmediatas:

1. **Integrar `audit_eg_health()` en el health check** de post-build (`autorig_tools/qa/health_check.py`). Estimado: 2h.
2. **Añadir un modo "diagnostic build"** al UI: build → auto-switch a Serial → `dbtrace` 30 frames → reportar undeclared deps. Estimado: 3h.

**Impacto esperado:** cero regresiones en rigs bien construidos (matrix-based) y detección temprana de custom nodes / expressions residuales que rompen Parallel Eval en producción. Un solo expression node oculto en un rig facial puede costar 15-30ms/frame — detectarlo automáticamente en el health check ahorra debugging horas después.

**Nota Serial vs Parallel:** el paper del whitepaper 2026 sugiere que para desarrolladores de rigs, **Serial Mode es el nuevo modo por defecto durante desarrollo**, no DG legacy. Todos los tests de unit rigs de autorig_tools deberían correrse en Serial para detectar bugs de dependencia antes de que el rig llegue a producción en Parallel.

## Fuente
- Using Parallel Maya 2026 (whitepaper): https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.pdf
- HTML version: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html
- Cached Playback 2026 whitepaper: https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2026/MayaCachedPlaybackWhitePaper.pdf
- Related — **Cached Playback modes** (2026-07-20 en Drive) — VP2 HW Cache / Evaluation Cache / GPU Cache.
- Related — **Expression Nodes & Dirty Propagation** (2026-07-27 en Drive) — el offender clásico.
- Related — **MPxNode SchedulingType** (2026-08-17 en Drive) — cómo declarar `kParallel` en C++.
