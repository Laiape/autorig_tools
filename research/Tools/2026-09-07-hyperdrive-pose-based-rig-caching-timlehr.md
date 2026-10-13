---
source: https://github.com/timlehr/hyperdrive
found: 2026-09-07
category: tool
priority: 3
tags: [maya, python, performance, caching, rig, pose-based, crowd, skinning, plugin, deformation]
status: NEW
---

# Hyperdrive — Pose-Based Rig Caching Plugin para Maya (timlehr, ~58 estrellas)

## Descripción
Hyperdrive (github.com/timlehr/hyperdrive, ~58 estrellas, activo agosto 2026) es un plugin Maya en Python que implementa caché de deformación basada en poses. En lugar de cachear por tiempo (frame N → geometría N), calcula un ID único de pose a partir de los valores de animación del rig y usa ese ID para recuperar la geometría pre-deformada. Si dos frames tienen la misma pose (e.g., un NPC que repite un ciclo de caminata), recupera del cache en lugar de re-evaluar la cadena de deformación completa. Complementa — no reemplaza — el Cached Playback de Maya.

## Fundamento matemático / técnico

### Pose ID: hash determinístico del estado del rig

```python
import hashlib, struct, maya.cmds as cmds

def compute_pose_id(joint_list, precision=4):
    """
    Calcula un hash MD5 del estado de pose cuantizado de los joints.
    precision=4 → tolerancia de ~0.0001 en cada componente de matrix.
    """
    values = []
    for jnt in joint_list:
        wm = cmds.getAttr(f'{jnt}.worldMatrix[0]')
        values.extend(wm)  # 16 floats por joint
    
    quantized = [round(v, precision) for v in values]
    packed = struct.pack(f'{len(quantized)}f', *quantized)
    return hashlib.md5(packed).hexdigest()

# Coste: O(N_joints x 16) flops + hash → <0.5 ms para 50 joints
```

### Cache lookup y escritura

```
Por frame:
  1. pose_id = hash(joint_worldMatrices)
  2. ¿pose_id en cache_dict?
     HIT  → copiar mesh_points[pose_id] → output  (~0.01-0.1 ms para 10k verts)
     MISS → evaluar deformer stack completo → guardar en cache_dict[pose_id]

cache_dict: { pose_id (str MD5) → np.ndarray(shape=(N_verts, 3), dtype=float32) }
```

### Cuándo funciona mejor (hit rate vs tipo de animación)

| Tipo de animación | Hit rate | Beneficio |
|---|---|---|
| NPC crowd con ciclo de 60 frames | 95–100% tras primer pase | Excelente |
| Idle animation en loop | 90–100% | Excelente |
| Hero character MoCap variado | 5–20% | Nulo o negativo |
| Personaje con SDK/RBF driven poses | 40–60% | Moderado |

Fórmula de break-even:
```
Beneficio (ms/frame) = hit_rate × deform_cost_ms − hash_cost_ms
Positivo si: hit_rate > hash_cost_ms / deform_cost_ms
             (típico: > 0.5 ms / 10 ms = 5% de hit rate)
```

### Diferencia fundamental vs Maya Cached Playback

```
Time-based cache (Maya Cached Playback):
  - Cachea: frame N → geometría N  (dependiente del tiempo)
  - Falla si: mismo NPC repite ciclo en frame 10 y frame 130 (evalúa dos veces)

Pose-based cache (Hyperdrive):
  - Cachea: pose_id → geometría  (tiempo-agnóstico)
  - Acierta si: misma pose aparece en cualquier frame, cualquier personaje
  
Los dos son ortogonales y se pueden activar simultáneamente.
```

### LRU cache para uso prolongado (limitación original: sin invalidation)

```python
from collections import OrderedDict
import numpy as np

class PoseCacheLRU:
    """Cache LRU con límite de tamaño en memoria."""
    
    def __init__(self, max_size_mb=500):
        self.max_bytes = max_size_mb * 1024 * 1024
        self._cache = OrderedDict()
        self._current_bytes = 0
    
    def get(self, pose_id):
        if pose_id not in self._cache:
            return None
        self._cache.move_to_end(pose_id)
        return self._cache[pose_id]
    
    def set(self, pose_id, mesh_points: np.ndarray):
        entry_bytes = mesh_points.nbytes
        while self._current_bytes + entry_bytes > self.max_bytes and self._cache:
            _, old = self._cache.popitem(last=False)
            self._current_bytes -= old.nbytes
        self._cache[pose_id] = mesh_points
        self._current_bytes += entry_bytes
    
    def stats(self):
        return {
            'entries': len(self._cache),
            'size_mb': self._current_bytes / (1024 * 1024)
        }
```

### Limitaciones documentadas (README de timlehr)

1. **Mejor con meshes pequeñas** — para mallas >50k verts, el overhead de cache write puede superar el beneficio en MISS frames.
2. **Sólo deformadores deterministas** — skinCluster, blendShape, deltaMush. No soporta nCloth ni simulaciones con estado interno.
3. **Sin invalidation automática** — el cache crece en memoria. Usar PoseCacheLRU (ver arriba) para producción.

## Implementación en Maya

```python
# Instalación:
# git clone https://github.com/timlehr/hyperdrive ~/.maya/modules/hyperdrive
# Añadir al Maya.env: MAYA_MODULE_PATH += ~/.maya/modules/hyperdrive

import hyperdrive

cache_node = hyperdrive.PoseCache(
    mesh='body_mesh',
    driver_joints=['root', 'hip', 'spine1', 'chest',
                   'shoulder_L', 'elbow_L', 'wrist_L',
                   'shoulder_R', 'elbow_R', 'wrist_R',
                   'hip_L', 'knee_L', 'ankle_L',
                   'hip_R', 'knee_R', 'ankle_R'],
    quantize_precision=3  # 3 decimales ≈ 0.001 rad de tolerancia angular
)
cache_node.enable()

# Diagnóstico de rendimiento:
def evaluate_hyperdrive_benefit(cache_node, n_frames=100):
    import maya.cmds as cmds, time
    stats = {'hits': 0, 'misses': 0, 'time_saved_ms': 0}
    for frame in range(n_frames):
        cmds.currentTime(frame)
        t0 = time.perf_counter()
        result = cache_node.evaluate()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if result.from_cache:
            stats['hits'] += 1
            stats['time_saved_ms'] += result.estimated_deform_cost_ms
        else:
            stats['misses'] += 1
    hit_rate = stats['hits'] / n_frames
    print(f"Hit rate:         {hit_rate*100:.1f}%")
    print(f"Time saved total: {stats['time_saved_ms']:.1f} ms")
    print(f"Time saved/frame: {stats['time_saved_ms']/n_frames:.2f} ms")
    return stats
```

## Comparación con autorig_tools

Hyperdrive complementa — no reemplaza — el Cached Playback de Maya. Para autorig_tools, el caso de uso más claro es **crowd**: si Laia construye rigs de crowd donde los agentes repiten ciclos de caminata/idle, Hyperdrive reduce el tiempo de deformación de coste lineal (N_agents × deform_time) a coste casi-cero para el ciclo estándar (sólo el primer pase completo evalúa la cadena). Para **hero characters** con MoCap variado: hit rate <10% → no instalar. La decisión debe basarse en `evaluate_hyperdrive_benefit()` sobre 100 frames de animación real del shot objetivo.

## Aplicable directamente

PARTIAL — Instalar y testear sólo en el contexto correcto. Pasos: (1) Identificar shots de autorig_tools con personajes con ciclos repetidos. (2) Instalar Hyperdrive sobre uno de esos personajes. (3) Ejecutar `evaluate_hyperdrive_benefit()` sobre 100 frames. Si hit rate >50% y mesh >5,000 vértices → beneficio real. Si hit rate <20% → no instalar. Tiempo de evaluación: 2-3h para setup, test y decisión.

## Fuente
https://github.com/timlehr/hyperdrive
https://timlehr.com/2019/04/hyperdrive-my-approach-to-pose-based-rig-caching-in-maya/
