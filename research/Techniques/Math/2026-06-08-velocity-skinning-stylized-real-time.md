---
source: https://arxiv.org/abs/2104.04934 | https://onlinelibrary.wiley.com/doi/abs/10.1111/cgf.142654 | https://velocityskinning.com/
found: 2026-06-08
category: math
priority: 1
tags: [maya, skinning, velocity, stylized-animation, squash-stretch, real-time, LBS, cartoon, secondary-motion, math]
status: NEW
---

# Velocity Skinning — Deformación Estilizada en Tiempo Real desde Velocidades Óseas

## Descripción
Velocity Skinning (Rohmer, Tarini, Kalyanasundaram, Moshfeghifar, Cani, Zordan — Computer Graphics Forum 2021, Vol. 40, No. 2, pp. 549-561) es una extensión de LBS/DQS que añade efectos de animación estilizados (squash-and-stretch, drag, follow-through) derivándolos automáticamente de las velocidades lineales y angulares de los huesos. Sin simulación física, sin integración temporal, sin rig adicional. Los efectos son controlables por el artista mediante mapas de peso pintados.

## Fundamento matemático / técnico

### Core Idea: Velocity as Deformation Driver

Standard LBS position at time t:
```
p_LBS(v, t) = Σ_i w_i(v) · T_i(t) · v_rest
```

Velocity Skinning adds a **velocity perturbation term**:
```
p_VS(v, t) = p_LBS(v, t) + Σ_i w_i(v) · s_i(v) · δ_vel(i, v, t)
```

where:
- `w_i(v)` = standard LBS weight (same weights reused, no new weight painting required)
- `s_i(v)` = per-vertex *stylization weight* for bone i (artist-painted, separate from LBS weights)
- `δ_vel(i, v, t)` = velocity-driven displacement for bone i at vertex v at time t

### Bone Velocity Computation

For each bone i, velocities are computed from **finite differences** of the skeleton state:

```
v_lin_i(t) = [pos_i(t) - pos_i(t-1)] / Δt        [linear velocity, world space, ℝ³]

ω_i(t) = [q_i(t) · q_i(t-1)^{-1}].log() / Δt     [angular velocity, quaternion log-map, ℝ³]
```

where:
- `pos_i(t)` = world position of bone i root at frame t
- `q_i(t)` = world rotation quaternion of bone i at frame t
- `.log()` = quaternion logarithm: log(q) = (θ/2)·n̂ where q = [cos(θ/2), sin(θ/2)·n̂]

**Angular velocity magnitude**: `||ω_i|| = θ/Δt` (radians per unit time)

### The Two Stylization Effects

#### Effect 1: Squashy (Squash-and-Stretch)

Driven by **angular velocity magnitude** ||ω_i||:
```
δ_squashy(i, v, t) = k_sq · ||ω_i(t)|| · (d_⊥(v, i) · n_⊥ - d_∥(v, i) · n_∥)
```
where:
- `d_∥` = signed distance from v to bone axis (along bone direction n̂_i)
- `d_⊥` = signed distance from v to bone axis (perpendicular to bone)
- `n_∥, n_⊥` = unit vectors along and perpendicular to bone
- `k_sq` = squashiness coefficient (global scale)

Interpretation: bone rotating fast → vertices near the bone **stretch along bone axis** and **squash perpendicular** (classic cartoon squash-and-stretch). Volume preservation is approximated by the ratio: if axis-scale = (1 + ||ω||·k), perpendicular-scale = 1/sqrt(1 + ||ω||·k).

#### Effect 2: Floppy (Drag / Follow-Through)

Driven by **linear velocity** v_lin_i:
```
δ_floppy(i, v, t) = -k_fl · w_i(v) · v_lin_i(t)
```

Interpretation: when a bone moves fast, vertices **lag behind** in the opposite direction of motion, creating follow-through / drag / jelly physics without simulation.

Signed by `w_i(v)` so that: vertices strongly influenced by bone i show more lag; vertices at the boundary (low weight) show less.

### Artist Controls

Per vertex, per bone, the artist paints:
1. **Squashiness weight** s_sq_i(v): how much this vertex responds to bone i's rotation speed
2. **Floppiness weight** s_fl_i(v): how much this vertex responds to bone i's linear speed

These are **independent** from LBS weights — they can be painted separately without affecting the base deformation. In practice:
- High squashiness at limb joints (elbows, knees) → dramatic squash on fast moves
- High floppiness at extremities (hair ends, antenna tips, tail) → natural secondary motion
- Zero weights → vertex behaves exactly like standard LBS (safe default)

### Runtime Properties

- **Single mesh pass**: one extra vertex computation after LBS (no iterative solver)
- **CPU time**: ~O(V × B) — same order as LBS
- **GPU-friendly**: all operations are local per-vertex, no global dependencies → maps to vertex shader
- **No temporal integration**: only reads v(t) and v(t-1) — no accumulation of state
- **No simulation**: deterministic, reproducible, no solver divergence

### Combination Formula (Full Velocity Skinning)

```
p_VS(v, t) = p_LBS(v, t)
           + Σ_i w_i(v) · s_sq_i(v) · δ_squashy(i, v, t)   [squash]
           + Σ_i w_i(v) · s_fl_i(v) · δ_floppy(i, v, t)    [floppy]
```

The two effects can be combined or used independently. Artists can also mix with DQS as the base instead of LBS.

## Implementación en Maya

Maya has no native Velocity Skinning node. Implementation options:

### Option A: Custom MPxDeformerNode (C++, production-quality)
```cpp
// Declare as kParallel for GPU-compatible parallel scheduling
MStatus DDMDeformer::setDependentsDirty(const MPlug& plug, MPlugArray& plugArray) {
    // Read: previous frame skeleton positions (need to store 1-frame cache)
    // Compute: linear + angular velocities per bone
    // Output: VS-perturbed vertex positions
}
```

### Option B: Python deformer (prototyping)
```python
import maya.cmds as cmds
import maya.api.OpenMaya as om
import numpy as np

class VelocitySkinningDeformer(om.MPxDeformerNode):
    def deform(self, data_block, geo_iter, local_to_world, geom_idx):
        # Get current frame skeleton
        current_poses = get_skeleton_world_transforms()  # all bone transforms T
        prev_poses = self.prev_frame_poses  # stored from last evaluation
        
        # Compute velocities
        dt = 1.0 / cmds.currentUnit(q=True, t=True)  # frame time
        lin_vels = [(p[1] - self.prev_frame_poses[i][1]) / dt 
                    for i, p in enumerate(current_poses)]
        ang_vels = [compute_angular_velocity(prev_poses[i][0], p[0], dt) 
                    for i, p in enumerate(current_poses)]
        
        # LBS is handled by skinCluster (upstream in deformer stack)
        # This deformer adds the VS perturbation on top
        while not geo_iter.isDone():
            v_idx = geo_iter.index()
            pos = geo_iter.position()
            
            delta = om.MVector(0, 0, 0)
            for b, bone in enumerate(bones):
                w = lbs_weights[v_idx][b]
                s_sq = squashy_weights[v_idx][b]
                s_fl = floppy_weights[v_idx][b]
                
                # Squashy contribution
                bone_axis = get_bone_axis(current_poses[b])
                ang_speed = np.linalg.norm(ang_vels[b])
                delta += w * s_sq * ang_speed * compute_squash_dir(pos, bone_axis)
                
                # Floppy contribution
                delta -= w * s_fl * om.MVector(*lin_vels[b])
            
            geo_iter.setPosition(pos + delta)
            geo_iter.next()
        
        self.prev_frame_poses = current_poses

def compute_angular_velocity(q_prev, q_curr, dt):
    """Quaternion finite-difference angular velocity."""
    q_delta = q_curr * q_prev.conjugate()
    # Quaternion log: log(q) = (θ/2) * axis
    angle = 2 * np.arccos(np.clip(q_delta.w, -1, 1))
    if abs(angle) < 1e-6:
        return np.zeros(3)
    axis = np.array([q_delta.x, q_delta.y, q_delta.z]) / np.sin(angle / 2)
    return axis * angle / dt
```

**Deformer stack placement**: VS node goes AFTER skinCluster (post-deformation), so it reads the LBS result and adds the velocity perturbation.

```
blendShape (pre) → skinCluster → VelocitySkinning → blendShape (post)
```

### Weight Painting
Per-vertex squashiness and floppiness weights are stored as custom geometry attribute arrays (`MFnMesh::createColorSetWithName` or custom float array attributes). A PySide2 paint tool can expose these maps.

## Comparación con autorig_tools

autorig_tools no implementa efectos estilizados de velocidad. El squash-and-stretch actual (si existe) probablemente es manual via SDK o controles del animador. Velocity Skinning añade squash/floppy *automático* basado en la velocidad del skeleton, sin trabajo adicional del animador — el efecto escala naturalmente con la velocidad de la animación. Para personajes estilizados, cartoon, o con elementos secundarios (colas, orejas largas, antenas), este sistema es un diferencial de calidad importante. Puede añadirse como post-deformador opcional en autorig_tools, activable/desactivable por personaje.

## Aplicable directamente

PARTIAL — Requiere MPxDeformerNode o deformer Python que lea el estado del frame anterior. Las dificultades:
1. **Frame caching**: el deformer necesita guardar las posiciones del frame t-1. Esto complica la integración con Cached Playback (que evalúa frames out-of-order).
2. **Weight painting**: necesitar una UI para pintar squashiness y floppiness por hueso es trabajo adicional.

**Plan recomendado**:
- Corto plazo: implementar prototipo Python (lento pero funcional) para validar el efecto visualmente
- Medio plazo: C++ MPxDeformerNode para velocidad y compatibilidad con parallel evaluation
- Largo plazo: integrar peso-painting en la UI PySide2 de autorig_tools

Los candidatos más directos para velocity skinning en personajes de Laia: cabello largo (floppiness alta), ropa suelta, y extremidades de criatura o cartoon.

## Fuente
- Preprint: https://arxiv.org/abs/2104.04934
- Publicación CGF: https://onlinelibrary.wiley.com/doi/abs/10.1111/cgf.142654
- Página del proyecto: https://velocityskinning.com/
- Institut Polytechnique de Paris: https://researchportal.ip-paris.fr/en/publications/velocity-skinning-for-real-time-stylized-skeletal-animation/
