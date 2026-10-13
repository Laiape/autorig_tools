---
source: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=Maya_SDK_Custom_evaluator_overview_Custom_Evaluator_API_html | https://around-the-corner.typepad.com/adn/2017/03/suggestions-best-practices-while-migrating-your-plugin-to-parallel-evaluation.html | https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.pdf
found: 2026-08-17
category: performance
priority: 2
tags: [maya, rigging, parallel-evaluation, MPxNode, scheduling, custom-node, OpenMaya, DG, performance]
status: NEW
---

# MPxNode::schedulingType — Custom Nodes en Parallel Evaluation

## Descripción
Cualquier plugin de Maya que implementa `MPxNode` tiene un impacto directo en cómo la Evaluation Manager (EM) puede paralelizar el rig. El método `schedulingType()` de MPxNode determina si el nodo puede evaluarse en paralelo con otros nodos, en serie, o como barrera global. Un solo nodo con el tipo equivocado puede serializar toda la evaluación del rig. Este archivo cubre los tipos de scheduling, sus consecuencias en el EG, y las best practices para C++ y Python API plugins en autorig_tools.

## Fundamento matemático / técnico

### Scheduling Types (MPxNode::SchedulingType enum)
```cpp
enum SchedulingType {
    kDefaultScheduling   = 0,  // Inherited from node type defaults
    kSerialize           = 1,  // This node runs alone in its cluster (safe default)
    kParallel            = 2,  // Can run concurrently with other kParallel nodes
    kGloballySerialize   = 3,  // Full barrier: ALL evaluation stops until this node finishes
    kUntrusted           = 4   // Treated as kGloballySerialize
};
```

### Impact on the Evaluation Graph (EG)

**kParallel** (ideal):
```
Thread 1: [nodeA] → [nodeC]
Thread 2: [nodeB] → [nodeD]   ← concurrent
Thread 3: [nodeE]              ← concurrent
```
All kParallel nodes in the EG that have no data dependency run simultaneously.

**kSerialize** (safe but limits throughput):
```
Thread 1: [nodeA]
               ↓ serialize barrier within cluster
Thread 1: [nodeB_serialized]
               ↓
Thread 1: [nodeC]
```
Nodes within the same cluster run sequentially if any is kSerialize. However, OTHER clusters can still run on other threads.

**kGloballySerialize** (worst case — full pipeline stall):
```
All threads → ██ WAIT ██ → [globally_serialized_node] → All threads resume
```
This creates a barrier across the entire Evaluation Graph. Every node that depends on the globally-serialized node is blocked. Every node that runs before it cannot overlap with nodes after it.

### Overhead Numbers
- `kGloballySerialize` node: adds 0.5–5ms overhead per frame (depending on how many threads are blocked)
- Expression nodes: always `kGloballySerialize` (cannot analyze MEL dependencies statically)
- Python MPxNode with no `schedulingType` override: defaults to `kSerialize`
- C++ MPxNode with no override: defaults to `kSerialize`

**A single kGloballySerialize node can negate all parallelism gains.**

### The setDependentsDirty Problem
If a custom node overrides `setDependentsDirty()` to manually manage dirty propagation:
```cpp
MStatus MyNode::setDependentsDirty(const MPlug&, MPlugArray&) {
    // Custom dirty logic
    return MS::kSuccess;
}
```
This prevents the EM from correctly building the Evaluation Graph — it cannot statically analyze which attributes depend on which. The EM may fall back to serializing the entire cluster containing this node.

**Fix**: Instead of `setDependentsDirty`, use `attributeAffects()` declarations in `initialize()`:
```cpp
MStatus MyNode::initialize() {
    // Declare all input→output dependencies statically
    attributeAffects(inputAttr, outputAttr);
    return MS::kSuccess;
}
```

### Thread Safety Requirements for kParallel
To safely declare `kParallel`, the node must:
1. **No global/static mutable state** — all computation is from input plug values only
2. **No Maya API calls that aren't thread-safe** (e.g., `MGlobal::setActiveSelectionList` is not thread-safe)
3. **Use thread-local storage** for any temporary computation buffers
4. **No output writes to non-owned plugs** during `compute()`

## Implementación en Maya

### C++ MPxNode — Declaring Parallel-Safe
```cpp
#include <maya/MPxNode.h>

class MyRigNode : public MPxNode {
public:
    static MTypeId id;
    
    // Override to declare parallel-safe scheduling
    virtual MPxNode::SchedulingType schedulingType() const override {
        return MPxNode::kParallel;
    }
    
    // All dependencies declared statically
    static MStatus initialize() {
        // inputAttr and outputAttr are MObject members
        attributeAffects(inputAttr, outputAttr);
        return MS::kSuccess;
    }
    
    MStatus compute(const MPlug& plug, MDataBlock& data) override {
        // Thread-safe: only reads from data, writes to data
        // No static state, no MGlobal calls
        MDataHandle inputH = data.inputValue(inputAttr);
        MDataHandle outputH = data.outputValue(outputAttr);
        // ... computation ...
        outputH.setFloat(result);
        data.setClean(plug);
        return MS::kSuccess;
    }
};
```

### Python MPxNode — Scheduling Type
```python
import maya.api.OpenMaya as om2

class MyRigNode(om2.MPxNode):
    kNodeId = om2.MTypeId(0x00127890)
    
    @classmethod
    def creator(cls):
        return cls()
    
    @classmethod
    def initialize(cls):
        # Declare attribute dependencies
        om2.MPxNode.attributeAffects(MyRigNode.inputAttr, MyRigNode.outputAttr)
    
    def schedulingType(self):
        # Python nodes should return kSerialize at minimum
        # kParallel only if thread-safe (Python GIL helps but not sufficient alone)
        return om2.MPxNode.kSerialize
    
    def compute(self, plug, dataBlock):
        if plug == MyRigNode.outputAttr:
            inputVal = dataBlock.inputValue(MyRigNode.inputAttr).asFloat()
            outputH = dataBlock.outputValue(MyRigNode.outputAttr)
            outputH.setFloat(inputVal * 2.0)
            dataBlock.setClean(plug)
```

**Note on Python GIL**: Python nodes with `kParallel` can cause issues because the GIL serializes Python execution. For true parallel Python nodes, use C++ extension or mark as `kSerialize` (which still allows other non-Python clusters to run concurrently).

### Diagnosis: Detect Badly-Scheduled Custom Nodes
```python
import maya.cmds as cmds

def audit_custom_node_scheduling(rig_root):
    """Find custom plugin nodes in the rig and report their scheduling impact."""
    all_nodes = cmds.listRelatives(rig_root, allDescendents=True, type='transform') or []
    
    problematic = []
    for node in all_nodes:
        node_type = cmds.nodeType(node)
        # Check if it's a plugin node
        if cmds.pluginInfo(node_type, query=True, loaded=True) == False:
            continue
        # Try to find scheduling type via evaluation toolkit
        # (requires Evaluation Toolkit plugin loaded)
        try:
            sched = cmds.evaluationManager(node=node, schedulingType=True)
            if sched in ['globallySerialize', 'untrusted']:
                problematic.append({'node': node, 'type': node_type, 'scheduling': sched})
        except:
            pass
    
    return problematic

# Usage:
issues = audit_custom_node_scheduling('|rig_root')
for issue in issues:
    print(f"WARNING: {issue['node']} ({issue['type']}) → {issue['scheduling']}")
```

### Maya Evaluation Toolkit (GUI diagnosis)
Window > Settings/Preferences > Evaluation Toolkit:
- Shows EG clusters and their thread assignments
- Color-codes globally-serialized nodes in red
- Shows "globally serialize" barriers as thick borders in the graph visualization

## Comparación con autorig_tools

Si autorig_tools incluye Python plugins o nodos custom (p.ej. para el solver FABRIK, para el interpolador RBF, o para nodos de spline), su scheduling type determina si rompen el parallel evaluation. Los nodos `multiplyDivide`, `multMatrix`, `decomposeMatrix` nativos de Maya son todos `kParallel` — por eso el patrón local_mmx es ideal para PE. Si se añade un MPxNode Python en el futuro, declarar `kSerialize` es seguro; solo escalar a `kParallel` si se puede garantizar thread safety completo.

## Aplicable directamente

YES — El script `audit_custom_node_scheduling()` es directamente ejecutable en cualquier escena con autorig_tools para detectar si algún plugin de terceros (p.ej. zoo tools, mGear, o RBF solvers externos) introduce nodos globally_serialize. Tiempo: 30 min de integración como health check en el post-build de autorig_tools.

## Fuente
- Maya Custom Evaluator API: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=Maya_SDK_Custom_evaluator_overview_Custom_Evaluator_API_html
- Best practices for Parallel Evaluation migration: https://around-the-corner.typepad.com/adn/2017/03/suggestions-best-practices-while-migrating-your-plugin-to-parallel-evaluation.html
- Using Parallel Maya 2026 (official Autodesk): https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2026/UsingParallelMaya.pdf
- Using Parallel Maya 2025: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2025/UsingParallelMaya.pdf
