---
url: https://www.toadstorm.com/
found: 2026-07-22
category: portfolio
credits: multiple commercial/film VFX studios (unlisted individually), solo developer of MOPs (Motion Operators) for Houdini
tags: technical-artist, pipeline, tools, houdini, maya, python, blog, portfolio, vfx, procedural
status: NEW
---


# Henry Foster (Toadstorm) — Technical Artist / Pipeline TD


## Perfil profesional
Henry Foster, conocido en la industria como "Toadstorm", es un Technical Artist especializado en VFX y XR, actualmente Staff Designer en Intuitive Surgical (robótica médica, Sunnyvale CA). Empezó su carrera en 2006 como generalista 3D en Los Ángeles, trabajando sucesivamente como lighter, rigger, effects artist, pipeline engineer y tools developer en estudios comerciales y de film. Descubrió Houdini alrededor de 2011 y se convirtió en especialista en workflows procedurales. Es el desarrollador en solitario de MOPs (Motion Operators) para Houdini, un toolkit de motion graphics lanzado en 2018 que se convirtió en una herramienta de uso extendido en la industria VFX gratuita. Desarrolló también el sistema de pipeline Maya "Mustache" in-house, con herramientas Python para Maya, Houdini y Muster. Su blog "Toadstorm Nerdblog" es reconocido en la comunidad VFX por sus breakdowns técnicos con scene files descargables.


## Estructura del portfolio
The site has 4 main sections:
- **Projects** (/projects/): portfolio of visual work organized by project/client
- **Demo Reel** (/projects/reel/): dedicated showreel page
- **Blog — Toadstorm Nerdblog** (/blog/): long-running technical blog with 50+ posts, organized into categories: Maya (/blog/?cat=7), Houdini (/blog/?cat=30), plus pipeline, procedural animation, rendering, etc.
- **About/Info** (/about/): professional bio and career overview


Additionally, separate from the main portfolio:
- **motionoperators.com**: a completely independent site for the MOPs tool with its own documentation, changelog, tutorial resources, and community — NOT part of toadstorm.com


No explicit tools section within the portfolio itself (tools live in the blog posts and in motionoperators.com). No per-client credit pages visible from public data.


## Cómo presenta los proyectos
- Technical blog posts ARE the primary project presentation format: each post describes a specific problem, the approach taken, and the result — frequently with downloadable scene files attached
- "Info-rich breakdowns with scene to download" is the signature format recognized by cgwiki and the Houdini community: the download makes the breakdown verifiable, not just descriptive
- MOPs has its own dedicated website with documentation, changelog, and tutorial resources — the tool itself is the portfolio piece, not just a description of it
- Blog posts cross-reference Maya/Houdini techniques with production context (e.g. "getting data between Maya and Houdini for a show")
- Career narrative from interview at DoubleJump Academy: "started 2006 as generalist → lighter/rigger/FX artist/pipeline engineer → Houdini specialist → MOPs developer" is the professional arc told in third-party context
- No per-client or per-film breakdown pages; the studio work is alluded to in blog posts rather than listed as credits


## Cómo comunica sus skills
- Skills are communicated through the blog: 50+ posts in Maya/Houdini/pipeline demonstrate applied expertise without a skills table
- MOPs serves as the primary credibility signal: "solo developer of a widely-used free Houdini toolkit" is more specific than any skills bullet
- Blog categories (Maya, Houdini, pipeline) organize skills thematically rather than as a tag cloud
- External recognition: cgwiki publicly recognizes his "info-rich breakdowns with scene to download" as a signature content format — third-party community praise embedded in public commentary
- Third-party interview at DoubleJump Academy communicates career philosophy and technical identity — credentials validated by a third party, not self-reported
- Career arc communicates range: the fact that he moved from Maya rigger to Houdini developer to medical robotics designer is itself the portfolio story — breadth of expertise demonstrated by evolution, not by skills list


## Lo que tiene que Laia no tiene
1. **Blog técnico sostenido como portfolio piece activo**: Toadstorm tiene 50+ posts en el Nerdblog, cada uno resolviendo un problema técnico específico con código, imágenes o scene files. Laia no tiene ningún contenido publicado fuera del portfolio estático. Un post técnico de 400-600 palabras sobre una decisión de diseño del auto-rig (por qué matrix-based en lugar de constraints, cómo funciona el guide joint system) es el equivalente más accesible de este patrón — factible sin nueva funcionalidad, solo articulación escrita de lo que ya existe.
2. **Descargable o archivo compartible junto a un portfolio piece**: Toadstorm adjunta scene files descargables a sus breakdowns técnicos y la comunidad lo reconoce explícitamente por eso. Laia describe 9 tools y 7 personajes sin ningún componente verificable. Un solo descargable — un Maya file del facial rig de Freya, o el script de Auto Skin Transfer con README — transforma la descripción en evidencia verificable. No tiene que ser open-source completo: puede ser una demo limitada o un script de ejemplo.
3. **Tool con ecosistema independiente (site propio + docs + comunidad)**: MOPs tiene su propio dominio (motionoperators.com), documentación, changelog y comunidad — completamente separado del portfolio personal de Toadstorm. Laia tiene 9 tools como sección de pipeline.html. Si Auto Skin Transfer o Skin Manager tiene suficiente alcance, darle una página propia con documentación básica la transforma de "feature del pipeline" a "herramienta de producción con entidad propia" — el patrón de mayor madurez documentado en este research para comunicar una tool.


## Aplicable a Laiape.github.io
- **Publicar un post técnico (en el site o en LinkedIn) sobre una decisión de diseño del auto-rig**: elegir una decisión con un "por qué" no obvio — por qué matrix-based en lugar de constraints, por qué guide joints separados de los build joints, por qué el orden del build sequence importa. Formato Toadstorm: PROBLEMA → ALTERNATIVA CONSIDERADA → SOLUCIÓN ELEGIDA → POR QUÉ. 400-600 palabras, sin imágenes si no hay tiempo. Indexable, linkable desde pipeline.html como "Technical Notes."
- **Adjuntar un descargable mínimo a la tool más representativa**: para Auto Skin Transfer o Skin Manager, publicar en GitHub el script con README de 5-6 párrafos (problema, solución, uso, requisitos, limitaciones conocidas) y linkarlo desde pipeline.html. El modelo de Toadstorm es "scene to download" — el de Laia puede ser "script to download." Transforma pipeline.html de autodescripción en evidencia verificable.
- **Si una tool alcanza suficiente madurez, darle una URL propia**: no necesita ser un site separado inmediatamente — una página /auto-skin-transfer con nombre, problema, arquitectura, GIF de demo, y link a GitHub es suficiente para que un recruiter de herramientas llegue directamente sin navegar pipeline.html completo. El path a motionoperators.com empezó como un tool bien documentada antes de tener su propio site.


## Fuente
https://www.toadstorm.com/