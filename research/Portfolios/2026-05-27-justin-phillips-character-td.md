---
url: https://www.justindphillips.com/
found: 2026-05-27
category: portfolio
credits: [no confirmed studio credits in public searches — personal projects and tool development]
tags: [rigging, character-td, portfolio, blog, python, maya, modular-rig, phasrig, houdini, wix]
status: NEW
---

# Justin Phillips — Character TD

## Perfil profesional
Justin Phillips es un Character TD y Rigger con un portfolio personal en justindphillips.com. No tiene créditos de estudio listados públicamente, pero se posiciona como Character TD con reels, resume, y un blog técnico activo sobre rigging. Su diferenciador más claro es PhasRig, un rig builder modular que ha desarrollado personalmente en Maya y documenta progresivamente en su blog. También tiene experiencia con Houdini grooming. Su ArtStation profile es justintphillips.artstation.com. El blog tiene posts desde 2018-2019 aproximadamente.

## Estructura del portfolio
- Homepage con tagline: "Character TD | Justin Phillips | Portfolio"
- Reel(s) embebidos en la homepage
- About Me page (/about-me)
- Blog técnico (/blog-1) con categorías:
  - "PhasRig" — posts sobre desarrollo progresivo del modular rig builder
  - "Rigging" — posts técnicos de rigging generales
  - Posts de Houdini grooming (Houdini Fur Groom and Sim, Advanced Houdini Grooming)
- Resume y contact info
- ArtStation: justintphillips.artstation.com

## Cómo presenta los proyectos
El foco del portfolio no está en proyectos de cliente sino en el desarrollo de herramientas propias documentado progresivamente en el blog:
- "PhasRig" (post original): describe el modular rig builder para Maya con 3 categorías de librería — Builds, Modules, UI. El builder crea "placers" para posicionar joints que se orientan automáticamente. Documenta la arquitectura del sistema, no solo el resultado.
- "PhasRig — Update v001": documenta explícitamente la decisión de usar Maya commands en lugar de PyQt/PySide2 para la UI, con la razón: "to avoid headaches from Maya's transition from pyside to pyside2." Razonamiento de arquitectura expuesto, no solo resultado.
- Posts de Houdini (Houdini Fur Groom and Sim, Advanced Houdini Grooming): testing de groom en Houdini 17, grooming de personajes realistas — muestra diversificación técnica más allá de Maya rigging.
- Cada blog post funciona como una ventana al proceso de desarrollo con decisiones razonadas, no solo al resultado final.

## Cómo comunica sus skills
- Tagline de site: "Character TD | Justin Phillips | Portfolio" — rol declarado desde el primer momento
- Blog como demostración de proceso: muestra que puede razonar sobre decisiones de arquitectura (Maya commands vs PyQt/PySide2, estructura modular de un rig builder)
- Blog categorizado por tema (PhasRig, Rigging) — facilita que visitantes técnicos encuentren contenido específico
- PhasRig como portfolio piece independiente con nombre propio y arquitectura documentada (Builds/Modules/UI)
- Presencia en dos plataformas: personal site + ArtStation

## Lo que tiene que Laia no tiene
1. **Blog que documenta el PROCESO de desarrollo de una tool, no solo el resultado**: Justin tiene posts que explican decisiones de arquitectura mientras construye PhasRig (Maya commands vs PySide2, estructura Builds/Modules/UI). Laia tiene 9 tools completadas en pipeline.html sin ningún post que documente por qué tomó las decisiones técnicas que tomó al construirlas. Un post de 200-300 palabras sobre cómo y por qué construyó el Auto Skin Transfer o el Skin Manager sería más valioso para un recruiter técnico que añadir una décima tool a la lista.
2. **Razonamiento explícito de decisiones de implementación de UI**: Justin explicó por qué usó Maya commands en lugar de PySide2 en su rig builder UI. Laia menciona "PySide2 UIs" como skill en su stack pero en ningún sitio del portfolio explica sus decisiones de implementación de UI (¿por qué PySide2 y no MEL? ¿qué arquitectura tiene la UI de Skin Manager o de Rig Tools? ¿dockable panel? ¿QMainWindow?). Articular una decisión de implementación, aunque sea en una frase por tool, comunica experiencia de producción real en lugar de solo listar un framework.
3. **Categorías de blog que indexan expertise por área técnica**: Justin categoriza sus posts en "PhasRig" y "Rigging" — alguien que busca contenido técnico específico puede navegar directamente. El portfolio de Laia no tiene ningún espacio de escritura técnica, así que no hay categorías. Incluso 2-3 posts en el propio site con tags como "facial rigging", "matrix rigging", o "RBF correctives" crearían tráfico orgánico de búsquedas y documentarían el expertise de Laia en áreas donde tiene un conocimiento real y profundo.

## Aplicable a Laiape.github.io
- Añadir una entrada de blog (o una sección "Development Notes" expandible en pipeline.html) para al menos una de las 9 tools, con el formato: PROBLEMA → DECISIÓN → RAZÓN. Ejemplo concreto: "Auto Skin Transfer — necesitaba transferir pesos entre meshes con topología diferente sin rebind manual → implementé comparación por cercanía de vértice con normalización proporcional → reduce el tiempo de re-rigging tras cambios de modeling de horas a menos de 2 minutos."
- Para cada tool en Standalone Tools de pipeline.html, añadir una frase de arquitectura de implementación: e.g., "Skin Manager — PySide2 dockable panel; reads/writes skinCluster data as JSON for cross-rig portability" o "Rig Tools — single-window utility with category tabs (joint, control, constraint) for session-level workflow speed."
- Si Laia tiene cualquier experiencia con Houdini (aunque sea básica), mencionarla en la About page o en el stack de skills — la demanda de riggers que pueden moverse entre Maya y Houdini crece en VFX y Laia no la menciona en ningún sitio del portfolio actual.

## Fuente
https://www.justindphillips.com/
