---
url: https://robertjoosten.github.io/
found: 2026-07-01
category: portfolio
credits: No Time to Die (Bond 25), Sea of Thieves: Captains of Adventure (Rare/Microsoft), His Dark Materials S2, The Witcher, Pokémon Sword & Shield, Audi Enders Game
tags: [rigging, td, pipeline, tools, modular-rig, python, maya, supervision, github-pages, frankenstein, skinning, documentation]
status: NEW
---


# Robert Joosten — Pipeline Rigging Supervisor (robertjoosten.github.io)


## Perfil profesional
Robert Joosten es un Pipeline Rigging Supervisor/TD con sede en los Países Bajos, actualmente en Tencent. Ha trabajado en producción VFX de alto perfil incluyendo No Time to Die (Bond 25), Sea of Thieves: Captains of Adventure (Rare/Microsoft), His Dark Materials S2, The Witcher, y Pokémon Sword & Shield. Su especialización abarca rigging, desarrollo de pipeline y supervisión. Es conocido en la comunidad por haber desarrollado Frankenstein, un sistema modular de rigging para Maya inspirado en Django con core DCC-independent, y una suite completa de herramientas de skinning con documentación técnica pública alojada en GitHub Pages.


## Estructura del portfolio
El site (robertjoosten.github.io) está organizado en dos grandes secciones paralelas de igual peso:
- /rigging — producciones: proyectos con créditos y descripciones técnicas de cada show
- /rnd — herramientas: todas las tools de producción como proyectos independientes
Páginas individuales por producción: /projects/no_time_to_die/, /projects/sea_of_thieves_captains_of_adventure/, /projects/audi_enders_game/
Páginas individuales por tool: /projects/frankenstein/, /projects/spline_ik/, /projects/dem_bones/, /projects/timeline_marker/, /projects/channel_box_plus/, /projects/anchor_transform/, /projects/reorder_attributes/, /projects/delinear_weights/, /projects/transfer_blend_shape/
Documentation sites separados: maya-skinning-tools (docs Python con API completa), maya-quality-assurance
Sin blog, sin about page separada detectada.


## Cómo presenta los proyectos
Cada producción tiene su propia URL y se describe en términos del PROBLEMA TÉCNICO específico + la SOLUCIÓN implementada:
- No Time to Die: "had to build automation to detect new/removed/updated cogs coming from modellers due to the ever-changing nature of these shots" — el build process fue completamente automatizado para ese set específico de cogs.
- Sea of Thieves: describe el "rebuild workflow" explícitamente: skeletal meshes de Rare deconstruidos en skeleton + geometry publishes separados, recompilados por Frankenstein, exportables directamente a engine — "which allows the exported skeletal animation to be used directly onto the engine assets."
El resultado para el animador o el studio se menciona en segundo lugar; el problema técnico y la decisión de solución van primero.


## Cómo comunica sus skills
Las skills no se listan — se demuestran a través de las tools publicadas. La existencia de Frankenstein (sistema modular, Django-inspired, ORM execution tree, DCC-independent core) comunica nivel de pipeline TD mucho más que cualquier lista. La documentación completa de maya-skinning-tools con Python API docs públicas es otro nivel de evidencia. La suite incluye: smooth weights context, remove weights context, initialize weights, mirror weights, soft-selection to weights, tweak weights, delinear weights, projection plane from joints. Sin tabla de skills declarada.


## Lo que tiene que Laia no tiene
1. **Sección /tools completamente separada de /personajes con URL propia y peso equivalente**: Robert tiene /rigging y /rnd como secciones de igual jerarquía. Pipeline.html de Laia mezcla en la misma página arquitectura del auto-rig, build sequence, design decisions, 9 tools, y 7 personajes — el contenido más valioso para reclutadores técnicos (las herramientas) está enterrado bajo otros tipos de contenido. Una URL separada /tools con su propio nav item y una card por herramienta (nombre + problema + técnica de implementación) permitiría a un reclutador de pipeline tools llegar directamente sin scrollear por 7 personajes.
2. **Descripción de proyecto centrada en el problema técnico resuelto, no en el resultado final**: Robert describe No Time to Die en términos del problema (cogs cambiantes) y la solución (automatización de detección). Laia lista los personajes (Freya, Mechanic, etc.) sin ningún "el reto técnico de este personaje fue X, lo resolví con Y." Un párrafo de 2-3 frases por personaje en formato PROBLEMA → DECISIÓN → RESULTADO transformaría pipeline.html de catálogo de resultados en documentación de decisiones de ingeniería.
3. **Site de documentación técnica separado para la tool principal**: maya-skinning-tools tiene su propio documentation site con API docs Python organizadas por módulos y funciones. Laia tiene Auto Skin Transfer descrita en unas frases. Crear una página de documentación mínima (GitHub Pages con README + funciones y parámetros documentados) para Auto Skin Transfer o Skin Manager elevaría la percepción de la tool de "script de producción" a "herramienta de ingeniería documentada y mantenible."


## Aplicable a Laiape.github.io
- Crear dos URLs separadas dentro del site: /pipeline (personajes, arquitectura, design decisions) y /tools (las 9 standalone tools), con nav items propios para cada una. No requiere nuevo contenido — es reorganización del existente con anclas o páginas separadas.
- Para cada personaje de Characters en pipeline.html, añadir 2-3 frases en formato "El reto técnico de este rig fue [X] — lo resolví con [Y] — el resultado para el animador fue [Z]." Transforma una lista de personajes en documentación de decisiones.
- Para Auto Skin Transfer o Skin Manager, crear un GitHub Pages mínimo con README estructurado: nombre → problema → uso → funciones clave — 30 minutos que transforma la tool en una herramienta con presencia pública indexable.


## Fuente
https://robertjoosten.github.io/