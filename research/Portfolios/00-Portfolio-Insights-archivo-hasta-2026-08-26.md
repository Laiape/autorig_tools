# Portfolio Insights — Laia Peris Research

Archivo de síntesis semanal de investigación de portfolios de riggers y TDs de referencia.
Objetivo: identificar patrones de contenido aplicables a laiape.github.io para posicionarse en estudios AAA/VFX.

---

### 2026-08-26 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Jairo Alzate (jairoalzate.xyz — Character Rigger, Tempest Rising / Slipgate Ironworks), Maurofreecg Rigger (maurofreecgrigger.artstation.com — Sr Rigger Artist, Battlefield 6 / Fortnite Chapter 4), Scott Woodhams (scottwoo.artstation.com + temperancetechart.substack.com — Senior TA at EA / Temperance Technical Art newsletter), Kiel Figgins (3dfiggins.com — ILM Associate Animation Supervisor, Ready Player One / Doctor Strange)

**Patrones de contenido más comunes encontrados esta semana:**

- Origin story de producción como motivación de tool — presente en 1/4 (Jairo Alzate: "JAB Rigging Tools built after manually rigging for RTS game with <20 joint constraint — I decided to learn Python to solve this" — el constraint de producción como el POR QUÉ de la herramienta, no solo el QUÉ hace) — nuevo: primera aparición del "problema de producción → herramienta" como narrative explícita en el propio portfolio, diferente de la descripción de funcionalidad; el constraint específico (<20 joints, RTS game) hace la historia verificable y concreta

- Brand name para conjunto de tools usando iniciales del autor — presente en 1/4 (Jairo Alzate: "JAB Rigging Tools" donde JAB = iniciales — la herramienta tiene nombre de producto, no de categoría) — recurrente (HAT Rigs 05-13, Boomrigs 06-10, Mansur Rig 06-10, CreativeRigs 08-05) pero nuevo el uso de iniciales vs. un nombre inventado; aquí el nombre de la herramienta es literalmente el nombre del autor comprimido, señal de ownership personal de la herramienta

- Motor de juego nombrado explícitamente en la descripción del proyecto (no solo el título del juego) — presente en 1/4 (Maurofreecg: "FrostBite/FrostEd" nombrado junto a Battlefield 6 — el motor como contexto técnico del trabajo, no un dato implícito) — recurrente (Nathaniel Scheurer 07-15: "export to Unreal via Pose Wrangler"; Sean Teo 08-05: "cutscene vs. gameplay") pero nuevo el motor como primary technical context del entry, no como output o afterthought; señal directa de que el rigger comprende el pipeline downstream completo

- Documentación interna nombrada como deliverable explícito del rol — presente en 1/4 (Maurofreecg: "created internal documentation" como parte del scope del trabajo en Battlefield 6 — no el rig ni las tools sino la documentación como output nombrado) — nuevo: primera aparición de internal documentation como deliverable de portfolio en todos los perfiles analizados; transforma el scope del TD de "ejecuta técnicamente" a "deja el sistema documentado para otros"

- Newsletter/Substack como capa de contenido separada del portfolio, dirigida a la comunidad de pares — presente en 1/4 (Scott Woodhams: "Temperance Technical Art" Substack con portfolio tips, bag of tricks, job board analysis — lenguaje dirigido a otros technical artists como pares, no al hiring manager) — recurrente (Justin Phillips 05-27: blog sobre proceso de desarrollo de tools; Henry Foster 07-22: 50+ posts técnicos) pero nuevo el framing peer-to-peer vs. showcase; el contenido no muestra trabajo propio sino comparte perspectivas sobre la carrera de TA con otros TAs como audiencia principal

- Portfolio de ArtStation organizado por tipo de disciplina/skill, no por proyecto — presente en 1/4 (Scott Woodhams: ArtStation con entries organizados como Tools / Realtime Rendering / Shaders / Destruction, no por proyecto o cliente) — nuevo: taxonomía por disciplina como estructura de portfolio; todos los portfolios analizados hasta ahora organizaban por proyecto, personaje o producción; aquí el eje organizador es lo que el artista SABE HACER, no dónde lo hizo

- Sección Resources con contenido descargable gratuito (free rigs, scripts, links curados) como motivo de visita independiente del portfolio de trabajo — presente en 1/4 (Kiel Figgins 3dfiggins.com: Free Rigs + curated Websites + Maya/Max Scripts + FAQ — sección Resources más extensa de cualquier portfolio analizado en esta investigación) — recurrente (Henry Foster 07-22: scene files descargables; Robert Joosten 07-01: documentation site; Benoit Gielly 08-05: GitHub público) pero nuevo en escala y taxonomía: categorías separadas para rigs, scripts, links curados, FAQ — un portfolio dentro del portfolio dirigido a usuarios de los recursos, no a empleadores

- Writeup técnico autónomo (documento sin fecha, no blog post) como página propia con URL estable — presente en 1/4 (Kiel Figgins: "Corrective Joint Rigging Setups", "Prepping a Mesh to Rig" — documentos técnicos permanentes con URL propia, sin fecha, sin atarse a ningún proyecto) — recurrente (Mason Smigel 06-24: dev-log de Rigamajig; Justin Phillips 05-27: blog de proceso) pero nuevo el formato: documentos técnicos estables como referencia permanente, no blog posts fechados que envejecen

**Top 3 ideas aplicables a Laia esta semana:**

1. **Añadir el motor de juego o pipeline downstream a cada entry de personaje y tool en pipeline.html** (patrón de Maurofreecg — el dato que más sistemáticamente falta en los 7 personajes y 9 tools de Laia y que más directamente comunica AAA readiness a un reclutador técnico)

Mauro nombra "FrostBite/FrostEd" directamente junto al crédito de Battlefield 6 — no solo el juego, sino el motor en el que se integran los assets. Laia tiene 7 personajes y 9 tools sin ninguna mención de qué pipeline recibe el rig o la herramienta después de Maya. Si los personajes son exclusivamente en Maya (portfolio), decirlo; si se exportan a Unity/Unreal u otro engine, nombrar el motor. Si las tools están integradas en un pipeline con Shotgun/ShotGrid, nombrarlo. Una línea por entry: "export pipeline: Maya → Unity FBX humanoid avatar" o "rig validated in Maya 2022 only, no game engine export" — ambas frases comunican comprensión del pipeline completo y honestidad sobre el alcance del trabajo.

2. **Añadir la production origin story a al menos 3 de las 9 tools en pipeline.html** (patrón de Jairo Alzate — el contenido que más diferencia "tool de hobby" de "tool de producción" y que más consistentemente falta en la sección Standalone Tools del portfolio de Laia)

Alzate describe el origen de JAB Rigging Tools como respuesta a un constraint real: "después de riguear manualmente personajes para un RTS donde los personajes no podían superar 20 joints, decidí aprender Python para resolver esto." Una frase con: (1) problema de producción concreto + (2) constraint técnico específico + (3) decisión de resolverlo con código. Aplicado a Laia: "Auto Skin Transfer — built after a mesh revision required rebinding 12 characters simultaneously; each manual rebind took 45 minutes, making the combined cost 9 hours. The tool reduced the full batch to under 20 minutes." Si los números son reales, esta frase cierra simultáneamente el problema de métricas, el de tools sin contexto de uso, y el de propuesta de valor técnica — todo en un solo cambio de texto por tool.

3. **Publicar un writeup técnico autónomo de 400-600 palabras sobre una decisión de arquitectura del auto-rig, como página propia en el site con URL estable** (patrón de Kiel Figgins — el tipo de contenido más ausente de laiape.github.io y el que más contribuye a SEO y a credibilidad técnica sin requerir nuevos proyectos)

Figgins tiene "Corrective Joint Rigging Setups" y "Prepping a Mesh to Rig" como páginas independientes con URL propia, sin fecha, sin atarse a ningún proyecto concreto. Son documentos técnicos estables encontrables en Google permanentemente. Laia tiene Design Decisions en pipeline.html integradas en la descripción del sistema propio — no son documentos independientes. Escribir un documento de 400-600 palabras sobre "Por qué matrix-based rigging para este auto-rig: el problema de gimbal lock en personajes de acción" o "RBF vs. SDK correctives: cuándo usar cada uno" como página con URL propia (/writeups/matrix-rigging o similar) crearía contenido técnico encontrable por cualquiera que busque esas decisiones en Google, independientemente de si busca contratar a un rigger.

---

### 2026-08-19 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Iker J. de los Mozos (artstation.com/ikerclon — WDAS Frozen/Zootopia/Moana/Frozen 2, Google XR Staff Tech Artist), Nick Van Diem (zerply.com/nicko — ILM Creature Supervisor, Wicked + Transformers One), Lukas Bilek (zerply.com/lukas-bilek — Pipeline TD DreamWorks Spirit Untamed + HTTYD Homecoming, Jellyfish Pictures), David Lantos (zerply.com/imp99 — DNEG Creature Technical Supervisor, Secret Invasion + Black Widow + She-Hulk + Carnival Row)

**Patrones de contenido más comunes encontrados esta semana:**

- Stack técnico de deformación por personaje como contenido explícito de la entry — presente en 1/4 (Iker de los Mozos: "joints + skin + in-house deformers + PSDs" para Sven Frozen 2; "curves + ribbons + RBF + constraints" para Genies Face Rig — secuencia de técnicas nombradas al nivel de componente individual, no el sistema genérico) — recurrente (Nathaniel Scheurer 07-15: IK/FK + soft IK + foot roll; Martin Gunnarsson 07-29: fleshy deformation + eyelid controllers + picker) pero aquí por primera vez como STACK FACIAL en un personaje de producción de WDAS Oscar-winning features, no en un rig personal

- ArtStation como portfolio primario sin website personal independiente — presente en 1/4 (Iker de los Mozos: artstation.com/ikerclon como única presencia de portfolio, con entries individuales por personaje) — recurrente (Areeba Rikhan 08-05, Sebastien Camrrubi 07-08, Sean Teo 08-05) pero nuevo: primera aparición de ArtStation-como-único-portfolio en un TD con créditos de WDAS de nivel Oscar-winning — demuestra que en ciertos perfiles de industria ArtStation es suficiente como única presencia digital y que la ausencia de website personal no es un bloqueador si la presencia en ArtStation es sólida

- Plugin development nombrado como competencia separada de tool development — presente en 1/4 (David Lantos: "tool development, plugin development, automation methods" como items separados; "plugin development" = Maya API / C++ level, distinto de Python scripting) — nuevo: primera aparición explícita de la distinción scripting vs. plugin-level en la separación de competencias declaradas; en portfolios anteriores las herramientas se agrupaban bajo "tools" o "Python" sin distinción de nivel de implementación

- Pipeline consulting como servicio activo junto al portfolio — presente en 1/4 (Lukas Bilek: consultoría activa de pipeline CGI para estudios pequeños y medianos, con tipo de cliente especificado en el propio perfil) — recurrente (Sebastian Cisneros 08-12: freelance con testimonials; J Reinhart 07-29: Gumroad como canal) pero nuevo el framing de "consultoría de pipeline" como oferta específica para un cliente específico (small/mid-size studios), diferente de "available for freelance" como nota genérica

- Simulation breadth como lista explícita de disciplinas separadas — presente en 1/4 (Nick Van Diem: "cloth, hair, flesh surfaces, rigid body simulations" — cada tipo listado individualmente, no agrupado) — recurrente (Ariel Podreider Lenzi 07-08: creature + CFX + groom; Navin Pinto 07-15: Rigging|Sim TD) pero nuevo: lista de 4 tipos de sim en un perfil identificado como "Creature TD" no "CFX" — la simulación como componente integrado del rigging, no como especialización alternativa

- Goals / output standard declarado como sección explícita del perfil — presente en 1/4 (David Lantos: "create anatomically and technically perfect rigs for various creatures" como goals section) — nuevo: primera aparición de una declaración de estándar de calidad de output como sección separada, distinta de skills list o credits; framing del QUÉ PRODUCE vs. QUÉ SABE HACER

- Career escalation cross-studio como única prueba de seniority — presente en 2/4 (Nick Van Diem: DNEG → ILM con progresión de rol TD → Lead → Supervisor; David Lantos: Image Engine → Digital Domain con TD → Lead → Supervisor → DNEG Creature Supervisor) — recurrente (Marin Petrov 07-08; Ariel Podreider Lenzi 07-08) pero aquí los dos portfolios usan EXCLUSIVAMENTE la progresión como evidencia de seniority, sin technical breakdowns ni quantified metrics — la progresión como argumento suficiente a ciertos niveles de carrera

- Multi-software Python stack como señal de pipeline breadth — presente en 1/4 (Lukas Bilek: Maya + Nuke + Houdini + Blender + Shotgun + Deadline + bash con Python como hilo conductor de todo) — recurrente (Grant Laker 06-03; Shervin Shahidi 06-03) pero nuevo el framing de Python como "hilo conductor transversal de un stack multi-software", diferente de Python como skill adicional de un software específico

**Top 3 ideas aplicables a Laia esta semana:**

1. **Describir el stack técnico de deformación para los personajes con sistema facial en pipeline.html** (patrón de Iker de los Mozos — la especificidad de deformación más urgente que falta en la sección Characters del portfolio actual)

Iker describe el Sven rig con "joints + skin + in-house deformers + PSDs" y el Genies rig con "curves + ribbons + RBF + constraints" — una secuencia de componentes discretos, no "facial rigging" como descripción genérica. Laia tiene Maui y Moana en pipeline.html con sistemas faciales documentados (jaw, eyes, teeth, tongue, lips) pero sin ningún componente técnico nombrado del sistema de deformación. Añadir para cada personaje con sistema facial una línea de stack: "jaw: [RBF solver/SDK/driver joints], eyes: [aim constraint/matrix-based], correctives: [PSD/SDK]". Son 3-5 items por personaje, menos de 30 minutos de trabajo, y la diferencia entre describir que hay un facial system y demostrar qué hay dentro de él.

2. **Especificar el nivel de implementación técnica por tool en pipeline.html** (patrón de David Lantos — el detalle que diferencia "Python tools" de "pipeline-level tooling" en la lectura de un reclutador técnico)

Lantos lista "plugin development" separado de "tool development" — la distinción señala Maya API vs. Python scripting. Laia describe 9 tools pero ninguna especifica el nivel técnico de implementación. Añadir para cada tool una línea: "Auto Skin Transfer — Python (OpenMaya API for topology-agnostic weight transfer)" si usa la API, o "Skin Manager — Python (Maya cmds + PySide2 UI)" si es scripting-level.

3. **Añadir una declaración de estándar de output a About page** (patrón de David Lantos — el framing de propuesta de valor que más consistentemente falta en laiape.github.io desde el inicio de esta investigación)

Lantos declara "create anatomically and technically perfect rigs for various creatures" como goals statement. Laia describe skills y herramientas pero no declara a qué estándar aspira. Una frase en About page — "I build auto-rigs that produce production-ready results in under 2 minutes, with fewer than 5 manual adjustments per character" — si es verdad es simultáneamente: declaración de estándar de output, primera métrica cuantificada del portfolio, y propuesta de valor técnica dirigida al hiring manager.

---

### 2026-08-12 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Nims Bun (Framestore Rigging Supervisor, Baguette nodal rigging tool), Sebastian Cisneros (rigsbycisneros.com — freelance Marvel/Netflix), Valentin Procida (Storm Studios VFX Londres, Black Widow + Shang-Chi + The Gorge), Ian Woskey (iancw.com — Genies, AI-driven facial auto-rigger)

**Patrones de contenido más comunes encontrados esta semana:**

- Distributed portfolio model: sin site personal, presencia en Vimeo + IMDB + press coverage como portfolio completo — presente en 1/4 (Nims Bun: Framestore Rigging Supervisor con 18+ años, portfolio distribuido entre Vimeo, IMDB y press coverage en CG Channel/3DVF/80.lv — ninguna web personal propia) — nuevo: a nivel Supervisor/Lead, la suma de plataformas especializadas puede superar a un portfolio personal en credibilidad percibida

- Cobertura de prensa de industria como validación externa de herramienta (CG Channel, 80.lv, 3DVF) — presente en 1/4 (Nims Bun: Baguette cubierto por 3 publicaciones de referencia en 2023 tras release gratuito) — recurrente (Assaf Ben Zur 06-10: mansur-rig CG Channel coverage) pero aquí con múltiples medios simultáneos como señal de impacto diferente a cobertura de un solo medio

- Testimonials section en el portfolio personal como social proof de freelancers — presente en 1/4 (Sebastian Cisneros: rigsbycisneros.com tiene sección de testimonials de clientes, no solo créditos de producción)

- Clientes internacionales en múltiples países como señal de alcance freelance — presente en 1/4 (Sebastian Cisneros: Stellar Creative Lab Canadá, Arts and Spells Turquía, Fair Play Labs Costa Rica, Kalahari Pictures Sudáfrica — 4 continentes)

- Tagline dual de dos especialidades ("Rigger & CFX Artist") para ampliar alcance de búsqueda — presente en 1/4 (Valentin Procida)

- Especificaciones técnicas cuantificadas en proyectos personales de R&D sin restricción NDA ("800K+ XGen guide curves") — presente en 1/4 (Valentin Procida: tiger rig con 800K+ guide curves, horse rig con hoof mechanics)

- AI/ML como especialización emergente de rigging TD — presente en 1/4 (Ian Woskey: AI-driven facial auto-rigger en Genies, pipeline de datos sintéticos para entrenamiento ML)

- Framing de proyecto como pregunta de investigación con hipótesis y métrica de éxito explícita — presente en 1/4 (Ian Woskey: "Can a face be procedurally rigged to 80-90% fidelity, where fidelity = production-ready blendshape rigs with zero white-glove tweaks?")

**Top 3 ideas aplicables a Laia esta semana:**

1. **Añadir especificaciones técnicas cuantificadas al menos a un rig en pipeline.html** (patrón de Valentin Procida — joint counts, número de controles, tiempo de build del auto-rig)

2. **Reformular el auto-rigging system en pipeline.html como pregunta de investigación con hipótesis** (patrón de Ian Woskey — "Can a Maya Python script produce a production-ready biped rig in under 2 minutes, with fewer than 5 manual adjustments per character?")

3. **Añadir sección de testimonials con 2-3 citas de colaboradores en la About page o en pipeline.html** (patrón de Sebastian Cisneros — el elemento de social proof más ausente del portfolio de Laia)

---

### 2026-08-05 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Areeba Rikhan (areebarikhan.artstation.com — Sony/Spider-Man + Ember Lab/Kena: Bridge of Spirits, Senior Character TD), Sean Teo (seant3o.artstation.com + seanteo.carrd.co — PlayStation Character TD, The Last of Us Part 1 & 2 Remastered), Drago Avdalovic (creativerigs.com — Senior Character TD DreamWorks/ILM/MPC/Crystal Dynamics, 20+ años), Benoit Gielly (github.com/BenoitGielly + IMDb — Pipeline TD/Character Rigger DNEG, Stim Studio CTO, bgdev open-source tools)

**Patrones de contenido más comunes encontrados esta semana:**

- Constraint técnico del asset como contenido de la descripción del proyecto — presente en 1/4 (Areeba Rikhan: Kena stick characters — "ensuring stick characters retained their stick shape rather than bending like an organic form")
- Diferenciación de tipo de trabajo dentro de un mismo crédito de producción — presente en 1/4 (Areeba Rikhan: "previz rigging for Doc Ock & cars" + "supporting the auto rig system" en Spider-Man)
- Cutscene vs. gameplay como especificación técnica del contexto de uso del rig — presente en 1/4 (Sean Teo)
- Hub de links centralizado (carrd.co) como landing page que distribuye tráfico a canales especializados — presente en 1/4 (Sean Teo)
- Reels separados por producción con nombre de proyecto en el título del entry — presente en 1/4 (Sean Teo: The Last of Us Part 1 vs. Part 2 Remastered como dos entries distintos)
- Marca personal bajo nombre de estudio/servicio (no nombre propio) — presente en 1/4 (Drago Avdalovic: creativerigs.com)
- GitHub público con historial de commits multi-año como evidencia de tool sostenida en el tiempo — presente en 1/4 (Benoit Gielly: bgdev con 55 commits desde 2013)
- Documentación de API separada del README (readthedocs.io) como señal de tool diseñada para terceros — presente en 1/4 (Benoit Gielly)

**Top 3 ideas aplicables a Laia esta semana:**

1. **Añadir el constraint técnico específico de cada personaje en pipeline.html, 1 frase por personaje** (patrón de Areeba Rikhan)

2. **Publicar Auto Skin Transfer en GitHub y hacer commits regulares durante 3 meses** (patrón de Benoit Gielly — cierra el hueco de verificación técnica más urgente del portfolio; recomendación pendiente desde semana 05-06)

3. **Registrar un dominio personalizado que incluya "td", "rigging", o "pipeline" en el nombre** (patrón de Drago Avdalovic / creativerigs.com)

---

### 2026-07-29 — Weekly Portfolio Research
- Portfolios analizados: 3
- Archivos escritos: 3
- Portfolios: Ernesto Ruiz Velasco (ernesto.ruizvelasco.com — Rigging Supervisor at Buck Design), J Reinhart (jreinhart.gumroad.com — Rigging TD at Framestore), Martin Gunnarsson / Deer Stranger (vimeo.com/deerstranger — Freelance Character Rigger)

**Patrones de contenido más comunes encontrados esta semana:**

- Nombres de fase como vocabulario de sistema — presente en 1/3 (Ernesto Ruiz Velasco: PLACE/BUILD/CONNECT como etiquetas de las 3 fases del auto-rig)
- Gumroad como validación externa de herramientas — presente en 2/3 (Ernesto Ruiz Velasco + J Reinhart)
- Sin personal site, Gumroad como portfolio primario — presente en 1/3 (J Reinhart)
- Contexto de producción específico (advertising) como parte de la descripción del rig — presente en 1/3 (Martin Gunnarsson: Honda/Nike/Audi advertising rigs)
- Breakdown de componentes a nivel de asset individual — presente en 1/3 (Martin Gunnarsson: Audi eye rig con "fleshy deformation + manual eyelid controllers + face detail controllers + easy-access picker")
- Multi-plataforma con función explícita por canal — presente en 1/3 (Ernesto Ruiz Velasco: 5 plataformas con 5 propósitos distintos)

**Top 3 ideas aplicables a Laia esta semana:**

1. **Nombrar las etapas del auto-rig con una secuencia de 3-4 palabras en pipeline.html** (patrón de Ernesto Ruiz Velasco)

2. **Añadir un breakdown de 4-6 componentes técnicos al personaje más complejo en pipeline.html** (patrón de Martin Gunnarsson)

3. **Publicar una herramienta en Gumroad (free) con README de 5 párrafos** (patrón de J Reinhart + Ernesto Ruiz Velasco — validación externa urgente, 13 semanas como recomendación no ejecutada)

---

### 2026-07-22 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Brittany McGrath (brittanymcgrath.com — Disney Animation + Blizzard Character TD), Walt Hyneman (walthyneman.com — ILM Sr. Creature TD), Henry Foster / Toadstorm (toadstorm.com — VFX Technical Artist / Pipeline TD), Jose Antonio Martin Martin (domestika.org — Character TD Educator, Framestore/MPC/DNEG/ILM)

**Patrones de contenido más comunes encontrados esta semana:**

- Demo Reel Breakdown como página independiente escrita con descripción por shot — presente en 1/4 (Brittany McGrath)
- Framing de "pitch + spec + build" como autoría de sistema vs. ejecución de requisito — presente en 1/4 (Brittany McGrath)
- Site title como positioning statement de especialidad cross-pipeline — presente en 1/4 (Walt Hyneman)
- Nombre de personaje hero como señal de nivel de complejidad sin texto adicional — presente en 1/4 (Walt Hyneman)
- Blog técnico de largo recorrido como portfolio activo (50+ posts) con scene files descargables — presente en 1/4 (Henry Foster/Toadstorm)
- Tool con ecosistema independiente: dominio propio + docs + changelog + comunidad — presente en 1/4 (Henry Foster)
- Teaching content en plataformas con enrollment como señal cuantificada de expertise — presente en 1/4 (Jose Antonio Martin Martin)
- Background técnico no-rigging enmarcado como ventaja de identidad del rol — presente en 1/4 (Jose Antonio)

**Top 3 ideas aplicables a Laia esta semana:**

1. **Añadir una página /breakdown con descripción escrita por segmento del reel** (patrón de Brittany McGrath)

2. **Añadir una frase de pitch/autoría a la intro de cada sección de pipeline.html** (patrón de Brittany McGrath)

3. **Publicar un descargable mínimo junto a la herramienta más representativa** (patrón de Henry Foster/Toadstorm)

---

### 2026-07-15 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Adien Dendra (adiendendra.com + zerply.com/adien — ILM Sydney), Navin Pinto (zerply.com/studiop — Blizzard/Avengers/Spider-Man), François Chancrin (zerply.com/fchancrin — DNEG Supervisor/Avatar), Nathaniel Scheurer (nathanielscheurer.com — TGA Technical Art)

**Patrones de contenido más comunes encontrados esta semana:**

- Subdominio separado para tools como site independiente — presente en 1/4 (Adien Dendra)
- Títulos de rol compuestos que nombran dos especialidades simultáneas por producción — presente en 1/4 (Navin Pinto)
- VES Award nomination vinculada al entry de producción específico — presente en 1/4 (Navin Pinto)
- Narrative de origen de la especialización como señal de identidad técnica — presente en 1/4 (Navin Pinto)
- Portfolio mínimo como señal inversa de crédito suficiente — presente en 1/4 (François Chancrin)
- Documentación de arquitectura interna del auto-rig como portfolio piece propio — presente en 1/4 (Nathaniel Scheurer)
- ARKit compatibility como especificación explícita del facial system — presente en 1/4 (Nathaniel Scheurer)
- Game engine export pipeline como feature documentada del auto-rig — presente en 1/4 (Nathaniel Scheurer)

**Top 3 ideas aplicables a Laia esta semana:**

1. **Documentar la arquitectura interna del auto-rig con 4-5 frases en pipeline.html** (patrón de Nathaniel Scheurer)

2. **Añadir un título de rol específico por personaje en pipeline.html** (patrón de Navin Pinto)

3. **Añadir en About la narrativa de origen de la especialización** (patrón de Navin Pinto, confirmado por contraste con François Chancrin)

---

### 2026-07-08 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Sebastien Camrrubi (secam_station.artstation.com + zerply.com/mrsecam), Dorota Sikorska (zerply.com/fairydora), Marin Petrov (zerply.com/marin-petrov + marinpetrov.com), Ariel Podreider Lenzi (zerply.com/3Apost)

**Patrones de contenido más comunes encontrados esta semana:**

- Per-character ArtStation entries con label de tipo de rigging separadas por personaje — presente en 1/4 (Sebastien Camrrubi)
- Pipeline co-authorship framing — presente en 1/4 (Marin Petrov)
- Solo ownership signal para proyecto individual — presente en 1/4 (Dorota Sikorska)
- Multi-disciplina documentada como pipeline end-to-end — presente en 1/4 (Ariel Podreider Lenzi)
- Animación propia como evidencia de que los rigs son usables en práctica real — presente en 1/4 (Marin Petrov)
- ArtStation project description que documenta el PROBLEMA técnico específico del personaje — presente en 1/4 (Camrrubi)

**Top 3 ideas aplicables a Laia esta semana:**

1. **Añadir una etiqueta de rigging TYPE a cada personaje en pipeline.html** (patrón de Sebastien Camrrubi)

2. **Cambiar la voz de pipeline.html de documentación a autoría** (patrón de Marin Petrov)

3. **Añadir una frase de contexto de producción a cada personaje en la sección Characters** (patrón de Ariel Podreider Lenzi + Dorota Sikorska)

---

### 2026-07-01 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Robert Joosten (robertjoosten.github.io), Michele Trabona (micheletrabona.com), Bram Van Rompuy (zerply.com/bram-van-rompuy + bramvanrompuy.be), Tim Coleman (zerply.com/tccoleman)

**Patrones de contenido más comunes encontrados esta semana:**

- Separación del portfolio en dos secciones con URL propia: /rigging y /rnd — presente en 1/4 (Robert Joosten)
- Descripción de proyecto centrada en el problema técnico resuelto — presente en 1/4 (Robert Joosten)
- Documentation site separado para la tool principal con API docs — presente en 1/4 (Robert Joosten)
- Crédito de award vinculado al componente técnico específico — presente en 1/4 (Michele Trabona)
- Testimonials de colegas de producción integrados como sección estructurada — presente en 1/4 (Michele Trabona)
- IMDb credits page como mecanismo de verificación externa — presente en 1/4 (Bram Van Rompuy)
- Multi-plataforma intencionada con propósito específico por canal — presente en 1/4 (Bram Van Rompuy)
- Entrevista en publicación de referencia como thought leadership content — presente en 1/4 (Tim Coleman)

**Top 3 ideas aplicables a Laia esta semana:**

1. **Separar las 9 tools en su propia URL /tools con una card expandible por herramienta** (patrón de Robert Joosten)

2. **Vincular el resultado de producción más concreto al sistema técnico que lo hizo posible** (patrón de Michele Trabona)

3. **Añadir un link externo verificable junto a cualquier proyecto de producción real** (patrón de Bram Van Rompuy)

---

### 2026-06-24 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Mason Smigel (masonsmigel.com), Pradeep Kumar Katta (pcgart.weebly.com), Christopher McCabe (christopher-mccabe.com), Jose "Peperig" Lozano (peperig.com)

**Patrones de contenido más comunes encontrados esta semana:**

- Dev-log / blog serializado documentando decisiones de arquitectura — presente en 1/4 (Mason Smigel: Rigamajig)
- GitHub repo stats como señal de madurez de tool open-source — presente en 1/4 (Mason Smigel)
- Career-length headline cuantificado en la página principal — presente en 1/4 (Pradeep Kumar Katta)
- Documento de "Reel Breakdown" escrito y fechado, separado del vídeo — presente en 1/4 (Pradeep Kumar Katta)
- Proyectos personales de R&D al mismo nivel de tratamiento que créditos pagados — presente en 1/4 (Christopher McCabe)
- Páginas individuales por proyecto con crédito de producción nombrado completo — presente en 1/4 (Peperig)
- Frase de problema/caso de uso de una línea por cada herramienta — presente en 1/4 (Peperig)

**Top 3 ideas aplicables a Laia esta semana:**

1. **Añadir una frase de problema/caso de uso a cada una de las 9 standalone tools en pipeline.html** (patrón de Peperig)

2. **Añadir un dato de trayectoria cuantificado al inicio de la About page** (patrón de Pradeep Kumar Katta)

3. **Crear una página o sección de "R&D / Proyectos personales" separada de los personajes de cliente** (patrón de Christopher McCabe)

---

### 2026-06-10 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Matthew R. Tucker (tuckertd.com), Vittorio Leone (vittorioleone3d.com), Subbu Addanki (boomrigs.com / creature-productions.com), Assaf Ben Zur (mansur-rig.com)

**Patrones de contenido más comunes encontrados esta semana:**

- Impacto cuantificado vinculado a producción específica — presente en 1/4 (Tucker: 30% reduction in facial dev time, 200% delivery speed increase)
- Framework de producción como specialty signal en el tagline del site — presente en 1/4 (Leone: "mGear & Kangaroo Specialist")
- Deformation quality como especialización nombrada explícitamente — presente en 1/4 (Leone)
- Tool-as-primary-portfolio-piece con documentación de arquitectura pública y press coverage — presente en 1/4 (Ben Zur: mansur-rig.com)
- Open-source release como generador de validación externa — presente en 1/4 (Ben Zur)
- Ecosistema de tools integrado vs. lista de tools separadas — presente en 1/4 (Addanki)
- Pipeline Maya → game engine como AAA-readiness signal explícito — presente en 1/4 (Tucker)

**Top 3 ideas aplicables a Laia esta semana:**

1. **Añadir en pipeline.html una sección de integración downstream de 3-5 frases** (patrón de Tucker)

2. **Convertir Auto Skin Transfer en primary showcase con documentación de arquitectura** (patrón de Ben Zur)

3. **Cambiar el tagline del hero a un positioning statement framework-específico** (patrón de Leone)

---

### 2026-06-03 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Niels Kleinheinz (kleinhei.nz), Grant Laker (zerply.com/grant_laker), Jakub Krompolc (rig-it.net), Shervin Shahidi (zerply.com/shervin)

**Patrones de contenido más comunes encontrados esta semana:**

- Páginas individuales por proyecto con URL propia y contexto de producción — presente en 1/4 (Niels Kleinheinz)
- Sequence-level VFX breakdown como portfolio piece autónoma — presente en 1/4 (Grant Laker)
- Tutorial estructurado como portfolio piece + producto vendible simultáneamente — presente en 1/4 (Jakub Krompolc)
- Métrica de impacto cuantificada para tool de producción ("+300% department output") — presente en 1/4 (Shervin Shahidi)
- Descripción de variantes del mismo rig para distintos contextos de uso — presente en 1/4 (Jakub Krompolc)
- Especificación de escala de producción ("1000+ shots lean version" vs. "heavy rig with muscle systems") — presente en 1/4 (Niels Kleinheinz)
- C/C++ o Maya API como señal de pipeline-level TD vs. scripting-level rigger — presente en 2/4

**Top 3 ideas aplicables a Laia esta semana:**

1. **Añadir UNA métrica de impacto cuantificada a la tool más impactante** (patrón de Shervin Shahidi)

2. **Crear páginas individuales para los 2 personajes más complejos** (patrón de Niels Kleinheinz)

3. **Grabar un sequence-level breakdown de 90 segundos para un sistema técnico específico** (patrón de Grant Laker)

---

### 2026-05-27 — Weekly Portfolio Research
- Portfolios analizados: 3
- Archivos escritos: 3
- Portfolios: Justin Phillips (justindphillips.com), Ozgur Aydogdu (ozguraydogdu.com), Markus Daum (zerply.com/markus_daum)

**Patrones de contenido más comunes encontrados esta semana:**

- Descripción de tareas por proyecto con formato VERBO + OBJETO + TECNOLOGÍA — presente en 2/3
- Blog que documenta el PROCESO de desarrollo de herramientas — presente en 1/3 (Justin Phillips)
- Validación académica o de prensa vinculada al portfolio — presente en 1/3 (Ozgur Aydogdu)
- Multi-plataforma complementaria: personal site + Zerply + IMDb + Vimeo — presente en 2/3
- Reasoning explícito de decisiones de implementación en herramientas — presente en 1/3 (Justin Phillips)

**Top 3 ideas aplicables a Laia esta semana:**

1. **Reformatear los 7 personajes de pipeline.html con formato VERBO + OBJETO + TÉCNICA** (patrón de Markus Daum)

2. **Añadir una descripción técnica con timestamps al reel en Vimeo/YouTube** (patrón de Ozgur Aydogdu)

3. **Publicar un "Development Notes" para una de las 9 tools con razonamiento de decisiones técnicas** (patrón de Justin Phillips)

---

### 2026-05-20 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Saurabh Kapoor (saurabhrigtd.com), Nicky Liu (nickyliu.com), Jeremy Ernst (jeremyernst.com), Chris Lesage (chrislesage.com / rigmarolestudio.com)

**Patrones de contenido más comunes encontrados esta semana:**

- Site title / tagline como positioning statement de rol y stack técnico — presente en 3/4
- Dev blog o blog técnico con posts fechados — presente en 3/4
- Post que combina lanzamiento de reel con explicación técnica del sistema — presente en 2/4
- Cada herramienta como portfolio piece independiente con nombre, propósito y demo — presente en 2/4
- Unreal Engine como pipeline output explícito para AAA game studio positioning — presente en 2/4
- Tutorial técnico que referencia la producción donde se usó la técnica — presente en 2/4

**Top 3 ideas aplicables a Laia esta semana:**

1. **Publicar un post técnico simultáneamente con el próximo demo reel** (patrón de Jeremy Ernst + Chris Lesage)

2. **Cambiar el browser title, el tagline del hero y el meta description a un positioning statement** (patrón de Nicky Liu + Saurabh Kapoor)

3. **Añadir Unreal Engine / game-ready rigging como skill explícito** (patrón de Saurabh Kapoor)

---

### 2026-05-13 — Weekly Portfolio Research
- Portfolios analizados: 4
- Archivos escritos: 4
- Portfolios: Hector Abraham Torres / HAT Rigs (hatrigs.com), Joy Johnson (joyjohnsonproductions.com), Bernat Mas (mrbmp33.github.io), Alexander Richter (alexanderrichtertd.com)

**Patrones de contenido más comunes encontrados esta semana:**

- Especificaciones técnicas numéricas por rig: joint count + corrective count (HAT Rigs Vittorio: 300+ joints, 140 body correctives, 85 facial correctives)
- Rig reel separado del showreel: vídeo técnico con controles visibles y deformación en pose
- Progresión de carrera visible como narrativa cronológica
- Award specificity al nivel máximo: "VES Award + personaje + film + año"
- Open source pipeline-level project en GitHub
- TDD y software engineering rigor en tools de Maya
- Rig descargable con specs completas como portfolio piece comercial y técnico
- Teaching / workshops como multiplicador de credibilidad — presente en 3/4

**Top 3 ideas aplicables a Laia esta semana:**

1. **Crear un rig reel separado del demo reel** (patrón de Joy Johnson)

2. **Añadir especificaciones técnicas numéricas al personaje más complejo en pipeline.html** (patrón de HAT Rigs / Vittorio)

3. **Añadir contexto de producción a cada personaje** (patrón de Bernat Mas / Joy Johnson)

---

### 2026-05-06 — Weekly Portfolio Research
- Portfolios analizados: 5
- Archivos escritos: 5
- Portfolios: Carlos Contreras (mothman-td.com), Josh Carey (cgjosh.com), Ericka Go (erickago.com), James Dunlop (jamesbdunlop.github.io), Sergi Caballer (sergicaballer.com)

**Patrones de contenido más comunes encontrados esta semana:**

- Páginas individuales por proyecto con rol, estudio, año y lista de tareas específicas (todos los portfolios)
- Cuantificación de escala de producción — presente en 4/5
- Software + nivel de competencia declarado explícitamente — presente en 3/5
- Código o recursos descargables públicos como evidencia directa de skill — presente en 3/5
- Blog o artículos técnicos publicados externamente — presente en 3/5
- Presencia externa verificable: IMDb listing, entrevistas, speaker credits — presente en 3/5
- Diferenciación de especialidades como áreas distintas — presente en 2/5
- Herramientas nombradas con propósito de una línea — presente en 2/5

**Top 3 ideas aplicables a Laia esta semana:**

1. **Una frase de propósito + impacto por cada tool en pipeline.html** (todos los portfolios fuertes hacen esto)

Modelo exacto: "Auto Skin Transfer — Transfers skin weights between meshes of different topology without manual rebind, cutting re-rigging time after modeling changes."

2. **Añadir el PORQUÉ a cada decisión técnica en la sección Design Decisions de pipeline.html** (patrón de Sergi Caballer)

Formato: ELECCIÓN → POR QUÉ → BENEFICIO PARA EL ANIMADOR. Ejemplo: "Matrix-based rigging — avoids constraint node overhead — gives animators clean rotation channels with no gimbal lock across extreme poses."

3. **Publicar al menos una tool en GitHub y linkearlo desde pipeline.html** (patrón de James Dunlop)

Laia describe 9 tools en detalle. Sin código o demo pública, un recruiter técnico no puede verificar nada. Publicar una tool — aunque sea Auto Skin Transfer o IK/FK Match, con README claro — transforma la descripción en evidencia.

---
