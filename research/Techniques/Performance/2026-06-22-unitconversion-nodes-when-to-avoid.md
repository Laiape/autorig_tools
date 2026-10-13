---
source: https://lesterbanks.com/2016/09/rid-rigs-wasteful-unitconversion-nodes/
found: 2026-06-22
category: performance
priority: 2
tags: [maya, python, rigging, performance, dg]
status: NEW
---

# unitConversion Nodes — Cuándo Aparecen y Cuándo Eliminarlos

## Descripción
Maya inserta automáticamente un nodo `unitConversion` cada vez que conecta dos atributos que requieren una conversión de unidad implícita — típicamente un float/radianes a `doubleAngle`/grados, o cuando las preferencias de unidad lineal de la escena no coinciden con lo que el nodo aguas abajo espera. En rigs grandes con cientos de SDKs, RBFs y conexiones de control, estos nodos se multiplican silenciosamente y aparecen en cada perfilado de rig como un coste fijo no obvio.

## Fundamento matemático / técnico
The conversion itself is trivial (`out = in × conversionFactor`, e.g. ×57.2958 for radians→degrees), so the *math* isn't expensive — the cost is structural: each `unitConversion` node is a separate DG evaluation node with its own dirty-propagation entry, its own scheduling overhead in Parallel Evaluation, and its own cache-invalidation footprint. In a profiled production facial rig, evaluation time attributed to `unitConversion` + `blendWeighted` nodes (the two most commonly auto-inserted utility nodes) measured over 760ms cumulative per frame — not because any single node is slow, but because hundreds of them sit in series along blendshape/SDK driven chains, each adding fixed per-node graph-traversal overhead (node lookup, dirty-flag check, attribute fetch) that dominates over the actual float multiply.

The deeper cause: connecting a `float` attribute (e.g. a custom rig attribute, 0-1 range) into a `doubleAngle` attribute (e.g. a joint rotation) forces Maya to insert the node because the two attribute types are not unit-compatible — this happens silently every time you connect attributes of different unit types, including in SDK (setDrivenKey) and RBF pose-driver setups, which is exactly Laia's stack.

## Implementación en Maya
Detection: query the scene for unitConversion node count and check what feeds them —
```python
from maya import cmds
nodes = cmds.ls(type="unitConversion")
print(len(nodes))
for n in nodes:
    src = cmds.listConnections(n + ".input", source=True, destination=False, plugs=True)
    dst = cmds.listConnections(n + ".output", source=False, destination=True, plugs=True)
```
Mitigation paths:
1. **Rig in consistent units** — author SDKs/RBF drivers using `doubleLinear`/`doubleAngle` consistently rather than mixing float (0-1) custom attributes directly into angle attributes; an explicit `multDoubleLinear` with the conversion baked into the rig's own scale avoids the implicit node.
2. **offsetParentMatrix / matrix pipelines** — since most of Laia's stack already routes through `multMatrix`/`decomposeMatrix` rather than direct attribute-to-attribute SDK connections, unit mismatches mostly disappear because matrix attributes carry no unit type at all — this is a structural side-benefit of her `local_mmx` pattern that's worth being deliberate about.
3. **AngularNodes (Ryan Porter)** — a small native-node library (`angleBinaryOp`, `angleMultiOp`, `angleScalarOp`, `angleUnaryOp`, `clampAngle`) that operates directly on `doubleAngle` values without ever instantiating `unitConversion`, useful for the handful of cases where pure-matrix isn't applicable (e.g. driving a UI slider's displayed angle).

## Comparación con autorig_tools
Como el stack de Laia ya es predominantemente matrix-based (`wtAddMatrix`, `multMatrix`, `local_mmx`), la mayoría de la cadena de transform-a-transform ya evita unitConversion por diseño. El riesgo real está en las zonas donde SÍ conecta atributos escalares directamente — RBF/SDK correctives y el rig facial (blendshape weights, custom attributes 0-1 alimentando rotaciones de joints de cejas/labios) — exactamente donde el research de producción citado midió el coste de 760ms. Vale la pena auditar específicamente esas dos zonas.

## Aplicable directamente
YES — Una función `audit_unit_conversion_nodes()` que recorre la escena, cuenta nodos `unitConversion`, identifica cuáles están en la cadena de evaluación facial/SDK (no en transform matrix chains, que son inocuos ahí donde existan), y reporta los que tienen mayor fan-out (alimentan a más nodos downstream, indicando mayor coste de propagación). Es una función de diagnóstico de 1-2 horas, directamente reutilizable como parte del post-build health check que ya existe en autorig_tools (mencionado en research anterior como `rig_health_report()`).

## Fuente
https://lesterbanks.com/2016/09/rid-rigs-wasteful-unitconversion-nodes/
https://download.autodesk.com/us/maya/2009help/Nodes/unitConversion.html
https://lesterbanks.com/2017/07/maya-native-matrix-nodes-constraints/
