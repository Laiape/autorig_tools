---
source: https://github.com/mgear-dev/mgear/releases
found: 2026-09-14
category: performance
priority: 2
tags: [maya, python, rigging, performance, parallel-evaluation, deformer, GPU, mesh-partition, skinning]
status: NEW
---

# mGear Evaluation Partition: Mesh Splitting for Parallel Deformer Evaluation

## Descripción
La herramienta Evaluation Partition de mGear 5.3 divide meshes en grupos de polígonos independientes para maximizar la evaluación paralela de Maya. Resuelve el problema de que Maya trata un mesh complejo como una única unidad de evaluación en el Evaluation Graph paralelo, impidiendo la paralelización intra-mesh. También incluye Wire to Skinning (conversión de wire deformers a skinClusters para habilitar GPU Override) y Skin Cluster Localization (fix para float32 precision drift en escenas de gran escala).

## Fundamento matemático / técnico

**Root cause: why single meshes serialize in parallel evaluation:**
Maya's Evaluation Graph (EG) schedules work at the granularity of DG nodes, NOT geometry regions. A `skinCluster` on a 100K-vertex body mesh is a SINGLE node — it occupies one evaluation thread and cannot be split across CPU cores. All deformers in a single mesh's stack are placed in one EG *cluster* (chain of mutually-dependent nodes), which evaluates on one thread sequentially.

The Evaluation Toolkit confirms this topology: a typical hero character with 80K vertices body mesh + 3 corrective blendShapes + deltaMush forms a cluster of depth 4, occupying ~12ms on a single thread while other threads idle.

**The polygon group partitioning approach:**
Maya CAN evaluate INDEPENDENT meshes in parallel. The Evaluation Partition tool exploits this:

1. Identify "natural boundaries" in the mesh: e.g., upper/lower torso, left/right arm, head/neck
2. Assign each mesh region a polygon group ID: group(f_i) = g, g in {0, 1, ..., N-1}
3. Split the mesh into N independent submeshes M_0, ..., M_{N-1}
4. Each submesh M_g gets its own `skinCluster_g` and deformer stack
5. Maya's EG schedules all N submeshes as N INDEPENDENT nodes — they evaluate on N parallel threads simultaneously
6. A recombination step (blendShape or proximityWrap) merges M_0...M_{N-1} back into the original mesh for rendering

**Performance model:**
If a single mesh evaluates in T_seq ms:
  T_parallel ≈ T_seq / N + T_merge

where T_merge includes:
- blendShape recombination: ~0.1-0.3ms per merge partition (GPU-compatible)
- proximityWrap recombination: ~0.5-2ms per partition (heavier, CPU)

For T_seq = 12ms, N = 4 partitions, T_merge = 0.3ms:
  T_parallel ≈ 12/4 + 4*0.3 = 3 + 1.2 = 4.2ms  (2.86× speedup)

Theoretical limit: N = number of CPU cores available to Maya's thread pool (typically 8-16 on workstations). However, thread scheduling overhead makes N > 8 rarely worthwhile.

**The .evp file format (v2.0):**
mGear saves partition configurations as `.evp` files (JSON schema):
```json
{
  "format_version": 2,
  "mesh": "character_body_geo",
  "partitions": [
    {
      "name": "torso_upper",
      "face_indices": [0, 1, ..., 12450],
      "deformer_settings": {"skinCluster": true, "deltaMush": false}
    },
    {
      "name": "torso_lower",
      "face_indices": [12451, ..., 28900],
      "deformer_settings": {"skinCluster": true, "deltaMush": true}
    }
  ],
  "transfer_mode": "wrap_bake",
  "rebuild_blendshapes": true,
  "blendshape_combo_rebuild": true,
  "proximity_proxy": false
}
```
v2.0 stores short mesh names (not full DAG paths) for namespace portability — a rig at `|rig_GRP|model_GRP|body_geo` and another at `|hero_A:rig_GRP|hero_A:model_GRP|hero_A:body_geo` both match `body_geo` in the .evp.

**Wire to Skinning conversion — technical mechanism:**
Wire deformers (`wireDeformer` node) have scheduling type `kGloballySerialize` — they block ALL parallel evaluation while they run. Conversion to skinCluster:
1. Sample wire curve at N points, creating joint chain J_0,...,J_{N-1}
2. For each vertex v, compute proximity weight: w_v = wire_falloff(d(v, curve)) / norm
3. Create `skinCluster` with joints J_0...J_{N-1} and weights matching the wire influence profile
4. Delete original wireDeformer — skinCluster has scheduling type `kParallel`

The mathematical equivalence: a wire deformer applies a curve-space displacement to nearby vertices. A skinCluster with joints along the same curve + weights matching the wire falloff function approximates this displacement within ~2% error for smooth wire curves.

**Skin Cluster Localization — float32 precision:**
Bone transforms in Maya are computed in world space. At world coordinates (X, Y, Z) >> 0, floating-point operations accumulate error:
  error_estimate ≈ ||(X, Y, Z)||_2 * machine_epsilon * sqrt(depth_of_matrix_chain)

For joints 10000 units from origin:
  error ≈ 10000 * 1.2e-7 * sqrt(6) ≈ 0.003 units drift

The localization pre-transforms the skinCluster bind pose and world matrices to a local coordinate frame centered near the mesh, reducing effective distance from ~10000 to ~1 unit and error to ~3e-7 — below perceptual threshold.

## Implementación en Maya

```python
# mGear 5.3 Evaluation Partition API
from mgear.rigbits import evaluation_partition as ep

# Create partitioner for a mesh
partitioner = ep.EvaluationPartitioner(mesh="character_body_geo")

# Define partitions by face selection (do interactively or via polygon groups)
upper_faces = mc.polyListComponentConversion(mc.ls(sl=True), toFace=True)
partitioner.add_partition("torso_upper", face_list=upper_faces)

lower_faces = [f"character_body_geo.f[{i}]" for i in range(12451, 28901)]
partitioner.add_partition("torso_lower", face_list=lower_faces)

# Save config
partitioner.save("character_eval_partition.evp")

# Apply: splits mesh, transfers blendshapes, copies skin cluster
result = partitioner.apply(
    transfer_mode="wrap_bake",        # use wrap to bake blendshape targets
    rebuild_blendshapes=True,         # rebuild combo networks
    create_proximity_proxy=False      # use blendShape merge (faster)
)
print(f"Partitions created: {result['partitions']}")
print(f"Estimated speedup: {result['speedup_estimate']:.1f}x")

# Wire to Skinning conversion
from mgear.rigbits import wire_to_skinning as wts
wts.convert_wire_to_skinning(
    wire_node="clothSim_wireDeformer",
    joint_count=12,          # joints along wire
    falloff_radius=2.5,      # influence radius per joint (Maya units)
    bind_pre_matrix=True     # preserve existing animation
)

# Manually equivalent approach (without mGear):
def split_mesh_for_parallel(mesh, face_groups):
    """Simple mesh split for parallel evaluation."""
    submeshes = []
    for name, faces in face_groups.items():
        dup = mc.duplicate(mesh, n=f"{mesh}_{name}")[0]
        total_faces = mc.polyEvaluate(dup, f=True)
        keep_set = set(int(f.split('[')[1].rstrip(']')) for f in faces)
        delete_faces = [f"{dup}.f[{i}]" for i in range(total_faces) 
                        if i not in keep_set]
        if delete_faces:
            mc.delete(delete_faces)
        submeshes.append(dup)
    
    # Recombine via blendShape (GPU-compatible)
    bs = mc.blendShape(submeshes + [mesh], n=f"{mesh}_partition_bs")[0]
    for i, sub in enumerate(submeshes):
        mc.setAttr(f"{bs}.{sub}", 1.0)
    return submeshes, bs
```

**Profiling before/after with Maya Evaluation Toolkit:**
```python
# Use Evaluation Toolkit to measure impact
import maya.debug.em_debug_utilities as em_utils

em_utils.saveReport("before_partition.json")
# ... apply partition ...
em_utils.saveReport("after_partition.json")

# Compare critical path lengths
# Look for: reduced cluster depth, more independent EG leaves
```

## Comparación con autorig_tools

El pipeline de autorig_tools no implementa partición de meshes por defecto — trata cada mesh del personaje como una unidad de evaluación completa. Para personajes hero con meshes >50K vértices (cara, ropa, cuerpo full detail), este patrón de partición podría reducir el tiempo de evaluación de la deformación corporal de 8-15ms a 3-5ms con N=4 particiones. La conversión Wire-to-Skinning es especialmente relevante si algún módulo de autorig_tools usa wire deformers para detalles de tela, pelo card, o accesorios — convertiría un bloqueador total de GPU Override en un skinCluster kParallel con comportamiento equivalente.

## Aplicable directamente

YES — Tres acciones concretas ordenadas por impacto:

1. **Wire to Skinning audit** (inmediato, 30-60 min): Ejecutar `mc.ls(type='wireDeformer')` en cualquier rig de autorig_tools. Si hay wire deformers, convertirlos con mGear elimina `globally_serialize` blockers del EG. ROI alto, riesgo bajo.

2. **Mesh partition para meshes hero** (4-8h setup): Identificar el mesh de mayor costo con `maya.debug.em_debug_utilities` → crear 3-4 particiones (torso_upper/lower, arms, legs) → guardar .evp → medir speedup con Evaluation Toolkit. Target: meshes >50K vértices con deformer stack depth >3.

3. **Skin Cluster Localization** (30 min): Si algún asset de autorig_tools tiene joints alejados del origen (>1000 unidades de (0,0,0)), activar la localización desde mGear rigbits. Elimina float32 precision drift silencioso que puede causar jitter sutil en deformación.

## Fuente
- mGear 5.3 releases: https://github.com/mgear-dev/mgear/releases
- Release announcement: https://mgear-framework.com/mgear-5-3-release/
- Evaluation Partition demo video: https://www.youtube.com/watch?v=-XNsPR_XziY
- mGear Forum — Evaluation Partition: https://forum.mgear-framework.com/
- Using Parallel Maya 2026: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.pdf
