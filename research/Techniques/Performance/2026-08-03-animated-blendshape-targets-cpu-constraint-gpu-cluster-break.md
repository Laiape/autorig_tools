---
source: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html
found: 2026-08-03
category: performance
priority: 2
tags: [maya, performance, GPU, blendshape, parallel-evaluation, deformer-stack, CPU-GPU]
status: NEW
---


# Animated BlendShape Targets — CPU Constraint That Breaks GPU Clusters


## Descripción
Una regla crítica de rendimiento en Maya: cuando un blendShape tiene un target mesh que es una malla animada (live, en vivo), Maya fuerza TODO el cluster GPU upstream a caer a CPU. Este es uno de los fallos de GPU Override más comunes en rigs de producción y a menudo es invisible sin el deformerEvaluator command. Complementa el archivo de deformer stack ordering (2026-07-13) con el caso específico más frecuente y frecuentemente olvidado.


## Fundamento matemático / técnico


### El GPU Deformer Cluster


Maya's GPU Override groups compatible deformer chains into "GPU clusters" — sequences of nodes that can all run in OpenCL without CPU readback:


```
[skinCluster] → [blendShape] → [deltaMush] → [mesh]
       ↑                                        ↑
   GPU cluster start                     GPU cluster end
   (all evaluated in OpenCL, no CPU roundtrip)
```


A cluster break forces:
1. Current cluster → GPU → download to CPU (readback, ~0.3-2ms overhead)
2. Breaking node → CPU evaluation
3. Downstream cluster → CPU upload to GPU (upload overhead)
4. Downstream cluster → GPU evaluation


**Each cluster break costs ~0.5-4ms in I/O overhead PLUS any per-frame computation difference.**


### The Animated Target Constraint


**Condition that breaks GPU cluster:**
A blendShape node has a "live animated target" when:
- The target mesh (`blendShape.inputTarget[i].inputTargetGroup`) is connected from another mesh
- That source mesh has its own deformer stack (skinCluster, blendShape, etc.)
- OR: the target mesh is animated via geometry cache


**Why it breaks GPU:**
- GPU evaluation is purely feedforward: `undeformed → GPU kernel → deformed`
- If a blendShape target changes shape per-frame, it needs to be re-uploaded to GPU each frame
- Maya does NOT support live-target blendShapes in the GPU deformer pipeline (as of Maya 2026)


**deformerEvaluator command to diagnose:**
```python
import maya.cmds as cmds


# Find why a mesh's deformer chain is not GPU-eligible
def audit_gpu_blockers_detail(mesh):
    results = cmds.deformerEvaluator(mesh, query=True, verbose=True)
    if results:
        for line in results:
            if 'not supported' in line.lower() or 'fail' in line.lower():
                print(f"GPU BLOCKER: {line}")
    return results


# Check if blendShape has live targets
def find_live_blendshape_targets(mesh):
    deformers = cmds.listHistory(mesh, type='blendShape')
    live_targets = []
    for bs in (deformers or []):
        # Get all input targets
        targets = cmds.blendShape(bs, query=True, target=True) or []
        for t in targets:
            # Check if target geometry is connected (live)
            target_conn = cmds.listConnections(
                f'{bs}.inputTarget[0].inputTargetGroup[0].inputTargetItem[6000].inputGeomTarget',
                source=True, destination=False
            )
            if target_conn:
                live_targets.append((bs, t, target_conn[0]))
    return live_targets
```


### Common Patterns That Trigger This


**Pattern 1: Corrective driven by another rig mesh**
```
char_body_mesh:
  skinCluster → blendShape (target = corrective_shape_mesh)
                                         ↑
                           corrective_shape_mesh animated by another skinCluster
```
→ The corrective_shape_mesh has its own deformer stack → GPU cluster breaks.


**Pattern 2: Wrap deformer with animated cage**
```
cloth_mesh: 
  wrapDeformer (low-res cage = animated low_res_mesh)
               ↑
  low_res_mesh has skinCluster → GPU cluster breaks for cloth_mesh
```


**Pattern 3: Copy Deformed Position as Target**
Using `cmds.setAttr` to update target points per-frame → technically not a "live" connection, but the per-frame attribute changes can still prevent caching.


### Solutions


**Solution 1: Bake targets (static sculpts only)**
If the corrective target shape doesn't need to deform independently, freeze/bake it:
```python
# Convert live target to baked static target
bs_node = 'my_blendShape'
# Duplicate current shape as baked target
baked_target = cmds.duplicate('live_target_mesh', name='baked_target')[0]
# Remove skinCluster from baked_target
skin_on_target = cmds.listHistory(baked_target, type='skinCluster')
if skin_on_target:
    cmds.delete(skin_on_target)
# Update blendShape to use baked target
# (replace live connection with baked geometry)
```


**Solution 2: SDK/RBF weight driver (preferred)**
Instead of live target mesh, drive blendShape weights with SDK:
```python
# blendShape target is a static sculpt
# weight is driven by joint rotation (SDK/RBF)
cmds.setDrivenKeyframe(
    'corrective_blendShape.corrective_target',
    currentDriver='shoulder_joint.rotateZ',
    driverValue=0.0, value=0.0
)
cmds.setDrivenKeyframe(
    'corrective_blendShape.corrective_target',
    currentDriver='shoulder_joint.rotateZ',
    driverValue=90.0, value=1.0
)
# Result: static target mesh → weight varies → GPU cluster preserved
```


**Solution 3: Move corrective logic to pre-skin blendShape**
A pre-skin blendShape (Front of Chain) with a static target is evaluated before the skinCluster. Its output is GPU-compatible because the skinCluster sees static offsets.


### Maya 2024+ Improvement: Granular GPU Download


Since Maya 2024, when a single node in a cluster is CPU-only, Maya can now do a partial GPU download (just the affected mesh), do the CPU operation, and re-upload — rather than forcing the ENTIRE chain to CPU.


```
GPU cluster: [skinCluster] → GPU download → [CPU: live-target blendShape] → GPU upload → [GPU: deltaMush]
```


The overhead is still 0.5-2ms per cluster break, but it no longer contaminates the entire upstream chain.


### deformerEvaluator — Full Diagnostic Workflow


```python
def full_gpu_audit(mesh):
    """Complete GPU eligibility audit for a mesh's deformer chain."""
    print(f"=== GPU Audit: {mesh} ===")
    
    # 1. Check evaluation mode
    mode = cmds.evaluationManager(query=True, mode=True)[0]
    print(f"Evaluation mode: {mode}")
    
    # 2. Get deformerEvaluator report
    report = cmds.deformerEvaluator(mesh, query=True, verbose=True) or []
    for line in report:
        print(f"  {line}")
    
    # 3. List all deformers
    deformers = cmds.listHistory(mesh, pruneDagObjects=True, interestLevel=1)
    deformers = [d for d in deformers if cmds.objectType(d) in
                 ['skinCluster','blendShape','cluster','deltaMush','nonLinear','tweak']]
    
    print(f"\nDeformer chain ({len(deformers)} nodes):")
    for d in deformers:
        node_type = cmds.objectType(d)
        # Check for live connections
        if node_type == 'blendShape':
            in_targets = cmds.listConnections(d + '.inputTarget', source=True) or []
            flag = ' ← LIVE TARGETS' if in_targets else ''
            print(f"  [{node_type}] {d}{flag}")
        else:
            print(f"  [{node_type}] {d}")
```


## Implementación en Maya


**Recommended deformer stack order (GPU-safe):**
```
1. [blendShape FOC] - pre-skin, static targets only → GPU ✓
2. [skinCluster]  → GPU ✓
3. [blendShape POST] - correctives, SDK-driven weights, static targets → GPU ✓
4. [deltaMush] - Maya 2024+ GPU-compatible → GPU ✓
5. [tweak] - always CPU, but typically zero overhead
```


**Pattern that BREAKS GPU:**
```
1. [skinCluster] → GPU ✓
2. [blendShape POST] ← live animated target mesh → BREAKS GPU
3. [deltaMush] → forced to CPU due to break
```


## Comparación con autorig_tools


Este es el gotcha más frecuente en rigs de producción con correctives avanzados. El sistema de correctives de autorig_tools (RBF/SDK) probablemente tiene algunas situaciones donde se usan targets vivos (mallas animadas como correctives). Cada uno de estos rompe el cluster GPU. La regla de oro: **todos los targets de blendShape deben ser mallas estáticas; los pesos se drivean con SDK/RBF desde rotaciones de joints**. Si se necesita un target que varía (ej. morphTarget para LOD), se debe hacer como atributo weight animado, nunca como malla animada conectada al target slot.


## Aplicable directamente


**YES** — Ejecutar `full_gpu_audit(mesh)` sobre los meshes hero del próximo proyecto para identificar si algún corrective usa live targets. Corregir convirtiendo targets a sculpts estáticos + weight driven por SDK. Ganancia esperada: 2-10ms por frame si hay 3-5 live targets en la cadena.


## Fuente
- Using Parallel Maya 2026: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html
- deformerEvaluator command: https://help.autodesk.com/cloudhelp/2022/ENU/Maya-Tech-Docs/CommandsPython/deformerEvaluator.html
- Deformation Layering (Charles Wardlaw): https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82
- Cached Playback White Paper: https://damassets.autodesk.net/content/dam/autodesk/www/html/maya-cached-playback/2024/MayaCachedPlaybackWhitePaper.html