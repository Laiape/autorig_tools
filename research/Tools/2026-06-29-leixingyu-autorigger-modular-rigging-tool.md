---
source: https://github.com/leixingyu/autoRigger
found: 2026-06-29
category: tool
priority: 3
tags: [maya, python, rigging, autorig, modular, github, biped, quadruped]
status: NEW
---

# autoRigger (leixingyu) — Herramienta Modular de Auto-Rigging en Python

## Descripción
`autoRigger` es una herramienta de rigging modular y procedural para Maya, desarrollada en Python por Xingyu Lei (Senior Technical Artist en PlayStation/Sony Interactive Entertainment). Permite construir rigs de biped, quadruped y cadenas genéricas a partir de plantillas (templates) componibles — un enfoque muy cercano al de `autorig_tools` en cuanto a filosofía (componentes reutilizables en vez de un único rig monolítico hardcodeado), aunque con una base matemática más simple (constraints/joints estándar en vez de un sistema matrix-based puro).

## Fundamento matemático / técnico
El repositorio organiza el rig en una arquitectura de **templates** por tipo de extremidad/componente (spine, arm, leg, hand, tail, quadruped leg, etc.), cada uno con su propia clase Python que define:
1. **Placement guides**: joints temporales o locators posicionados por el usuario para definir la proporción del personaje.
2. **Build step**: conversión de los guides a la jerarquía final de joints + controles, usando principalmente IK handles nativos de Maya (`ikRPsolver`, `ikSCsolver`) y constraints estándar (`parentConstraint`, `orientConstraint`, `pointConstraint`) en vez de un sistema matrix-based custom.
3. **Naming convention** centralizada vía un módulo de utilidades que aplica prefijos/sufijos consistentes (similar en propósito a cualquier sistema de naming de `autorig_tools`, aunque la implementación concreta varía).

La arquitectura modular por templates (cada componente es una clase independiente que se puede instanciar y combinar) es el patrón de diseño más transferible del repositorio, independientemente de que la implementación interna use constraints en vez de matrices — es el mismo principio arquitectónico de "componentes reutilizables y combinables" que ya sigue `autorig_tools`.

## Implementación en Maya
```python
# Patrón de uso típico (basado en la estructura del repo)
from autoRigger.module import biped

rig = biped.Biped(side='', name='character')
rig.build_guide()      # coloca joints/locators de guía
# usuario ajusta proporciones en el viewport
rig.build_rig()         # construye joints finales + controles + IK/constraints
```
Cada template hereda de una clase base común que define el contrato (`build_guide()`, `build_rig()`, métodos de limpieza) — un patrón de Template Method clásico de OOP, aplicable directamente como referencia de estructura de clases si se quiere formalizar o refactorizar la arquitectura interna de componentes de `autorig_tools`.

## Comparación con autorig_tools
La diferencia fundamental es la base matemática: `autoRigger` usa IK solvers nativos y constraints (parentConstraint/orientConstraint), mientras que `autorig_tools` usa el patrón matrix-based (`wtAddMatrix`/`multMatrix`/`pickMatrix`/`composeMatrix`/`decomposeMatrix`/`local_mmx`), que ya está documentado en archivos de Performance como significativamente más eficiente en Parallel Evaluation (los constraints fuerzan más overhead de evaluación que los nodos de matriz puros, ver `rig-optimization-patterns-maya.md`). En términos de calidad de output, `autorig_tools` ya está en una categoría superior a este repositorio en cuanto a rendimiento de evaluación. Donde `autoRigger` sí puede aportar valor es como referencia de organización de código: la separación clara entre fase de guía y fase de build, y la arquitectura de templates por clase, son patrones de ingeniería de software transferibles independientemente de la implementación matemática interna.

## Aplicable directamente
PARTIAL — útil como referencia de arquitectura de software, no de técnica matemática:
1. Revisar la separación `build_guide()`/`build_rig()` como posible patrón a formalizar si `autorig_tools` no tiene ya esa separación explícita entre fase de colocación y fase de construcción final.
2. NO adoptar su uso de IK solvers nativos/constraints — el enfoque matrix-based actual de autorig_tools es superior en rendimiento.
3. Revisar el sistema de naming convention del repo solo como punto de comparación, sin asumir que sea mejor que el propio.

## Fuente
- https://github.com/leixingyu/autoRigger
