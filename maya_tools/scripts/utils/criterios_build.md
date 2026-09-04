# Criterios: orden del build y QA

Parent: `maya_tools/scripts/utils/como_funciona.md`.
Codigo: `maya_tools/scripts/utils/create_rig.py` (`AutoRig.build`), `build_rig` en `maya_tools/scripts/utils/rig_manager.py`.
Reglas: `.claude/rules/deformacion-y-skin.md` (stack), `.claude/rules/datos-y-versionado.md`.
Poses: `POSE_LIBRARY` en `maya_tools/scripts/tools/pose_tester.py`.

Este fichero es el sitio para cambiar el orden del build o una pose de QA.
Cuando cambie, en la misma tarea: `create_rig.py` (o `rig_manager.build_rig`),
la seccion 2.2 de `maya_tools/scripts/utils/como_funciona.md` y, si es una
pose, `pose_tester.py`.

---

## 1. Orden del build y por que

| Paso | Por que va ahi | Que rompe si se mueve |
|---|---|---|
| Fast session (evaluationManager off, cycleCheck off, undo sin flush, refresh suspendido) antes de construir | el build hace miles de conexiones; el EM reconstruiria el grafo por nodo y el cycleCheck comprobaria cada conexion | sin ella el build tarda mucho mas. Contrapartida: los ciclos no avisan; se validan en QA con `cycleCheck -e on` |
| `new_build()` del cache antes de nada | un modulo leeria claves del build anterior | nombres de otro personaje en el cache |
| `basic_structure` primero | publica `modules_GRP`, `skel_GRP`, `masterwalk_ctl`, `preferences_ctl` que todo modulo lee en `__init__` | `get_data` devuelve None y los modulos parentean en la raiz |
| Spine antes que patas, cola y cuello | publica `local_hip_ctl`, `body_ctl`, `local_chest_ctl` (la pierna biped lee `local_hip_ctl` en `__init__`; la escapula lee `local_chest_ctl`) | space switches sin target; sling inerte |
| Clavicula antes que brazo | el brazo lee `clavicle_module/{side}_clavicle` para el auto-clavicle | sin auto-clavicle |
| Brazo antes que dedos | fingers lee `arm_module/{side}_wrist_JNT` | dedos sin padre |
| Cuello antes que cualquier modulo facial | todos leen `neck_module/head_ctl`, `face_ctl`, `head_guide_matrix` | cara en el origen |
| Jaw antes que teeth y tongue; eyebrow antes que eyelid; eyelid antes que cheekbone | matrices locales de la jaw; `main_eyebrow_ctl`; `lower_socket_ctl` | dientes y lengua sin seguir la mandibula; sockets sin ceja |
| `facial_correctives` el ultimo de la cara | necesita los joints de skin y controles ya creados; cada bloque salta con warning si falta su base | correctivas sin base |
| Space switches despues de todos los modulos | resuelven sus targets por cache | targets None (quadruped los salta en silencio) |
| `skeleton_hierarchy` despues de todos los modulos | duplica los joints de skin que existen en ese momento | joints sin `_ENV` |
| `apply_character_extras` al final de `build_rig` | toca atributos de nodos ya creados (resuelve `"modulo/clave"` por cache) | atributo inexistente, warning |
| `label_joints`, `hide_connections`, `inherit_transforms` dentro de la fast session | barridos masivos de `setAttr` | lentitud |
| Fin de la fast session ANTES de `import_weights` | los deformers se crean y reordenan (`multi=True`, `reorderDeformers`) con el estado normal de Maya | orden observado en el codigo; no cambiarlo sin medir |
| `localize_correctives` justo despues de `import_weights`, en pose neutra | `bindPreMatrix` se hornea con la matriz del padre EN REPOSO; si algo ya movio el rig, la localizacion queda con offset | doble transformacion o pop en rest |
| `import_corrective_blendshapes` despues del skin | `frontOfChain` y `_push_before_skin` necesitan el skinCluster existente para reordenar | blendshape detras del skin |
| `hide_all_utility_nodes` casi al final | tras crear todo; respeta `KEEP_TYPES` | nodos nuevos visibles o deformers escondidos |
| Picker el ultimo y tolerante a fallo | necesita todos los controles; DWPicker puede no estar instalado | build sin picker pero valido |
| `apply_delta_mush` COMENTADO | patron listo (`_DMH`, escala por `C_deltaMushScale_DCM`); fuera porque una capa de suavizado no viaja al engine (`_ENV` + morphs) y cuesta fps | - |
| `_auto_transfer_from_source` COMENTADO | depende de `auto_skin_transfer`, dado por roto | - |

## 2. Contratos que el orden protege

- Todo modulo lee `basic_structure` en `__init__` y publica al final de `make`.
- Nada de nombres de nodo a mano entre modulos.
- El build corre desde escena nueva: `auto_rig_UI.rig` y el Asset Manager
  hacen `file(new=True, force=True)` y `new_build()` antes.
- Sin `.skc` no hay bind: `import_skins` da error y el build sigue.
- El build no es idempotente dentro de la misma escena: rebuild = escena
  nueva.

## 3. QA despues de un build (checklist)

1. Consola: sin errores; warnings solo los esperados (`[Picker]` si no hay
   DWPicker; bloques faciales que se saltan por falta de guias).
2. `cycleCheck -e on` y mover un control de cada modulo: sin avisos.
3. `skeletonHierarchy_GRP`: `C_freeze_ENV` de raiz, un `_ENV` por joint de
   skin, correctivas colgando del `_ENV` de su padre; mover el rig y
   comprobar que el `_ENV` sigue identico al `_JNT`.
4. Masterwalk: escala 0.1x y 10x, translate a 1000 u, rotate 90 y 180 grados
   con una pose puesta: nada tiembla ni se queda atras. Si algo flota: prune
   de pesos; si es el skin de correctivas: falta localizar.
5. Rest = identidad: todos los `*Enable` de correctivas a 0 y a 1 en bind
   pose; la malla no cambia.
6. Switch IK/FK en reposo: salto 0 (`measure_fk_ik_drift` en quadruped).
7. ROM con ANIMATION > Test Rig (tabla 4), zona por zona, mirando siluetas.
8. Mirror numerico L/R en una pose simetrica.
9. Rebuild desde escena nueva: mismo resultado.

## 4. Poses canonicas (`POSE_LIBRARY` de `pose_tester`)

| Zona | Poses (grados; total o por control) |
|---|---|
| Spine | flexion / extension rotateZ +75 / -30; lateral rotateY +-35; twist rotateX +-45 |
| Neck / Head | flexion / extension rotateZ +25 / -30 por control; lateral rotateY +-20; turn rotateX +-40 |
| Clavicle | shrug rotateZ +40 / -15; forward / back rotateY +-30 |
| Shoulder | raise / lower rotateZ +170 / -50; abduction / adduction rotateY +110 / -40; twist rotateX +90 / -70 |
| Elbow | bend rotateY +-145; pronation / supination rotateX +-85 |
| Wrist | flexion / extension rotateZ +80 / -70; radial / ulnar rotateY +30 / -25; twist rotateX +-85 |
| Fingers | Curl, Spread, Cup, Fan, Thumb_Curl, Thumb_Spread +-10 |
| Hip | kick / splits rotateZ +120 / -70; side split rotateY +90 / -30; twist rotateX +-45 |
| Knee | bend rotateZ +-140; tibial twist rotateX +-15 |
| Ankle / Foot | dorsi / plantar rotateZ +25 / -50; inversion / eversion rotateY +35 / -25; ball roll rotateZ +40 / -25 |

Keys cada 10 frames (`DEFAULT_SPACING`), secuencia neutral -> max -> neutral
-> min -> neutral, una zona y un eje cada vez. Poses de doble activacion
obligatorias para correctivas (sit 90/90, squat abierto, reach diagonal,
brazos cruzados, brazo a 90 con twist completo):
`.claude/skills/corrective-joints/references/repo-y-qa.md` seccion 8.
Quadruped: la suite headless es la QA (`test_build_horse_leg_self.py`); la
pose de medida esta en `maya_tools/scripts/quadruped/autorig/criterios_solvers.md`.

## 5. Constants cheat sheet

```
fast session           evaluationManager off, cycleCheck off, undoInfo stateWithoutFlush False, refresh suspend
orden de deformers     blendShape correctivo (frontOfChain) -> skinCluster body -> skinCluster *corrective* (localizado) -> [deltaMush]
deltaMush (comentado)  smoothingIterations 10, smoothingStep 0.5, pinBorderVertices True, .scale <- C_deltaMushScale_DCM
skc                    numero mas alto; tolerancia de pesos 1e-5
ROM                    10 frames entre keys
masterwalk QA          0.1x, 10x, 1000 u, 90 y 180 grados
cycleCheck             off en build, ON en QA
```
