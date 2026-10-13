---
url: https://robbiereid.artstation.com
found: 2026-09-02
category: portfolio
credits: Method Studios Melbourne (Senior/Lead Rigging TD, 10+ años): Terminator: Dark Fate (Rev-9 rig), Men in Black International (Pawny rig), Mortal Kombat (Goro rig), Lyle Lyle Crocodile, Borderlands
tags: [rigging, td, portfolio, method-studios, artstation, gumroad, python, correctives, ziva, creature, mechanical, vfx, melbourne, freelance]
status: NEW
---


# Robbie Reid — Senior Rigging TD / Freelance (robbiereid.artstation.com)


## Perfil profesional
Robbie Reid es un Rigging TD australiano de Melbourne con más de 10 años de experiencia, incluyendo roles senior y lead, principalmente en Method Studios Melbourne. Actualmente trabaja como freelance construyendo rigs game-engine-friendly usando su propio framework de rigging en Maya. Su especialidad declarada abarca character, animal, creature y mechanical rigging, con interés explícito en problem solving, optimización y "building broad pipelines". Es autor de un framework personal de rigging en Python y distribuye rigs gratuitos y pagados en Gumroad (robbiereidrigs.gumroad.com). Tiene canal de YouTube (@RobbieReidRigs). *Nota: acceso directo a robbiereid.artstation.com bloqueado por proxy de red; información obtenida de snippets de ArtStation, búsquedas web, y Gumroad.*


## Estructura del portfolio
- **robbiereid.artstation.com** — portfolio ArtStation principal con entries por proyecto de producción
- **robbiereidrigs.gumroad.com** — distribución de rigs (free y potencialmente pagados)
- **YouTube (@RobbieReidRigs)** — canal de vídeo para demos de rigs y herramientas
- **LinkedIn (au.linkedin.com/in/robbie-reid-rigs)** — presencia profesional complementaria
- Sin website personal independiente identificado


Entries de ArtStation identificados:
- Terminator: Dark Fate — Rev-9 Rig (2019)
- Men in Black International — Pawny Rig (2019)
- Mortal Kombat — Goro Rig
- Guardian — Free Maya Rig (personal project / Gumroad showcase)
- Biped to Quadruped Motion Capture Pipeline (Summer 2020)


## Cómo presenta los proyectos
Cada entry de ArtStation documenta el contexto de producción con precisión técnica. Ejemplo del Rev-9 rig: rig construido en 2019 en Method Studios Melbourne, Robbie era el primary rigger en el personaje para sus secuencias, el personaje tenía dos variantes de digi-double más un endoskeleton robótico completo, el rig se usó principalmente para augmentar plates con brazos digitales y daño en batalla, la estructura full endoskeleton estaba rigeada en su totalidad y podía snapear al human rig para mostrar internals durante la secuencia del helicopter crash. Este nivel de descripción comunica: contexto exacto de producción, su rol específico dentro del equipo (primary rigger bajo el rigging lead), el constraint técnico del asset (dual-variant character), y la función específica del rig en producción (augmentation, no full CG replacement).


El entry del Goro rig documenta una técnica específica de producción: extracción de 400+ corrective shapes de simulaciones de Ziva para mejorar la deformación en el animation rig, reduciendo la necesidad de muscle sims en cada shot. Esto es una decisión de pipeline con impacto documentado: correctivos de Ziva → correctives del animation rig, con el motivo explícito (performance de shots sin muscle sim).


El Guardian rig como entry separado funciona como portfolio piece pública descargable: 154 joints, 4 max influences, game-engine compatible, incluye full body rig + simplified face rig + sword prop + automated skirt y hair modules. Rigeado con su propio framework personal de Maya.


## Cómo comunica sus skills
- Bio de ArtStation con descripción explícita del rango de especialidades: "character, animal, creature and mechanical rigging"
- "Building broad pipelines" como self-description — señal de interés en scope más amplio que rigging artístico
- Propio Python rigging framework como evidencia de tool authorship además de rigging artístico
- Entry del Guardian rig especifica: joint count (154), max influences (4), compatibilidad con game engine — métricas técnicas que comunican comprensión de constraints de producción de juegos
- YouTube canal dedicado = demos visuales de rigs en movimiento fuera del contexto de ArtStation
- Gumroad = validación comercial/comunidad: si otros riggers descargan el Guardian, la calidad es verificable por cualquiera


## Lo que tiene que Laia no tiene


1. **Extracción de correctivos desde simulaciones musculares (Ziva → corrective shapes) como técnica documentada en el portfolio** — Robbie documenta explícitamente que el Goro rig incluye "400+ corrective shapes extracted from Ziva sims to enhance deformation in the anim rig, reducing the need for muscle sims in every single shot." Este patrón — usar sims de alta fidelidad para hornear correctives en el animation rig — es una técnica de producción VFX que ningún portfolio analizados hasta ahora ha documentado con este nivel de especificidad de workflow. Laia menciona RBF/SDK correctives como skill pero no documenta el workflow completo: qué inputs generan los correctives, cómo se integran en el rig de animación, qué problema de producción resuelven. Una descripción de 50 palabras del pipeline de correctives para un personaje en pipeline.html comunicaría que conoce el ciclo completo de deformación de producción, no solo que "hace correctives".


2. **Rig público descargable (free) en Gumroad con especificaciones técnicas como carta de presentación verificable** — El Guardian rig en robbiereidrigs.gumroad.com es descargable gratuitamente y viene con especificaciones completas (154 joints, 4 max influences, game-engine compatible). Cualquier animator o rigger puede abrirlo en Maya y evaluarlo directamente. Laia describe rigs en pipeline.html con screenshots pero ninguno es abriblemente evaluable. Un "lite rig" de cualquiera de los 7 personajes — simplificado si es necesario por tiempo — subido a Gumroad free o GitHub releases transformaría la descripción en evidencia directa.


3. **YouTube canal dedicado a demos de rigs con nombre propio ("RobbieReidRigs") como canal independiente del portfolio** — @RobbieReidRigs es un canal separado de YouTube para demos y breakdowns de rigs. Laia tiene el demo reel pero no tiene un canal de vídeo con su nombre donde los rigs y herramientas se demuestren en movimiento. Un vídeo de 90 segundos de Auto Skin Transfer en acción o del sistema de facial rig Maui funciona mejor como evidencia técnica que cualquier descripción textual, y un canal propio hace esos vídeos buscables independientemente del portfolio.


## Aplicable a Laiape.github.io
1. En pipeline.html, para el personaje más complejo con correctives (Maui o Freya si tienen RBF correctives), añadir una descripción del workflow de correctives: "correctives generated from [method: manual sculpt / RBF from poses / extracted from sim] → integrated as [SDK/RBF nodes/blendshapes] → triggered by [driver joint rotation / pose space]". Una frase por componente.


2. Publicar el auto-rig o uno de los 7 personajes como rig descargable gratuito en Gumroad, con especificaciones: joint count, número de controles, si es biped/quadruped/facial, si es game-engine compatible o solo Maya. La distribución gratuita elimina la barrera de acceso y permite que el rig sea evaluado directamente.


3. Crear un canal de YouTube o playlist de Vimeo nombrado explícitamente con el nombre de la autora para demos de herramientas y rigs, con nombres de vídeo que incluyan el tipo de rig/tool (ej: "Auto Skin Transfer Demo — Maya Python Tool") para que aparezcan en búsquedas orgánicas.


## Fuente
Información recopilada via WebSearch: búsquedas "Robbie Reid artstation portfolio breakdown method studios", "Robbie Reid Terminator Dark Fate Rev-9 rig", "Robbie Reid Mortal Kombat Goro correctives Ziva", "Robbie Reid Guardian rig gumroad framework Python", Gumroad (robbiereidrigs.gumroad.com), LinkedIn (au.linkedin.com/in/robbie-reid-rigs), ArtStation (robbiereid.artstation.com — acceso bloqueado por proxy, información de snippets de búsqueda).