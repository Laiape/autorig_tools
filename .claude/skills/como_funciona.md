# Skills de Claude: indice

Parent: `como_funciona.md` (raiz). Reglas: `.claude/rules/`.
El detalle vive en cada `SKILL.md`; este fichero solo dice cual abrir.

Las skills son CONOCIMIENTO de dominio (que shape buscar, que metodo elegir,
como se hace en un estudio). Las CONVENCIONES del repo (naming, matrices,
stack, datos) viven en `.claude/rules/` y en
`maya_tools/scripts/criterios_naming.md`: las skills enlazan ahi y no las repiten.

## Que skill leer
| Tarea | Skill |
|---|---|
| Skinnear una zona, que shape buscar, pintar pesos, `.skc`, referencias visuales por foto | `.claude/skills/skinning-deformation/SKILL.md` |
| Skinnear el cuerpo con proxy, binding que no cruce influencias, Delta Mush, bake a skin lineal | `.claude/skills/body-proxy-skinning/SKILL.md` |
| Corrective joints de cuerpo y cara, drivers de pose, `utils/correctives.py` | `.claude/skills/corrective-joints/SKILL.md` |
| Deformers custom o nativos, plugins MPx, AdonisFX, Bifrost, orden del stack | `.claude/skills/custom-deformers/SKILL.md` |
| Como riggear una prenda, alternativas al copy skin, sim frente a rig | `.claude/skills/rigging-clothing-methods/SKILL.md` |
| Revisar o empezar un modulo o tool "como lo haria un estudio", estandares, QC | `.claude/skills/rigging-studio-standards/SKILL.md` |

## Referencias de repo dentro de las skills (interinas)
Describen el repo y pasaran a los `como_funciona.md` por area en la Fase 2
(`docs/plan_workflow.md`). Hasta entonces son la fuente de ese tema.

| Tema | Fichero |
|---|---|
| Joints de skin que genera cada modulo, naming real, claves del `.build` que los controlan | `.claude/skills/skinning-deformation/references/esqueleto-deformacion.md` |
| Orden del build, `.skc`, skin apilado, transferencia, QA de pesos | `.claude/skills/skinning-deformation/references/flujo-pesos-y-qa.md` |
| API de `utils/correctives.py`, integracion en el build, `character_extras`, QA | `.claude/skills/corrective-joints/references/repo-y-qa.md` |
| Deformers que usa el repo, sistemas por nodos, historia de los colliders, persistencia | `.claude/skills/custom-deformers/references/repo-deformers.md` |
| Arquitectura, patron de modulo, flujo guides -> cache | `.claude/skills/rigging-studio-standards/references/convenciones-repo.md` |

## Anadir una skill
Carpeta `.claude/skills/<nombre>/` con `SKILL.md` (frontmatter `name` y
`description` con frases disparadoras), `references/` y, si aporta,
`evals/evals.json`. Fila nueva en la tabla de arriba en la misma tarea.
