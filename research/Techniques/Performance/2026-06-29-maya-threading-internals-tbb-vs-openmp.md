---
source: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-0FF1BA78-0493-463F-8E66-8014FB0F47BC
found: 2026-06-29
category: performance
priority: 2
tags: [maya, performance, threading, TBB, OpenMP, multithreading, parallel-evaluation, MThreadPool]
status: NEW
---

# Threading Interno de Maya — Intel TBB vs OpenMP y MThreadPool

## Descripción
Maya's Parallel Evaluation (documentado en `maya-parallel-evaluation-architecture.md`) decide QUÉ nodos pueden ejecutarse en paralelo, pero por debajo de eso hay una capa de threading real que determina CÓMO se reparten esos hilos sobre los cores de la CPU. Maya migró de OpenMP a Intel Threading Building Blocks (TBB) como su librería de threading interna — entender esta capa explica por qué mezclar plugins/deformadores que usan OpenMP con la Parallel Evaluation nativa de Maya puede degradar el rendimiento en vez de mejorarlo (thread oversubscription), un problema real al integrar plugins de terceros (dem-bones, RBF solvers compilados, etc.) en un pipeline que ya usa Evaluation Manager paralelo.

## Fundamento matemático / técnico

### Por qué Maya cambió de OpenMP a TBB
OpenMP usa un modelo de threads "fork-join" estático: cada región paralela (`#pragma omp parallel for`) crea/reutiliza un pool fijo de threads del tamaño configurado por `OMP_NUM_THREADS`. Si dos sistemas independientes dentro del mismo proceso usan OpenMP simultáneamente (p.ej. Maya's Evaluation Manager Y un plugin de deformación compilado con OpenMP), cada uno reserva SU PROPIO pool de N threads — con N cores físicos, esto produce 2N threads compitiendo por N cores: **thread oversubscription**. El sistema operativo hace context-switching constante entre threads que esperan turno, y el overhead de cambio de contexto puede hacer que el cómputo paralelo sea más lento que el secuencial.

TBB (usado por Maya desde ~2016 para Parallel Evaluation y Bifrost) usa un modelo de **task-based scheduling** con un único `tbb::task_scheduler` global por proceso: todas las tareas paralelas (de Maya Y de cualquier plugin que también use TBB) se reparten sobre el MISMO pool de worker threads, gestionado por un algoritmo de **work-stealing**: cada thread tiene su propia cola de tareas; cuando se queda sin trabajo, "roba" una tarea de la cola de otro thread en vez de esperar ocioso.

```
Work-stealing scheduler (TBB):
  Thread_i: cola_local = [task_a, task_b, task_c]
  Thread_j: cola_local = []  (vacía, sin trabajo)
  → Thread_j roba task_c del FONDO de la cola de Thread_i (LIFO local, FIFO para robos)
  → Garantiza balanceo de carga dinámico sin coordinación central costosa
```

Esto significa: si un plugin/deformador custom también usa TBB (y se linka contra LA MISMA versión de la librería que usa Maya, vía `MAYA_LOCATION/include/tbb`), sus tareas comparten el pool de threads de Maya de forma cooperativa — sin oversubscription. Si el plugin usa OpenMP (o crea sus propios `std::thread` manualmente), no coopera con el scheduler de Maya y compite por los mismos cores.

### MThreadPool — la API pública para escribir plugins thread-safe
Para deformadores/nodos custom en C++ que necesiten paralelismo interno (no solo participar en Parallel Evaluation a nivel de DG, sino paralelizar el cómputo DENTRO de un solo nodo, p.ej. recorrer miles de vértices), Maya expone `MThreadPool` (wrapper sobre TBB):

```cpp
// Patrón estándar de MThreadPool para paralelizar el loop de un deformador
void parallelDeformTask(void* data) {
    DeformTaskData* taskData = (DeformTaskData*)data;
    for (unsigned int i = taskData->start; i < taskData->end; i++) {
        // cómputo independiente por vértice — sin escritura compartida
        taskData->outPoints[i] = computeDeformedPosition(taskData->inPoints[i], ...);
    }
}

MStatus MyDeformer::deform(MDataBlock& block, MItGeometry& iter,
                            const MMatrix& mat, unsigned int multiIndex) {
    MThreadPool::init();
    const unsigned int numTasks = MThreadPool::getNumProcessors();
    // dividir el rango de vértices en numTasks bloques, lanzar con MThreadPool::newParallelRegion
    MThreadPool::newParallelRegion(createTasksAndExecute, &sharedData);
    MThreadPool::release();
    return MS::kSuccess;
}
```

**Regla crítica de coste-beneficio**: `MThreadPool::init()`/`release()` tienen overhead de sincronización (~microsegundos). Para deformadores que procesan pocos vértices (<~1000), el overhead de repartir el trabajo en tareas paralelas puede superar el ahorro — el threading interno de un nodo solo vale la pena con cargas de cómputo grandes por nodo (mallas densas, miles de vértices), no para joints/controles ligeros.

### GIL de Python como caso límite de "no cooperación"
A diferencia de OpenMP, el GIL de Python no es un sistema de threading que compita por cores — es un lock que serializa CUALQUIER ejecución de bytecode Python entre threads del mismo proceso. Esto ya está documentado en `custom-mpxnode-parallel-evaluation.md`: ningún nodo Python puede participar realmemente en Parallel Evaluation, independientemente de qué scheduling type se declare, porque el GIL bloquea a nivel de intérprete, no a nivel de scheduler de Maya.

### Bifrost como sistema separado
Bifrost Graph corre su propio motor de evaluación, también sobre TBB pero en un grafo de compute separado del DG de Maya — sus tareas comparten el pool de threads de Maya (cooperación correcta vía TBB) pero el grafo de Bifrost en sí no pasa por el Evaluation Manager / clusters de Parallel Evaluation. Esto significa que un grafo Bifrost pesado puede ejecutarse en paralelo con el resto de la escena sin entrar en conflicto de scheduling con el DG, pero también que no se beneficia directamente de las optimizaciones de Evaluation Toolkit pensadas para el DG (esas herramientas auditan nodos DG, no grafos Bifrost internamente).

## Implementación en Maya
Diagnóstico práctico de oversubscription: si un rig usa un plugin custom (p.ej. dem-bones para SSDR, o un solver RBF compilado) y el rendimiento en Parallel Evaluation es PEOR que en DG serial, sospechar de conflicto de threading:

```python
import maya.cmds as cmds

def check_thread_environment():
    """Diagnóstico simple: comparar threads activos en reposo vs durante playback."""
    import os
    print(f"OMP_NUM_THREADS env: {os.environ.get('OMP_NUM_THREADS', 'unset')}")
    print(f"Maya threads (idle):")
    # Comparar con un profiler de sistema (htop/Activity Monitor) durante playback
    # buscando un número de threads activos sustancialmente mayor que el número de cores físicos
    cmds.evaluationManager(query=True, threadCount=True)
```

Mitigación práctica si se detecta oversubscription por un plugin OpenMP:
```bash
# Limitar el pool de OpenMP del plugin de terceros para dejar margen al TBB de Maya
export OMP_NUM_THREADS=2   # en vez de el default (= num_cores), reservando cores para TBB
```
o, si se controla el código fuente del plugin, recompilarlo contra TBB en vez de OpenMP para que comparta el scheduler de Maya nativamente.

## Comparación con autorig_tools
`autorig_tools` es puramente Python (nodos `wtAddMatrix`/`multMatrix`/etc. son nodos nativos de Maya, no custom) — no hay riesgo directo de conflicto OpenMP/TBB porque no hay plugins C++ compilados en el pipeline propio. El riesgo aparece SOLO si se integran herramientas de terceros compiladas (dem-bones para SSDR, maya-math-nodes, o un futuro solver RBF en C++) — en ese caso vale la pena verificar contra qué librería de threading están compiladas antes de asumir que "más cores = más rápido" en Parallel Evaluation. Para nodos Python custom (si existieran), el GIL ya es la limitación dominante, documentada en el archivo existente de MPxNode.

## Aplicable directamente
PARTIAL — conocimiento de diagnóstico, no requiere cambios inmediatos:
1. Si se evalúa integrar dem-bones (ya documentado en Tools) u otro plugin C++ de terceros, comprobar su documentación/build para ver si usa OpenMP o TBB antes de medir su impacto en Parallel Evaluation.
2. Si se observa que activar Parallel Evaluation empeora el rendimiento con algún plugin de terceros instalado, usar `check_thread_environment()` o un profiler de sistema para descartar oversubscription antes de buscar otras causas.
3. No aplica a los nodos nativos de Maya usados en `local_mmx`/matrix-based rigging — esos ya están gestionados correctamente por el scheduler TBB de Maya.

## Fuente
- https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-0FF1BA78-0493-463F-8E66-8014FB0F47BC
- https://www.threadingbuildingblocks.org/ (Intel TBB documentation — work-stealing scheduler)
- Relacionado: archivos existentes `maya-parallel-evaluation-architecture.md`, `custom-mpxnode-parallel-evaluation.md`
