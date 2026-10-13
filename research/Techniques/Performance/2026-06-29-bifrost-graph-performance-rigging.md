---
source: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=Bifrost_Performance_Overview
found: 2026-06-29
category: performance
priority: 2
tags: [maya, performance, bifrost, parallel-evaluation, GPU, deformation, rigging]
status: NEW
---

# Bifrost Graph — Características de Rendimiento para Rigging

## Descripción
Bifrost es el motor de grafo de compute visual de Maya, ejecutado en un sistema de evaluación separado del Dependency Graph clásico. Para rigging es relevante más allá de FX/simulación: Bifrost puede implementar deformadores custom (incluyendo skinning, correctivas, e incluso simulaciones tipo Cosserat/PBD para jiggle) sin escribir C++, y su modelo de evaluación tiene características de rendimiento muy distintas a los nodos DG nativos o a un `MPxNode` custom — relevante al decidir DÓNDE implementar una operación nueva en el pipeline.

## Fundamento matemático / técnico

### Modelo de evaluación: grafo de flujo de datos puro, no DG con dirty propagation
El DG clásico de Maya (incluso con Parallel Evaluation) sigue el modelo de dirty propagation: un nodo se reevalúa solo si sus inputs cambiaron, y el grafo completo de la escena se analiza para construir clusters de evaluación. Bifrost, en cambio, compila su grafo a un programa de flujo de datos que se **re-ejecuta completo cada vez que cualquier input cambia** (similar a un shader graph) — no hay dirty propagation parcial dentro de un grafo Bifrost individual. Esto tiene una consecuencia de rendimiento directa: un grafo Bifrost grande con una sola entrada animada se reevalúa entero cada frame, mientras que el equivalente en nodos DG nativos solo reevaluaría la rama afectada (gracias a dirty propagation + clusters de Parallel Evaluation).

```
DG con Parallel Evaluation:
  input cambia → solo se marca dirty el subgrafo downstream → solo esos nodos se reevalúan

Bifrost graph:
  input cambia → el compute graph completo se re-ejecuta (compilado como un único kernel/pipeline)
  → coste proporcional al TAMAÑO TOTAL del grafo, no al tamaño de la región afectada
```

**Implicación de diseño**: Bifrost es más eficiente para operaciones donde TODO el grafo necesita recomputar de todas formas en cada frame (simulación, deformación de malla completa por vértice), y menos eficiente que nodos DG nativos para grafos grandes donde solo una pequeña parte cambia por frame (un rig de control jerárquico típico, donde mover un dedo no debería tocar el cómputo de otro dedo).

### Paralelismo SIMD/multi-hilo nativo por diseño
A diferencia de un `MPxNode` (que requiere `MThreadPool` manual para paralelizar internamente, ver documento de threading TBB/OpenMP), las operaciones de Bifrost sobre arrays (`per-vertex`, `per-point`) se paralelizan automáticamente por el compilador del grafo: cada nodo que opera "por elemento" sobre un array de N puntos se vectoriza/threadea sin código adicional. Esto es comparable a cómo un GPU shader paraleliza por píxel/vértice automáticamente.

```
Nodo Bifrost "per-point: compute_deformation"
  → el compilador genera automáticamente:
     for (i = 0; i < N; i += SIMD_WIDTH) { ... vectorizado ... }
     repartido entre threads del pool TBB compartido con Maya
```

Esto hace de Bifrost una opción atractiva para deformadores custom de alto coste por vértice (correctivas geométricas complejas, simulación de strands) sin escribir C++ ni gestionar threading manualmente — el coste de desarrollo es mucho menor que un `MPxDeformerNode`, a cambio de perder el control fino de dirty propagation parcial.

### Independencia del DG — no bloquea ni es bloqueado por Evaluation Manager
Como Bifrost evalúa en su propio sistema, NO participa en los clusters de Parallel Evaluation del DG. Esto significa: un grafo Bifrost pesado no fuerza serialización del resto del rig (a diferencia de un nodo Python MPxNode, que SÍ degrada el scheduling del DG circundante por el GIL). Pero también significa que el coste de un grafo Bifrost no aparece en el Evaluation Toolkit/Profiler de la misma forma que los nodos DG — requiere su propio panel de diagnóstico (Bifrost Graph Editor → Performance/Profiling overlay) para medir coste real.

### Cuándo usar Bifrost vs nodos nativos vs MPxNode en rigging
| Caso | Mejor opción | Por qué |
|---|---|---|
| Operación matricial simple (multiplicar, componer transforms) | Nodos nativos (`multMatrix`, etc.) | Coste mínimo, dirty propagation parcial, Parallel Evaluation completo |
| Deformación custom por-vértice, coste alto, sin C++ disponible | Bifrost Graph | Paralelismo automático, no requiere compilar plugin |
| Deformación custom por-vértice, coste alto, con build C++ | `MPxDeformerNode` + `MThreadPool`/`MPxGPUDeformer` | Máximo control, integración completa con Evaluation Manager/GPU Override |
| Lógica de control simple, pocos huesos | Nodos nativos | Bifrost tiene overhead de grafo completo no justificado para cargas pequeñas |
| Simulación (jiggle, rods, cloth simple) | Bifrost Graph (strand/point simulation) | Motor de física ya integrado, corre en hilos propios |

## Implementación en Maya
Para exponer un grafo Bifrost como deformador en un rig:
```python
import maya.cmds as cmds

# Crear un grafo Bifrost y conectarlo como input/output de geometría
graph_node = cmds.createNode('bifrostGraphShape')
cmds.vnnCompound(graph_node, '/', addNode='per_vertex_deform_node')
# Conectar mesh de entrada/salida vía los puertos estándar del compound
cmds.connectAttr('inputMesh.outMesh', f'{graph_node}.input')
cmds.connectAttr(f'{graph_node}.output', 'outputMesh.inMesh')
```
Profiling: Bifrost Graph Editor tiene un overlay de "Execution Time" por nodo (Windows > Bifrost Graph Editor > View > Show Execution Time), análogo al Evaluation Toolkit pero específico del grafo Bifrost — necesario porque el Profiler estándar de Maya no descompone el coste interno de un grafo Bifrost, solo ve el nodo contenedor como una caja negra con un tiempo total.

## Comparación con autorig_tools
`autorig_tools` es matrix-based puro sobre nodos nativos (`wtAddMatrix`/`multMatrix`/`pickMatrix`/`composeMatrix`/`decomposeMatrix`) — la elección correcta para el control rig jerárquico (huesos, espacios, constraints), donde el dirty propagation parcial de nodos nativos es justamente la ventaja que se quiere conservar. Bifrost sería relevante SOLO si se añade una deformación de malla custom de alto coste (p.ej. una correctiva geométrica compleja, o el sistema de jiggle/Cosserat-rod descrito en los documentos de Math) y no se quiere/puede compilar un plugin C++ — en ese caso, Bifrost da paralelismo automático sin el coste de desarrollo de un `MPxDeformerNode`. No sustituye al control rig existente.

## Aplicable directamente
PARTIAL — herramienta a considerar para casos específicos, no un cambio de arquitectura:
1. Si se implementa el sistema de jiggle XPBD o el Cosserat rod (documentos de Math de esta semana) y se prefiere no escribir C++, prototipar primero en Bifrost Graph antes que en Python puro — el paralelismo automático por vértice puede dar mejor rendimiento en tiempo real que un loop Python equivalente.
2. Mantener el control rig (huesos, espacios, IK/FK) en nodos nativos — no migrar a Bifrost, perdería el dirty propagation parcial que ya funciona bien.
3. Si se evalúa Bifrost para algo, usar el overlay de Execution Time del Bifrost Graph Editor para medir coste real antes de comprometerse — el Evaluation Toolkit estándar no lo perfila correctamente.

## Fuente
- https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=Bifrost_Performance_Overview
- https://www.autodesk.com/products/bifrost/overview — overview general de Bifrost Graph
- Relacionado: `maya-parallel-evaluation-architecture.md`, `custom-mpxnode-parallel-evaluation.md`, archivo nuevo `maya-threading-internals-tbb-vs-openmp.md`
