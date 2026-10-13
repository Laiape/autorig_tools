---
source: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-Evaluation-Toolkit
found: 2026-06-29
category: performance
priority: 2
tags: [maya, performance, locators, transforms, DAG, node-count, offsetParentMatrix, optimization]
status: NEW
---

# Locators vs Transforms — Coste Oculto de Nodos DAG en Rigs Grandes

## Descripción
El archivo existente `rig-optimization-patterns-maya.md` toca brevemente que usar `decomposeMatrix` directo es mejor que un `spaceLocator` conectado vía `connectAttr` a `offsetParentMatrix`, pero no profundiza en POR QUÉ un locator/transform DAG cuesta más que un nodo de cómputo puro, ni en cuántos locators "extra" acumula típicamente un rig grande. Este documento detalla el coste estructural de los nodos DAG (locator, joint, group) frente a nodos de cómputo DG puros, relevante porque `autorig_tools` genera potencialmente decenas de locators auxiliares por componente (espacios, pivotes, helpers de aim) que se multiplican rápido en un rig de cuerpo completo + manos + cara.

## Fundamento matemático / técnico

### Por qué un nodo DAG (transform/locator/joint) cuesta más que un nodo DG puro
Un `multMatrix` o `decomposeMatrix` es un nodo de DEPENDENCY GRAPH puro: tiene atributos de entrada/salida y un método `compute()`, sin más responsabilidades. Un `transform`/`locator`/`joint` es un nodo DAG: además de ser un nodo DG (con sus propios atributos `translate`/`rotate`/`scale`/`matrix`/`worldMatrix`/`parentMatrix`/`inverseMatrix`...), participa en la jerarquía de la escena, lo cual implica:

1. **Atributos compuestos siempre presentes**: cada transform expone matrices `matrix`, `inverseMatrix`, `worldMatrix[]`, `worldInverseMatrix[]`, `parentMatrix[]`, `parentInverseMatrix[]` — cada una es un atributo computado que puede ser solicitado por downstream y debe mantenerse consistente, incluso si nada lo usa. Un `multMatrix` solo tiene el atributo `matrixSum` que realmente se usa.
2. **Coste de composición jerárquica**: el `worldMatrix` de un transform se computa como `localMatrix * parentMatrix` recursivamente hacia la raíz del DAG. Cada nivel de anidamiento DAG (locator dentro de grupo dentro de grupo) añade una multiplicación de matriz 4x4 a la cadena de cómputo de `worldMatrix`, incluso si el rigger solo necesita el resultado final.
3. **Selección/UI overhead**: los nodos DAG aparecen en el Outliner, son seleccionables en viewport, participan en bounding-box updates, y Maya mantiene metadata adicional (display layers, render stats, etc.) que un nodo DG puro no tiene. Esto es overhead de UI/escena, no de evaluación per se, pero se acumula en escenas con miles de nodos (tiempos de carga de escena, refresco de Outliner).

### Medición aproximada de overhead relativo
Basado en benchmarks de node-count ya documentados en `rig-optimization-patterns-maya.md` (overhead ~0.5-2µs por nodo DG simple):

```
multMatrix / decomposeMatrix (DG puro):         ~0.5-1µs por evaluación
transform / locator / joint (DAG, sin constraint): ~1.5-3µs por evaluación
  (incluye composición de worldMatrix recursiva + mantenimiento de atributos DAG)
parentConstraint (DAG + constraint):             ~3-5µs por evaluación (de archivo existente)
```

El factor dominante no es el nodo individual sino la PROFUNDIDAD de anidamiento: un locator a 8 niveles de profundidad en el Outliner fuerza 8 multiplicaciones de matriz para resolver su `worldMatrix`, mientras que el mismo resultado calculado con una cadena de `multMatrix` explícita (el patrón `local_mmx` ya usado en autorig_tools) tiene el mismo número de multiplicaciones pero SIN el overhead de mantenimiento de atributos DAG extra en cada nivel.

### El patrón "locator auxiliar" y su multiplicación en rigs grandes
Patrón común y costoso: usar un `spaceLocator` como "espacio intermedio" para resolver una orientación o pivote (p.ej. un locator en el world-space de un aim target, conectado de vuelta vía `offsetParentMatrix`):

```
BAD (patrón locator auxiliar):
  spaceLocator (DAG, +worldMatrix chain)
    → connectAttr loc.worldMatrix → otherNode.offsetParentMatrix
  Coste: 1 nodo DAG completo (con toda su cadena de worldMatrix) solo para
  transportar una matriz que podría calcularse directamente.

GOOD (cómputo directo):
  multMatrix (DG puro) → decomposeMatrix (DG puro) → conectar directamente
  Coste: 2 nodos DG puros, sin participación en jerarquía DAG, sin worldMatrix chain extra.
```

En un rig de cuerpo completo con ~15-20 componentes (brazos, piernas, spine, cuello, dedos), si cada componente usa 2-3 locators auxiliares "por comodidad" (espacios de aim, pivotes de pole vector, helpers de twist), eso son 30-60 nodos DAG extra cuya única función es transportar una matriz — equivalente a 30-60 cadenas de `worldMatrix` recursivas que no aportan nada al resultado final más allá de lo que ya hace el cómputo matricial directo.

### offsetParentMatrix como mitigación parcial (Maya 2020+)
`offsetParentMatrix` (atributo nativo desde Maya 2020) permite inyectar una matriz de offset directamente en la cadena de transformación de un nodo SIN necesidad de un transform/locator padre adicional en el DAG — colapsa lo que antes requería un grupo/locator extra en un solo atributo del propio nodo. Esto reduce el problema (menos nodos DAG necesarios para offsets), pero no elimina el coste si la fuente de la matriz de offset sigue siendo un locator en vez de un `multMatrix`/`pickMatrix` puro.

## Implementación en Maya
Auditoría de locators auxiliares en una escena:
```python
import maya.cmds as cmds

def audit_auxiliary_locators():
    """Encuentra locators cuyo único propósito es transportar matrices
    (sin geometría de shape usada, sin display visible, solo conectados a worldMatrix downstream)."""
    locators = cmds.ls(type='locator')
    suspects = []
    for loc_shape in locators:
        transform = cmds.listRelatives(loc_shape, parent=True)[0]
        # ¿Su worldMatrix se conecta a un offsetParentMatrix u otro driver de matriz?
        connections = cmds.listConnections(f'{transform}.worldMatrix', plugs=True) or []
        matrix_only_use = any('offsetParentMatrix' in c or 'matrixIn' in c for c in connections)
        if matrix_only_use:
            depth = transform.count('|')  # profundidad aproximada en el Outliner
            suspects.append((transform, depth, connections))
    suspects.sort(key=lambda x: -x[1])  # los más profundos primero (mayor coste de worldMatrix chain)
    for name, depth, conns in suspects[:30]:
        print(f"  depth={depth:2d}  {name}  -> {conns}")
    return suspects

def replace_locator_with_matrix_node(locator_transform):
    """Patrón de reemplazo: capturar la matriz mundial actual del locator como
    una matriz estática (pickMatrix/composeMatrix), eliminar el locator del DAG."""
    world_matrix = cmds.xform(locator_transform, q=True, ws=True, m=True)
    # construir composeMatrix/multMatrix equivalente con esa matriz como constante de entrada
    # y reconectar downstream antes de borrar el locator
    ...
```

## Comparación con autorig_tools
El patrón `local_mmx`/matrix-based de `autorig_tools` ya evita gran parte de este problema en el núcleo del rig (usando `multMatrix`/`pickMatrix`/`composeMatrix`/`decomposeMatrix` en vez de constraints o transforms intermedios para la jerarquía principal). El riesgo más probable está en componentes auxiliares construidos rápido o heredados de versiones anteriores del pipeline: locators de pole vector, locators de aim target, locators de pivote de espacio — cualquier sitio donde se haya usado un locator "porque es visual y fácil de mover en el viewport" en vez de resolver la matriz directamente. Esos locators SÍ son necesarios cuando un animador necesita manipular su posición directamente (un control real) — el problema es específicamente cuando el locator es puramente un intermediario de cómputo sin que nadie lo seleccione nunca.

## Aplicable directamente
SÍ — acción concreta y de bajo riesgo:
1. Ejecutar `audit_auxiliary_locators()` (o equivalente) sobre un rig de producción de autorig_tools para cuantificar cuántos locators auxiliares existen y a qué profundidad de DAG están.
2. Para cada locator detectado que NO sea un control manipulable por el animador (solo transporta una matriz), reemplazar por `pickMatrix`/`multMatrix`/`composeMatrix` directo + `decomposeMatrix` si se necesita en formato no-matriz.
3. Mantener locators reales SOLO donde el animador/rigger necesita seleccionarlos y moverlos en el viewport (pole vectors visibles, pivotes ajustables a mano) — no como mero transporte de matrices internas.
4. Si el pipeline usa offsetParentMatrix para offsets, verificar que la fuente conectada sea un nodo DG puro y no un locator innecesario.

## Fuente
- https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-Evaluation-Toolkit
- Relacionado: archivo existente `rig-optimization-patterns-maya.md` (snippet breve sobre locator overhead, expandido aquí)
- Documentación de `offsetParentMatrix`: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-offsetParentMatrix
