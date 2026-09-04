# autorig_tools: contexto antes de cambiar

Autorig modular para Maya 2025+ (Python, rig por matrices, build data-driven
por guias) mas notas de export a Unreal. Idioma castellano; texto nuevo en
ASCII (`.claude/rules/idioma-y-ascii.md`).

## Flujo obligatorio
1. Identifica el area y lee su `como_funciona.md` (tabla de abajo), salvo que
   ya se haya leido en esta conversacion con contexto suficiente.
2. Sigue las dependencias que nombra ese documento y despues mira el codigo.
3. Los docs guian; el codigo y los datos de `maya_tools/assets` son la fuente
   de verdad. Si difieren, se arregla el doc en esta misma tarea.
4. Tras cambiar comportamiento, modulo, tool, menu, formato de datos, build o
   skill: actualiza el `como_funciona.md` afectado y su indice padre en la
   misma tarea. Texto nuevo en castellano ASCII.
5. Lee SOLO el `como_funciona.md` del area. Despues ejecuta sin rodeos
   (`.claude/rules/ejecutar-sin-rodeos.md`).

## Rutas en docs y reglas
Punteros a ficheros siempre desde la raiz del repo, en backticks:
`maya_tools/scripts/utils/create_rig.py`. Sin `../`, sin `C:\`, sin barra inicial.

## Indice de entrada
| Area o cambio | Lee primero |
|---|---|
| Vision general, pipeline de build, personajes, arbol del repo | `como_funciona.md` |
| Naming, sufijos de nodos, matrices, nodos 2024+, patron de modulo | `.claude/rules/convenciones-rig.md` y `maya_tools/scripts/criterios_naming.md` |
| Assets, versiones `_vNNN`, claves del `.build`, cache | `.claude/rules/datos-y-versionado.md` |
| Stack de deformacion, skin apilado, `.skc`, QA de skin | `.claude/rules/deformacion-y-skin.md` |
| Skinning, correctivas, deformers, ropa, estandares (conocimiento) | `.claude/skills/como_funciona.md` |
| Arranque de Maya, `.mod`, `userSetup`, cache, plugin | `maya_tools/como_funciona.md` |
| Build, `rig_manager`, guias, matrices, ribbons, picker | `maya_tools/scripts/utils/como_funciona.md` |
| Un modulo biped o facial | `maya_tools/scripts/biped/autorig/como_funciona.md` |
| Un modulo quadruped, un solver, el pie | `maya_tools/scripts/quadruped/autorig/como_funciona.md` |
| Una tool, un test, el `.skc` | `maya_tools/scripts/tools/como_funciona.md` |
| Menu, shelf, Asset Manager, ventanas | `maya_tools/scripts/ui/como_funciona.md` |
| AdonisFX | `maya_tools/scripts/adonis/como_funciona.md` |
| Un personaje, sus carpetas, claves del `.build` | `maya_tools/assets/como_funciona.md` |
| Export a Unreal | `ue_tools/como_funciona.md` |
| API de correctivas y QA | `.claude/skills/corrective-joints/references/repo-y-qa.md` |
| Plan del workflow (fases 3 y 4 pendientes) | `docs/plan_workflow.md` |

## Validacion
- Maya carga el repo por `maya_tools/self_module.mod` (ruta absoluta de
  Windows: ajustar al clone). Imports: `from maya_tools.scripts.utils import x`.
- Build completo: menu AutoRig Tools > RIGGING > CREATE RIG, con el asset
  activo en el Asset Manager (`auto_rig_UI.rig` -> `create_rig.AutoRig.build`).
- Tests headless: `mayapy maya_tools/scripts/tools/tests/test_<x>.py`
  (`maya.standalone` y cache falso; no tocan `maya_tools/cache`).
- Tras un build: consola limpia, `cycleCheck -e on` sin avisos, todos los
  joints nuevos como `_ENV` en `skeletonHierarchy_GRP`, masterwalk a 0.1x/10x
  y lejos del origen sin temblores.
- Espera aprobacion explicita del usuario antes de `git add`, commit o push.
