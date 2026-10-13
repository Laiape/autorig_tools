---
source: https://github.com/electronicarts/dem-bones | https://www.ea.com/technology/news/seed-tech-gdc2021
found: 2026-06-15
category: tool
priority: 3
tags: [maya, python, skinning, SSDR, dem-bones, EA, electronicarts, deformation, animation-compression, open-source, github, C++]
status: NEW
---

# DEM Bones (Electronic Arts) — SSDR Production Implementation

## Descripción
DEM Bones es la implementación de producción del algoritmo SSDR (Smooth Skinning Decomposition with Rigid Bones) publicada por Electronic Arts como open source (BSD-3-Clause). Convierte animaciones de malla (Alembic, FBX) en rigs LBS con joints virtuales y skin weights optimizados, sin necesidad de un esqueleto previo. Desarrollada internamente en EA para comprimir animaciones de simulación de tela y crowd assets para motores de juegos en tiempo real. Tiene plugin para Maya y Houdini. Activa y mantenida (última actualización: 2024).

## Fundamento matemático / técnico

### Core Algorithm (SSDR — ver archivo 2026-06-15-ssdr)

DEM Bones implements the full SSDR formulation with EA-specific optimizations:

```
Input:  Animated mesh sequence (ABC/FBX) — T frames, V vertices
Output: B virtual bones with T×B rigid transforms + V×B weight matrix

Algorithm: Block Coordinate Descent
  Repeat until convergence:
    1. Fix W → solve for bone transforms via weighted SVD (O(B·T·V))
    2. Fix transforms → solve for weights via NNLS with sparsity (O(V·B²))
```

### EA Extensions to SSDR

DEM Bones adds several production-critical extensions:

**1. Bone init from existing skeleton (optional):**
```bash
# If you have a skeleton, initialize bones from it
# (rather than random/k-means init)
DemBones --initBonesByJoints joint_file.fbx animated.abc output.fbx
```

**2. Soft weight regularization:**
```
E_total = E_reconstruction + λ_smooth · E_smooth + λ_sparse · ||W||₀
```
Where `E_smooth` penalizes weight discontinuities between neighboring vertices (spatially smooth weights without manual smoothing).

**3. Configurable sparsity:**
```bash
--nTransIters 5   # iterations for transform solve
--nWeightsIters 3 # iterations for weight solve
--nnz 4           # non-zeros per vertex (max influences)
--patience 3      # early stop if error doesn't improve for N iters
```

**4. Lossless joint correspondence (if skeleton known):**
When given an existing skeleton, DEM Bones can constrain specific virtual bones to match existing joints exactly, making the output compatible with the original animation system.

---

### Command Line Interface

```bash
# Basic usage: convert alembic to LBS rig
DemBones --nBones 20 input_anim.abc output_rig.fbx

# Production usage with tuned parameters
DemBones \
  --nBones 30 \          # number of virtual bones
  --nInitIters 10 \      # initialization iterations
  --nIters 50 \          # main BCD iterations
  --nTransIters 5 \      # inner transform iterations
  --nWeightsIters 3 \    # inner weight iterations
  --nnz 4 \              # max 4 influences per vertex
  --patience 5 \         # convergence patience
  input_simulation.abc \
  output_skinned_rig.fbx

# With existing skeleton as bone initialization
DemBones \
  --nBones 0 \           # use skeleton bones only (no virtual bones)
  --initBonesByJoints \  # init from skeleton
  skeleton.fbx \
  input_simulation.abc \
  output_weights_only.fbx
```

---

### Maya Plugin Workflow

DEM Bones includes Maya Python scripts for integration:

```python
# DEM Bones Maya plugin workflow
import maya.cmds as cmds

# Step 1: Export animated mesh as Alembic
cmds.AbcExport(
    j=f'-frameRange 1 100 -file /tmp/sim_anim.abc '
      f'-root |nClothSim_geo'
)

# Step 2: Run DEM Bones (command line)
import subprocess
result = subprocess.run([
    '/path/to/DemBones',
    '--nBones', '20',
    '--nIters', '50', 
    '--nnz', '4',
    '/tmp/sim_anim.abc',
    '/tmp/demb_output.fbx'
], capture_output=True, text=True)

print(result.stdout)
if result.returncode != 0:
    print("ERROR:", result.stderr)

# Step 3: Import result back into Maya
cmds.file('/tmp/demb_output.fbx', i=True, 
          mergeNamespacesOnClash=False,
          namespace='demb')

# Step 4: Apply weights to original mesh if needed
# (FBX import creates new joints + skinCluster)
# Can manually transfer weights to existing skeleton using Maya's copy skin weights
```

---

### Use Cases in Production

| Scenario | DEM Bones Application |
|----------|----------------------|
| Cloth simulation → GPU skin | Convert nCloth/Qualoth sim to skinCluster (game-ready) |
| Crowd animation | Compress simulation to LBS for 1000s of crowd instances |
| Blend shape → LBS | Replace 50-blend-shape rig with 15-bone SSDR rig for performance |
| Skinning initialization | Use SSDR weights as starting point, refine manually |
| Animation compression | Convert 100-bone capture to 30-bone LBS for mobile |
| Secondary motion | Convert physics sim (hair, breasts) to LBS playback for RT |

---

### Integration with autorig_tools Pipeline

Proposed workflow for cloth/muscle assets:

```python
# autorig_tools integration: SSDR pre-skinning pass
import subprocess
import maya.cmds as cmds

def ssdr_preskin(source_mesh, sim_cache_abc, num_bones=20, max_influences=4):
    """
    Run DEM Bones on a simulation cache and import result.
    Use as first pass before manual weight painting.
    
    source_mesh: existing Maya mesh to apply weights to
    sim_cache_abc: path to Alembic simulation cache
    """
    import tempfile, os
    
    output_fbx = tempfile.mktemp(suffix='.fbx')
    
    # Run DEM Bones
    result = subprocess.run([
        'DemBones',
        '--nBones', str(num_bones),
        '--nIters', '50',
        '--nnz', str(max_influences),
        sim_cache_abc,
        output_fbx
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f'DEM Bones failed: {result.stderr}')
    
    # Import result
    cmds.file(output_fbx, i=True, namespace='demb')
    
    # Extract the generated joints and weights
    # (demb:joint_0, demb:joint_1, ... created by FBX import)
    demb_joints = cmds.ls('demb:joint_*', type='joint')
    demb_mesh = cmds.ls('demb:*', type='transform', dag=True)[0]
    demb_skin = cmds.ls(cmds.listHistory(demb_mesh), type='skinCluster')[0]
    
    # Transfer weights from demb_mesh to source_mesh
    # (requires compatible topology or closest-point transfer)
    cmds.select([demb_mesh, source_mesh])
    cmds.copySkinWeights(
        noMirror=True,
        surfaceAssociation='closestPoint',
        influenceAssociation=['name', 'closestJoint']
    )
    
    os.remove(output_fbx)
    print(f'SSDR preskin complete: {num_bones} bones, max {max_influences} influences')
    return demb_joints
```

## Comparación con autorig_tools

DEM Bones resuelve un problema que actualmente no tiene solución directa en autorig_tools: convertir animación de simulación en un rig LBS. Si el pipeline de Laia incluye simulaciones de tela, pelo, o músculo, DEM Bones es la herramienta que permite "rigificar" esas simulaciones para usarlas en tiempo real o en rigs de crowd. La comparación directa: dm2skin (ya en 2026-06-01) convierte delta-mush a pesos LBS desde poses estáticas; DEM Bones convierte secuencias de animación completas a LBS (más general, más robusto). Para producción VFX donde las simulaciones son la referencia de calidad, DEM Bones es el puente correcto entre el departamento de FX y el de rigging.

## Aplicable directamente

YES — DEM Bones tiene build para Linux/Mac/Win, plugin para Maya, y licencia BSD-3 (uso comercial libre). El workflow es: simulación → Alembic → DEM Bones → FBX → Maya skinCluster. La función `ssdr_preskin()` de arriba es directamente integrable en autorig_tools. Instalación estimada: 2-4h (compilar desde fuente o usar binarios precompilados del repo).

## Fuente
- GitHub: https://github.com/electronicarts/dem-bones
- EA Tech announcement: https://www.ea.com/technology/news/seed-tech-gdc2021
- SSDR paper (math base): http://graphics.cs.uh.edu/ble/papers/2012sa-ssdr/index.html
- Related: 2026-06-15-ssdr-smooth-skinning-decomposition-rigid-bones.md (math foundations)
