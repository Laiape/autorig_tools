---
source: https://github.com/V1Interactive/FreeformTools
found: 2026-05-05
category: tool
tags: [maya, python, rigging, modular, space-switching, animation-preservation, ikfk]
status: NEW
---

# FreeformTools (V1Interactive) — Rigging Modular con Reestructuración en Animación

## Descripción
FreeformTools es un sistema de rigging modular open-source para Maya que resuelve un problema muy específico y valioso: permite a los animadores reestructurar el rig en cualquier momento de la animación sin perder los keyframes. Trata los keyframes del esqueleto como la fuente de verdad definitiva, permitiendo cambiar jerarquías de control y espacios sin destruir la animación existente.

## Stack técnico
- Language: Python 97.3% + C# 2.3% (UI via XAML/MVVM con Python.NET bridge)
- Platform: Autodesk Maya 2023/2024, Python 3.9
- Architecture: cross-DCC (1 UI para Maya, 3DS Max, y otros entornos Python)
- Stars: 35 | Last updated: v1.1.0 (July 13, 2024)
- License: open-source (GitHub)

## Detalles técnicos

### Arquitectura de Metanodos
- **Metanode system**: usa nodos de red de Maya (`network` nodes) en estructura de árbol para almacenar relaciones de escena como metadatos. Los metanodos no son transforms; son contenedores de información sobre la estructura del rig.
- Esto desacopla la estructura lógica del rig de la jerarquía de transforms en el outliner.

### Componentes Modulares
- **FK/IK Overdrivers**: componentes que crean relaciones de constraint sobre controles existentes. Cuando un overdriver cambia el espacio de un control, la animación existente se rebakea automáticamente al nuevo espacio.
- **Constraint-based space switching**: al cambiar de espacio, el sistema no destruye la animación — rebakea las curves al espacio nuevo.
- **Lossless rig restructure**: "skeleton keyframes as the definitive source of animation" — los joints del esqueleto siempre tienen datos; todo lo demás son capas de control encima.

### Resolución de ciclos
- Relaciones cíclicas en constraints se resuelven dentro del sistema de constraints de Maya. El sistema detecta y gestiona estos casos automáticamente.

### Módulo de exportación
- Sistema de exportación integrado con skeleton markup para identificar joints de exportación. Útil para pipelines de juegos.

### Cross-DCC UI
- La UI XAML/C# + Python.NET permite que la misma interfaz corra en Maya, 3DS Max, y cualquier entorno Python, con funcionalidad específica por DCC cargada en los eventos C# de la UI.

## Comparación con autorig_tools
FreeformTools aborda un problema distinto al de autorig_tools: no es un constructor de rig, sino una capa de control dinámico encima de rigs existentes. El concepto de "skeleton as source of truth" y el rebake automático al cambiar espacio es una filosofía diferente a los space switches tradicionales (que usan blend constraints o matrix blends). La arquitectura metanode es más compleja de implementar pero muy robusta para pipelines donde el rig cambia durante la animación (algo habitual en producción de juegos o TV donde hay iteraciones rápidas).

## Takeaways aplicables
- El patrón de **metanodos como árbol de relaciones** (network nodes, no transforms) es una técnica de arquitectura limpia aplicable a autorig_tools para almacenar metadatos del rig sin contaminar el outliner.
- El **rebake automático de animación al cambiar espacio** es una funcionalidad muy demandada por animadores. Implementar en autorig_tools como parte del sistema de space switch.
- El concepto de **Overdrivers** (capas de control añadidas sobre el rig, no parte del rig original) es interesante para añadir correctives o dinámicas sin reabrir el rig.
- Investigar más la integración Maya 2025+ y si el proyecto tiene actualizaciones pendientes.

## Fuente
https://github.com/V1Interactive/FreeformTools
