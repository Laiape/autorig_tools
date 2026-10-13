---
source: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2025/UsingParallelMaya.html | https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-0FF1BA78-0493-463F-8E66-8014FB0F47BC
found: 2026-05-25
category: performance
priority: 2
tags: [maya, performance, MPxNode, MPxDeformerNode, parallel-evaluation, scheduling, C++, Python, GIL, custom-nodes]
status: NEW
---

# Custom MPxNode Design for Parallel Evaluation — Scheduling Declarations & Python vs C++

## Descripción
Cuando autorig_tools necesita operaciones que los nodos nativos de Maya no cubren (deformadores custom, solvers de IK especiales, drivers de RBF no estándar), se implementan como `MPxNode` o `MPxDeformerNode`. La elección entre Python y C++, y cómo se declara el scheduling type del nodo, determina si el nodo puede participar en Parallel Evaluation o fuerza serialización de todo lo downstream. Este documento cubre los requisitos técnicos para escribir nodos custom compatibles con Parallel Evaluation.

## Fundamento matemático / técnico

### Why Python MPxNodes Cannot Be Parallel-Safe

The Python Global Interpreter Lock (GIL) prevents multiple Python threads from executing Python bytecode simultaneously. Since Maya's Parallel Evaluation uses multiple OS threads, and all Python-based MPxNodes share the GIL:

```
Thread 1: evaluating joint_chain_A → hits Python MPxNode → acquires GIL → blocks
Thread 2: evaluating joint_chain_B → also Python MPxNode → waits for GIL → stalls

Net result: Python MPxNodes serialize each other even if their DG branches
            are completely independent.
```

**Consequence:** A Python MPxNode forces `globally_serialize` or `locally_serialize` scheduling, eliminating the thread parallelism that Parallel Evaluation provides. Even if the node has no DG dependencies on anything else, its presence in the graph creates scheduling barriers.

**This includes:** Python-based `MPxDeformerNode`, Python `MPxNode` used as corrective drivers, Python `MPxIkSolverNode`.

---

### C++ MPxNode Scheduling Declarations

A C++ MPxNode must explicitly declare its scheduling type. Default if not declared: `locally_serialize` (conservative, not parallel).

**Scheduling types available (`MFnPlugin::registerNode` API):**

```cpp
// In plugin initialization:
MFnPlugin plugin(obj, "VendorName", "1.0", "Any");

plugin.registerNode(
    "myCustomNode",       // node type name
    MyCustomNode::id,     // unique MTypeId
    MyCustomNode::creator,
    MyCustomNode::initialize,
    MPxNode::kDependNode, // node type
    nullptr,              // classification
    MFnPlugin::kParallel  // ← scheduling type (KEY PARAMETER)
);
```

**Available scheduling constants:**

| Constant | Meaning | Use when |
|----------|---------|---------|
| `MFnPlugin::kParallel` | Can run concurrently with any other node | Node has no side effects, only reads from input plugs |
| `MFnPlugin::kSerial` | Must run serially within its evaluation cluster | Node reads from scene (not only from input plugs) |
| `MFnPlugin::kGlobal` | Forces serial across entire scene | Node modifies global scene state |
| `MFnPlugin::kUntrusted` | Not verified; Maya schedules last, serially | Legacy plugins, unknown safety |

**The `kParallel` contract:**
To safely declare `kParallel`, the node's `compute()` method must:
1. Read data ONLY from `MDataBlock` (the evaluation context — the safe, thread-local data store)
2. Write data ONLY to `MDataBlock` outputs
3. Never call `MGlobal::displayWarning/Error` or any scene-modifying Maya API
4. Never access `MDGModifier`, `MDagModifier`, or any object outside of `MDataBlock`

```cpp
MStatus MyParallelNode::compute(const MPlug& plug, MDataBlock& data) {
    // SAFE: reading from data block (thread-local)
    MDataHandle inputH = data.inputValue(aInput, &status);
    double inputVal = inputH.asDouble();
    
    // SAFE: computation using only local variables
    double result = inputVal * 2.0 + 3.5;
    
    // SAFE: writing to data block output
    MDataHandle outputH = data.outputValue(aOutput, &status);
    outputH.setDouble(result);
    data.setClean(plug);
    
    return MS::kSuccess;
    
    // UNSAFE (would require kSerial or kGlobal):
    // MGlobal::displayInfo("Computing...");    // ← scene access
    // MObject scene_node = MFnDependencyNode::create(...); // ← graph modification
    // cmds.setAttr("someNode.attr", val);     // ← never in compute()
}
```

---

### MPxDeformerNode and Parallel Evaluation

For custom deformers (`MPxDeformerNode` subclass), parallel scheduling is declared differently:

```cpp
// In plugin.registerNode, use kDeformerNode:
plugin.registerNode(
    "myCustomDeformer",
    MyDeformer::id,
    MyDeformer::creator,
    MyDeformer::initialize,
    MPxNode::kDeformerNode
    // Note: MPxDeformerNode has its own parallel mechanism via
    // the "setMPSafe" function below
);

// In MyDeformer::initialize():
MStatus MyDeformer::initialize() {
    // ... attribute setup ...
    MyDeformer::setMPSafe(true);  // ← declare parallel-safe
    return MS::kSuccess;
}
```

`setMPSafe(true)` tells Maya's Evaluation Manager that the deformer can safely be called from multiple threads for different geometry simultaneously (not the same geometry — each mesh is owned by one thread at a time).

**Custom GPU deformer (MPxGPUDeformer):**
```cpp
class MyGPUDeformer : public MPxGPUDeformer {
public:
    MPxGPUDeformer::DeformerStatus evaluate(
        MDataBlock& block,
        const MEvaluationNode& evaluationNode,
        const MPlug& outputGeom,
        const MPlugArray& inputGeomPlugs,
        const MGPUArray<float>& inputPositions,
        MGPUArray<float>& outputPositions) override;
};
// This runs on GPU — input/output are GPU arrays (VRAM)
```

---

### Python Workaround: Precompute and Bake

When a Python node is unavoidable (prototyping phase, no C++ build), minimize its impact:

```python
import maya.cmds as cmds
import maya.api.OpenMaya as om

class MyPythonNode(om.MPxNode):
    """
    Python MPxNode — CANNOT be kParallel due to GIL.
    Best practice: minimize what this node does at evaluation time.
    """
    
    kNodeName = "myPythonNode"
    kNodeId = om.MTypeId(0x00127350)
    
    aInput = om.MObject()
    aOutput = om.MObject()
    
    @classmethod
    def initialize(cls):
        nAttr = om.MFnNumericAttribute()
        cls.aInput  = nAttr.create("input",  "i",  om.MFnNumericData.kDouble, 0.0)
        cls.aOutput = nAttr.create("output", "o",  om.MFnNumericData.kDouble, 0.0)
        nAttr.writable = False  # output
        cls.addAttribute(cls.aInput)
        cls.addAttribute(cls.aOutput)
        cls.attributeAffects(cls.aInput, cls.aOutput)
    
    def compute(self, plug, dataBlock):
        if plug == MyPythonNode.aOutput:
            # MINIMAL compute — no scene access, no cmds, no om2 scene queries
            input_val = dataBlock.inputValue(MyPythonNode.aInput).asDouble()
            result = input_val * 2.0  # pure math only
            
            dataBlock.outputValue(MyPythonNode.aOutput).setDouble(result)
            dataBlock.setClean(plug)

def register_node():
    """Registration — scheduling will be locally_serialize (Python limitation)."""
    om.MFnPlugin(om.MGlobal.findPlug("message", False).node()).registerNode(
        MyPythonNode.kNodeName,
        MyPythonNode.kNodeId,
        lambda: MyPythonNode(),
        MyPythonNode.initialize
    )
```

**Production pattern for Python-to-parallel pipeline:**
```python
# Instead of computing in Python at runtime, precompute lookup tables at rig BUILD time
# and drive the rig with native Maya math nodes + the precomputed data.

# Example: Python RBF corrective driver → bake to SDK at rig publish
def bake_rbf_to_sdk(rbf_node, target_attr, sample_poses):
    """
    Convert Python RBF node to pure SDK (setDrivenKey) at rig publish.
    Result: no Python node in final published rig.
    """
    driver_attr = cmds.listConnections(f'{rbf_node}.inputPose', plugs=True)[0]
    
    for pose_value, output_value in sample_poses:
        cmds.setAttr(driver_attr.split('.')[0] + '.tx', pose_value)  # simplified
        cmds.setDrivenKeyframe(target_attr, currentDriver=driver_attr)
    
    # Remove Python RBF node — rig now drives via SDK only
    cmds.delete(rbf_node)
```

---

### Diagnosing Scheduling Type

```python
import maya.cmds as cmds

def audit_node_scheduling(scene=True):
    """Find all nodes and their scheduling types."""
    nodes = cmds.ls(dag=False) if scene else cmds.ls()
    results = []
    for n in nodes:
        try:
            sched = cmds.evaluationManager(query=True, schedulingType=n)
            node_type = cmds.nodeType(n)
            results.append((sched, node_type, n))
        except Exception:
            pass
    
    # Sort by worst scheduling first
    order = {'globally_serialize': 0, 'untrusted': 1,
             'locally_serialize': 2, 'parallel': 3}
    results.sort(key=lambda x: order.get(x[0], 99))
    
    print("=== Scheduling Audit ===")
    for sched, ntype, name in results[:30]:
        if sched in ('globally_serialize', 'untrusted'):
            print(f"  ⚠️  {sched:25s} | {ntype:30s} | {name}")
        elif sched == 'locally_serialize':
            print(f"  ℹ️  {sched:25s} | {ntype:30s} | {name}")
    return results
```

## Implementación en Maya

When building autorig_tools components that require custom logic:

**Decision tree:**
```
Need custom computation in the rig?
  ├─ Can it be done with native nodes? (multMatrix, condition, clamp, etc.)
  │   YES → Use native nodes (fastest, always parallel-safe)
  │
  ├─ Can it be expressed as a math expression?
  │   YES → Use maya-math-nodes plugin (C++, parallel-safe, expression builder)
  │
  ├─ Need truly custom logic?
  │   ├─ Python (prototype) → MPxNode, accept locally_serialize limitation
  │   │   → Plan to port to C++ before shipping
  │   │
  │   └─ C++ (production) → MPxNode with kParallel declaration
  │       → Deformer: MPxDeformerNode with setMPSafe(true)
  │       → GPU deformer: MPxGPUDeformer
```

## Comparación con autorig_tools

Si autorig_tools tiene algún nodo Python custom (RBF driver, helper joint solver, SDK corrective), este documento establece por qué esos nodos causan serialización y cómo mitigarlo. La estrategia más práctica a corto plazo: mantener Python en fase de prototipo y rig build, pero publicar el rig final sin nodos Python en tiempo real — usando baking a SDK, o usando el plugin `maya-math-nodes` (C++) para operaciones matemáticas complejas que de otro modo requerirían expresiones o Python.

## Aplicable directamente

PARTIAL — **Aplicable a medio plazo:**
1. **Ahora**: Auditar autorig_tools con `audit_node_scheduling()` para identificar si hay expresiones o nodos Python en los rigs publicados.
2. **Si hay expresiones**: reemplazar con nodos nativos o maya-math-nodes (ver `2026-05-18-maya-math-nodes-kalentchouk.md`).
3. **Futuro**: si se desarrolla un deformador custom en C++, usar `setMPSafe(true)` en el MPxDeformerNode y declarar `kParallel` en el registerNode para máxima compatibilidad con GPU Override.

## Fuente
- https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2025/UsingParallelMaya.html
- https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-0FF1BA78-0493-463F-8E66-8014FB0F47BC — Profiler interpretation
- https://forums.autodesk.com/t5/maya-ideas/parallel-evaluation-and-gpu-override-stability/idi-p/7976579
- https://download.autodesk.com/us/company/files/2018/UsingParallelMaya.html — Original parallel Maya whitepaper
