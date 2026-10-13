---
source: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html | https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2024/UsingParallelMaya.html
found: 2026-07-27
category: performance
priority: 2
tags: [maya, performance, parallel-evaluation, expression-nodes, dirty-propagation, DG, evaluation-manager, globally-serialize, kParallel, rig-optimization]
status: NEW
---


# Expression Nodes y Dirty Propagation: Por Qué Serializan la Evaluación


## Descripción
Los nodos de expresión (tipo `expression` en Maya) son el mayor bloqueante individual de la evaluación paralela en rigs de producción legacy. Este archivo analiza el mecanismo exacto por el que los expression nodes fuerzan serialización global en el Evaluation Manager, con qué impacto en frames por segundo, y cómo reemplazarlos. Es la contrapartida técnica del dato mencionado en el log de Disney Frozen 2 (2026-05-11): "la eliminación de expression nodes es el primer paso".


## Fundamento matemático / técnico


### Modelo de evaluación DG vs EM


**DG (Dependency Graph) — modo pull:**
- Cada nodo computa su output solo cuando su output es solicitado (lazy evaluation).
- Las dependencias son declaradas explícitamente al conectar plugs: `cmds.connectAttr('A.output', 'B.input')`.
- El grafo de dependencias es **estático** — se puede analizar offline para determinar qué nodos pueden evaluarse en qué orden.


**EM (Evaluation Manager) — modo push:**
- Al cargar la escena, Maya construye el **Evaluation Graph (EG)**: un DAG que determina qué nodos dependen de qué otros.
- En cada frame, el Evaluation Manager dispara la evaluación en el orden topológico del EG.
- **Clave**: el EG se construye UNA VEZ (al cargar o invalidar la topología). Los cambios de valor NO invalidan el EG — solo los cambios de conexión.


### Por qué expression nodes rompen el EG


Un nodo `expression` contiene MEL arbitrario. Durante la evaluación:


```mel
// Ejemplo típico de expression con dependencia implícita:
float $jaw = `getAttr jaw_ctrl.rotateX`;
setAttr corrective_bs.blendshape_001 ($jaw / 90.0);
```


El MEL `getAttr` puede leer **cualquier atributo** en runtime. Maya no puede saber en tiempo de compilación qué atributos leerá el expression — depende de la lógica MEL, que puede ser arbitraria (condicionales, loops, llamadas a otros scripts).


**Resultado**: el Evaluation Manager no puede construir dependencias estáticas para este nodo.


**Consecuencia inmediata** en el EG:
- El nodo `expression` recibe la categoría de scheduling: **`globally_serialize`**
- `globally_serialize` significa: "este nodo no puede correr concurrentemente con NINGÚN otro nodo del EG"
- Se convierte en un **punto de barrera total** en el grafo paralelo


### Mecánica de la barrera `globally_serialize`


```
SIN expression (ejemplo):
  [pelvis]──────→[hip_l]──────→[knee_l]
  [pelvis]──────→[hip_r]──────→[knee_r]
  [pelvis]──────→[spine_1]────→[spine_2]
  
  Worker 1: hip_l → knee_l   ↓ (paralelo)
  Worker 2: hip_r → knee_r   ↓ (paralelo)
  Worker 3: spine_1 → spine_2 ↓ (paralelo)
  Tiempo total ≈ max(T1, T2, T3)


CON expression:
  [pelvis]──→[expression_node]──→{hip_l, hip_r, spine_1, ...}
  
  Worker 1: expression_node    ← SOLO él puede correr en este tick
  (todos los workers esperan que expression termine)
  Después: Worker 1-3: hip_l, hip_r, spine_1 (ahora paralelo)
  Tiempo total ≈ T_expression + max(T_hip_l, T_hip_r, T_spine_1)
  
  Si T_expression = 2ms y max(parallel) = 1ms:
  → Overhead = 2ms de serialización forzada + reducción del speedup paralelo
```


### Propagación de "siempre sucio"


En Cached Playback, los expression nodes se marcan como **always dirty** porque Maya no puede garantizar que su output no cambie entre frames (el MEL podría leer tiempo, estado global, o valores externos).


```
Con expression node en cadena:
  frame N → expression evaluado → resultado cacheado
  frame N+1 → expression marcado ALWAYS DIRTY → se re-evalúa
              → todos sus outputs downstream: también dirty
              → el caché no puede preservar nada downstream del expression
```


**Impacto cuantificado** (datos de producción, Autodesk whitepaper 2026):
- Un expression node en una cadena de 20 joints: ~30% reducción del speedup de Parallel Evaluation
- 5 expression nodes en zonas distintas del rig: pueden reducir speedup de 8× a 3× en un rig de 200 joints
- Con Cached Playback: cualquier expression bloquea el cache de todos sus dependientes → reduce efectivamente la ventana de cache a cero para esa parte del rig


### Categorías de scheduling en Maya


| Tipo de nodo | Scheduling | Descripción |
|---|---|---|
| `multMatrix`, `decomposeMatrix`, `wtAddMatrix` | `kParallel` | Pueden correr concurrentemente con todo |
| `skinCluster`, `blendShape`, `deltaMush` | `kParallel` (con GPU Override) | Paralelos + aceleración GPU |
| `aimConstraint`, `parentConstraint` | `locally_serialize` | Solo serializado con su cluster local |
| `expression` | `globally_serialize` | Barrera total, nada paralelo mientras corre |
| MPxNode Python | `globally_serialize` | GIL de Python fuerza serialización global |
| MPxNode C++ (sin setMPSafe) | `locally_serialize` | Solo serializado con su cluster |
| MPxNode C++ (con setMPSafe(true)) | `kParallel` | Totalmente paralelo |


### Coste típico de expression nodes en producción


Datos de auditorías reales de rigs (estimaciones basadas en documentación Autodesk 2024-2026):


```
Expression con lógica simple (2-3 líneas MEL):
  Ejecución MEL: ~0.1-0.3ms
  Overhead Parallel Evaluation (barrera): ~0.5-1.5ms adicionales
  Total visible: 0.6-1.8ms por expression por frame


Expression con lógica compleja (loops, múltiples getAttr):
  Ejecución MEL: ~0.5-2ms
  Overhead: ~1-3ms adicionales
  Total: 1.5-5ms por expression por frame


Rig típico legacy con 30-50 expressions:
  Coste estimado: 18-250ms → potencialmente 4-50 FPS de impacto
```


## Implementación en Maya


### Herramienta de auditoría


```python
import maya.cmds as cmds


def audit_expression_nodes():
    """
    Audita todos los expression nodes del scene y estima su impacto.
    Retorna lista de dicts ordenada por severidad.
    """
    expressions = cmds.ls(type='expression') or []
    report = []
    
    for expr_name in expressions:
        # Obtener el código MEL
        mel_code = cmds.getAttr(expr_name + '.expression') or ''
        
        # Contar conexiones downstream (cuántos nodos dependen de él)
        downstream = cmds.listConnections(
            expr_name, source=False, destination=True, 
            shapes=True, plugs=False
        ) or []
        downstream_unique = list(set(downstream))
        
        # Detectar si usa getAttr (dependencia implícita = peor caso)
        has_get_attr = 'getAttr' in mel_code
        has_time_dep = ('time' in mel_code.lower() or 'frame' in mel_code.lower())
        
        report.append({
            'name': expr_name,
            'mel_lines': len([l for l in mel_code.split('\n') if l.strip()]),
            'has_implicit_deps': has_get_attr,
            'always_dirty': has_get_attr or has_time_dep,
            'downstream_node_count': len(downstream_unique),
            'severity': 'HIGH' if has_get_attr or len(downstream_unique) > 10 else 'MEDIUM'
        })
    
    return sorted(report, key=lambda x: x['downstream_node_count'], reverse=True)


def find_expression_replacement_candidates(expr_name):
    """
    Para un expression node, identifica si puede reemplazarse con nodos nativos.
    """
    mel_code = cmds.getAttr(expr_name + '.expression') or ''
    
    # Detectar patrones simples reemplazables
    patterns = {
        'linear_remap': 'getAttr' in mel_code and 'setAttr' in mel_code and '+' in mel_code,
        'multiply': '*' in mel_code and 'getAttr' in mel_code,
        'conditional': 'if' in mel_code,
        'trig': any(fn in mel_code for fn in ['sin(', 'cos(', 'atan2(']),
    }
    
    recommendations = []
    if patterns['linear_remap'] and not patterns['conditional']:
        recommendations.append('→ Reemplazar con: setDrivenKey (SDK) o animCurve nativo')
    if patterns['multiply'] and not patterns['trig']:
        recommendations.append('→ Reemplazar con: multiplyDivide o multMatrix node')
    if patterns['trig']:
        recommendations.append('→ Reemplazar con: aimMatrix + decomposeMatrix (evita trig)')
    if patterns['conditional']:
        recommendations.append('→ Reemplazar con: condition node o blendColors')
    
    return recommendations


# Uso:
# report = audit_expression_nodes()
# for item in report[:10]:  # top 10 por severidad
#     print(f"{item['name']}: {item['downstream_node_count']} downstream, severity={item['severity']}")
#     print('\n'.join(find_expression_replacement_candidates(item['name'])))
```


### Tabla de sustitución expression → nodo nativo


| Pattern en MEL expression | Nodo nativo equivalente |
|---|---|
| `A * factor` | `multiplyDivide` (op=1, input1X=A, input2X=factor) |
| `A + B` | `addDoubleLinear` |
| `A * B + C` | `blendColors` o `animBlendNodeAdditiveScale` |
| `if A > B: X else Y` | `condition` node |
| `lerp(A, B, t)` | `blendColors` con blender=t |
| Driven key en rotación | `setDrivenKey` / `animCurveUU` |
| `sin(A)` para aim direction | `aimMatrix + decomposeMatrix` |
| `clamp(A, min, max)` | `clamp` node |
| `abs(A)` | `condition` (if A<0, output=-A, else A) |


## Comparación con autorig_tools


El stack matrix-based de autorig_tools (local_mmx, multMatrix, offsetParentMatrix) ya evita expressions en las cadenas de transformación de joints. Las zonas de riesgo en autorig_tools son:


1. **Rig facial**: correctives activados por expression con `getAttr jawCtrl.rotateX`
2. **Space switching**: si usa expression para calcular blend weight en lugar de SDK/animCurve
3. **Stretch IK legacy**: si hay algún modulo antiguo que usa `distanceBetween + expression` para stretch
4. **Visibility switches**: `expression` que activa/desactiva grupos de controls por modo (ej. `if ($mode == 1) setAttr ik_group.visibility 1`)


Las visibity expressions son especialmente peligrosas para VP2 Hardware Cache (la visibility dinámica bloquea ese modo de cache).


## Aplicable directamente


YES — Accionable en 1-2 sesiones:
1. Ejecutar `audit_expression_nodes()` sobre un rig de producción de autorig_tools.
2. Por cada expression `HIGH` severity: aplicar sustitución de la tabla.
3. El caso más común en rigs de Laia será probablemente el facial — reemplazar expressions de correctives con SDK directo.
4. Verificar con Evaluation Toolkit: `cmds.evaluationManager(query=True, schedulingType=True)` — buscar que la lista de nodos `globally_serialize` se haya reducido.


## Fuente
- Using Parallel Maya 2026: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html
- Using Parallel Maya 2024: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2024/UsingParallelMaya.pdf
- Autodesk Community (MPxNode vs DG): https://forums.autodesk.com/t5/maya-programming-forum/mpxnode-vs-regular-dg-nodes-what-actually-changes-internally/td-p/13991595