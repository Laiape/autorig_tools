---
source: https://github.com/MarcadrienLePape/maya-matrix-autorig
found: 2026-06-22
category: tool
priority: 3
tags: [maya, python, rigging, tool, matrix, autorig, github]
status: NEW
---

# maya-matrix-autorig (MarcadrienLePape)

## Descripción
Framework de autorig para Maya construido íntegramente sobre nodos de matriz — sin constraints, "solo cálculos matemáticos puros" según su propia descripción. Sigue la metodología de Jean-Paul Tossings (Polder Animation), una de las referencias más citadas en rigging matrix-based de la industria. Repo pequeño (4 estrellas) pero con actividad reciente (commit en noviembre 2025) y enfoque metodológico que coincide casi exactamente con el stack que Laia ya usa en autorig_tools.

## Fundamento matemático / técnico
El proyecto reemplaza la cadena clásica constraint→decompose por composición directa de matrices: cada control alimenta su `worldMatrix` a un `multMatrix` que combina offsets locales, y el resultado se conecta directamente al `offsetParentMatrix` del joint/control destino (o a un `decomposeMatrix` cuando el destino necesita canales separados de translate/rotate/scale para animación). Esto es exactamente el patrón "local_mmx" que usa autorig_tools: preservar el espacio local vía matemática de matrices en vez de constraints, evitando el doble cálculo de jerarquía que ocurre cuando un `parentConstraint` decompone y luego Maya vuelve a componer la matriz final del transform.

La ventaja estructural sobre constraints clásicos: cada `parentConstraint`/`orientConstraint` internamente ya hace este álgebra de matrices, pero además añade overhead de nodo (cálculo de peso, weight blending, soporte de múltiples targets) que rara vez se usa en un rig de producción con un solo target por control. Sustituir por `multMatrix` puro elimina ese overhead y dejas el grafo de evaluación más plano (menos profundidad de dependencia = mejor scheduling en Parallel Evaluation).

## Implementación en Maya
- Apunta a Maya 2020+ (requisito mínimo para `offsetParentMatrix`).
- Licencia MIT, en desarrollo activo ("CURRENTLY IN DEV" en el README).
- Arquitectura modular extensible — define una interfaz para módulos custom, similar conceptualmente a cómo autorig_tools organiza sus builders de brazo/pierna/columna.
- Workflow no destructivo declarado como objetivo (preservar animación al reconstruir el rig) — funcionalidad marcada como TBD en el momento de este research.

## Comparación con autorig_tools
Es, en filosofía, un primo cercano del propio sistema de Laia — mismo enfoque "pure matrix, no constraints" que ya implementa con `wtAddMatrix`/`multMatrix`/`local_mmx`. No aporta una técnica nueva que Laia no tenga ya, pero es una referencia útil para comparar arquitectura de módulos (su sistema de "extensible interface for custom modules" vs la estructura de builders que ya tiene autorig_tools) y como caso de estudio de cómo otro TD ha resuelto el mismo problema de preservar animación al reconstruir jerarquías matrix-driven (el TBD de "non-destructive workflow" es justamente un problema abierto que probablemente Laia también enfrenta).

## Aplicable directamente
NO — No hay código o técnica aquí que autorig_tools no tenga ya en una forma más madura. El valor es de benchmarking/inspiración arquitectónica, no de integración directa. Vale la pena revisar su solución (si la publican) al problema de rigs no-destructivos matrix-based, ya que es un punto débil común en este tipo de sistemas.

## Fuente
https://github.com/MarcadrienLePape/maya-matrix-autorig
