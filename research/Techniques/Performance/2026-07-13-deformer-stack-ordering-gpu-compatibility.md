---
source: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html | https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82
found: 2026-07-13
category: performance
priority: 2
tags: [maya, rigging, performance, GPU, deformer-stack, skinCluster, blendShape, SC-order, parallel-evaluation, topology]
status: NEW
---

# Deformer Stack Ordering para GPU Override y Parallel Evaluation

## Descripcion
El orden de los deformers en el stack de Maya determina si la cadena de deformacion puede ejecutarse en GPU o fuerza una round-trip CPU. Las reglas no son intuitivas: colocar un blendShape ANTES del skinCluster (front-of-chain) o DESPUES cambia tanto el resultado visual como la compatibilidad GPU. Este archivo cubre las reglas de ordenacion optimas, el problema outMesh->inMesh, la pasarela blendShape, y patrones de topologia de conexion que minimizan el coste de evaluacion.

## Fundamento matematico / tecnico

### How Maya's Deformer Stack Works

Maya's deformation stack is a linked list of deformers connected through the `.inMesh`/`.outMesh` attributes of the shape node:

```
SHAPE NODE
  .inMesh  <-- deformer_N.outputGeometry[0]
                deformer_N.inputGeometry[0] <-- deformer_(N-1).outputGeometry[0]
                ...
                deformer_1.inputGeometry[0] <-- .inMeshOrig (rest position)
```

**Evaluation order:** Bottom-to-top. deformer_1 runs first, deformer_N runs last.
- deformer_1 = "front of chain" (FoC) -- operates on rest mesh
- deformer_N = last applied (closest to the visible shape)

**GPU cluster definition:** A consecutive sequence of GPU-capable deformers evaluates as one GPU cluster:
```
[skinCluster(GPU) -> blendShape(GPU) -> tweak(GPU)]  = ONE GPU cluster
[skinCluster(GPU) -> myCustomNode(CPU) -> blendShape(GPU)]  = TWO GPU clusters + CPU readback
```

### SC Order (Pre-Deformation vs Post-Deformation)

Maya blendShapes have two main positions in the stack:

**Pre-deformation (Front of Chain -- FoC):**
```
Stack (bottom to top):
  1. blendShape_corrective (FoC) -- operates on UNDEFORMED rest mesh
  2. skinCluster
  3. tweak (default, auto-created)
```
Used for: corrective shapes that ADD to the rest shape before skinning.
Example: "pre-sculpted shapes" that define the rest shape variation.

**Post-deformation:**
```
Stack (bottom to top):
  1. skinCluster
  2. blendShape_corrective (post)
  3. tweak
```
Used for: corrective shapes that FIX skinning artifacts AFTER skinning.
Example: elbow bulge correction on top of the skinned pose.

**GPU impact of ordering:**
```
Option A: [blendShape_FoC(GPU)] -> [skinCluster(GPU)] -> [tweak(GPU)]
  Result: ONE GPU cluster, optimal

Option B: [skinCluster(GPU)] -> [blendShape_post(GPU)] -> [tweak(GPU)]
  Result: ONE GPU cluster, also optimal (all GPU-capable in sequence)

Option C: [skinCluster(GPU)] -> [deltaMush_pre24(CPU)] -> [blendShape(GPU)]
  Result: TWO GPU clusters + CPU round-trip (4-10ms overhead)
  Fix: update to Maya 2024 (deltaMush now GPU) or move non-GPU node outside cluster
```

### The outMesh -> inMesh Anti-Pattern

**WORST case: connecting mesh outputs between mesh shapes:**
```
bodyMesh.outMesh -> warpMesh.inMesh
```

This creates a **shape-level dependency** that forces Maya to:
1. Evaluate bodyMesh's full deformation stack (GPU cluster)
2. **Read back from GPU to CPU** (forced by the shape-level connection)
3. Transfer to warpMesh.inMesh (on CPU)
4. Continue evaluation of warpMesh deformers (GPU cluster re-upload)

Cost: **4-10ms extra per frame**, regardless of how simple the warp operation is.

**Why this pattern exists:**
It's common for cloth rigs (nCloth output -> collision proxy), or multi-mesh rigs where body geometry wraps accessory geometry.

**Fix: Use blendShape as a passthrough:**
Instead of:
```
bodyMesh.outMesh -> accessoryMesh.inMesh
```
Use:
```
blendShape on accessoryMesh, with bodyMesh as TARGET at weight=1.0
-> accessoryMesh deforms by following bodyMesh via blendShape (GPU-safe)
```

```python
import maya.cmds as cmds

def replace_outmesh_with_blendshape(source_mesh, target_mesh):
    """
    Replace a direct outMesh->inMesh connection with a blendShape passthrough.
    Restores GPU cluster integrity.
    
    WARNING: blendShape requires IDENTICAL topology between source and target.
    For non-identical topology, use a wrap deformer or proximityWrap instead.
    """
    # Check topology match
    src_verts = cmds.polyEvaluate(source_mesh, v=True)
    tgt_verts = cmds.polyEvaluate(target_mesh, v=True)
    if src_verts != tgt_verts:
        raise ValueError(f"Topology mismatch: {source_mesh}={src_verts}, {target_mesh}={tgt_verts}")
    
    # Disconnect direct outMesh->inMesh if exists
    connections = cmds.listConnections(f'{target_mesh}.inMesh', plugs=True, source=True) or []
    for conn in connections:
        if 'outMesh' in conn or 'outputGeometry' in conn:
            cmds.disconnectAttr(conn, f'{target_mesh}.inMesh')
    
    # Create blendShape passthrough (weight=1.0, target=source_mesh)
    bs = cmds.blendShape(source_mesh, target_mesh, name=f'{target_mesh}_passthrough_bs',
                         weight=[0, 1.0], before=True)[0]
    
    print(f"Created blendShape passthrough: {bs}")
    print(f"Source: {source_mesh} -> Target: {target_mesh}")
    print("GPU cluster integrity restored for both meshes.")
    return bs
```

### Connection Topology Rules for Minimal Dirty Propagation

**Rule 1: Wide trees beat deep chains**
```
Bad (deep chain -- serial dirty propagation):
  ctrl_A -> ctrl_B -> ctrl_C -> ctrl_D -> joint_E -> deformer

Good (wide tree -- parallel evaluation possible):
  ctrl_A -> joint_1 -> deformer_1
  ctrl_A -> joint_2 -> deformer_2
  ctrl_A -> joint_3 -> deformer_3
```
The Evaluation Manager (EM) can schedule independent branches in parallel. A deep chain forces sequential evaluation at every step.

**Rule 2: Avoid implicit dependencies**
Implicit dependencies (e.g., `getAttr` in Python expressions that read from a node not in the DG connection) are invisible to the EM and cause full EG invalidation:
```python
# BAD: creates invisible implicit dependency
import maya.cmds as cmds
def bad_expression():
    val = cmds.getAttr('someNode.attr')  # EM can't see this dependency
    cmds.setAttr('otherNode.attr', val * 2)

# GOOD: explicit DG connection
md = cmds.createNode('multiplyDivide')
cmds.connectAttr('someNode.attr', f'{md}.input1X')
cmds.setAttr(f'{md}.input2X', 2.0)
cmds.connectAttr(f'{md}.outputX', 'otherNode.attr')
```

**Rule 3: blendWeighted vs multiplyDivide vs condition nodes**
```
blendWeighted:   DG-friendly, GPU-cluster transparent, use for additive blends
multiplyDivide:  DG-friendly, use for math operations
condition:       DG-friendly, use for if-else logic
unitConversion:  AVOID where possible -- added auto by Maya between some attr types
expression:      AVOID in production rigs -- always serializes downstream evaluation
```

**Rule 4: unitConversion nodes -- the silent performance killer**
Maya auto-inserts `unitConversion` nodes when connecting:
- float -> doubleAngle (e.g., driving rotateX from a float attribute)
- cm -> inches (unit mismatches)

Each unitConversion breaks the "clean DG attribute type" chain. In a facial rig with 100+ SDK correctives each driving rotateX from float attributes:
```
100 SDK curves -> 100 unitConversion nodes -> 100 rotateX attrs
Total unitConversion overhead: up to 760ms in one measured production facial rig
```
**Fix:** Use doubleAngle attributes on driver controls, or drive translate/scale (no conversion needed) instead of rotate for corrective activations:
```python
# Instead of:
cmds.addAttr(ctrl, ln='eyeOpen', min=0, max=1, dv=0)  # float
cmds.connectAttr(f'{ctrl}.eyeOpen', f'{eyelid_jnt}.rotateX')  # adds unitConversion!

# Use:
cmds.addAttr(ctrl, ln='eyeOpen', min=0, max=10, dv=0, at='doubleAngle')  # no conversion
cmds.connectAttr(f'{ctrl}.eyeOpen', f'{eyelid_jnt}.rotateX')  # direct, no unitConversion
```

### Deformer Ordering Audit

```python
import maya.cmds as cmds

def audit_deformer_stack(mesh):
    """
    Print the full deformer stack for a mesh with GPU status.
    Identifies non-GPU nodes that break GPU clusters.
    """
    GPU_TYPES = {
        'skinCluster', 'blendShape', 'cluster', 'ffd', 'nonLinear',
        'proximityWrap', 'tension', 'wire', 'tweak', 'softMod',
        'sculpt', 'solidify', 'deltaMush'
    }
    
    history = cmds.listHistory(mesh, pruneDagObjects=True, interestLevel=1) or []
    
    print(f"\nDeformer stack for {mesh}:")
    print("-" * 50)
    cluster_id = 1
    last_was_gpu = True
    
    for i, node in enumerate(reversed(history)):  # reversed = bottom-to-top
        node_type = cmds.nodeType(node)
        is_gpu = node_type in GPU_TYPES
        
        # Detect cluster breaks
        if i > 0 and not is_gpu and last_was_gpu:
            print(f"  *** GPU CLUSTER BREAK ***")
            cluster_id += 1
        
        status = f"[GPU cluster {cluster_id}]" if is_gpu else "[CPU-ONLY -- CLUSTER BREAK]"
        print(f"  {i+1}. {node} ({node_type}) {status}")
        last_was_gpu = is_gpu
    
    # Check for outMesh->inMesh anti-pattern
    in_mesh_sources = cmds.listConnections(f'{mesh}.inMesh', source=True, plugs=True) or []
    for src in in_mesh_sources:
        if 'outMesh' in src:
            print(f"\n  WARNING: Direct outMesh->inMesh connection from {src}")
            print(f"           This forces CPU readback! Replace with blendShape passthrough.")
    
    print("-" * 50)

def find_unit_conversion_nodes(scene=True):
    """Find all unitConversion nodes and their connected contexts."""
    uc_nodes = cmds.ls(type='unitConversion') or []
    print(f"unitConversion nodes in scene: {len(uc_nodes)}")
    for uc in uc_nodes:
        src = cmds.listConnections(f'{uc}.input', source=True, plugs=True) or []
        dst = cmds.listConnections(f'{uc}.output', destination=True, plugs=True) or []
        if src and dst:
            print(f"  {src[0]} -> [unitConversion] -> {dst[0]}")
    return uc_nodes
```

## Implementacion en Maya

**The three most important actions for deformer stack optimization:**

1. **Check for direct outMesh->inMesh (highest impact):**
```python
for mesh in cmds.ls(type='mesh', long=True):
    sources = cmds.listConnections(f'{mesh}.inMesh', source=True, plugs=True) or []
    for s in sources:
        if 'outMesh' in s:
            print(f"CRITICAL: {s} -> {mesh}.inMesh (GPU cluster break)")
```

2. **Identify non-GPU deformers in stack:**
```python
for mesh in cmds.ls(type='mesh', long=True):
    audit_deformer_stack(mesh)
```

3. **Count unitConversion nodes in facial rig context:**
```python
face_meshes = [m for m in cmds.ls(type='mesh') if 'face' in m.lower() or 'head' in m.lower()]
for fm in face_meshes:
    hist = cmds.listHistory(fm) or []
    uc_count = len([n for n in hist if cmds.nodeType(n) == 'unitConversion'])
    if uc_count > 10:
        print(f"WARNING: {fm} has {uc_count} unitConversion nodes in history")
```

## Comparacion con autorig_tools

El stack matrix-based de `autorig_tools` ya evita los GPU blockers mas comunes (constraints, distanceBetween). Este archivo cubre las reglas de ordenacion que afectan a la segunda capa: el propio stack de deformacion. La inspeccion de outMesh->inMesh es especialmente relevante en rigs con cloth proxy o accessory meshes. El problema de unitConversion en el rig facial (documentado en 2026-06-22) es el punto de mayor riesgo para el pipeline actual de Laia dado que el facial rig conecta muchos atributos float a rotaciones de joint.

## Aplicable directamente

YES -- funciones de auditoria inmediatamente aplicables:
1. **`audit_deformer_stack(mesh)` (30 min):** Correr sobre todos los meshes de produccion. Identificar cluster breaks.
2. **`find_unit_conversion_nodes()` (15 min):** Contar nodos en el rig facial. Si >20, priorizar la conversion de attrs float a doubleAngle.
3. **`replace_outmesh_with_blendshape()` (1h por conexion):** Para cada `outMesh->inMesh` directo encontrado, aplicar la sustitucion por blendShape passthrough.

## Fuente
- https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.html -- Using Parallel Maya 2026
- https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82 -- Deformation Layering in Maya's Parallel GPU World (Charles Wardlaw)
- Ver tambien: 2026-06-22 unitConversion nodes research, 2026-06-15 outMesh->inMesh (introduccion)
