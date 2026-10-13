---
source: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2025/UsingParallelMaya.html
found: 2026-05-11
category: performance
priority: 2
tags: [maya, performance, optimization, matrix-nodes, constraints, deformer-stack, node-graph, dirty-propagation]
status: NEW
---

# Rig Optimization Patterns in Maya — Matrix vs Constraints, Deformer Stack, Node Topology

## Descripción
La performance de un rig en Maya depende de la topología del grafo DG (cuántos nodos, cómo están conectados, qué tipos de nodos son) y del orden de los deformadores en el stack. Este documento recopila los patrones de optimización más impactantes: reemplazo de constraints por matrix nodes, ordenamiento del stack de deformadores, reducción de dirty propagation, y evitar nodos problemáticos. Basado en documentación oficial de Autodesk y casos de producción publicados.

## Fundamento matemático / técnico

### Constraint vs Matrix Nodes: Real Performance Difference
**Constraint nodes** (`parentConstraint`, `orientConstraint`, etc.) are Maya DG nodes that:
1. Compute transformation matrices internally
2. Have significant overhead from attribute validation, channel box integration, and fallback computations
3. Are NOT schedulable in parallel (they belong to a serial cluster by default)
4. Add visible nodes to the outliner (cosmetic overhead)

**Matrix nodes** (`multMatrix`, `decomposeMatrix`, `wtAddMatrix`) are lean, purpose-built nodes:
1. Single-purpose matrix operations — no overhead from general-purpose attribute handling
2. Fully parallel-schedulable (declared as parallel-safe by Autodesk)
3. Fewer attribute evaluations per frame
4. GPU-side: don't directly run on GPU, but they feed into deformers that do

**Measured impact (Rigging Dojo 2022):** Replacing 50 parentConstraints with matrix node equivalents on a production character: 40% DG evaluation time reduction. In Parallel mode, the impact is larger because constraints formed serialization bottlenecks.

### Dirty Propagation — Minimizing Re-evaluation
Every attribute change triggers dirty propagation forward through the DG. Design strategies:

**Wide vs Deep graphs:**
- Wide (many parallel branches from one root): only the affected branch re-evaluates
- Deep (long chains where B depends on A depends on root): everything re-evaluates on any change

**Dead-end connections:** Avoid connecting outputs of frequently-changing nodes to inputs of rarely-changing nodes if there's a simpler alternative. Use `condition` nodes to gate propagation when blend values are 0 or 1.

**Avoiding locator overhead:**
```python
# BAD: transform node as a position proxy (has full transform stack overhead)
loc = cmds.spaceLocator()[0]
cmds.connectAttr('joint.worldMatrix[0]', loc+'.offsetParentMatrix')

# GOOD: decomposeMatrix directly (no transform node in the path)
dcmp = cmds.createNode('decomposeMatrix')
cmds.connectAttr('joint.worldMatrix[0]', dcmp+'.inputMatrix')
# Use dcmp.outputTranslate directly as input to next node
```
Transform nodes have more overhead than pure DG utility nodes because they participate in the DAG, have VP2 visibility computation, and register with the selection system.

### Deformer Stack Order Optimization
Deformer evaluation follows the stack from top to bottom. Order matters for:
1. **Correctness:** blendShape (pre-skin) must precede skinCluster; corrective blendShape (post-skin) must follow skinCluster
2. **Performance:** More expensive deformers lower in the stack benefit from simpler input geometry (fewer faces after a lattice, etc.)

**Recommended production stack:**
```
1. blendShape (pre-deform) — shape targets, corrective basis shapes
2. skinCluster (LBS or DQS) — primary skin binding
3. deltaMush — optional smooth post-processing
4. blendShape (post-deform) — corrective shapes driven by joint pose
5. (rarely) wrap/proximityWrap — if needed for clothing
```

**GPU override and stack order:** GPU processes the stack sequentially. Each GPU deformer that follows a CPU deformer requires a GPU upload. Therefore, group all GPU deformers together (don't alternate GPU/CPU).

### Skinning Influences Count
| Influences per vertex | GPU performance | Deformation quality |
|----------------------|----------------|---------------------|
| 1-4 | Fastest | Adequate for game chars |
| 4-8 | Fast (default) | Good for film/VFX |
| 8-16 | Medium | Best for hero characters |
| 16+ | Slower | Use deltaMush instead of more influences |

Maya's `skinCluster.maxInfluences` attribute. For GPU: 4-8 influences is the sweet spot. More than 8 provides diminishing returns vs cost.

### Avoiding Expression Nodes: Full DG Math Alternatives
| Expression operation | DG node equivalent |
|---------------------|-------------------|
| `a = b * c` | multiplyDivide (multiply) |
| `a = b / c` | multiplyDivide (divide) |
| `a = b ^ c` | multiplyDivide (power) |
| `a = clamp(b, min, max)` | clamp |
| `a = lerp(b, c, t)` | blendTwoAttr |
| `a = if (b > 0): c else: d` | condition |
| `a = abs(b)` | abs (or condition with negation) |
| `a = sin(b)` | (no native) — avoid, or use animCurve |
| Matrix multiply | multMatrix |
| Matrix weighted blend | wtAddMatrix |
| Dot product | vectorProduct (dot mode) |
| Cross product | vectorProduct (cross mode) |

**Key rule:** Any operation achievable with DG nodes should NOT be in an expression. Expressions run on the main thread and force all downstream nodes to serialize.

### Unit Conversion Nodes
`unitConversion` nodes are automatically inserted by Maya when connecting attributes with different units (e.g., radians to degrees). They have negligible overhead individually but:
- Many spurious unitConversion nodes (from mismatched unit connections) add up
- In very large rigs, cleaning up spurious unitConversion nodes can shave 5-10% eval time

```python
# Find all unitConversion nodes in scene
ucs = cmds.ls(type='unitConversion')
# Identify spurious ones: those where input and output factor = 1.0
for uc in ucs:
    factor = cmds.getAttr(uc + '.conversionFactor')
    if abs(factor - 1.0) < 1e-6:
        print(f'Spurious unitConversion: {uc}')
```

### Node Count Benchmarks
From Autodesk internal testing and community reports:
- Each DG node adds ~0.5-2µs overhead to evaluation time (modern hardware, small DG)
- At 1000 extra nodes: ~0.5-2ms extra per frame — noticeable at 60fps targets
- Constraint vs matrix: parentConstraint ≈ 3-5× slower than equivalent multMatrix chain
- Expression node: 10-50× slower than equivalent DG node (plus forces serialization)

## Implementación en Maya

```python
import maya.cmds as cmds

# Audit: count nodes by type
def rig_node_audit():
    constraints = cmds.ls(type=['parentConstraint', 'orientConstraint',
                                 'pointConstraint', 'scaleConstraint'])
    expressions = cmds.ls(type='expression')
    matrix_nodes = cmds.ls(type=['multMatrix', 'decomposeMatrix', 'wtAddMatrix'])
    
    print(f"Constraints: {len(constraints)} (consider replacing with matrix nodes)")
    print(f"Expressions: {len(expressions)} (REPLACE with DG nodes — force serialization)")
    print(f"Matrix nodes: {len(matrix_nodes)}")
    
    return constraints, expressions, matrix_nodes

# Check dirty propagation chains (depth of longest chain from root)
# Useful for identifying serial bottlenecks
def find_deep_chains(root_node, max_depth=50):
    """Trace dependency depth from root — deep chains hurt parallel evaluation."""
    # Use cmds.listConnections recursively to trace downstream...
    pass
```

## Comparación con autorig_tools

autorig_tools ya usa matrix nodes (local_mmx, wtAddMatrix). Los puntos de auditoría son: (1) ¿quedan constraints en el rig? Si sí, cuántos y si son necesarios. (2) ¿Hay expression nodes? Si sí, reemplazar por DG equivalentes. (3) ¿El stack de deformadores tiene deltaMush antes del skinCluster por error? (4) ¿El número de influences está optimizado para el target platform (game vs VFX)?

## Aplicable directamente
YES — Ejecutar `rig_node_audit()` en un rig construido con autorig_tools. Target: 0 expression nodes, < 10 constraints (solo donde matemáticamente necesario), matrix nodes para todo el resto. Documentar el node count baseline y comparar después de optimizaciones.

## Fuente
- Autodesk Parallel Maya 2025: https://damassets.autodesk.net/content/dam/autodesk/www/html/using-parallel-maya/2025/UsingParallelMaya.html
- Deformation layering GPU world: https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82
- Rigging Dojo optimization: https://ondemand.riggingdojo.com/OptimizingRigsforParallelEvaluation
- Maya Evaluation Manager: https://knowledge.autodesk.com/support/maya/learn-explore/caas/CloudHelp/cloudhelp/2016/ENU/Maya/files/GUID-190D97E7-9AC0-4D67-8A07-1AF3A9DBAF15-htm.html
