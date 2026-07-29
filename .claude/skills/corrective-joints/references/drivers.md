# Drivers: cómo se activan las corrective joints

Cómo leer la pose para disparar una correctiva, con las herramientas de ESTE repo.

## 1. Principio fundamental: leer la POSE, no el control

**En el cuerpo**, el driver se lee SIEMPRE del esqueleto de deformación, nunca de los
controles de animación:

- Un SDK/conexión sobre `ctl_elbow_FK.rotateZ` **muere en IK** (el control FK no rota
  cuando el solver IK produce la pose). Igual con space switching y mocap.
- Los canales euler de un control no son función unívoca de la pose (gimbal, rotate order,
  valores acumulados).
- En este repo, además, las joints van por `offsetParentMatrix`: su `rotate` local vale
  **0 siempre** — un driver sobre `joint.rotate*` no lee nada.

→ El driver se calcula desde `worldMatrix` de las joints de deformación: es la única
representación FK/IK-agnóstica. Es exactamente lo que hace `correctives.bend_driver`.

**Excepción: la cara.** En los módulos faciales no hay dualidad FK/IK — el control facial
ES la fuente canónica de la pose (las skinning joints se derivan de él por `Local_MMX`).
Leer `L_lipCorner_CTL.translateY` o un peso de blendshape es correcto y es lo que ya hace
el pipeline (thaiz). Matiz: si varias capas suman sobre la zona (`C_mainMouth_CTL` encima
de los lipCorner), lee el `matrixSum` del `Local_MMX` de la skinning joint o los plugs ya
normalizados (`{side}_lipNarrow_CLM.outputR`). Para la jaw usa `C_jaw_CTL.rotateX` (como el
auto-sticky, que mide el signo empíricamente en build) o `C_jawLocal_MMT.matrixSum`.

## 2. Los readers del repo (de simple a complejo)

### 2.1 `correctives.bend_driver(name, upper, lower, axis, sign=1.0)` — bisagras

`multMatrix` (lower.worldMatrix × upper.worldInverseMatrix) → `decomposeMatrix` con
`inputRotateOrder` puesto para que **el eje de la bisagra vaya primero** (X→xyz, Y→yzx,
Z→zxy: el ángulo tiene rango ±180 completo y no flipa al pasar de 90°) → `subtract` que
lleva el rest (bind) a 0. Devuelve un plug en grados.

- Úsalo para: codo (eje Y en este rig), rodilla (Z), dedos, flexión de muñeca.
- **NO lo extiendas a hombro/cadera/muñeca completa**: la resta euler tras el decompose
  solo es fiable en bisagras casi puras. Multi-eje → cone driver o RBF.
- L/R: el ángulo de la matriz relativa NO cambia de signo en R (verificado en arm/leg:
  ambos llaman con sign=1). No inviertas el signo "por si acaso".

### 2.2 `matrix_manager.bend_factor(m0, m1, m2, name)` — factor 0-1 suave

Flexión de una cadena de 3 puntos por producto escalar: `(1-cos)/2`. Monótono, sin flips
cerca de 180°, ya normalizado 0-1. Alternativa a bend_driver cuando quieres un factor
directo sin pensar en grados. **Ojo a la firma**: `m0/m1/m2` son NODOS con atributo
`.outputMatrix` (blendMatrix/aimMatrix — los custom modules le pasan los blendMatrix de la
cadena), NO joints: con una joint (solo `worldMatrix`) el connectAttr falla. Para joints,
interpon un nodo o adapta la función a plugs de matriz.

### 2.3 `matrix_manager.extract_twist(source_plug, ref_plug, axis, name)` — twist

Descomposición **swing-twist por quaternions** (proyección del quaternion sobre el eje del
hueso, rest neutralizado). Sin gimbal, exacto. Límite: ±180° (suficiente para
pronosupinación anatómica ±90–110°; para acumulación >180° haría falta quatSlerp 0.5 ×2 o
un plugin tipo QuatTwist — documéntalo si surge, no lo improvises).

Receta de correctiva driven por twist (pendiente de instanciar en el repo). Ojo: los
joints del ribbon reparten el twist creciente hacia la muñeca (`armLower00` ≈ 0%,
el último ≈ 100%) — lee el twist del joint MÁS DISTAL del ribbon (con
`arm_skinning_jnts=5`, `armLower04`), no del medio (que solo lleva ~50%):

```python
tw = matrix_manager.extract_twist(f"{side}_armLower04_JNT.worldMatrix[0]",
                                  f"{side}_armLower00_JNT.worldMatrix[0]",
                                  axis="x", name=f"{side}_wristTwist")
correctives.corrective_push(f"{side}_wristTwistCorrective", base_jnt,
                            f"{tw}.outputRotateX", in_min=0, in_max=90,
                            axis=..., amount_attr=...)
# supinación: segunda push con in_max=-90, eje opuesto y canales de translate distintos
```

### 2.4 `correctives.cone_driver(name, joint, ref_parent, target_world, bone_axis="X", axis_sign=1.0, margin=0.02, half_angle=None)` — multi-eje (hombro, cadera)

**YA implementado** en `utils/correctives.py`. Pose reader de cono AUTO-CALIBRADO:
devuelve un plug 0..1 que vale **0 en la pose de build** (sea T-pose o A-pose: el
`inputMin` del remap se fija al dot del eje en rest contra el target) y **1 cuando el eje
del hueso apunta a `target_world`** (dirección MUNDO en bind, convertida a espacio de
`ref_parent` y horneada estática). Grafo: multMatrix (hueso × padre⁻¹) → rowFromMatrix
(eje) → vectorProduct dot (normalizeOutput) → remapValue smooth. Devuelve `None` si el
target está demasiado cerca del rest (cono degenerado) — trátalo siempre.

- La dirección se mide respecto a un ref que siga al TORSO/PELVIS
  (`C_localChestSkinning_JNT`, `C_localHipSkinning_JNT`): mundo-agnóstico, inmune a
  masterwalk.
- **`onset` SIEMPRE en producción** (25–30°): grados de VIAJE desde el rest antes de
  arrancar — se auto-adapta al bind (con A-pose el arco rest→target puede ser 135° y un
  `half_angle` fijo llegaba tardísimo; con onset arranca a N° de elevación salga de donde
  salga el rest, y sigue valiendo 0 exacto en bind). `half_angle` existe como alternativa
  de semiángulo fijo. Sin ninguno: rampa de hemiesfera que se cuela en poses cotidianas.
- **Targets anatómicos, no cardinales ciegos**: el deltoides pica a ~90° de abducción
  (brazo en T+45), así que su cono apunta a la DIAGONAL fuera-arriba
  `(±0.707, 0.707, 0)`, no a (0,1,0) — con target vertical el push llega tarde y débil
  justo en la pose donde más se ve el hombro.
- **`axis_sign`**: en R el ribbon puede aimear −X a lo largo del hueso — mide el signo con
  `dot(ejeX_de_la_fuente, dirección upper→lower)` y pásalo (así lo hacen
  `shoulder_corrective_setup` y `hip_corrective_setup`).
- **Fuente = frame RÍGIDO, no un joint de ribbon**: los bendys reorientan
  `armUpper00`/`legUpper00` y contaminan el cono — usa `{side}_armNonRollAim_AMX` /
  `{side}_legNonRollAim_AMX` (cone_driver acepta nodos con `outputMatrix` vía
  `matrix_source`). Las correctivas de hombro/cadera van SOLO en upper00 o en un frame
  non-roll: upper01+ llevan twist y las harían orbitar.
- **Pre-rota la dirección de empuje**: la correctiva vive en el frame del hueso, que rota
  rest→target al activarse — una dirección autorada en mundo "en bind" llega girada hasta
  90° en la pose donde el driver vale 1 (el deltoides empujaría hacia el cuello). Autora
  la dirección EN LA POSE OBJETIVO y pásala por `correctives.target_frame_dir(dir,
  bone_rest_world, target_world)` antes de `world_to_local_dir` (patrón de los `push()`
  de shoulder/hip).
- El twist es invisible al cono (feature): combínalo con `extract_twist` si la pose
  necesita twist.
- Usos reales: hombro (`arm_module.shoulder_corrective_setup`: diagonal fuera-arriba
  onset=25 → deltoid/armpit, (0,0,±1) onset=30 → pec/shoulderBack, ref = chest) y cadera
  (`leg_module.hip_corrective_setup`: flexión (0,0,1) onset=30 y abducción ±X onset=25 →
  glute/groin/hipOut, ref = pelvis).
- **QA tras pintar influencias nuevas**: `localize_corrective_skin` corre en el BUILD —
  una influencia añadida al `C_corrective_SKC` después de buildear queda SIN localizar
  (bindPreMatrix estática → doble transformación: la zona se hunde en vez de empujar).
  Tras añadir/pintar influencias, re-ejecuta
  `correctives.localize_corrective_skin("C_corrective_SKC")` en pose neutra (idempotente).

### 2.5 RBF / pose space (cuándo escalar)

Un solver RBF interpola N poses ejemplo → valores driven ("next-level set driven key").
Implementaciones: `weightDriver` (Ingo Clemens / mGear RBF Manager), `poseInterpolator`
nativo de Maya (Pose Editor), Pose Driver de UE + Pose Driver Connect.

Regla: si estás normalizando conos a mano o encadenando 3+ condition/remap para que las
poses no se pisen → es momento de RBF. **No reimplementes RBF a mano**: usa mGear
weightDriver (el `.build` ya tiene el flag `mGear_integration`) o `poseInterpolator`.
Hasta 4–6 poses por articulación, los conos cardinales bastan.

### 2.6 Drivers faciales

Ver `faciales.md` §drivers — pesos de blendshape (`C_facial_local_BLS.<target>`, plug
0..1 conectable), controles faciales, `distanceBetween` (blink/sticky — ¡divide por
`globalScale`!), y combos por `multiply`/`combinationShape`.

## 3. Redes de nodos (Maya 2024+/2025, el estilo del repo)

Cadena estándar por correctiva (así lo hace `correctives.py`):

```
reader (bend_driver / bend_factor / twist / cone)
  → remapValue  {name}_RMV     (rango in_min→in_max ⇒ 0..1, AUTO-CLAMP)
  → multiply    {name}T{X|Y|Z}_MUL:
       input[0] = 0..1 del remap
       input[1] = amount (PLUG del atributo tunable, nunca valor horneado)
       input[2] = componente del eje (normalizado)
       input[3] = enable (0/1) opcional
  → jnt.translate{X|Y|Z}       (la joint es hija del hueso, jointOrient=0)
```

- Nodos math 2024: `multiply`/`sum` con arrays `input[i]`, `subtract` con
  `input1/input2` — NO uses `multiplyDivide`/`multDoubleLinear` en código nuevo.
- `remapValue` clampa por defecto fuera de rango: es el seguro contra "la correctiva
  dispara al infinito a 160°". Siempre entre driver y translate.
- `rowFromMatrix` `input=0/1/2` = ejes X/Y/Z de una matriz, `input=3` = traslación: el
  idioma del repo para extraer vectores sin decomposeMatrix.
- Todo nodo con `ss=True` y sufijo del repo (`_MUL`, `_SUM`, `_RMV`, `_MM`, `_DEC`…) para
  que `hide_all_utility_nodes()` lo trate bien.
- Exponer el output del reader como attr legible (p.ej. `settings.elbowAngle`) ayuda a
  debuggear sin abrir el Node Editor.

## 4. Mirroring L/R — LA regla de este repo (no re-razonarla)

Las guías se espejan con `mirrorJoint -mirrorBehavior` → en R los ejes locales NO son un
espejo limpio. Consecuencias verificadas en producción (arm/leg):

1. **Driver angular** (bend_driver/bend_factor/twist/cone): da el MISMO signo en L y R →
   no toques `sign` ni rangos. (El docstring de `bend_driver` que dice "sign: -1 en R"
   está obsoleto y contradice las llamadas reales de arm/leg — ignóralo; si tocas esa
   zona, arregla el docstring.)
2. **Vectores driven** (ejes de push, rest_offset, forward/up del arc, target_vec del
   cono): **negar el vector COMPLETO en R** — `_ax(v) = v if L else (-vx, -vy, -vz)`.
   (La helper `_ax` está duplicada en arm y leg; si tocas esa zona, muévela a
   `utils/correctives.py` como `mirror_axis(v, side)`.)
3. **Pesos**: pintar L → `copySkinWeights` con `mirrorMode="YZ"`,
   `influenceAssociation=["oneToOne","name","closestJoint"]` (el naming L_/R_ hace el
   match) → exportar `.skc`.
4. **Blendshapes correctivos**: ya resuelto por el CBS manager (`mirror_targets` niega
   `tx, ry, rz` del driver — correcto para mirror-behavior).
5. **Verificación numérica obligatoria**: pose simétrica (ambos codos a 90°) y comparar
   `getAttr translate` de cada correctiva L vs R. Nunca a ojo.

## 5. Escala global y lejos del origen

- Readers por matriz relativa (`world × worldInverse`) → inmunes al masterwalk. ✔
- Pushes en translate LOCAL de una hija → heredan el `globalScale` del padre. ✔
- Defaults calculados de las guías (12% del hueso) → independientes del tamaño. ✔
- **Riesgo**: drivers por `distanceBetween` (blink, sticky) SÍ dependen de la escala →
  divide la distancia por `C_masterwalk_CTL.globalScale` (o por una distancia de rest
  medida en build) antes del remap. El patrón existe: `segment_volume` ya recibe
  `global_scale_attr`.
- Test obligatorio: masterwalk a 0.1x/2x/10x, a 1000 unidades y rotado.

## 6. Errores comunes de driver (checklist)

1. ¿Lees `worldMatrix` del esqueleto (cuerpo) o el control/peso canónico (cara)? — nunca
   el rotate local de una joint por matriz, nunca un FK ctl del cuerpo.
2. ¿Rest = 0 exacto en el reader?
3. ¿Rotate order del decompose con el eje de bisagra primero?
4. ¿Twist por quaternion, no por euler?
5. ¿remapValue clampa el rango? (nada de extrapolación)
6. ¿`amount` y `enable` como plugs?
7. ¿Sin leer la malla deformada, sin escribir hacia arriba de la jerarquía? (ciclos)
8. ¿Mirror verificado numéricamente?
9. ¿Sobrevive a masterwalk escalado/trasladado/rotado?

## 7. Export / bake

Los nodos del grafo no viajan por FBX. En este repo el esqueleto de export `_ENV` se
encadena por matrices y **toda joint con `corrective`/`ring` en el nombre se cuelga del
`_ENV` de su joint padre automáticamente** (`skeleton_hierarchy`). Para engine: bakear la
animación sobre los `_ENV` (correctivas incluidas) por clip. Si algún día hace falta
runtime procedural en UE: Pose Driver / Pose Driver Connect (autoría RBF en Maya, mismo
solver en UE) — no aplica al pipeline actual.
