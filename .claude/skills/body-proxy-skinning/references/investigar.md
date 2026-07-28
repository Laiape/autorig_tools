# Investigar en vivo métodos de proxy skinning del cuerpo

El catálogo (`metodos.md`) es el backbone, pero conviene profundizar en vivo cuando el caso lo pide:
para confirmar flags/versión de un nodo, encontrar la tool o el tutorial concretos, o ver qué se usa
ahora. Esta guía dice **cómo** hacerlo bien.

## Reglas de red

- Investiga con **`web_search`** y **`web_fetch`** nativas. **No** uses Python con `requests`: el
  proxy del entorno solo permite unos pocos dominios y lo bloqueará.
- **GitHub sí** está permitido: `github.com`, `codeload.github.com`, `raw.githubusercontent.com`. Los
  repos de tools de skinning (cvWrap, dm2skin, ngSkinTools) se **clonan con `git clone`** para leerlos.
- Si un `web_fetch` falla, dilo; no rellenes con lo que "debería" poner.

## Cuándo investigar en vivo (y cuándo no)

- **No** hace falta si el catálogo cubre el método y el usuario solo quiere decidir: recomienda y ya.
- **Sí** conviene para: confirmar un flag/comando por versión de Maya (`copySkinWeights
  -surfaceAssociation`, `geomBind`, `deltaMush`, `bakeDeformer`), encontrar la tool/tutorial concretos
  (dm2skin, cvWrap, ngSkinTools2), o cuando el usuario pide "lo último".

## Plantillas de búsqueda

Combina **técnica × Maya × formato**. Lanza varias (3–8 para un caso normal).

- `geodesic voxel binding maya vs closest joint influences`
- `proxy skinning workflow maya low res paint transfer high res`
- `copy skin weights uvSpace influenceAssociation label maya`
- `delta mush to skin weights bake maya dm2skin`
- `bakeDeformer maya linear skin maxInfluences`
- `ngSkinTools2 layers workflow bind refine mirror`
- `cvWrap vs proximityWrap deformation transfer maya`
- `pose space deformation corrective shoulder hip maya SHAPES`
- `<tool> github maya python skinCluster`

## Dónde vive la información buena

- **Docs oficiales**: Autodesk Maya (`copySkinWeights`, `geomBind`/Geodesic Voxel, `deltaMush`,
  `bakeDeformer`, skinCluster `skinningMethod`/`maxInfluences`). Fuente de verdad para *cómo* y *qué
  versión*.
- **Tools y repos**: ngSkinTools2 (docs + API Python), cvWrap (Chad Vernon), dm2skin
  (duncanskertchly), brave rabbit (SHAPES / weightDriver), mGear (RBF manager).
- **Writeups y comunidad**: Rigmarole / Chris Lesage (proxy geometry), Kiel Figgins (pintado de
  pesos), Tech-Artists.org, Cult of Rig, Rigging Dojo, foros de Maya.
- **Papers**: Geodesic Voxel Binding (Dionne & de Lasa), Bounded Biharmonic Weights (Jacobson et
  al.), Delta Mush (Mancewicz et al.), Direct Delta Mush (Le & Lewis), SSDR (Le & Deng), Pose Space
  Deformation (Lewis et al.). Para el *porqué* matemático.

## Leer una tool o un nodo ajeno

Cuando un repo implemente el método, léelo para entender *cómo está hecho*:

1. Clónalo (`git clone`) si es GitHub; si es un snippet, `web_fetch`.
2. Localiza el núcleo: qué nodos/deformadores crea o qué API usa (`maya.cmds`, OpenMaya,
   `MFnSkinCluster`, `skinPercent`), y cómo optimiza los pesos.
3. Extrae la **técnica** (no el código literal): qué resuelve, qué trade-off asume, qué llevarías a
   su pipeline. Respeta la licencia; no copies archivos enteros ni los presentes como suyos.

## Cerrar con criterio

La investigación alimenta la recomendación, no la sustituye. Después de buscar, vuelve al flujo:
compara los candidatos frente al closest-joint del usuario, aterriza en su pipeline y recomienda la
cadena más simple que resuelve el problema. Cita solo recursos que hayas confirmado que existen.
