---
url: http://morganloomis.com
found: 2026-09-16
category: portfolio
credits: Charlotte's Web (Rigger, Animator), The Spiderwick Chronicles (Rigger, Animator), Cats and Dogs 2 (Puppet Lead, Animator), Santa Clause 3 (Rigger), Beverly Hills Chihuahua (Animator), Spore (Lead Rigger), varios commercials (Milka, Quaker State)
tags: rigging, animation, pipeline, portfolio, maya, python, tools, new-zealand, open-source, ml-tools, mit-license, animator, puppet-lead
status: NEW
---


# Morgan Loomis — Animation | Rigging | Pipeline (morganloomis.com)


## Perfil profesional
Morgan Loomis es un Rigger/Animator/Pipeline Developer basado en Nueva Zelanda con más de 20 años en la industria (activo desde 2005). Sus créditos como rigger incluyen The Spiderwick Chronicles, Charlotte's Web, Santa Clause 3, y Spore (Lead Rigger). También tiene créditos de Puppet Lead en Cats and Dogs 2, lo que indica que ha gestionado tanto el rigging como el trabajo de puppet técnico. Su tagline de site es "Animation | Rigging | Pipeline" — tres áreas declaradas explícitamente. Es el autor de ml_tools, una colección de 50+ herramientas de Maya para animación y rigging disponibles en GitHub (github.com/morganloomis/ml_tools, 243 stars, 72 forks, licencia MIT). Su valor como referencia es el modelo de site con pages dedicadas por área y la estrategia de distribución de tools como recursos de comunidad.


## Estructura del portfolio
morganloomis.com es un site con páginas separadas por función:
- **/** — Home
- **/reel/** — Reel dedicado con breakdown enlazado en Zerply
- **/tools/** — Página de tools que lista las herramientas por categoría
- **/tool/[nombre]/** — Página individual por herramienta (e.g. /tool/ml_centerOfMass/, /tool/ml_utilities/) con descripción propia
- **/about/** — Bio personal
- Blog con entradas sobre tools (e.g., "ml_dynamics Licence Change", "Tools Update and Shelf Added")


Tres características estructurales destacables: (a) cada tool tiene su propia URL (/tool/nombre/), lo que permite indexación individual en búsquedas; (b) ml_dynamics (secondary motion/XPBD simulation) fue movido a un repositorio GitHub separado (anim_dynamics), señalando disciplina de refactorización cuando una tool crece; (c) el tagline del site aparece en el browser tab como "Morgan Loomis – Animation | Rigging | Pipeline", un meta-positioning explícito.


## Cómo presenta los proyectos
- El reel (/reel/) es una página dedicada con el vídeo embebido y un breakdown externo en Zerply
- Las tools no tienen vídeo demo — tienen descripción escrita y la disponibilidad en GitHub con el código como evidencia
- Los créditos de film no se presentan como case studies separados sino agrupados en el About/Zerply
- Los blog posts sobre tools (e.g., "ml_dynamics Licence Change") informan del estado del desarrollo — sirven como changelog público


## Cómo comunica sus skills
- El tagline tripartito ("Animation | Rigging | Pipeline") comunica scope inmediatamente
- La lista de tools en /tools/ categorizada (Animation, Rigging, Skinning, Utility) comunica profundidad en cada área
- ml_tools en GitHub con 243 stars actúa como proof-of-work visible: una herramienta con 243 stars es una herramienta que otros profesionales usan en producción
- Zerply profile enlazado desde el reel con breakdown adicional de créditos
- No tiene skill bars, no tiene logos — la profundidad se comunica por la masa de herramientas y la calidad de los créditos


## Lo que tiene que Laia no tiene


1. **URL individual por herramienta (/tool/nombre/)**: Morgan tiene no solo /tools como landing page sino una sub-URL para cada tool. Esto tiene dos consecuencias prácticas: (a) cada tool es indexable en búsquedas por nombre ("ml_centerOfMass Maya") y puede aparecer en resultados de búsqueda independientemente del portfolio; (b) cada tool puede ser enlazada directamente — un reclutador puede mandar a un hiring manager el link directo a una tool específica. Las 9 tools de Laia en pipeline.html son inaccesibles individualmente. Añadir anclas con ID (#auto-skin-transfer, #skin-manager) es el mínimo viable; crear pages individuales sería el equivalente completo.


2. **Tagline estructurado como declaración de scope tripartita en el browser title**: morganloomis.com aparece en el tab del navegador como "Morgan Loomis – Animation | Rigging | Pipeline". Laia tiene su site con title genérico. Cambiar el <title> del site a "Laia Peris — Rigging TD | Python Tools | Auto-Rig Pipeline" haría que cualquier persona que tenga el tab abierto viera el positioning exacto, y que el site apareciera en búsquedas de Google con esa descripción como rich snippet. Es un cambio de una línea en el HTML con impacto en SEO y en percepción.


3. **Comunidad de herramientas como señal de adopción industrial** (ml_tools con 243 stars): Morgan no dice "hago buenas tools" — lo dice el número de stars y forks en GitHub. Laia menciona tools pero no tiene ninguna publicada en GitHub. Publicar Auto Skin Transfer en GitHub con un README bien escrito (descripción del problema, instalación, use cases, ejemplos) y enlazarlo desde pipeline.html añadiría el primer dato verificable de adopción externa al portfolio. Incluso con 0 stars al principio, la herramienta en GitHub es descubrible vía búsqueda — "maya skin transfer topology tool python" lleva a repositorios.


## Aplicable a Laiape.github.io


- **Cambiar el <title> del HTML** de laiape.github.io a "Laia Peris — Rigging TD | Auto-Rig Pipeline | Python Tools for Maya". Un cambio de una línea que afecta: tab del navegador, Google rich snippet, og:title para compartir en redes.
- **Añadir anclas con ID a cada tool en pipeline.html** para que las URLs laiape.github.io/pipeline.html#auto-skin-transfer sean funcionales. Paso siguiente: convertir cada tool en una página propia o un modal con URL única.
- **Publicar ml_tools equivalente en GitHub**: crear un repo python-maya-tools o similar con al menos Auto Skin Transfer y Skin Manager, README completo, y enlace desde pipeline.html. El objetivo es que el trabajo sea verificable externamente, no solo declarado.


## Fuente
http://morganloomis.com


*Nota: el site principal estaba inaccesible durante el análisis por restricciones de red del entorno. El análisis es de search snippets, Zerply profile, y el repositorio github.com/morganloomis/ml_tools (accedido directamente vía WebFetch).*