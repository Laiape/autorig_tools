---
source: https://github.com/asaf-b/Mansur-Rig
found: 2026-05-05
category: tool
tags: [maya, python, rigging, modular, cpp-plugin, autorig, facial, biped, free]
status: NEW
---

# Mansur-Rig 3.0 — Modular Rig Builder con C++ Node Library

## Descripción
Mansur-Rig es un constructor de rigs modulares para Maya desarrollado por Assaf Ben Zur (ex Lead Rigging TD de MPC). En diciembre 2025, la versión 3.0 se lanzó como completamente gratuita y open-source (MIT), eliminando toda restricción de licencia. Su diferencial técnico es una biblioteca de nodos C++ custom (mnsPlugins) que ofrece alto rendimiento. Compatible con Maya 2026 en Windows.

## Stack técnico
- Language: Python 34.6%, Wolfram Language 65.4% (build/install scripts)
- Core: C++ plugin library (mnsPlugins) — nodos custom para operaciones de rigging
- Platform: Autodesk Maya 2020+ (Windows only; Linux dropped temporalmente en v3.0)
- License: MIT
- Stars: 22 | Latest release: 3.0.0 (December 9, 2025)
- Free including for commercial projects; rigs built with it can be sold

## Detalles técnicos

### Arquitectura
- **mnsPlugins**: librería de nodos C++ custom compilados para Maya. Permiten operaciones de rigging de alto rendimiento que en Python puro serían más lentas. Ésta es la característica más diferencial del sistema.
- **Modular non-linear workflow**: el rig puede construirse en cualquier orden (no lineal), a diferencia de sistemas que requieren jerarquía estricta.
- **Guide objects**: la posición y orientación del rig se define mediante guides; el sistema puede construir el rig desde guides y también deconstruirlo de vuelta a guides.
- **Rig deconstruction**: capacidad bidireccional guides ↔ rig; facilita iteraciones y ajustes post-build.
- **Non-T-pose**: el sistema puede rigear modelos que no están en T-pose, lo cual es ventajoso en pipelines con modelos entregados en poses arbitrarias.
- **LODs Tool**: gestión automática de Level of Detail states del personaje.
- **Animation Picker UI**: picker de selección de controles incluido.
- **Maya 2026 support**: añadido en v3.0; incluye utilidad centralizada para actualizar rigs existentes al nuevo formato.

### Tipos de rig soportados
- Full body biped (articulaciones + facial)
- Humanoids
- *No* incluye auto-skinning

## Comparación con autorig_tools
La propuesta de valor de Mansur-Rig es principalmente la velocidad de ejecución via nodos C++ custom. Laia trabaja en Python puro, lo que supone un punto de diferencia fundamental. Si bien Python es más portable y mantenible, los nodos C++ son más rápidos para operaciones matemáticas complejas en cada frame. El flujo no-lineal y la deconstrucción guides↔rig son ideas arquitecturales que autorig_tools podría adoptar sin necesitar C++. El soporte de non-T-pose es un pain point real en producción.

## Takeaways aplicables
- El concepto de **rig deconstruction** (volver a guides desde un rig construido) es muy valioso para pipelines donde el personaje llega con cambios de modelo tras el rigging. Implementar en autorig_tools una función de "extract guides from rig".
- El **non-T-pose rigging** requiere resolver la orientación de joints en espacio de la pose. Investigar el algoritmo de Mansur-Rig para esto (documentación en mansur-docs).
- La **LODs Tool** centralizada es una funcionalidad práctica para games y tiempo real; considerar un módulo LOD en autorig_tools.
- La eliminación de licencias y el modelo MIT + GitHub es el modelo de distribución a seguir para autorig_tools si se plantea publicar.

## Fuente
https://github.com/asaf-b/Mansur-Rig  
https://www.cgchannel.com/2025/12/get-free-modular-maya-character-rig-builder-mansur-rig-3-0/  
https://docs.mansur-rig.com
