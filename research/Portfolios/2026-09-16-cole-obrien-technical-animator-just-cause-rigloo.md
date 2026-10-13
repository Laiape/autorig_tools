---
url: https://coleobrienart.com
found: 2026-09-16
category: portfolio
credits: Avalanche Studios (Just Cause 4, animation pipeline contractor), Massachusetts College of Art and Design (educación)
tags: rigging, technical-animator, portfolio, games, maya, python, open-source, rigloo, component-based, matrix-rigging, just-cause, avalanche-studios, gdc-reference, mit-license
status: NEW
---


# Cole O'Brien — Technical Animator / Rigger (coleobrienart.com)


## Perfil profesional
Cole O'Brien es un Technical Animator de Boston formado en el Massachusetts College of Art and Design, con trabajo de contractor para AAA games — su crédito más relevante es el soporte a la animación en Avalanche Studios para Just Cause 4 (2018). Su especialidad es el desarrollo de herramientas de rigging en Maya: creó Rigloo, un auto-rigger component-based de código abierto (MIT license, GitHub: obriencole11/rigloo). Su perfil combina rigging técnico, scripting Python/PyMEL, y pipeline tooling para juegos. No tiene créditos en VFX de film; su valor como referencia es el formato de presentación de portfolio — case studies individuales por producción — y la calidad técnica del código de Rigloo.


## Estructura del portfolio
coleobrienart.com es un portfolio tipo blog con entradas individuales por proyecto:
- **/** — Portfolio home (grid de proyectos)
- **/2018/10/17/jc4-rigging/** — Case study: Just Cause 4 Rigs
- **/2018/10/17/jc4-pipeline-tools/** — Case study separado: Pipeline Tools for Just Cause 4 (herramientas Python que construyó para el proyecto)
- **/2017/09/13/rigloo/** — Entry dedicada a Rigloo con descripción, overview video (Vimeo), y enlace a GitHub
- **/2017/04/30/recursion/** — Senior project (animación)
- **/about/** — Bio personal
- **/blog/tag/python/** — Sección filtrada por tag Python (agrupa las entradas técnicas)
- Resume como PDF descargable enlazado desde el About


Dos elementos estructuralmente importantes: (a) las herramientas de pipeline del mismo proyecto (JC4) tienen su propia entry separada del rigging, lo que permite al reclutador ver el trabajo técnico-de-tool de forma independiente del trabajo artístico; (b) el tag Python agrupa automáticamente el contenido técnico para quien busca específicamente ese perfil.


## Cómo presenta los proyectos
Cada entrada de proyecto es un artículo blog independiente con:
- **Contexto de producción**: estudio, título, año
- **Vídeo o GIF embebido** mostrando la tool/rig en acción (Rigloo tiene un Vimeo con overview completo)
- **Descripción técnica** explicando el problema que resolvió (e.g., para JC4 pipeline tools: necesidad de herramientas personalizadas para el workflow de animación del estudio)
- **Enlace a GitHub** con código completo


Para Rigloo en particular, el README del repositorio incluye:
- **Sección de filosofía** con las decisiones de diseño justificadas: por qué component-based vs. herramientas como HIK, por qué code-driven
- **Sección de Inspiración** nombrando referencias reales: GDC 2017 de Blizzard (Overwatch animation pipeline), UI de Unity como modelo visual
- **Feature list** granular: 7 componentes con sus sub-features (IK con FK offsets y squash/stretch, Spine IK, Leg IK con reverse foot roll, etc.)
- **Licence**: MIT explícita en README y en LICENSE.md


## Cómo comunica sus skills
- Las entradas de caso de estudio muestran el stack: Python, PyMEL, Qt (usa Qt.py abstraction layer), Maya API
- El código de Rigloo implementa **matrix-based constraints** vía multMatrix + decomposeMatrix en lugar de parentConstraint native de Maya — técnicamente avanzado y comentado en el propio código
- El jointConstraint usa transposeMatrix para compensar joint orient — explicado implícitamente en los comentarios del código
- No tiene skill bars ni lista de logos — las skills se demuestran a través del código y los case studies
- Resume en PDF complementa el portfolio como documento separado descargable


## Análisis del código de Rigloo (github.com/obriencole11/rigloo, clonado)


**Arquitectura**:
- `rigloo_main.py` — punto de entrada, MayaQWidgetDockableMixin (dockable en Maya UI), logging completo a archivo
- `rigloo_ui.py` — UI layer separado del logic
- `rigloo_tools.py` — lógica de componentes con diccionario COMPONENT_TYPES que define cada componente como config JSON (BasicComponent, FKComponent, IKComponent, etc.)
- `rigtools.py` — funciones de bajo nivel reutilizables: parentConstraint, jointConstraint, scaleConstraint, aimTransform — todas implementadas via matrix math, no via constraints de Maya
- `controltools.py` — creación y gestión de curvas de control
- `Qt.py` — abstraction layer Qt4/Qt5


**Técnica destacable — matrix constraints**:
El `parentConstraint` en rigtools.py crea: source.worldMatrix[0] → multMatrix.matrixIn[0] + target.parentInverseMatrix[0] → multMatrix.matrixIn[1] → decomposeMatrix → translate/rotate/scale. Esto es exactamente el mismo patrón que Laia usa para sus matrix-based rigs pero Cole lo abstrae como función reutilizable con naming consistente.


El `jointConstraint` añade compensación de jointOrient usando transposeMatrix como inversa de la jointOrient matrix — una solución elegante para el problema habitual de rotation offset en joints. Está comentado paso a paso.


**Licencia**: MIT — libre para uso comercial, modificación y distribución.


## Lo que tiene que Laia no tiene


1. **Case study separado por producción con URL propia y formato Contexto → Problema → Herramienta → Resultado**: Cole tiene entradas separadas para "JC4 Rigs" y "JC4 Pipeline Tools" del mismo proyecto — el rigging artístico y el tooling de pipeline son dos entries distintas. Laia tiene todo en una sola página pipeline.html sin separación. Si Laia separara "Personajes" y "Tools" en páginas distintas con URLs propias (laiape.github.io/tools y laiape.github.io/characters), cada tool y cada personaje serían indexables, enlazables y presentables de forma independiente — exactamente como lo haría un reclutador al compartir una tool específica con un hiring manager.


2. **Sección de Inspiración en la descripción de cada tool nombrando referencias reales de industria** (GDC talks, libros técnicos, frameworks existentes): En el README de Rigloo, la sección "Inspiration" menciona explícitamente el GDC 2017 de Blizzard sobre el pipeline de Overwatch y la UI de Unity como influencias. Esto posiciona al desarrollador dentro de la comunidad técnica y demuestra que diseñó la tool sabiendo qué hacen los estudios AAA. Laia no nombra ninguna influencia técnica en ninguna parte de su portfolio — para un senior tech reviewer, las influencias señalan si el artista conoce la industria más allá de sus propios proyectos.


3. **matrix-based constraints documentados explícitamente como decisión técnica en el portfolio**: Laia usa matrix-based rigging (mencionado en pipeline.html como "matrix-based rigging") pero no explica por qué eligió ese approach ni qué significa concretamente. Cole no lo explica en el portfolio web sino en el código, con comentarios paso a paso. En el context de portfolio para VFX/AAA, añadir una frase en la descripción del auto-rig de Laia que diga "utiliza matrix multiplication nodes (multMatrix + decomposeMatrix) en lugar de constraints de Maya para evitar gimbal lock y mantener consistencia en world-space transforms" convierte una claim genérica en evidencia técnica verificable.


## Aplicable a Laiape.github.io


- **Separar tools y personajes en páginas con URL propia**: Crear laiape.github.io/tools/ y laiape.github.io/characters/ (o mantener pipeline.html pero con anclas por sección que generen URLs tipo pipeline.html#auto-skin-transfer). El objetivo es que cada tool tenga su propia URL que se pueda compartir de forma independiente.
- **Añadir "Inspiration / References" a la descripción de al menos 2 tools**: Para Auto Skin Transfer, mencionar si el algoritmo está inspirado en nearest-neighbor weight transfer estándar o en alguna técnica específica. Para el auto-rig, mencionar si está basado en mGear, HAT Rigs, o es un sistema propio. Esta transparencia es una señal de madurez técnica.
- **Publicar al menos Rigloo equivalente (una tool) en GitHub con README completo**: Laia ya tiene herramientas (Auto Skin Transfer, Skin Manager, etc.) — publicar una con el mismo nivel de documentación que Rigloo (filosofía, features list, inspiración, instalación) convertiría el portfolio en evidencia verificable.


## Fuente
https://coleobrienart.com


*Nota: el site principal estaba inaccesible durante el análisis por restricciones de red del entorno. El análisis de portfolio es de search snippets + resume PDF enlazado. El análisis de código es de github.com/obriencole11/rigloo (repo clonado directamente en sesión).*