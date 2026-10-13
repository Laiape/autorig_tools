---
url: https://github.com/tpoveda
found: 2026-10-07
category: portfolio
credits: That's No Moon (Senior Animation TD), Ubisoft (Beyond Good & Evil 2, Assassin's Creed III Remastered), Counterplay Games (Rogue Company era), Promethean AI, Artella
tags: rigging, td, pipeline, python, open-source, github, animation-pipeline, dcc-agnostic, unreal-engine, game-AAA
status: NEW
---


# Tomás Poveda — Senior Animation TD / Pipeline TD


## Perfil profesional
Tomás Poveda es un Senior Animation TD y desarrollador de software especializado en pipelines de animación y herramientas DCC, con sede en Alicante, España. Actualmente trabaja en That's No Moon (desde febrero de 2023), estudio AAA conocido por proyectos AAA en Unreal Engine. Previamente: Counterplay Games (pipeline DCC-agnostic de cero), Ubisoft (Beyond Good & Evil 2 — character pipeline tooling + cross-DCC I/O; Assassin's Creed III Remastered — outfit rigging + cloth in-engine). También freelance en Promethean AI, Artella y mcsGear. Ha publicado 89 paquetes en PyPI bajo su framework tpDcc.


## Estructura del portfolio
- GitHub profile (github.com/tpoveda) como portfolio primario — no tiene web personal conocida
- 18 repositorios públicos organizados por función: framework base (tp-dcc), rigging toolkit (tp-rigtoolkit), tools individuales (tpJointOrient, tpColorChanger, tpFlexiLineRig), integraciones (ueGear = Maya/Unreal, xnormal-batch-baker)
- README del perfil como bio + positioning statement: "building artist-friendly tools, robust pipelines, and reliable services so teams can move faster"
- PyPI profile con 89 paquetes publicados como evidencia de adopción distribuible
- Sin página de about, sin reel, sin breakdown de personajes — portfolio 100% orientado a evidencia de tooling


## Cómo presenta los proyectos
Cada repositorio tiene:
- Descripción de una línea que nombra el problema que resuelve, no el nombre del autor
- README con contexto de uso y, para los frameworks, arquitectura de módulos
- Licencia MIT explícita en todos los repositorios públicos
- Studio context integrado en el README del perfil (no en páginas separadas): "Beyond Good & Evil 2 — character pipeline tooling, cross-DCC data I/O" / "Built modular, DCC-agnostic pipeline from ground up" (Counterplay)
- Stars y forks como métricas de adopción: tp-dcc (16 stars, 2 forks), tpJointOrient (18 stars, 5 forks), xnormal-batch-baker (16 stars, 3 forks)
- Para Ubisoft específica título del juego, tipo de trabajo y tecnología usada — sin NDA evasivo


## Cómo comunica sus skills
- No tiene skills list explícita — las skills están implícitas en los repos
- El alcance DCC-agnostic es el claim principal: "tools that work under any DCC that supports Python 3"
- PyPI publication (89 paquetes) como diferenciador: cualquier rigger puede `pip install` una herramienta suya — eso es adopción verificable, no solo un claim
- GitHub stars como signal de utilidad comunitaria (no espectacular en número, pero presentes y verificables)
- Unreal Engine mencionado explícitamente (ueGear: Maya/UE integration) — señal de game pipeline breadth
- OpenMaya API / Maya API 2.0 implícito en las implementaciones (no explicitado en bio)
- No cuantifica nada más allá de repos y estrellas


## Lo que tiene que Laia no tiene
1. **Paquetes en PyPI como artefacto verificable e instalable**: Tomás tiene 89 paquetes publicados en pypi.org/user/tpoveda — cualquier recruiter o rigger puede ejecutar `pip install tp-dcc` y comprobar que funciona. Laia describe 9 tools en pipeline.html pero ninguna es instalable ni descargable públicamente. El gap no es solo visibilidad — es la diferencia entre "claim de herramienta" y "herramienta que alguien puede usar ahora mismo".


2. **"Built from ground up" como claim de ownership explícito por proyecto**: Para cada studio, Tomás especifica qué construyó de cero vs qué mantuvo ("Built modular, DCC-agnostic pipeline from ground up" en Counterplay). Laia no diferencia entre tools creadas desde cero y tools que puedan ser extensiones o mantenimiento — lo cual deja la escala de contribución ambigua.


3. **Alcance cross-DCC como positioning diferenciador**: La descripción "DCC-agnostic framework" es un nivel de ingeniería superior a "Maya Python tools". Incluso si el 95% del trabajo de Laia es Maya-only, hay preguntas honestas: ¿la arquitectura de sus tools es DCC-agnóstica internamente? ¿alguna tool funciona fuera de Maya? La respuesta podría generar un claim real de breadth.


## Aplicable a Laiape.github.io
- Publicar Auto Skin Transfer en PyPI con un nombre de paquete propio (ej. `maya-auto-skin-transfer`) — incluso con 0 descargas, la URL pypi.org/project/nombre-tool/ es un artefacto verificable que refuerza el claim de las otras 8 tools
- Añadir lenguaje de ownership explícito en pipeline.html: "Diseñado e implementado desde cero" vs "adaptación de workflow existente" — la distinción dice al recruiter qué hizo Laia vs qué aprendió de otro
- Revisar si alguna tool tiene potencial de uso fuera de Maya (ej. Curve Library con formato de datos exportable, Model Checker con output en JSON) — si existe esa posibilidad, declararlo como "compatible con exportación a cualquier DCC via ..."


## Fuente
https://github.com/tpoveda