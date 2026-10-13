---
source: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html | https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2024/MayaCachedPlaybackWhitePaper.html
found: 2026-07-27
category: performance
priority: 2
tags: [maya, performance, parallel-evaluation, evaluation-graph, cluster-graph, dirty-propagation, topology, connection-topology, rig-optimization, kParallel, scheduling]
status: NEW
---


# Topología del Cluster Graph en Parallel Evaluation: Minimizando Re-evaluación


## Descripción
El Evaluation Manager de Maya construye un grafo de clusters (grupos de nodos que se evalúan juntos) a partir de la topología de conexiones del rig. La forma de ese grafo determina cuántos workers pueden correr en paralelo y cuánto tiempo queda "perdido" esperando nodos serialivos. Este archivo analiza las topologías óptimas vs subóptimas, las reglas de merging de clusters, y cómo diseñar el grafo de nodos de un rig para maximizar la paralelización — con código de diagnóstico concreto.


## Fundamento matemático / técnico


### Definición de Cluster en el Evaluation Graph


El Evaluation Manager construye el **Evaluation Graph (EG)** como un DAG donde:
- Cada **nodo EG** = un nodo DG de Maya o un grupo de nodos equivalente
- Cada **cluster** = un subgrafo conexo del EG donde todos los nodos tienen scheduling compatible (todos `kParallel`, o todos `locally_serialize`, etc.)
- Las **aristas de cluster** indican dependencias entre clusters (un cluster no puede comenzar hasta que todos sus predecesores hayan terminado)


### Regla de merging de clusters


Cuando dos clusters A y B están conectados por una arista en el EG:
1. Si A y B tienen scheduling **compatible** (ambos `kParallel`): se evalúan en parallel dentro del mismo tick, pero cada uno en su propio worker.
2. Si A o B contiene un nodo `globally_serialize`: los dos clusters se **fusionan en uno** (merge), creando un cluster serial más grande. Esto destruye el paralelismo potencial.


**Ejemplo crítico**: si un expression node (globally_serialize) conecta dos subgrafos kParallel, los tres (pre-expression, expression, post-expression) se funden en un único cluster serial enorme.


### Topología de cadena vs árbol (fan-out)


**Cadena lineal — PEOR CASO para paralelismo:**
```
A → B → C → D → E → F


Clusters:  [A]─[B]─[C]─[D]─[E]─[F]   (todos dependientes en secuencia)
Workers:   Solo 1 worker activo en cada paso
Tiempo:    T = T_A + T_B + T_C + T_D + T_E + T_F  (suma total, no máximo)
```


**Árbol de abanico — MEJOR CASO:**
```
         ┌→[B]→[D]
         ├→[C]→[E]
[A] ─────┤→[F]
         └→[G]→[H]→[I]


Clusters en paralelo después de A:
  Worker 1: B→D
  Worker 2: C→E
  Worker 3: F
  Worker 4: G→H→I   (el más lento)


Tiempo: T = T_A + max(T_B+T_D, T_C+T_E, T_F, T_G+T_H+T_I)
```


El speedup es determinado por el **camino crítico** (la ruta más larga del DAG de clusters). Reducir el camino crítico = reducir el tiempo total de frame.


### Reglas prácticas de diseño de topología


**Regla 1 — Evitar cadenas largas de dependencia:**
```
ANTES (cadena):
ctrl_root → offset_grp → joint_grp → joint_1 → joint_2 → joint_3 → ... → joint_N


DESPUÉS (aplanar):
ctrl_root → joint_1   (via multMatrix directo, sin grupos intermedios)
ctrl_root → joint_2
...
Todos los joints en paralelo, sin depender los unos de los otros.
```


**Regla 2 — Evitar "bottleneck" nodes que todos alimentan:**
```
PROBLEMA:
joint_1 ──┐
joint_2 ──┤
joint_3 ──┤─→ [globally_serialize expression] ─→ corrective_bs
joint_4 ──┘


Resultado: joint_1-4 corren en paralelo (OK), pero el expression detiene todo.


SOLUCIÓN:
Reemplazar expression con SDK (animCurve) para cada input individual:
joint_1 ─→ animCurveUU_1 ─→ corrective_bs.input[0]  (kParallel)
joint_2 ─→ animCurveUU_2 ─→ corrective_bs.input[1]  (kParallel)
```


**Regla 3 — Separar cadenas IK de cadenas FK:**
Las cadenas IK y FK de un mismo módulo son independientes entre sí hasta el blend. Si están conectadas a través de constraint nodes (`locally_serialize`), el scheduler puede fusionar clusters:


```
SUBÓPTIMO:
[fk_chain] ─→ [parentConstraint (locally_serialize)] ─→ [bind_joint]
                                                          ↑ forzado en mismo cluster


ÓPTIMO (matrix blend):
[fk_chain] ─┐
             ├─→ [wtAddMatrix (kParallel)] ─→ [decomposeMatrix (kParallel)] ─→ [bind_joint]
[ik_chain] ─┘
Resultado: fk_chain e ik_chain pueden correr completamente en paralelo
```


**Regla 4 — Ancho vs Profundidad del árbol:**


Para N nodos con W workers disponibles:
- Árbol balanceado (profundidad log₂(N), ancho N/2): speedup óptimo ~W
- Cadena lineal (profundidad N, ancho 1): speedup = 1 (no hay paralelismo)


Un biped típico:
```
ctrl_root → {
  pelvis_chain (depth 1-2),
  spine_chain (depth 3-5),
  arm_l_chain (depth 3-4, con IK/FK),
  arm_r_chain (depth 3-4),
  leg_l_chain (depth 4-5),
  leg_r_chain (depth 4-5),
  head_chain (depth 2)
}
→ 7 clusters en paralelo desde ctrl_root
→ Speedup potencial: ~7× con 8 workers (Intel i9 típico)
```


### Dirty propagation y el Caching Point


En Cached Playback, el **Caching Point** es el nodo donde Maya cachea el estado del frame. Todo lo ANTES del Caching Point se evalúa y guarda; en frames futuros, el evaluador salta directamente a ese punto si la topología no cambió.


**Qué invalida el Caching Point:**
1. Cambio en la **topología del EG** (conexión/desconexión de plugs)
2. Nodos marcados `always_dirty` (expressions, algunos MPxNode Python)
3. Cambio en visibility animada


**Qué NO invalida el Caching Point:**
- Cambio en valores de atributos (mover un control)
- Cambio en keyframe values


**Implicación para el diseño del rig:**
```
MAL: visibility animada en un transform node con hijos de skinCluster
→ El evaluador invalida el cache del skinCluster cada frame que cambia visibility


BIEN: visibility separada en un display layer (no en la cadena de evaluación)
→ El skinCluster puede ser cacheado independientemente
```


### Herramientas de diagnóstico


```python
import maya.cmds as cmds
import maya.debug.em_query as emq


def analyze_cluster_graph(verbose=False):
    """
    Analiza la topología del Evaluation Graph actual.
    Identifica bottlenecks y oportunidades de paralelismo.
    """
    # Activar Parallel Evaluation si no está activo
    current_mode = cmds.evaluationManager(query=True, mode=True)[0]
    if current_mode != 'parallel':
        cmds.evaluationManager(mode='parallel')
    
    report = {
        'globally_serialize': [],
        'locally_serialize': [],
        'kParallel': [],
        'cluster_count': 0
    }
    
    all_nodes = cmds.ls(dag=True, long=True) + cmds.ls(type=[
        'expression', 'constraint', 'multMatrix', 'decomposeMatrix',
        'skinCluster', 'blendShape', 'animCurve'
    ])
    
    for node in set(all_nodes):
        try:
            sched = cmds.getAttr(node + '.schedulingType') if cmds.attributeQuery(
                'schedulingType', node=node, exists=True) else None
        except:
            sched = None
        
        node_type = cmds.nodeType(node)
        
        if node_type == 'expression':
            report['globally_serialize'].append(node)
        elif node_type in ['parentConstraint', 'orientConstraint', 'aimConstraint']:
            report['locally_serialize'].append(node)
        elif node_type in ['multMatrix', 'decomposeMatrix', 'wtAddMatrix', 'skinCluster']:
            report['kParallel'].append(node)
    
    print(f"=== Cluster Graph Analysis ===")
    print(f"globally_serialize nodes: {len(report['globally_serialize'])}")
    print(f"  (expressions): {len([n for n in report['globally_serialize'] if cmds.nodeType(n) == 'expression'])}")
    print(f"  (Python MPxNode): {len([n for n in report['globally_serialize'] if cmds.nodeType(n) not in ['expression']])}")
    print(f"\nlocally_serialize nodes (constraints): {len(report['locally_serialize'])}")
    print(f"kParallel nodes (matrix): {len(report['kParallel'])}")
    
    if verbose:
        print(f"\nAll globally_serialize: {report['globally_serialize']}")
    
    # Caching Point compatibility check
    visibility_keyed = [
        n for n in cmds.ls(long=True)
        if cmds.listConnections(n + '.visibility', source=True, destination=False)
    ]
    
    if visibility_keyed:
        print(f"\n⚠ VP2 Hardware Cache BLOCKER: {len(visibility_keyed)} nodes with animated visibility")
        print(f"  → Will prevent VP2 Hardware Cache mode (use Evaluation Cache instead)")
    
    return report


def compute_critical_path_depth(start_node):
    """
    Calcula la profundidad del camino crítico desde start_node.
    Mayor profundidad = menos paralelismo potencial.
    """
    visited = {}
    
    def dfs(node):
        if node in visited:
            return visited[node]
        children = cmds.listConnections(node, source=False, destination=True, 
                                         skipConversionNodes=True) or []
        if not children:
            visited[node] = 0
            return 0
        depth = 1 + max(dfs(c) for c in children if c != node)
        visited[node] = depth
        return depth
    
    return dfs(start_node)


# Uso:
# report = analyze_cluster_graph()
# depth = compute_critical_path_depth('root_ctrl')
# print(f"Critical path depth from root_ctrl: {depth}")
```


### Benchmark de topología: datos de producción


Datos de Autodesk whitepaper 2026 + casos documentados:


| Rig type | Antes optimización | Después optimización | Speedup |
|---|---|---|---|
| Biped legacy (constraints) | 8-12ms/frame | 3-5ms/frame | 2.4-2.6× |
| Biped matrix-based | 3-5ms/frame | 1.5-2ms/frame | 2.0-2.5× |
| Facial rig (expressions) | 15-30ms/frame | 5-10ms/frame | 2.5-3.0× |
| Full character (body+face) | 25-50ms/frame | 8-18ms/frame | 2.3-2.9× |


*Notas: con Parallel Evaluation + GPU Override activos. Sin Cached Playback.*


Con Cached Playback correctamente configurado (sin blockers): 130fps+ para el mismo rig.


## Implementación en Maya


**Patrón óptimo de conexión para autorig_tools: "Star topology" desde controles:**


```python
import maya.cmds as cmds


def build_star_topology_module(ctrl, driven_joints, local_offset_matrices):
    """
    Conecta un control a N joints en topología de estrella (fan-out puro).
    Cada joint es independiente del resto → máximo paralelismo.
    
    ctrl: nombre del control (transform)
    driven_joints: lista de joints a drivear
    local_offset_matrices: lista de matrices 4x4 (offset de bind pose)
    """
    results = []
    
    for joint, offset_m in zip(driven_joints, local_offset_matrices):
        # multMatrix combina ctrl.worldMatrix con el offset → output es matriz local del joint
        mm = cmds.createNode('multMatrix', name=f'{joint}_mm')
        dc = cmds.createNode('decomposeMatrix', name=f'{joint}_dc')
        
        # Conectar: offset_local → ctrl.worldMatrix → joint.parentInverseMatrix
        cmds.setAttr(mm + '.matrixIn[0]', offset_m, type='matrix')
        cmds.connectAttr(ctrl + '.worldMatrix[0]', mm + '.matrixIn[1]')
        cmds.connectAttr(joint + '.parentInverseMatrix[0]', mm + '.matrixIn[2]')
        cmds.connectAttr(mm + '.matrixSum', dc + '.inputMatrix')
        
        # Resultado al joint
        cmds.connectAttr(dc + '.outputTranslate', joint + '.translate')
        cmds.connectAttr(dc + '.outputRotate', joint + '.rotate')
        
        results.append((mm, dc))
    
    # RESULTADO: ctrl → {joint_1, joint_2, ..., joint_N} 
    # Todos los joints en paralelo, sin dependencia entre sí
    return results
```


**Cómo verificar la topología creada:**
```python
# Después de build: verificar que no hay cadenas seriales no-intencionadas
depth = compute_critical_path_depth(ctrl)
print(f"Critical path depth: {depth}")  # Debe ser 1 para fan-out puro
```


## Comparación con autorig_tools


autorig_tools ya usa el patrón local_mmx (multMatrix + decomposeMatrix), lo que es óptimo para kParallel. Los puntos de riesgo de topología no-óptima son:


1. **Módulos heredados con parentConstraint**: si algún módulo aún usa constraints para space-switch, crea un cluster `locally_serialize` que interrumpe el fan-out de paralelismo.
2. **Grupos transform "de transporte"**: offset_grp → world_grp → deform_grp crean cadenas innecesarias de 3 nodos en vez de una sola multMatrix.
3. **La columna ribbon**: si los joints del ribbon dependen en cadena (ribbon_joint_1 → ribbon_joint_2 → ...) en vez de depender todos en paralelo del ribbon surface, el camino crítico es proporcional a N.
4. **Visibility animada**: si autorig_tools key-frame la visibilidad de módulos IK/FK según el blend, eso bloquea VP2 Hardware Cache.


## Aplicable directamente


YES — Ejecutar `analyze_cluster_graph()` sobre el rig más complejo de producción. Los findings típicos accionables en autorig_tools:
1. Contar constraints vs matrix nodes → si hay más de 10 `locally_serialize` constraints, planear migración a wtAddMatrix.
2. Identificar visibilities animadas → moverlas a display layers o usar `setAttr` en vez de keyframe.
3. Medir `compute_critical_path_depth('root_ctrl')` → si >8, hay cadenas seriales que se pueden aplanar.


## Fuente
- Using Parallel Maya 2026: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html
- Maya Cached Playback Whitepaper 2024: https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2024/MayaCachedPlaybackWhitePaper.html
- Charles Wardlaw "Deformation Layering in Maya's Parallel GPU World": https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82