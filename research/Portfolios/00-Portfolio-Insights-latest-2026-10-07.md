# Portfolio Insights — Laia Peris Research


Archivo de síntesis semanal de investigación de portfolios de riggers y TDs de referencia.


Objetivo: identificar patrones de contenido aplicables a laiape.github.io para posicionarse en estudios AAA/VFX.


*(Nota: las entradas anteriores a 2026-09-02 están en el archivo `00 - Portfolio Insights (Archivo hasta 2026-08-26).md` en la misma carpeta de Google Drive.)*


---


### 2026-10-07 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Tomás Poveda (github.com/tpoveda — Senior Animation TD, That's No Moon/Ubisoft; 89 paquetes en PyPI; frameworks DCC-agnostic tp-dcc + tp-rigtoolkit + ueGear), Mathieu Schmit/CG-WESK (github.com/wesk-fr — Rigging Lead TAT Productions; weSkel modular framework + weSkel Pushers quaternion RBF pose driver), Martin L'Anton (zerply.com/martin-lanton — Rigging Pipeline TD Animal Logic / Technical Artist EA; diseño de rigging publish+review process; instructor CG Master Academy), Nazmi Yazici (zerply.com/nazmi-yazici — Senior Rigging TD Cinesite/MPC; Snow White 2025, Nautilus 2024, KAOS 2024, The Family Plan 2023, True Detective 2024)


**Patrones de contenido más comunes encontrados esta semana:**


- Herramientas publicadas en PyPI como artefacto verificable e instalable — presente en 1/4 (Tomás Poveda: 89 paquetes en pypi.org/user/tpoveda — cualquier recruiter puede ejecutar `pip install tp-dcc` y verificar que el framework funciona) — nuevo en esta semana: primera aparición de PyPI como canal de distribución de tools de rigging en portfolios analizados; distinto de GitHub (código público) porque PyPI implica packaging, versionado semántico y documentación de dependencias — tres señales de engineering maturity que GitHub solo no implica


- Nombre de marca propio para sistema de correctives/RBF — presente en 1/4 (Mathieu Schmit: "weSkel Pushers — quaternion RBF pose driver" — tres capas: nombre de producto + técnica de implementación + descripción de caso de uso) — recurrente (Tim Petre 09-16: "Method's custom RBF interpolator" nombrado; Richard Stubbs 09-09: autorig con feature list; Robert Joosten 07-01: documentation site por tool) pero nuevo el formato nombre-de-producto + técnica-exacta + descripción-de-uso-caso en una sola frase; la combinación hace al sistema memorable, propietario y técnicamente evaluable de forma independiente del portfolio completo


- "Rigging publish and review process" como skill diferenciadora de pipeline TD — presente en 1/4 (Martin L'Anton: "design and maintenance of the rigging publish and review process, interaction between the rigging pipeline and the rest of the pipeline" en Animal Logic) — nuevo: primera aparición explícita del diseño del proceso de publicación/validación de rigs como competencia declarada; los portfolios analizados previos describen creación de rigs y herramientas pero ninguno documenta cómo esos rigs se validan y publican dentro del pipeline de producción


- Créditos de producción VFX nombrados con año como firma estándar de cada rig — presente en 1/4 (Nazmi Yazici: 5 producciones nombradas en 3 años — Snow White 2025, Nautilus 2024, KAOS 2024, The Family Plan 2023, True Detective 2024 — con studio asociado) — recurrente (Tim Petre 09-16: Godzilla/Avengers/Transformers; Bjørn Blaabjerg 09-02: ILM/MPC/DNEG) pero nuevo el framing producción+año+studio como firma por deliverable individual en perfil de nivel mid-senior (no solo Lead/Supervisor)


**Top 3 ideas aplicables a Laia esta semana:**


1. **Publicar Auto Skin Transfer en PyPI con nombre de paquete propio — `pip install maya-auto-skin-transfer` como primer artefacto verificable e instalable del portfolio** (patrón de Tomás Poveda — la brecha más concreta entre lo que Laia describe en pipeline.html y lo que cualquier recruiter técnico puede verificar en 30 segundos)


Poveda tiene 89 paquetes en PyPI. La cifra no es lo importante — lo importante es que cada paquete tiene: URL propia (pypi.org/project/nombre/), historial de versiones, instrucción de instalación, y archivo pyproject.toml que documenta dependencias. Esas cuatro cosas convierten una descripción de tool en un artefacto de ingeniería verificable. Para Laia, publicar Auto Skin Transfer en PyPI con el nombre `maya-auto-skin-transfer` no requiere que nadie la instale para que tenga impacto — la URL existe, el README está ahí, la versión 0.1.0 dice que existe. El coste es 2-3 horas de packaging (pyproject.toml + README + setup). El impacto es que cualquier recruiter técnico que duda de si Laia "de verdad hizo la tool" puede comprobarlo.


2. **Dar nombre propio al sistema de correctives/RBF de Laia y documentarlo con técnica nombrada** (patrón de Mathieu Schmit — el cambio de descripción con mayor impacto diferenciador sobre la competencia técnica que Laia ya tiene)


weSkel Pushers tiene nombre, técnica (quaternion RBF) y descripción de uso (pose driver). Laia menciona "RBF/SDK correctives" en pipeline.html pero como técnica genérica. La diferencia: "uso RBF correctives" describe lo que hace; "LaiaPRS — Pose-Relative Solver, implementación de RBF radial basis function para corrective shapes en biped y cuadrúpedo" describe qué construyó. No necesita ser un framework completo — basta con dar nombre propio al sistema, nombrar la técnica matemática exacta, y describir los tipos de rig para los que está validado. Con esa descripción, el sistema de correctives de Laia es evaluable de forma independiente del reel.


3. **Añadir contexto de producción mínimo a cada personaje en pipeline.html — aunque sea "Personal project, 2024" o "Commissioned rig, NDA"** (patrón de Nazmi Yazici — el cambio de menor coste y mayor signal para recruiters VFX que aún no está en el portfolio)


Yazici tiene Snow White (2025), Nautilus (2024), KAOS (2024). Laia tiene Freya, Mechanic, Thaiz, Jamal, Maui, Moana, Giraffe — sin ningún contexto temporal ni de producción. Para un recruiter de DNEG o Framestore, la primera pregunta es: ¿son estos personajes de producción real o portfolio personales? La ausencia de contexto se interpreta como portfolio académico. Añadir "Personal project, 2024" o "Portfolio character, based on original design" convierte la ambigüedad en información. El coste es cero horas de creación — es solo añadir una línea por personaje.


---


### 2026-09-16 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Tim Petre (timpetrecg.com — Lead Creature TD, ILM/Method Studios/Digital Domain, HoYoverse; créditos: Godzilla, Avengers, Transformers), Cole O'Brien (coleobrienart.com — Technical Animator, Avalanche Studios/Just Cause 4; tool: Rigloo MIT open source), Morgan Loomis (morganloomis.com — Rigger/Animator/Pipeline, Nueva Zelanda; ml_tools 50+ herramientas GitHub 243 stars), CreatureFX (creature-fx.com — Lead CFX TD anónimo, Image Engine/MPC, Vancouver/Londres; muscles+cloth+hair+tech anim+facial+puppet)


**Patrones de contenido más comunes encontrados esta semana:**


- Reel breakdown escrito por segmento con herramientas propietarias nombradas — presente en 1/4 (Tim Petre: /reel con párrafo por proyecto especificando personaje, técnica, tool de producción; "pose space deformation for shoulders, elbows, wrists" / "Zeno, ILM's proprietary 3D software" / "Method's custom RBF interpolator") — recurrente (Richard Stubbs 09-09: vídeo separado por tool; Noreen Qureshi 09-09: workflow cross-software documentado con steps) pero nuevo el uso de nombres de herramientas propietarias de estudio como evidencia de experiencia en pipeline real; "RBF interpolador" nombrado es una señal diferente de "uso correctives" — demuestra que el rigger operó dentro de un studio pipeline específico


- Case study separado por tipo-de-trabajo dentro del mismo proyecto — presente en 1/4 (Cole O'Brien: coleobrienart.com/2018/10/17/jc4-rigging/ y /jc4-pipeline-tools/ son dos entradas independientes para el mismo proyecto Just Cause 4 — el rigging artístico y el tooling de pipeline tienen URLs propias) — recurrente (Noreen Qureshi 09-09: workflow Maya→Houdini→Maya documentado por pasos; Robbie Reid 09-02: YouTube separado de ArtStation como canal de tools) pero nuevo la separación DENTRO del mismo proyecto — el reclutador puede ver "JC4 Pipeline Tools" de forma independiente de "JC4 Rigs" sin tener que leer el caso completo


- URL individual por herramienta como estrategia de indexación independiente — presente en 1/4 (Morgan Loomis: morganloomis.com/tool/ml_centerOfMass/, /tool/ml_utilities/ — cada tool tiene su propia URL propia) — recurrente (Robert Joosten 07-01: documentation site para tool; Adien Dendra 07-15: subdominio separado para tools; Benoit Gielly 08-05: GitHub como portfolio primario) pero nuevo el formato /tool/nombre/ dentro del dominio personal como micro-site por herramienta; permite indexación en búsquedas por nombre de tool individual


- Career arc narrative en el bio como evidencia de capacity for growth — presente en 1/4 (creature-fx.com: "started as a junior rigger, grew their portfolio, learned to code, and led their own shows quickly" — cinco hitos de crecimiento en una frase) — recurrente (Bjørn Blaabjerg 09-02: bio como capítulos de carrera con studio names como hitos; Kiel Figgins 08-26: cronología visible como seniority signal) pero nuevo el framing de self-improvement explícito ("learned to code", "led their own shows") como diferenciador vs solo listar créditos cronológicos; la narrativa de crecimiento responde implícitamente a "¿puede crecer con nosotros?"


- matrix-based constraints implementados en código públicamente legible como evidencia verificable de técnica — presente en 1/4 (Cole O'Brien: rigtools.py implementa parentConstraint via multMatrix + decomposeMatrix con comentarios paso a paso — la misma técnica que Laia usa pero en código cloneable) — nuevo: primera aparición de código público que implementa explícitamente matrix-based rigging con comentarios didácticos; la diferencia entre "uso matrix rigging" (claim) y código que lo demuestra en un repo público (evidencia) es la diferencia entre un portfolio y un portafolio técnico verificable


**Top 3 ideas aplicables a Laia esta semana:**


1. **Añadir reel breakdown escrito bajo el hero — un párrafo por personaje del reel con técnicas nombradas por nombre técnico exacto** (patrón de Tim Petre — el cambio de menor costo y mayor impacto en credibilidad técnica del portfolio actual de Laia)


Tim Petre escribe bajo cada segmento del reel: "pose space deformation setup for shoulders, elbows, wrists, knees, ankles and neck using Method's custom RBF interpolator and the morph plugin from SOuP" — el nombre técnico exacto de la técnica y la herramienta de producción. Laia tiene el reel embebido en el hero sin ningún texto que explique qué se ve. Para los 7 personajes del reel de Laia (Freya, Mechanic, Thaiz, Jamal, Maui, Moana, Giraffe), añadir una línea por personaje bajo el reel con formato "Nombre — Sistemas: [IK/FK biped/quad, facial jaw/eyes/teeth/tongue/lips, RBF correctives, matrix-based rigging], Software: Maya [versión], Python [versión]" transformaría el reel de black box en evidencia técnica que un senior recruiter puede escanear sin pausar el vídeo. Coste: 2-3 horas de escritura + HTML. Impacto: el reel pasa de ser una pieza visual a ser un documento técnico con evidencia por plano.


2. **Publicar Auto Skin Transfer en GitHub con README completo (filosofía, features, inspiración nombrada, instalación) y enlazarlo desde pipeline.html** (patrón convergente de Cole O'Brien y Morgan Loomis — ambos confirman en la misma semana que herramientas bien documentadas en GitHub consiguen tracción comunitaria)


Cole O'Brien's Rigloo (MIT, 2017) nombra en el README la GDC 2017 de Blizzard sobre Overwatch como inspiración del diseño. Morgan Loomis's ml_tools (MIT, 2015+) tiene 243 stars y 72 forks porque la colección es útil para cualquier rigger de Maya. La diferencia entre "tengo una tool de auto skin transfer" (claim en pipeline.html) y "github.com/laiape/auto-skin-transfer — MIT, 87 stars" (evidencia) es la que separa un portfolio de entry-level de uno de TD. El README necesita: (a) descripción del problema (transferencia entre topologías distintas), (b) algoritmo en una frase, (c) instalación, (d) use cases con antes/después, (e) licencia. El coste es 4-6 horas. El beneficio es un primer dato verificable de adopción comunitaria que crece solo.


3. **Añadir anclas con ID a cada tool en pipeline.html para crear URLs enlazables individuales — primer paso hacia /tool/nombre/** (patrón de Morgan Loomis — cambio técnico de 30 minutos que multiplica la utilidad del pipeline.html actual)


Morgan Loomis tiene morganloomis.com/tool/ml_centerOfMass/ — una URL por herramienta. El equivalente inmediato para Laia es añadir `id="auto-skin-transfer"` a cada sección de tool en pipeline.html, lo que crearía URLs funcionales del tipo laiape.github.io/pipeline.html#auto-skin-transfer. Esto tiene tres beneficios inmediatos: (1) el reclutador puede compartir una tool específica con un hiring manager sin pedirle que busque en la página; (2) Google indexa cada tool individualmente como fragmento; (3) es el primer paso hacia páginas individuales por tool si Laia decide expandir el portfolio. Coste: 30 minutos añadiendo atributos id a los elementos existentes.


---


### 2026-09-09 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Jordan Dion-Duval (jordandd.artstation.com — Rigger/Technical Animator, Ubisoft GameLab), Noreen Qureshi (noreenqureshi.com — Character TD / Creature FX, actualmente en Autodesk), Mr. Paween (mrpaween.com — Character TD, The Monk Studios Thailand / Rango), Richard Stubbs (artstation.com — Technical Rigger, muscle tools + modular Python autorig)


**Patrones de contenido más comunes encontrados esta semana:**


- Vídeo de breakdown dedicado por herramienta individual, enlazado directamente desde el reel con timestamp — presente en 1/4 (Richard Stubbs: dos vídeos de Vimeo separados, uno por herramienta principal, enlazados desde la descripción de la entry del reel con referencia cruzada explícita "more detailed breakdown at vimeo.com/...") — recurrente (Robbie Reid 09-02: YouTube channel de demos; Henry Foster 07-22: blog con escenas descargables; Jordan Dion-Duval 09-09: Vimeo channel para vídeos de proyectos) pero nuevo el formato de 1 vídeo de breakdown por herramienta + timestamp cruzado en el reel como estructura estándar; el reclutador puede ir de "veo la herramienta en el reel" a "veo el breakdown técnico completo" en un clic, sin buscar en el site


- Resume page dedicada en el portfolio site como URL accesible sin descarga — presente en 1/4 (Mr. Paween: /resume como página del site con experiencia cronológica por estudio) — recurrente (Carlos Contreras 05-06: resume page; Tim Coleman 07-01: zerply con resume section) pero nuevo como patrón de site personal; todos los demás lo tienen en plataformas de terceros (Zerply, LinkedIn, ArtStation) pero no en el propio site — /resume en el site propio elimina friction para hiring managers y mantiene al reclutador en el portfolio del artista


- Escala de impacto de empresa en una frase ("rig base usada para TODOS los personajes bípedos de la empresa") — presente en 1/4 (Mr. Paween: "base character rig used for every biped character" en Index Creative Village — la frase convierte un rig individual en evidencia de arquitectura de pipeline adoptada por producción) — nuevo: primera aparición de una declaración de escala de adopción de empresa en portfolios analizados; la diferencia entre "hice un rig" y "hice el rig que usa toda la empresa" es la diferencia entre habilidad técnica y impacto de pipeline


- Workflow cross-software documentado con pasos explícitos e inputs/outputs nombrados — presente en 1/4 (Noreen Qureshi: "animé el personaje en poses de test → importé a Houdini para weight painting → re-importé a Maya → espejar pesos en Z-Axis" — cada paso nombra herramienta, operación y output) — recurrente (Robbie Reid 09-02: Ziva VFX → corrective shapes → skinned mesh; Robert Joosten 07-01: "automate detection of new/removed/updated cogs" con tool de entrada y formato de output) pero nuevo el cross-software Maya→Houdini→Maya como diferenciación técnica; el paso de ir a Houdini para weight painting es no convencional y señala breadth de toolkit más allá del pipeline estándar Maya-only


- Animación propia sobre el rig como evidencia cruzada de usabilidad — presente en 1/4 (Jordan Dion-Duval: personaje Waldo rigeado Y animado por el mismo artista — facial expressions + fonemas — demostrando comprensión de necesidades del animador desde dentro) — recurrente (Deer Stranger 07-29: rigging y animación de personajes propios; Martin Savio 07-08: personajes rigeados con animación de test propia) pero nuevo el framing explícito de "lo rigé y lo animé yo mismo" como señal de comprensión downstream del rig; el artista que puede animar su propio rig demuestra que lo diseñó pensando en el animador


- Feature list granular de sistema de rigging como checklist de completitud — presente en 1/4 (Richard Stubbs: autorig descrito con "IK/FK snapping, elbow/knee pinning and sliding, soft IK" — cada sub-feature como línea separada) — recurrente (Bram Van Rompuy 07-01: features de tool por punto; Sean Teo 08-05: features de rig facial por componente) pero nuevo el uso de feature list como estrategia de portfolio para sistemas de rigging; "IK/FK Match" como nombre de herramienta no dice nada sobre su completitud, pero "IK/FK snap, elbow pinning, soft IK, world/local space switch" sí — es el equivalente rigging de una tabla de especificaciones de producto


**Top 3 ideas aplicables a Laia esta semana:**


1. **Grabar un vídeo de demo de 2-3 minutos por herramienta — empezando por Auto Skin Transfer o IK/FK Match — mostrando input → proceso → output, publicado en Vimeo y enlazado desde pipeline.html** (patrón de Richard Stubbs — la adición de contenido con mayor ratio impacto/esfuerzo que queda por hacer en el portfolio actual)


Stubbs tiene para cada herramienta: (a) segmento en el reel con timestamp, (b) vídeo separado de Vimeo con breakdown completo, (c) descripción que invita activamente al reclutador a ver el breakdown. Las 9 tools de Laia en pipeline.html existen solo como texto. Un reclutador técnico que ve "Auto Skin Transfer — transfiere pesos entre meshes de topología diferente" no puede verificar si funciona, qué interface tiene, qué hace con casos límite, o qué tan rápida es. Un vídeo de 2-3 minutos de Auto Skin Transfer en acción — seleccionar mesh origen → ejecutar transfer → mostrar resultado en mesh de topología diferente — transforma una afirmación en evidencia. El coste de producción es bajo (screen recording + narración o texto en pantalla), el impacto en credibilidad es alto.


2. **Añadir feature list granular a cada sistema de rigging en pipeline.html — no el nombre de la tool sino la lista de sub-features que la componen** (patrón de Richard Stubbs — el cambio de descripción que más directamente responde a las preguntas técnicas de un reclutador senior)


El pipeline.html de Laia describe las tools por función ("IK/FK Match — permite al animador hacer match entre IK y FK"). Un senior rigger o TD que lee esto no sabe si el sistema incluye: snap bidireccional FK→IK e IK→FK, funcionamiento en world space vs local space, compatibilidad con pole vector custom, snap en frame exacto vs interpolado. Estos detalles son las preguntas técnicas de una entrevista de rigging. Listarlos en pipeline.html — como hace Stubbs para su autorig — transforma la descripción de tool en una checklist de completitud que un reclutador experto puede evaluar en 30 segundos.


3. **Añadir una página /resume al site laiape.github.io con experiencia cronológica accesible desde la navegación** (patrón de Mr. Paween — el cambio estructural de menor costo y mayor utilidad para recruiters que aún no está en el portfolio)


El patrón más común en portfolios senior es tener /resume o /cv como URL propia del site, no solo como PDF descargable en un dropbox o separado. Mr. Paween tiene /resume en mrpaween.com. En laiape.github.io la navegación actual incluye home, pipeline, about — pero no resume. Para un reclutador que llega al portfolio y quiere saber el historial de experiencia sin salir del site, la ausencia de /resume es un punto de fricción.


---


### 2026-09-02 — Weekly Portfolio Research
- Portfolios analizados: 3
- Archivos escritos: 3
- Portfolios: Bjørn Blaabjerg Sørensen (blaabjergb.com — ILM/MPC/DNEG Creature TD), Robbie Reid (robbiereid.artstation.com — Method Studios Senior Rigging TD), Colin Kennedy (colinkennedy.github.io — Lead Pipeline Engineer The Mill/MPC)


**Patrones de contenido más comunes encontrados esta semana:**


- Narrativa de carrera cronológica como contenido central del About — presente en 2/3 (Bjørn Blaabjerg: bio estructurada como capítulos de carrera con studio names como hitos, no lista de skills; Robbie Reid: YouTube channel y Gumroad como extensión narrativa del trajectory freelance) — recurrente (Kiel Figgins 08-26: cronología visible como seniority signal; HAT Rigs 05-13: progresión cronológica como narrativa) pero nuevo el formato de bio como "career story" explícita donde cada studio es un capítulo, no solo un ítem de CV


- Plataforma institucional de terceros como canal de distribución de tutoriales — presente en 1/3 (Bjørn Blaabjerg: tutorial publicado en SideFX Learn, la plataforma oficial de Houdini — la plataforma valida al autor, no el autor a la plataforma) — nuevo: primera aparición de distribución en plataforma institucional oficial del proveedor de software (SideFX, Autodesk, Epic) como señal de credibilidad diferente de ArtStation, YouTube propio o blog personal


- Rig descargable gratuito con especificaciones técnicas game-engine-ready como portfolio entry point — presente en 1/3 (Robbie Reid: Guardian rig — 154 joints, 4 max influences, game-engine compatible — en Gumroad gratuito) — recurrente (HAT Rigs 05-13: rig descargable con specs; Kiel Figgins 08-26: Free Rigs section; J Reinhart 07-29: Gumroad) pero nuevo el framing de especificaciones game-engine-ready como señal explícita de AAA readiness; el joint count y max influences no son datos técnicos sino demostración de comprensión del pipeline downstream completo


- Ziva-to-corrective workflow como técnica documentada con inputs y outputs explícitos — presente en 1/3 (Robbie Reid: "Ziva VFX muscle simulation → corrective shapes extraction → skinned character mesh" como pipeline documentado con herramienta de entrada y formato de output) — nuevo: primera aparición de un workflow de simulación muscular documentado como pipeline con inputs/outputs específicos


- YouTube como canal de demos de herramientas separado del demo reel principal — presente en 1/3 (Robbie Reid: @RobbieReidRigs con demos de tools propias, separado del ArtStation con el trabajo de producción) — recurrente (Henry Foster 07-22: blog con escenas descargables como canal separado) pero nuevo el uso de YouTube específicamente como canal de demos de tools


- GitHub como portfolio primario sin website personal — presente en 1/3 (Colin Kennedy: colinkennedy.github.io como landing mínima que apunta a github.com/ColinKennedy con 146 repos) — recurrente (Benoit Gielly 08-05: GitHub como evidencia principal; James Dunlop 05-06: jamesbdunlop.github.io) pero nuevo en escala: 146 repos públicos como evidencia acumulada de tool development multi-año


**Top 3 ideas aplicables a Laia esta semana:**


1. **Publicar al menos un rig descargable gratuito en Gumroad o GitHub con especificaciones game-engine-ready explícitas** (patrón de Robbie Reid — el elemento de portfolio que más directamente demuestra AAA readiness a un recruiter técnico que no puede ver el código fuente del auto-rig)


2. **Documentar el workflow completo de correctives en pipeline.html como secuencia de pasos con inputs y outputs nombrados** (patrón de Robbie Reid — el tipo de contenido técnico más buscado en portfolios VFX y el más ausente en el portfolio actual de Laia)


3. **Publicar Auto Skin Transfer en GitHub como recurso de comunidad con documentación diseñada para ser usada por otros riggers, no solo como evidencia del propio trabajo** (patrón de Colin Kennedy's USD-Cookbook)


---


### 2026-08-26 — Weekly Portfolio Research
- Portfolios analizados: 4 · Archivos escritos: 4
- Portfolios: Jairo Alzate (jairoalzate.xyz), Maurofreecg Rigger (maurofreecgrigger.artstation.com), Scott Woodhams (scottwoo.artstation.com + temperancetechart.substack.com), Kiel Figgins (3dfiggins.com)
- Top 3: (1) Añadir motor de juego/pipeline downstream a cada entry de personaje y tool; (2) Añadir production origin story a al menos 3 tools; (3) Publicar writeup técnico autónomo de 400-600 palabras con URL propia.


### 2026-08-19 — Weekly Portfolio Research
- Portfolios analizados: 4 · Archivos escritos: 4
- Portfolios: Iker J. de los Mozos (artstation.com/ikerclon), Nick Van Diem (zerply.com/nicko), Lukas Bilek (zerply.com/lukas-bilek), David Lantos (zerply.com/imp99)
- Top 3: (1) Describir stack técnico de deformación por personaje; (2) Especificar nivel de implementación técnica por tool (cmds vs OpenMaya API); (3) Añadir declaración de estándar de output a About page.


### 2026-08-12 — Weekly Portfolio Research
- Portfolios analizados: 4 · Archivos escritos: 4
- Portfolios: Nims Bun (Framestore), Sebastian Cisneros (rigsbycisneros.com), Valentin Procida (Storm Studios), Ian Woskey (iancw.com)
- Top 3: (1) Añadir specs cuantificadas al menos a un rig; (2) Reformular auto-rig como pregunta de investigación con hipótesis; (3) Añadir testimonials con 2-3 citas de colaboradores.


### 2026-08-05 — Weekly Portfolio Research
- Portfolios analizados: 4 · Archivos escritos: 4
- Portfolios: Areeba Rikhan (areebarikhan.artstation.com), Sean Teo (seant3o.artstation.com), Drago Avdalovic (creativerigs.com), Benoit Gielly (github.com/BenoitGielly)
- Top 3: (1) Añadir constraint técnico específico de cada personaje; (2) Publicar Auto Skin Transfer en GitHub con commits regulares; (3) Registrar dominio personalizado con "td"/"rigging"/"pipeline".


### 2026-07-29 — Weekly Portfolio Research
- Portfolios analizados: 3 · Archivos escritos: 3
- Portfolios: Ernesto Ruiz Velasco (ernesto.ruizvelasco.com), J Reinhart (jreinhart.gumroad.com), Martin Gunnarsson / Deer Stranger (vimeo.com/deerstranger)
- Top 3: (1) Nombrar etapas del auto-rig con secuencia de palabras; (2) Añadir breakdown de 4-6 componentes técnicos al personaje más complejo; (3) Publicar herramienta en Gumroad (free) con README de 5 párrafos.


### 2026-07-22 — Weekly Portfolio Research
- Portfolios analizados: 4 · Archivos escritos: 4
- Portfolios: Brittany McGrath (brittanymcgrath.com), Walt Hyneman (walthyneman.com), Henry Foster / Toadstorm (toadstorm.com), Jose Antonio Martin Martin (domestika.org)
- Top 3: (1) Añadir página /breakdown con descripción por segmento del reel; (2) Añadir frase de pitch/autoría a intro de cada sección; (3) Publicar descargable mínimo junto a la herramienta más representativa.


### 2026-07-15 — Weekly Portfolio Research
- Portfolios analizados: 4 · Archivos escritos: 4
- Portfolios: Adien Dendra (adiendendra.com), Navin Pinto (zerply.com/studiop), François Chancrin (zerply.com/fchancrin), Nathaniel Scheurer (nathanielscheurer.com)
- Top 3: (1) Documentar arquitectura interna del auto-rig con 4-5 frases; (2) Añadir título de rol específico por personaje; (3) Añadir narrativa de origen de la especialización en About.


### 2026-07-08 — Weekly Portfolio Research
- Portfolios analizados: 4 · Archivos escritos: 4
- Portfolios: Sebastien Camrrubi (secam_station.artstation.com), Dorota Sikorska (zerply.com/fairydora), Marin Petrov (zerply.com/marin-petrov), Ariel Podreider Lenzi (zerply.com/3Apost)
- Top 3: (1) Añadir etiqueta de rigging TYPE a cada personaje; (2) Cambiar voz de pipeline.html de documentación a autoría; (3) Añadir frase de contexto de producción a cada personaje.


### 2026-07-01 — Weekly Portfolio Research
- Portfolios analizados: 4 · Archivos escritos: 4
- Portfolios: Robert Joosten (robertjoosten.github.io), Michele Trabona (micheletrabona.com), Bram Van Rompuy (zerply.com/bram-van-rompuy), Tim Coleman (zerply.com/tccoleman)
- Top 3: (1) Separar 9 tools en URL /tools con card expandible; (2) Vincular resultado de producción al sistema técnico; (3) Añadir link externo verificable junto a proyectos de producción.


### 2026-06-24 — Weekly Portfolio Research
- Portfolios analizados: 4 · Archivos escritos: 4
- Portfolios: Mason Smigel (masonsmigel.com), Pradeep Kumar Katta (pcgart.weebly.com), Christopher McCabe (christopher-mccabe.com), Jose "Peperig" Lozano (peperig.com)
- Top 3: (1) Añadir frase de problema/caso de uso a cada tool; (2) Añadir dato de trayectoria cuantificado a About; (3) Crear sección de R&D/Proyectos personales.


### 2026-06-10 — Weekly Portfolio Research
- Portfolios analizados: 4 · Archivos escritos: 4
- Portfolios: Matthew R. Tucker (tuckertd.com), Vittorio Leone (vittorioleone3d.com), Subbu Addanki (boomrigs.com), Assaf Ben Zur (mansur-rig.com)
- Top 3: (1) Añadir sección de integración downstream en pipeline.html; (2) Convertir Auto Skin Transfer en primary showcase; (3) Cambiar tagline del hero a positioning statement.


### 2026-06-03 — Weekly Portfolio Research
- Portfolios analizados: 4 · Archivos escritos: 4
- Portfolios: Niels Kleinheinz (kleinhei.nz), Grant Laker (zerply.com/grant_laker), Jakub Krompolc (rig-it.net), Shervin Shahidi (zerply.com/shervin)
- Top 3: (1) Añadir UNA métrica de impacto cuantificada a la tool más impactante; (2) Crear páginas individuales para los 2 personajes más complejos; (3) Grabar sequence-level breakdown de 90 segundos.


### 2026-05-27 — Weekly Portfolio Research
- Portfolios analizados: 3 · Archivos escritos: 3
- Portfolios: Justin Phillips (justindphillips.com), Ozgur Aydogdu (ozguraydogdu.com), Markus Daum (zerply.com/markus_daum)
- Top 3: (1) Reformatear 7 personajes con formato VERBO+OBJETO+TÉCNICA; (2) Añadir descripción técnica con timestamps al reel; (3) Publicar "Development Notes" para una tool.


### 2026-05-20 — Weekly Portfolio Research
- Portfolios analizados: 4 · Archivos escritos: 4
- Portfolios: Saurabh Kapoor (saurabhrigtd.com), Nicky Liu (nickyliu.com), Jeremy Ernst (jeremyernst.com), Chris Lesage (chrislesage.com)
- Top 3: (1) Publicar post técnico simultáneamente con el próximo reel; (2) Cambiar browser title, tagline y meta description a positioning statement; (3) Añadir Unreal Engine / game-ready rigging como skill.


### 2026-05-13 — Weekly Portfolio Research
- Portfolios analizados: 4 · Archivos escritos: 4
- Portfolios: Hector Abraham Torres / HAT Rigs (hatrigs.com), Joy Johnson (joyjohnsonproductions.com), Bernat Mas (mrbmp33.github.io), Alexander Richter (alexanderrichtertd.com)
- Top 3: (1) Crear rig reel separado del demo reel; (2) Añadir specs numéricas al personaje más complejo; (3) Añadir contexto de producción a cada personaje.


### 2026-05-06 — Weekly Portfolio Research
- Portfolios analizados: 5 · Archivos escritos: 5
- Portfolios: Carlos Contreras (mothman-td.com), Josh Carey (cgjosh.com), Ericka Go (erickago.com), James Dunlop (jamesbdunlop.github.io), Sergi Caballer (sergicaballer.com)
- Top 3: (1) Una frase de propósito+impacto por cada tool; (2) Añadir el PORQUÉ a cada decisión técnica en Design Decisions; (3) Publicar al menos una tool en GitHub.


---