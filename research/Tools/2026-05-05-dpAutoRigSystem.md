---
source: https://github.com/nilouco/dpAutoRigSystem
found: 2026-05-05
category: tool
tags: [maya, python, rigging, autorig, modular, open-source, facial, biped]
status: NEW
---

# dpAutoRigSystem — Sistema de Auto-Rigging Modular Open-Source

## Descripción
dpAutoRigSystem es un sistema de rigging automático open-source para Maya, desarrollado por Danilo Pinheiro (nilouco) con soporte activo desde 2011 hasta la actualidad. Destaca por su modularidad, soporte multilenguaje, y cobertura de módulos que va desde extremidades hasta facial y pelo dinámico. La versión 5.01 (octubre 2025) añadió compatibilidad con Maya 2026 y correcciones para negative scale issues.

## Stack técnico
- Language: Python 3 (100%)
- Platform: Autodesk Maya (compatible Maya 2026 desde v5.01)
- License: GPL-2.0
- Stars: 154 | Forks: 37 | Latest: v5.01 (October 29, 2025)

## Detalles técnicos

### Módulos de rigging incluidos
- **Biped limbs**: brazo, pierna con IK/FK switch + snap
- **Fingers**: cadenas FK con atributos de spread/curl en el control principal
- **Spine**: IK spline + FK con blend
- **Neck/Head**: FK con follow head/body
- **Face**: ojo (aim constraint), mandíbula, cejas, labios
- **FK Line Module**: cadena FK genérica (cola, orejas, pelo, props)
- **Dynamic Chain**: simulación dinámica integrada
- **Eye fkCtrl offset aim direction** (v5.2.1): control de offset de aim para ojos
- **Shoulder sub-controller**
- **IkFkSnap para Limbs** integrado en rig publicado

### Validators (pipeline integration)
- **Check-in validators**: LockedNormal, InvertedNormal (mesh quality checks)
- **Check-out validators**: OutlinerCleaner, UnusedSkinCleaner, UnusedNodeCleaner, ProxyCreator
- Arquitectura de validación pre/post build orientada a pipeline de estudio.

### Compatibilidad Maya 2026
- v5.01 corrige problemas de negative scale en Maya 2026
- PoleVector control calibration mejorada
- Set Finger preferred angle automation

## Comparación con autorig_tools
dpAutoRigSystem es más genérico y menos especializado que autorig_tools. Su punto fuerte es la cobertura modular amplia y la comunidad activa. Sin embargo, al ser GPL-2.0, no puede integrarse directamente en pipelines comerciales cerrados sin publicar el código derivado. La lógica de validators pre/post build es un patrón de pipeline más maduro que el de muchos sistemas similares. No usa explícitamente matrix nodes; sigue una aproximación más tradicional con constraints.

## Takeaways aplicables
- El sistema de **validators separados en check-in y check-out** es una arquitectura de control de calidad que autorig_tools podría adoptar: checks de geometría antes del rig, y limpieza/optimización al finalizar.
- El **Dynamic Chain module** integrado directamente en el auto-rig (sin necesidad de herramienta externa) es una funcionalidad de valor para colas, pelo y prendas simples.
- La **PoleVector calibration automatizada** es un detalle de UX que vale la pena implementar en autorig_tools — actualmente es un punto de fricción manual.
- Compatibilidad activa con Maya 2026 → revisar qué cambios de negative scale afectan a nuestros rigs.

## Fuente
https://github.com/nilouco/dpAutoRigSystem  
https://github.com/nilouco/dpAutoRigSystem/releases
