---
source: https://github.com/nickyliux/nl_rigging_tools
found: 2026-06-22
category: tool
priority: 3
tags: [maya, python, rigging, tool, autorig, github, simulation]
status: NEW
---

# nl_rigging_tools (nickyliux)

## Descripción
Sistema de autorig modular para Maya orientado específicamente a soportar workflows de simulación (Ziva VFX para músculos) y esqueletos anatómicamente complejos (vertebrados no-humanos). 18 estrellas, 1182 commits, actualizado hace 9 días en el momento de este research — claramente activo y con un historial de desarrollo sustancial, licencia MIT.

## Fundamento matemático / técnico
Arquitectura orientada a objetos en capas: clases base de nodo (`DagNode`, `JntNode`, `CrvNode`, etc.) y clases de "blueprint" de componente de rig (`Head`, `SpineBp`, `ArmBp`, `LegBp`) que se combinan declarativamente. El aspecto técnicamente más relevante no es un algoritmo nuevo, sino el caso de uso: rigging diseñado desde el inicio para alimentar una simulación de tejido blando (Ziva), lo que implica que el esqueleto y la jerarquía de joints deben ser compatibles con el sistema de attachments de Ziva (joints densos a lo largo del volumen muscular, no solo en las articulaciones de animación) — un problema de diseño de jerarquía distinto al rigging puramente de animación.

## Implementación en Maya
- Stack: nurbs curves/surfaces para guías, joints estándar de Maya, skinCluster para bind inicial.
- No usa explícitamente matrix nodes ni RBF en la documentación visible — parece más cercano a un framework de constraints/joints clásico que al stack matrix-based de Laia.
- README indica explícitamente "still under active development, use for study purpose" — no es production-ready tal cual, pero el código es legible y la arquitectura de blueprints está bien documentada.

## Comparación con autorig_tools
El interés principal para Laia no es la implementación (su propio sistema matrix-based es más avanzado técnicamente), sino el enfoque hacia esqueletos de simulación y cuadrúpedos/vertebrados no estándar — un área que el brief de Laia menciona explícitamente como objetivo (rigging de cuadrúpedos). Vale la pena revisar cómo estructura las "blueprints" de columna para anatomías no-bípedas como referencia de organización de casos especiales, aunque la solución matemática final (matrix-based, de Boor ribbon) seguiría siendo la de autorig_tools.

## Aplicable directamente
NO — Es útil como referencia de arquitectura para casos de simulación/cuadrúpedo, pero no aporta una técnica matemática o un módulo reusable directamente, y el propio autor advierte que no es production-ready. Mantener como referencia de lectura, no de integración.

## Fuente
https://github.com/nickyliux/nl_rigging_tools
