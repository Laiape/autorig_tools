# Modulos quadruped

Parent: `como_funciona.md` (raiz).
Reglas: `.claude/rules/convenciones-rig.md`, `.claude/rules/deformacion-y-skin.md`.
Skill relacionada: `.claude/skills/skinning-deformation/SKILL.md` (zonas quadruped).
Dispatch: `maya_tools/scripts/utils/rig_manager.py` (`build_rig`, rama `Rig_Type == 1`).
Criterios medidos de solver y pole vector: `maya_tools/scripts/quadruped/autorig/criterios_solvers.md` (Fase 3, pendiente; hoy los numeros viven en los docstrings de las clases y en los commits).
Test: `maya_tools/scripts/tools/tests/test_build_horse_leg_self.py`.

## 1. Que es y para que existe

Modulos del rig de cuadrupedo (`Rig_Type` 1 en el `.build`: horse, giraffe).
Misma arquitectura que biped (clase `XxxModule`, `make(side, ...)`, datos por
`data_manager`) con una idea propia en las patas, escrita en la cabecera de
`leg_module_self.py`: la superclase `LegModule` contiene lo comun a cualquier
cuadrupedo; las subclases `FrontLegModule` y `BackLegModule` solo cambian
TOPOLOGIA (escapula frente a cadera, sentido del doblez, signo del pole
vector); y lo que cambia entre especies (acoplamiento, tipo de pie, solver)
llega como VALOR desde el `.build`. No hay subclases por animal.

## 2. Como esta montado

### 2.1 Dispatch en `build_rig` (orden real)

1. Spine si existe `C_spine00_JNT` (`quad_spine_module`; `giraffe` fuerza
   `SAGITTAL_BIAS = 1.0` por `UNIFORM_SPINE_CHARS`).
2. Solvers por tren: `resolve_leg_solvers(rig_settings, override=leg_solver)`.
   Orden de prioridad: `leg_solver` del menu (SELF MATH -> `nodes`) >
   `solver_mode == 1` (custom solvers -> `nodes` en ambos trenes) >
   `solver_front_leg` / `solver_back_leg` (indice o nombre de
   `LEG_SOLVER_OPTIONS`) > `leg_solver` de builds viejos > `spring`.
3. Patas delanteras si existen `L_frontLegShoulder_JNT` y `R_`: `leg_impl`
   `"self"` -> `leg_module_self.FrontLegModule`; `"reference"` ->
   `leg_module.FrontLegModule`. Fallback con naming viejo `L_frontLeg_JNT`.
4. Patas traseras si existen `L_backLegHip_JNT` y `R_`: idem con `BackLegModule`.
5. Clavicula, brazos y dedos (modulos biped) si hay guias `L_clavicle_JNT`,
   `L_shoulder_JNT`, `L_thumb00_JNT`.
6. Cola si `C_tail00_JNT`; cuello si `C_neck00_JNT` (`neck_module` quad).
7. Cara: los mismos modulos que biped (eyelid sin sockets y con `surface=True`).
8. `quadruped_space_switches()`, `skeleton_hierarchy()`, `apply_character_extras()`.

### 2.2 Ficheros

| Fichero | Clases | Guias que lo activan | Firma de `make` | Estado |
|---|---|---|---|---|
| `leg_module_self.py` (2830) | `LegModule`, `BackLegModule`, `FrontLegModule`, `FootBase`, `HoofFoot`, `PawFoot` | `{side}_{prefix}{Root}_JNT` (cadena), `{side}_{prefix}Settings_LOCShape`, pivotes `{side}_{prefix}{role}_LOCShape`, `{side}_scapula_JNT` (delantera) | `make(side, solver="spring", skinning_joints_number=5, bendys=True, config=None)` | ACTIVO (`leg_impl="self"`, menu CREATE RIG SELF y SELF MATH) |
| `leg_module.py` (1625) | `LegModule`, `BackLegModule`, `FrontLegModule` | idem | `make(side, solver="spring", skinning_jnts=5, bendys=True, primaryInputAxis=(1,0,0), secondaryInputAxis=(0,1,0))`; solo `spring` o `rp` | REFERENCIA (`leg_impl="reference"`, menu CREATE RIG). Es la implementacion anterior; conserva `foot_offset_setup`, `_fetlock_spring`, `reciprocal_fk_coupling` y su propia escapula |
| `spine_module.py` (376) | `SpineModule` | `C_spine00_JNT` (cadena), `C_localHip_JNT` | `make(side, spine_joints, spine_controllers)` | activo. `SAGITTAL_BIAS = 1.3` medido contra la lumbosacra del caballo (docstring de la clase) |
| `neck_module.py` (287) | `NeckModule` | `C_neck00_JNT` (cadena) | `make(side, skinning_joints_number, controllers_number)` | activo |
| `tail_module.py` (259) | `TailModule` | `C_tail00_JNT` (cadena) | `make(side, skinning_joints_number, controllers_number)` | activo; tambien lo usa el biped si hay guia de cola |
| `digits_module.py` (289) | `DigitsModule` | dedos bajo `{prefix}_module/{side}_mtp_JNT` | `make(side, leg_prefix="frontLeg")` | SIN LLAMAR desde `build_rig`. Es la referencia del reparto de Spread que `PawFoot` de `leg_module_self` reimplementa. Solo `leg_module.py` publica la clave `_mtp_JNT` que necesita |

### 2.3 `leg_module_self`: orden de construccion (docstring de `make`)

`load_guides` -> `orient_guides` (frames horneados) -> `setup_chain` (indices,
plano, bend_dir) -> `create_chains` -> `controllers_creation` (settings, FK,
IK, pivotes del pie) -> `ik_setup` (conmuta el solver por `IK_CONFIGS`) ->
`ik_stretch_soft` -> `ik_calibration` (barrido de twist del spring, reposo
< 0.002) -> `fk_setup` -> `blend_setup` (blend FK/IK por joint, salida = plugs)
-> `reciprocal_coupling` si el `.build` lo pide -> `foot.build` (`HoofFoot` o
`PawFoot` segun `foot_type`) -> `roll_and_non_roll_setup` + `bendys_setup` si
`bendys` -> `skinning_setup` -> `publish`. La delantera anade `scapula_setup`.

Solvers (`LEG_SOLVER_OPTIONS` en `rig_manager`): `spring`, `rp`, `spring_rp`,
`nodes`, `sc_rp_sc`, `sc_rp_sc_carpus`, `rp_rp`. Las fichas de `IK_CONFIGS`
existen para `rp`, `spring`, `sc_rp_sc`, `sc_rp_sc_carpus` y `rp_rp`; `nodes`
va por `_ik_nodes` (IK analitico por teorema del coseno, carga los plugins
`matrixNodes` y `lookdevKit` y borra las cadenas IK al terminar). `spring_rp`
esta en la lista de opciones pero no tiene ficha en `IK_CONFIGS` (NO VERIFICADO
que construya).

Flags de clase (hechos anatomicos, no preferencias): `LEG_PREFIX`,
`ROOT_JOINT`, `FORWARD_AXIS`, `PV_SIGN` (-1 = caudal en ambos trenes, medido),
`PV_APEX_INDEX`, `REPOSITION_IK_TO_GUIDES`, `RECIPROCAL_COUPLING` (True en la
trasera: peroneo tercero tendinoso del equido), `FOOT_CLASS`,
`STANDARD_JOINT_COUNT = 6`.

Pie compuesto (`FootBase`): pivotes reversos por guia `{side}_{prefix}{role}_LOCShape`
con controles `{side}_{prefix}{Role}_CTL` (offsets GRP/SDK/ANM) y atributos
`FOOT_ATTRIBUTES`, `Roll_Break_Angle`, `Roll_Straight_Angle`, `Pivot_Controllers`.
`HoofFoot` anade `hoof_attach` y `fetlock_spring` (`SPRING`, `Load`);
`PawFoot` anade `paw_attach`, guias y FK/IK de dedos (`Toes_IK`) y SDK de
dedos con el reparto de Spread de `digits_module`.

### 2.4 Joints de skin y controles

| Modulo | Joints de skin | Controles y atributos principales |
|---|---|---|
| Pata (bendys) | un ribbon de Boor por segmento (nombres en `skinning_setup`), `{side}_{prefix}<Fetlock>Skinning_JNT` y `<Pastern>Skinning_JNT` (indices `leg_end` y `plant`), `...TipSkinning_JNT`, `{side}_scapulaSkinning_JNT` (delantera), `{base}{NN}Skinning_JNT` por falange (paw) | `{side}_{prefix}Settings_CTL` (`switchIkFk`), FK (`Stretch`, `extraAttr`), IK ankle y root (`STRETCHY`, `Stretch`, `SOFT`, `Soft`, `Soft_Start`, `BEND`, `Bend_Bias`, `Twist`), bendys (`bendys`), pie (arriba), escapula (`SCAPULA_ATTRIBUTES`, `Auto_Scapula`, `Multiply_Amount`, `Sling`), `Coupling` |
| Pata (sin bendys) | la cadena guia renombrada `*Skinning_JNT` | idem |
| Spine | `C_spine00_JNT ... C_spine0{n-1}_JNT` (ribbon por longitud de arco), `C_localHipSkinning_JNT`, `C_localChestSkinning_JNT` | `C_body_CTL`, `C_pelvis_CTL`, `C_localChest_CTL`, `C_spine0N_CTL` (`Stretch`, `Stretch_Activate`), `C_spine0NAttatchedFk_CTL` (`FK`, `FK_Vis`) |
| Neck | `C_neck00_JNT ...`; el ultimo se renombra `C_headSkinning_JNT` | `C_face_CTL` (`FACE_VIS`), `C_neckN_CTL` (`Stretch`, `Stretch_Activate`, `TANGENT_VISIBILITY`, `Controllers_Visibility`), `C_head_CTL` (`NECK_FOLLOW`, `HEAD_FOLLOW`) |
| Tail | `C_tail00_JNT ...` (ribbon); `C_tailIkNN_JNT` son mecanica, no skin | FK + IK spline (`ikSplineSolver`), `EXTRA_ATTRIBUTES`, `Bendy` |

## 3. Datos que lee y escribe

- Lee del `.build`: `leg_skinning_jnts`, `spine_skinning_jnts`,
  `spine_controllers`, `neck_*`, `tail_*`, `solver_mode`, `solver_front_leg`,
  `solver_back_leg`, `reciprocal_coupling`, `foot_type`. `leg_module_self`
  relee el `.build` dentro de `make` (`build_rig_from_data`) para
  `reciprocal_coupling` y `foot_type`.
- Publica en cache: `{prefix}_module/{side}_legIk`, `_rootIk`, `_hipFk`
  (self) y ademas `_scapula_master_ctl` (delantera). La referencia publica
  mas claves (`_legPv`, `_ikFkSwitch`, `_bendy_ctls`, `_footOffset`,
  `_mtp_JNT`, `_scapula_ctl`, `_scapula_end_ctl`). `spine_module/local_hip_ctl`,
  `body_ctl`, `local_chest_ctl`; `neck_module/head_ctl`, `neck_ctl`,
  `head_guide_matrix`, `face_ctl`; `tail_module/tail_ctl`.
- Consume: `basic_structure/*`, `spine_module/local_chest_ctl` (sling de la
  escapula). `quadruped_space_switches` resuelve sus targets por estas claves y
  salta en silencio los que no existen.
- `SAGITTAL_BIAS` del spine NO esta en el `.build`: el comentario de la clase
  avisa de que anadirlo exige tocar tambien `create_rig_settings` (solo admite
  int/enum) porque `get_rig_data` reescribe el `.build` desde los atributos.

## 4. Estado hoy

- `leg_module_self` es lo activo y donde esta el churn (10 de los ultimos 10
  commits tocan `quadruped/`). `leg_module` se mantiene como referencia
  comparable (menu CREATE RIG).
- Resultados medidos que ya son decision (numeros en los docstrings de
  `BackLegModule`, `FrontLegModule` y `SpineModule`, a pasar a `criterios_solvers.md`): pole vector caudal en ambos trenes; `rp_rp` con
  resultado negativo; `reciprocal_coupling` por especie desde el `.build`;
  `foot_type` hoof/paw por datos; `SAGITTAL_BIAS = 1.3`.
- `digits_module.py` no lo llama nadie: candidato a borrar cuando `PawFoot`
  cubra todo lo que hacia.
- Instrumentacion en el propio modulo: `measure_bend_distribution(pose)` y
  `measure_fk_ik_drift()`.

## 5. Como probarlo

- Build completo: Asset Manager con `horse` o `giraffe` activo -> menu
  RIGGING > CREATE RIG SELF (o SELF MATH para forzar `nodes`).
- Headless: `mayapy maya_tools/scripts/tools/tests/test_build_horse_leg_self.py`.
  Monta las cuatro patas con las guias del caballo y comprueba reposo sobre
  la guia, espejo L/R, `Bend_Bias` (spring y nodes), solver `nodes` sin
  ikHandles y con stretch, `sc_rp_sc` y `sc_rp_sc_carpus` (doblez del carpo,
  switch sin salto, roll), drift IK/FK ~0 y el sling de la escapula con el
  spine.
- Contra metraje real: `maya_tools/scripts/tools/analysis/gallop_kinematics.py`
  convierte landmarks 2D de un video de galope en los mismos angulos
  interiores (codo, carpo, menudillo) que mide el test.

## 6. Do not

- No crear una subclase por animal: lo que cambia por especie va al `.build`.
- No anadir un flag de clase sin escribir al lado el hecho anatomico que lo
  justifica (regla de oro de la cabecera del fichero).
- No cambiar `PV_SIGN`, `SAGITTAL_BIAS` ni un solver "a ojo": se mide con el
  test y se anota en el docstring (y en `criterios_solvers.md` cuando exista).
- No pasar nombres de nodo a mano entre pata, spine y switches: `publish` y
  `get_data`.
- No leer `rotate` local de los joints de la cadena: todo va por matrices y
  plugs (`blend_setup` devuelve plugs).
