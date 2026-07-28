# Investigar en vivo métodos de rigging de ropa

El catálogo (`metodos.md`) es el backbone, pero está bien profundizar en vivo cuando el caso lo pide:
para encontrar el tutorial concreto de un método, confirmar cómo funciona una tool o un nodo, o ver
qué se está usando ahora mismo. Esta guía dice **cómo** hacerlo bien.

## Reglas de red (importante)

- Investiga con las herramientas nativas **`web_search`** y **`web_fetch`**. **No** uses Python con
  `requests`/`urllib` para descargar páginas: el proxy del entorno solo permite unos pocos dominios y
  lo bloqueará.
- **GitHub sí está permitido**: `github.com`, `codeload.github.com` y `raw.githubusercontent.com`. Los
  repos de tools de rigging se pueden **clonar con `git clone`** por bash para leerlos a fondo.
- Si un `web_fetch` falla o una página no carga, dilo; no rellenes con lo que "debería" poner.

## Cuándo investigar en vivo (y cuándo no)

- **No** hace falta si el catálogo ya cubre el método y el usuario solo quiere decidir: recomienda y
  ya. Buscar por buscar gasta tiempo.
- **Sí** conviene cuando: el caso es raro y no está en el catálogo; el usuario quiere el tutorial/paper
  concreto para implementarlo; hay que confirmar un detalle de versión de la DCC (un nodo/flag cambia
  entre versiones de Maya/Houdini/engine); o el usuario pide "lo último" (una tool o técnica reciente).

## Plantillas de búsqueda

Combina **método × DCC × formato**. Una sola búsqueda no basta; lanza varias (3–8 para un caso
normal). Sustituye lo que va entre `< >`.

- `<método> cloth rig <Maya|Houdini|Unreal> tutorial`
- `rig <falda|vestido|capa> <joints|dynamic|ribbon> Maya tutorial`
- `proximity wrap vs copy skin weights clothing deformation`
- `pose space deformation wrinkles cloth rig SHAPES RBF`
- `nCloth to skin bake alembic clothing pipeline`
- `Houdini Vellum cloth to Maya rig workflow`
- `Chaos Cloth Unreal character skirt bone setup`
- `Maya ML Deformer cloth wrinkles train simulation`
- `<técnica> SIGGRAPH OR GDC talk clothing deformation`
- `<técnica> github maya python deformer` (para tools/nodos)

## Dónde vive la información buena

- **Docs oficiales**: Autodesk Maya (nCloth, proximityWrap, Delta Mush, deltaMush, wrap), SideFX
  Houdini (Vellum), Epic (Chaos Cloth), Unity (Cloth), Qualoth, Marvelous Designer, Ziva/AdonisFX.
  Son la fuente de verdad para *cómo funciona* un nodo y qué versión lo trae.
- **Charlas**: SIGGRAPH (Talks / Production Sessions), GDC (Animation/Tech), fdg, Rigging Dojo,
  cursos de estudios. Buenas para el *porqué* y el flujo de producción.
- **Papers**: Pose Space Deformation (Lewis et al.), síntesis de arrugas, deep/neural cloth,
  aproximación de sim por ML. Para métodos data-driven.
- **Comunidad y writeups**: blogs de riggers/CFX TDs, Tech-Artists.org, Cult of Rig, Rigging Dojo,
  hilos de foros de Maya/Houdini, Vimeo con breakdowns.
- **Repos y tools**: GitHub (nodos y deformadores custom, auto-rigs), Gumroad/Flippednormals
  (tools de pago con descripción del método), plugins (SHAPES, ngSkinTools, cvWrap).

## Leer una tool o un nodo ajeno

Cuando un repo o una tool implemente el método, vale la pena leerlo para entender *cómo está hecho*:

1. Clónalo (`git clone`) si es GitHub; si es un snippet en una web, `web_fetch`.
2. Localiza el núcleo: qué nodos de Maya/Houdini crea o qué API usa (`maya.cmds`, OpenMaya,
   `hou`, deformadores custom), y cómo conecta el grafo.
3. Extrae la **técnica** (no el código literal): qué resuelve, qué trade-off asume, qué se podría
   llevar al pipeline del usuario. Respeta la licencia; no copies archivos enteros al repo del usuario
   ni los presentes como suyos.

## Cerrar con criterio

La investigación en vivo alimenta la recomendación, no la sustituye. Después de buscar, vuelve al
flujo de la skill: compara los candidatos frente al copy skin del usuario, aterriza en su pipeline y
recomienda la pila más simple que resuelve el problema. Cita solo recursos que hayas confirmado que
existen.
