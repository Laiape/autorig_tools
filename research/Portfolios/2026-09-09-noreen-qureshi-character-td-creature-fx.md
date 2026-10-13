---
url: https://www.noreenqureshi.com/
found: 2026-09-09
category: portfolio
credits: Autodesk (empleadora actual como User Experience Designer), proyectos personales/académicos de rigging y creature FX
tags: rigging, td, creature-fx, houdini, maya, python, ux-design, portfolio, modular-script
status: NEW
---


# Noreen Qureshi — Character TD / Creature FX / UX Designer


## Perfil profesional
Noreen Qureshi es una profesional con trayectoria dual en rigging/creature FX y UX design, actualmente en Autodesk. Su portfolio noreenqureshi.com combina proyectos 3D (rigging de personajes/criaturas, creature FX con Houdini y Maya) con diseño de experiencia de usuario. Su especialidad de rigging incluye scripts modulares en Python y un workflow cross-software documentado paso a paso: Maya → Houdini para weight painting → de vuelta a Maya. No tiene créditos de producción de estudio conocidos — su relevancia como referencia es por la calidad de la documentación técnica de su proceso.


## Estructura del portfolio
- Website personal (noreenqureshi.com) con múltiples secciones
- Página dedicada "Rigging in Python" — writeup técnico con descripción detallada del script modular
- Páginas de proyecto individuales para trabajos 3D (personaje/criatura espiritual con Maya + Houdini + ZBrush + Redshift)
- Sección de portfolio con grid visual de proyectos
- Skills listadas: Maya, ZBrush, Houdini, Unity, JIRA & Confluence, Python, C#, C++, Adobe XD, Substance 3D Painter, Photoshop, Illustrator, Premiere


## Cómo presenta los proyectos
- Workflow documentado como secuencia de pasos con herramienta de entrada y output: "animé el personaje en poses de test de rango de movimiento, importé el modelo y las poses en Houdini para weight painting, lo re-importé a Maya, espejé los pesos en el Z-Axis"
- El principio de diseño del script explicado explícitamente: "el script está diseñado para ser modular de forma que gran parte del código se puede reutilizar para otras criaturas con modificaciones menores según la anatomía"
- Proyecto de criatura descrito con herramientas por capa: ZBrush (sculpt) + Maya (rig) + Houdini (weight paint + FX) + Substance 3D Painter (texturas) + Redshift (render)
- Énfasis en las decisiones de diseño del código, no solo en el resultado visual


## Cómo comunica sus skills
- Software listado con denominación técnica completa (ZBrush, Houdini, Unity — no solo "Maya y Python")
- Workflows cross-software documentados como diferenciación técnica — el uso de Houdini para weight painting es una técnica no convencional que señala breadth técnica
- Python descrito por principio arquitectónico: "modular, reutilizable, adaptable a anatomía diferente"
- Perfil dual rigging + UX design — posicionamiento como alguien que entiende tanto el pipeline técnico como el flujo de trabajo del usuario


## Lo que tiene que Laia no tiene
1. **Documentación de workflow paso a paso con herramienta de entrada, operación y output explícitos por sistema**: Qureshi documenta la secuencia completa del proceso de weight painting cruzando dos softwares — cada paso nombra la herramienta, la operación y el output. El portfolio de Laia describe técnicas (RBF correctives, matrix rigging) pero no documenta ningún workflow como secuencia de pasos con inputs y outputs específicos para ningún sistema.


2. **Principio arquitectónico del script como contenido del portfolio**: Qureshi menciona que el script "está diseñado para ser modular de forma que el código puede reutilizarse para otras criaturas" — el PORQUÉ del diseño del código como dato del portfolio, no solo el QUÉ hace. Las 9 tools de Laia tienen descripción funcional pero ninguna menciona si están diseñadas para ser modulares, pipeline-agnostic, o fácilmente extensibles — decisiones de diseño que distinguen a un TD senior.


3. **Stack técnico completo por capa de producción**: El proyecto de criatura de Qureshi lista las herramientas por capa: sculpting (ZBrush), rigging (Maya), weight painting (Houdini), texturing (Substance), rendering (Redshift). Los personajes de Laia en pipeline.html no especifican el stack técnico de producción por capa — el reclutador no sabe qué software se usó en cada etapa.


## Aplicable a Laiape.github.io
- Para cada personaje en pipeline.html: añadir una línea "Production stack" que liste el software usado por capa (sculpting / retopology / rigging / skinning / correctives / render para preview)
- Para la sección Design Decisions: reformatear cada decisión como "HERRAMIENTA DE ENTRADA → OPERACIÓN → OUTPUT" — el mismo formato que Qureshi usa para su workflow de weight painting
- Para las tools: añadir una frase de principio arquitectónico a las más complejas: "Auto Skin Transfer — diseñado para ser topology-agnostic: funciona independientemente de cambios en la malla entre versiones" o "IK/FK Match — funciona sin necesidad de espacios intermedios: el match es directo entre rig en espacio world"


## Fuente
https://www.noreenqureshi.com/