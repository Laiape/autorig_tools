---
source: "https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2026/MayaCachedPlaybackWhitePaper.pdf"
source_secondary: "https://help.autodesk.com/view/MAYAUL/2026/ENU/?guid=GUID-BC659D17-2C13-4FBE-B072-63406E99B1B8"
found_date: 2026-07-20
category: Performance/Caching
priority: 2
tags:
  - maya-performance
  - cached-playback
  - evaluation-cache
  - GPU-override
  - rig-topology
  - parallel-evaluation
  - maya-2026
  - autorig
status: NEW
---

# Maya 2026 Cached Playback -- Topology Tracking y Tres Modos de Cache

## Descripcion

Maya Cached Playback es el sistema que permite playback en tiempo real de animaciones complejas **almacenando en memoria los resultados de evaluacion** en lugar de re-evaluarlos cada frame. En Maya 2026 el sistema se refina con **dynamic GPU node reclamation** y tracking mas granular de topologia de dependencia.

Este archivo cubre la arquitectura completa del sistema, los tres modos de cache, como la topologia del rig afecta que cache es posible, y las implicaciones directas para diseno de rigs en autorig_tools.

## Fundamento matematico/tecnico

### El Evaluation Graph y el Caching Point

Maya Parallel Evaluation construye un **Evaluation Graph (EG)** -- un DAG donde los nodos son operaciones de evaluacion y las aristas son dependencias de datos. El EG se construye **una vez** al abrir la escena o al modificar conexiones (no cada frame).

El **Caching Point** es un nodo especial insertado en el EG despues del rig completo y antes del display stack. Su funcion:

1. **Frame fill**: durante la fase de llenado, evalua el rig normalmente y almacena el resultado del Caching Point en el Eval Cache.
2. **Playback**: si el Caching Point es valido, restaura los datos cacheados y **omite toda evaluacion upstream** -- el rig no se evalua.
3. **Invalidacion**: si detecta un cambio topologico (nueva conexion, eliminacion de nodo, cambio de atributo `message`), invalida el cache del frame actual y todos los posteriores.

```
[Rig Nodes] --> [Deformers] --> [Caching Point] --> [VP2 Cache] --> [Display]
                                       ^
                            Cache almacena aqui
```

**Lo critico**: el Caching Point invalida por **topologia**, no por valores. Un atributo numerico que cambia cada frame es OK -- el Caching Point lo captura en fill. Una conexion que se crea/destruye dinamicamente rompe el cache.

### Tres modos de cache

#### Modo 1: Evaluation Cache (default)

- **Que almacena**: los valores de los atributos de salida del Caching Point -- tipicamente las matrices world de los joints/transforms y los puntos de malla deformada.
- **Donde vive**: RAM del sistema (CPU memory).
- **Playback**: lee la malla + matrices desde RAM -> VP2 los renderiza. El overhead es la transferencia CPU->GPU por frame.
- **Invalidacion**: cambio topologico en el subgraph upstream del Caching Point.
- **Compatibilidad**: la mas amplia -- funciona con cualquier deformer/constraint que no anime topologia.

```
Frame N: rig evalua --> Caching Point guarda {vertex_positions, joint_matrices} --> RAM
Frame N (playback): RAM --> VP2 rasterizer --> pantalla (sin evaluacion del rig)
```

#### Modo 2: VP2 Hardware Cache

- **Que almacena**: los draw calls de VP2 **pre-renderizados** -- VBOs (Vertex Buffer Objects) en VRAM de la GPU.
- **Donde vive**: VRAM (GPU memory).
- **Playback**: zero CPU overhead -- VP2 solo hace swap de VBO activo. Es el modo **mas rapido** para playback.
- **Restricciones criticas** (cualquiera de estas lo desactiva automaticamente):
  - Topologia animada (vertex/edge/face count cambia por frame)
  - Visibilidad animada (`visibility` keyed)
  - Render layer overrides animados
  - Shader assignments que cambian por frame
  - Material overrides procedurales
- **Aplicabilidad a autorig_tools**: si el rig no usa ninguno de los anteriores -> VP2 Hardware Cache es alcanzable.

#### Modo 3: GPU Cache

- **Que almacena**: geometria deformada en GPU memory via Alembic GPU cache (`gpuCache` node) o a traves del GPU Override deformer cluster.
- **Diferencia**: el GPU Cache se llena con deformacion GPU (GPU Override debe estar activo); el Evaluation Cache puede co-existir con GPU Override pero almacena los resultados post-deformacion en CPU memory primero.
- **Memoria**: para geometria deformada en GPU Override, el cache en VRAM almacena el resultado **final** despues de toda la deformacion -- mismo footprint que el resultado, no la malla original.

### Topologia de rig y compatibilidad con cache

**Matrix-based rigs (multMatrix, decomposeMatrix, wtAddMatrix)** -- Cache-friendly:
- No animan topologia
- No tienen visibilidad animada
- Evaluacion determinista por frame -> Caching Point capta correctamente
- Compatible con VP2 Hardware Cache

**Nodos que bloquean o degradan el cache**:

| Nodo/Patron | Efecto en Cache |
|-------------|-----------------|
| `expression` con condicionales que crean/destruyen conexiones | Invalida Caching Point |
| `Python script node` con `mc.connectAttr()` inside | Invalida topologia |
| Animated `visibility` attribute | Bloquea VP2 Hardware Cache |
| `setDrivenKey` en visibility | Bloquea VP2 Hardware Cache |
| `switch` nodes que bypass deformers | Invalida topologia |
| Globally-serialize nodes en Parallel Eval | No bloquean cache pero si crean serializacion en fill phase |
| `ikHandle` + `ikSolver` (legacy) | Compatible con Eval Cache, puede no ser compatible con VP2 |

### Interaction con GPU Override

GPU Override y Cached Playback son **ortogonales y aditivos**:

```
Sin nada:      rig eval (CPU) -> deform (CPU) -> VP2 (GPU)       [baseline]
GPU Override:  rig eval (CPU) -> deform (GPU) -> VP2 (GPU)       [interactivity up]
Cache:         [cached] -> VP2 (GPU)                             [playback up]
GPU + Cache:   [GPU-cached] -> VP2 (GPU)                         [maximo speedup]
```

El modo GPU + Cache activo simultaneamente es el estado optimo: la fase de fill usa GPU Override para deformar rapido, y el playback reproduce desde VRAM sin re-deformar.

**Memory implication**: con GPU Override + VP2 Hardware Cache activos, la VRAM almacena:
- VBOs de la malla final deformada (todos los frames cacheados)
- Tamano = vertex_count * frame_count * bytes_per_vertex
- Para una malla de 50k verts, 240 frames, float3: ~50000 * 240 * 12B = ~144 MB

### Dynamic GPU Node Reclamation (Maya 2026)

Maya 2026 introduce reclamacion dinamica de nodos GPU del Evaluation Graph:
- Nodos que estaban marcados como `globally_serialize` en versiones anteriores por incompatibilidad GPU ahora se reclasifican dinamicamente si el sistema detecta que son seguros.
- Esto amplia el numero de nodos que pueden participar en GPU Override clusters sin modificar el plugin.
- Relevante si autorig_tools usa deformers de terceros que en Maya 2024/2025 bloqueaban GPU -- vale la pena re-testar en 2026.

### Dirty Propagation y Cache Invalidation

En Parallel Evaluation sin cache, cada frame propaga "dirty" por todo el EG. Con cache activo:

```
Frame N cached:
  Time change --> dirty propagates --> hits Caching Point
  Caching Point: "Tengo datos para frame N?"
    YES --> restore + skip upstream eval
    NO  --> propagate dirty upstream --> evaluate rig --> store at Caching Point
```

**La invalidacion de topologia** es mas costosa que la invalidacion por valor porque requiere **reconstruir el Evaluation Graph**, no solo marcar nodos dirty. Reconstruir el EG es O(nodos * aristas) y puede tomar decenas de ms en rigs complejos.

Por esto, cualquier nodo en autorig_tools que modifique conexiones dinamicamente (incluso en setup time, si ocurre despues de que el EG fue construido) puede causar **EG rebuild** que interrumpe el cache.

## Implementacion en Maya

### Verificar estado del cache

```python
import maya.cmds as mc

def check_cache_state():
    """Report current Cached Playback configuration."""
    cache_enabled = mc.evaluationManager(q=True, cachingPoints=True)
    cache_mode = mc.optionVar(q='cachedPlaybackMode') \
                 if mc.optionVar(exists='cachedPlaybackMode') else 'unknown'

    print(f"Caching enabled: {cache_enabled}")
    print(f"Cache mode: {cache_mode}")

    gpu_override = mc.evaluationManager(q=True, gpuOverride=True)
    print(f"GPU Override: {gpu_override}")

    return cache_enabled, cache_mode, gpu_override


def find_visibility_animated_nodes():
    """
    Find transforms with animated visibility -- these block VP2 Hardware Cache.
    """
    blockers = []
    all_transforms = mc.ls(type='transform')

    for node in all_transforms:
        vis_connections = mc.listConnections(
            node + '.visibility', source=True, destination=False, type='animCurve')
        if vis_connections:
            blockers.append(node)

        sdk_connections = mc.listConnections(
            node + '.visibility', source=True, destination=False,
            type='animBlendNodeAdditiveDA')
        if sdk_connections:
            blockers.append(node)

    return list(set(blockers))


def find_topology_animating_nodes():
    """
    Find nodes that could animate topology -- invalidate Caching Point.
    Returns dict of {node: reason}.
    """
    suspects = {}

    exprs = mc.ls(type='expression')
    for expr in exprs:
        expr_string = mc.expression(expr, q=True, string=True)
        if 'connectAttr' in expr_string or 'disconnectAttr' in expr_string:
            suspects[expr] = 'expression modifies connections'

    script_nodes = mc.ls(type='script')
    for sn in script_nodes:
        try:
            before = mc.scriptNode(sn, q=True, beforeScript=True) or ''
            after = mc.scriptNode(sn, q=True, afterScript=True) or ''
            if 'connectAttr' in before or 'connectAttr' in after:
                suspects[sn] = 'script node modifies connections'
        except Exception:
            pass

    return suspects


def audit_rig_for_cache_compatibility(rig_root):
    """
    Full audit of a rig for Cached Playback compatibility.
    rig_root: top-level transform of the rig
    """
    report = {
        'vp2_cache_blockers': [],
        'topology_risks': {},
        'globally_serialize_nodes': [],
        'recommendations': []
    }

    vis_blockers = find_visibility_animated_nodes()
    rig_nodes = set(mc.listRelatives(rig_root, allDescendents=True) or [])
    report['vp2_cache_blockers'] = [n for n in vis_blockers if n in rig_nodes]

    report['topology_risks'] = find_topology_animating_nodes()

    em_info = mc.evaluationManager(q=True, info=True) or []
    for info_line in em_info:
        if 'globally_serialize' in info_line:
            report['globally_serialize_nodes'].append(info_line)

    if report['vp2_cache_blockers']:
        report['recommendations'].append(
            f"Remove animation from .visibility on: {report['vp2_cache_blockers'][:3]}"
        )
    if not report['vp2_cache_blockers'] and not report['topology_risks']:
        report['recommendations'].append(
            "Rig is VP2 Hardware Cache compatible -- activate via Timeline menu or optionVar"
        )

    return report
```

### Activar Cached Playback por codigo

```python
def enable_cached_playback(mode='evaluationCache'):
    """
    Enable Cached Playback programmatically.
    mode: 'evaluationCache' | 'vp2HardwareCache'
    """
    valid_modes = ('evaluationCache', 'vp2HardwareCache')
    if mode not in valid_modes:
        raise ValueError(f"mode must be one of {valid_modes}")

    mc.evaluationManager(cachingPoints=True)
    mc.optionVar(sv=('cachedPlaybackMode', mode))

    print(f"Cached Playback enabled in {mode} mode.")
    print("Fill the cache by playing the timeline once end-to-end.")
```

## Comparacion con autorig_tools

| Aspecto | Estado actual | Con cache optimizado |
|---------|--------------|---------------------|
| Playback performance | Depende de complejidad de rig | VP2 Hardware Cache -> near-realtime independiente de rig |
| Visibility switching | Posiblemente keyed en algunos rigs | Requiere eliminar visibility keys para VP2 cache |
| Matrix nodes (multMatrix etc.) | Ya usados en autorig_tools | Cache-friendly by design |
| IK handles | Posiblemente en uso | Compatibles con Eval Cache, verificar VP2 |
| Expression nodes | Si los hay | Auditar si modifican conexiones |
| GPU Override + Cache | No configurado en setup | Activar en Preferences para maximo beneficio |

**Hallazgo clave**: autorig_tools usa matrix nodes como patron base -- este es exactamente el tipo de rig que mejor se beneficia del VP2 Hardware Cache. El riesgo principal son switches de visibilidad o expression nodes legacy.

## Aplicable directamente

### Inmediato (verificacion):
1. Ejecutar `audit_rig_for_cache_compatibility(rig_root)` sobre un rig de autorig_tools en Maya 2026 para identificar blockers de VP2 Hardware Cache.
2. Revisar si algun modulo de autorig_tools key-ea la visibilidad (`.visibility`) -- si es asi, reemplazar por un override de display layer o por attribute en un nodo control sin `.visibility` directamente.

### Corto plazo (configuracion):
3. Anadir a la documentacion de autorig_tools una nota de setup: activar GPU Override + Cached Playback en `evaluationCache` mode para sesiones de animacion -- activable desde el icono de reloj en el Time Slider sin cambiar el rig.
4. En builds de produccion, verificar que ningun setup script de autorig_tools ejecuta `mc.connectAttr()` despues de que el EG esta construido.

### Medio plazo (optimizacion de memoria):
5. Para personajes con mallas de mas de 100k vertices, calcular el footprint de VRAM del VP2 Hardware Cache: verts * frames * 12 bytes, y documentar limites recomendados de frame range para no agotar VRAM.

## Fuente

- **Whitepaper oficial 2026**: https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2026/MayaCachedPlaybackWhitePaper.pdf
- **Maya 2026 Help -- Cached Playback**: https://help.autodesk.com/view/MAYAUL/2026/ENU/?guid=GUID-BC659D17-2C13-4FBE-B072-63406E99B1B8
- **Archivos relacionados en esta libreria**:
  - `2026-05-18-maya-evaluation-toolkit-rig-profiling.md` -- Evaluation Graph, scheduling types, dirty propagation
  - `2026-06-08-ml-deformer-maya-2025-performance.md` -- GPU Override + ML Deformer interaction
