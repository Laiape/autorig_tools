---
url: https://mrbmp33.github.io/
found: 2026-05-13
category: portfolio
credits: Spellbound (Netflix, 2024 — Skydance Animation Madrid), Swapped (Netflix, 2026 — Skydance Animation Madrid)
tags: rigging, td, portfolio, skydance, python, tdd, maya, github, tools, software-engineering, test-driven
status: NEW
---

# Bernat Mas — Technical Director, Skydance Animation

## Perfil profesional
Bernat Mas es un Technical Director en Skydance Animation Madrid, con créditos en Spellbound (Netflix, 2024) y Swapped (Netflix, 2026). Además de su rol en producción como TD que da soporte técnico a artistas y otros departamentos, ha desarrollado herramientas de ingeniería de software específicamente para Maya con un nivel de rigor técnico inusual en portfolios de rigging: utiliza test-driven development (TDD) para sus tools, y ha publicado herramientas para ejecutar código Maya fuera del entorno de Maya mediante proxy objects. Su portfolio es un GitHub Pages (Hugo con Toha theme) complementado por un perfil de GitHub con repositorios públicos. Perfil especializado en Python y en el cruce entre rigging/TD y ingeniería de software.

## Estructura del portfolio
- GitHub Pages (mrbmp33.github.io) con Hugo/Toha theme — portfolio técnico ligero
- About / bio section con créditos y descripción de rol
- GitHub profile (github.com/mrbmp33) con repositorios públicos:
  - **maya_mock_completion** (11 stars) — proxy objects para ejecutar código Maya fuera de Maya
  - **maya_tdd_suite** (1 star) — toolkit de TDD para Autodesk Maya
  - **cmdx fork** — fork del repo mottosso/cmdx (subset optimizado de maya.cmds)
- Sin sección de blog separada confirmada
- Sin demo reel o showreel

## Cómo presenta los proyectos
El perfil de GitHub es la presentación principal de sus herramientas, más que el portfolio web:
- maya_mock_completion: "Modification of maya stubs that allow the user to run maya-specific code outside of maya using proxy objects" — descripción técnica precisa en una línea
- maya_tdd_suite: "Toolkit for test-driven development for Autodesk Maya" — una frase de propósito

Los créditos de producción (Spellbound, Swapped) están en el about de la web. El rol en Skydance incluye dar soporte técnico a artistas y otros departamentos mediante ticketing system — señala experiencia de pipeline transversal, no solo rigging.

## Cómo comunica sus skills
- **TDD approach para Maya tools**: no es frecuente en portfolios de rigging. Señala ingeniería de software seria, no solo scripting.
- **maya_mock_completion con 11 GitHub stars**: otros desarrolladores reconocen el trabajo — social proof de peers técnicos, imposible de fabricar
- Fork activo de cmdx = participación en el ecosistema de herramientas open source de Maya
- Feature film credits en Skydance (Spellbound, Swapped) = validación de nivel de producción AAA
- Ticketing system para soporte = experiencia real de integración de pipeline en estudio, no solo rig building aislado

## Lo que tiene que Laia no tiene
1. **Nivel de software engineering explícito en sus tools**: Bernat tiene un framework de TDD para Maya y proxy objects para ejecutar código fuera de Maya — esto comunica madurez de ingeniería que va más allá del scripting típico de TD. Laia describe 9 tools con nombre y propósito pero no dice nada sobre cómo están estructuradas (¿modulares? ¿con tests? ¿con documentación interna?). Incluso una frase como "built with modular architecture and unit tests" elevaría la percepción técnica de sus tools sin añadir páginas.
2. **GitHub stars como social proof de peers técnicos**: La maya_mock_completion de Bernat tiene 11 stars de otros desarrolladores. Esto es validación técnica que ningún portfolio puede autoafirmar. Publicar una de las 9 tools de Laia en GitHub, aunque sea pequeña, da acceso a este tipo de validación externa y hace que el código sea auditable por recruiters técnicos.
3. **Feature film credits en estudio nombrado**: Bernat lista Spellbound (Skydance, Netflix 2024) y Swapped (Skydance, Netflix 2026) como créditos explícitos en su site. Los 7 personajes de Laia no tienen contexto de producción declarado — no queda claro si son personajes para clientes, para estudios o para proyectos personales. La diferencia entre "personaje personal" y "personaje para producción de estudio" es enorme para un recruiter.

## Aplicable a Laiape.github.io
- En la sección Standalone Tools de pipeline.html, para cada tool añadir una nota de arquitectura de una frase si aplica: "modular build with callbacks", "unit-tested in Maya standalone", "reusable across rigs via shared configuration". No tiene que ser extensa — 5 palabras por tool bastan para comunicar ingeniería seria.
- Publicar al menos una tool en GitHub con README que incluya: qué hace, qué problema resuelve, cómo se usa, requisitos (Maya version, Python version). El README es tan importante como el código para la percepción de calidad.
- Para cada personaje en pipeline.html, añadir una línea de contexto: "personal project", "client work — [tipo de cliente]", o "studio production". Si hay cualquier crédito de producción formal, nombrarlo con el nombre del estudio.

## Fuente
https://mrbmp33.github.io/
