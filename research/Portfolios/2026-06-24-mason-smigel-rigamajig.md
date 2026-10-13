---
url: https://www.masonsmigel.com/
found: 2026-06-24
category: portfolio
credits: Riot Games (Rigging Technical Artist), Mikros Animation Paris (internship), SCAD Animation Studios (Hex Limit, 2020-2021), AnimSchool advanced rigging (Bartok, 2020 Golden Malcolm award)
tags: [rigging, td, portfolio, tools, opensource, blog, devlog]
status: NEW
---

# Mason Smigel

## Perfil profesional
Character TD / Rigging Technical Artist. Ha trabajado en Riot Games como Rigging Technical Artist y ha hecho una pasantía en Mikros Animation (París). Es el creador de Rigamajig2, un sistema de rigging modular y data-centric de código abierto para Maya, con un repositorio activo (47 stars, 7 forks, 1.105 commits, versión 1.3.2). Se especializa en sistemas de rigging modulares y herramientas de deformación post-rig (correctivos sobre animación).

## Estructura del portfolio
Más allá de la home, el site tiene: una página `/portfolio` (grid de proyectos), una página `/about`, y páginas de case-study individuales por proyecto/herramienta: `/rigamajig`, `/hexlimit`, `/bearly`, `/bartok`, `/shotsculptor`. Tiene un blog con posts en `/post/...`, incluyendo un dev-log serializado: "Rigamajig 2 Dev Log: Planning and Concept", que documenta decisiones de planificación y concepto de la herramienta a medida que se desarrolla — no es un post único sino una serie. Cada herramienta importante (Rigamajig, Shot Sculptor) tiene su propio repositorio público en GitHub con README de nivel de documentación técnica (instrucciones de instalación, dev tooling: Black, Pylint, Pytest/mayatest, Sphinx).

## Cómo presenta los proyectos
Los proyectos combinan contexto de producción/estudio con rol específico: Hex Limit (SCAD Animation Studios, 2020-2021) — "responsible for modeling the female character (Nitro Lux) and creating character and prop rigs using Rigamajig." Bartok (2020, clase avanzada de rigging en AnimSchool) incluye una credencial externa cuantificada: ganador del "2020 Golden Malcolm" en la categoría de rigging — no es solo una afirmación, es un premio verificable. La página de Rigamajig describe la arquitectura del sistema en tres capas con nombre propio: Author Interface (framework Python para construir componentes), Rigger Interface (UI para ensamblar rigs desde componentes/arquetipos prediseñados), y Animator Interface (el rig entregado, con IK/FK match, quick-select, etc.) — es un diagrama de arquitectura en prosa, dirigido a tres audiencias distintas (TD, rigger, animador).

## Cómo comunica sus skills
Las skills se comunican a través de case studies de herramientas, no como lista plana. Shot Sculptor se describe funcionalmente: "creates, edits and animates tangent space blendshapes across skinned meshes," permitiendo a los animadores "sculpt corrective shapes directly on specific frames of animation" mediante una UI simple que envuelve las herramientas nativas de sculpting de Maya. Es una herramienta con nombre de marca propio ("MS Shot Sculptor"), con propuesta de valor clara (qué problema de animador resuelve) y su propio repo de GitHub. La cuantificación viene de las stats públicas del repo (estrellas, forks, commits, versión) como señal de madurez/mantenimiento, más que de números de producción.

## Lo que tiene que Laia no tiene
- **Un blog de dev-log serializado** que documenta el pensamiento EN PROGRESO de una herramienta (planificación, conceptos, iteraciones) a lo largo de varios posts — no solo el resultado final como en pipeline.html, sino el proceso de decisión mientras ocurre.
- **Arquitectura de herramienta presentada como producto con tres audiencias nombradas** (Author/Rigger/Animator Interface) — explica explícitamente quién usa cada capa y qué obtiene, en lugar de listar la herramienta como una caja negra con nombre.
- **Una herramienta individual con su propio repositorio open-source, nombre de marca, problema declarado y stats públicas de mantenimiento** (estrellas, commits, versión) como evidencia de seriedad técnica continuada — ninguna de las 9 tools de Laia tiene esta presencia independiente fuera de la lista en pipeline.html.

## Aplicable a Laiape.github.io
1. Elegir la tool más madura de Laia (Auto Skin Transfer o Skin Manager) y publicarla en un repo de GitHub propio con README de instalación/uso, y empezar un dev-log corto (2-3 posts) en pipeline.html o una sección /blog documentando una decisión de diseño en curso (ej. cómo decidió el formato de exportación JSON en Skin Manager).
2. Para 2-3 de las 9 tools, añadir una frase que identifique explícitamente la audiencia/nivel de uso (ej. "Rig Tools — para riggers ensamblando el esqueleto" vs. "IK/FK Match — para animadores cambiando de espacio en pose"), igual que el modelo Author/Rigger/Animator Interface de Rigamajig.
3. Añadir a cualquier tool con código disponible las stats que dan señal de madurez: número de versiones, fecha de última actualización, o simplemente "en uso activo desde 2023" — el equivalente de las stats de GitHub de Mason cuando no hay repo público propio.

## Fuente
https://www.masonsmigel.com/
