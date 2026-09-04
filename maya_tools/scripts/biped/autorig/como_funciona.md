# Modulos biped (cuerpo y cara)

Parent: `como_funciona.md` (raiz).
Reglas: `.claude/rules/convenciones-rig.md`, `.claude/rules/deformacion-y-skin.md`.
Skills: `.claude/skills/skinning-deformation/SKILL.md` (que pinta cada joint),
`.claude/skills/corrective-joints/SKILL.md` (correctivas de cuerpo y cara).
Dispatch: `maya_tools/scripts/utils/rig_manager.py` (`build_rig`, rama `Rig_Type == 0` y bloque FACIAL).
Motor de ribbons: `maya_tools/scripts/utils/ribbon.py`. Correctivas: `maya_tools/scripts/utils/correctives.py`.

## 1. Que es y para que existe

Un fichero por parte del cuerpo o de la cara. Cada modulo es una clase
`XxxModule` con `make(side, ...)` que lee `basic_structure` del cache, importa
sus guias, construye por matrices, crea sus joints de skin bajo
`{side}_{modulo}Skinning_GRP` (en `skel_GRP`) y publica en cache lo que otros
modulos necesitan. Los modulos faciales cuelgan de `neck_module/head_ctl` y
`face_ctl`, y la mandibula publica las matrices locales que usan dientes y
lengua.

## 2. Como esta montado

### 2.1 Patron de modulo (el que siguen todos)

```
class XxxModule(object):
    def __init__(self):          # lee basic_structure (modules_GRP, skel_GRP, masterwalk_ctl, preferences_ctl)
    def make(self, side, ...):   # crea {side}_xxxModule_GRP, {side}_xxxSkinning_GRP, {side}_xxxControllers_GRP
        self.load_guides()       # guides_manager.get_guides("<nombre exacto de la guia>")
        ...setups...             # controles con curve_tool.create_controller, matrices, ribbons
        self.corrective_setup()  # solo arm y leg: correctivas de cuerpo al final del make
        data_manager.DataExportBiped().append_data("xxx_module", {...})
```

Cabecera: `from maya_tools.scripts.utils import x` + `reload(x)`. Los grupos
`Module_GRP` conectan `globalScale` del masterwalk a su escala.

### 2.2 Dispatch en `build_rig` (orden real, `Rig_Type == 0`)

| Orden | Condicion (guias) | Modulo y llamada |
|---|---|---|
| 1 | `C_spine00_JNT` | `spine_module.SpineModule().make("C", spine_skinning_jnts, spine_controllers)` |
| 2 | `L_hip_JNT` y `R_hip_JNT` | `leg_module.LegModule().make(side, leg_skinning_jnts)` |
| 3 | `L_clavicle_JNT` y `R_` | `clavicle_module.ClavicleModule().make(side)` (floating desactivado) |
| 4 | `L_shoulder_JNT` y `R_` | `arm_module.ArmModule().make(side, arm_skinning_jnts)` |
| 5 | `L_thumb00_JNT` y `R_` | `fingers_module.FingersModule().make(side)` |
| 6 | `C_tail00_JNT` | `tail_module` (quadruped) |
| 7 | `C_neck00_JNT` | `neck_module_de_boor.NeckModule().make("C", neck_skinning_jnts, neck_controllers, mGear_integration=bool)` |
| 8 | `C_jaw_JNT` | `jaw_module_nurbs.JawModule().make("C")` |
| 9 | `L_eyebrowMain_JNT` y `R_`, o `L_eyebrow_CRVShape` y `R_` | `eyebrow_module.EyebrowModule().make(side)` |
| 10 | `L_eye_JNT` y `R_` | `eyelid_module.EyelidModule().make(side, sockets=(biped), surface=...)`; `surface` es True en quadruped o si el personaje esta en `EYELID_SURFACE_CHARS` (thaiz, mechanic, freya, maui, anne, edward) |
| 11 | `C_tongue00_JNT` | `tongue_module.TongueModule().make("C")` |
| 12 | `C_upperTeeth_JNT` | `teeth_module.TeethModule().make("C")` |
| 13 | `L_ear00_JNT` y `R_` | `ear_module.EarModule().make(side)` |
| 14 | `C_nose_JNT` | `nose_module.NoseModule().make("L")` y `make("R")` |
| 15 | `L_cheekbone_JNT` y `R_` | `cheekbone_module.CheekboneModule().make(side)` |
| 16 | jaw, eye o eyebrow presentes | `facial_correctives_module.FacialCorrectivesModule().make()` |
| 17 | `mGear_integration == 0` | `biped_space_switches()` |
| 18 | siempre | `skeleton_hierarchy()`, `apply_character_extras(rig_settings)` |

`biped_space_switches` cablea: neck (chest, body), localHip (body), armIk
(body, clavicle, chest, localHip, head), armPv (body, armIk, clavicle, chest),
legIk (localHip, body), legPv (body, legIk), shoulderFk (clavicle, chest,
body), hipFk (body, localHip), rootIk (localHip), clavicle (chest, body),
armIkRoot (clavicle, chest). Los nodos salen del cache, nunca a mano.

### 2.3 Cuerpo

| Fichero | `make` | Guias | Joints de skin | Controles y atributos | Publica en cache | Estado |
|---|---|---|---|---|---|---|
| `arm_module.py` (987) | `make(side, skinning_jnts, primaryInputAxis=(1,0,0), secondaryInputAxis=(0,0,1))` | cadena `{side}_shoulder_JNT`, `{side}_armSettings_LOCShape` | ribbons `{side}_armUpper00..`, `{side}_armLower00..` (n = `arm_skinning_jnts`), `{side}_wristSkinning_JNT`; correctivas `{side}_bicepsCorrective_JNT`, `tricepsCorrective`, `elbowRing0N`, hombro (cone) | `{side}_armSettings_CTL` (`Ik_Fk`), FK `{side}_<joint>Fk_CTL`, `{side}_armIkWrist_CTL`, `{side}_armPv_CTL`, `{side}_armIkRoot_CTL`, bendys `{side}_arm{Upper,Lower}{Main,Up,Low}Bendy_CTL`; attrs `STRETCHY`, `SOFT`, `EXTRA_ATTRIBUTES`/`Pin`, `Height`, `Extra_Controllers`, `CORRECTIVES_SEP`; en la clavicula `AUTO_CLAVICLE`/`AutoClavicle`/`StartAngle`/`Factor` | `arm_module/{side}_shoulder_JNT`, `_wrist_JNT`, `_armSettings`, `_armIk`, `_armPv`, `_shoulderFk`, `_armIkRoot`, `_skinningJoints`; consume `clavicle_module/{side}_clavicle` | activo |
| `arm_module_custom.py` (805) | misma firma | idem | idem sin correctivas | `Curvature`, `AutoBend`, `Volume` en vez de correctivas y soft IK | `arm_module/*` (mismas claves) | LEGACY: no lo llama `build_rig`; variante anterior con pole vector por matrices propio |
| `leg_module.py` (1003) | `make(side, skinning_jnts, primaryInputAxis=(1,0,0), secondaryInputAxis=(0,-1,0))` | cadena `{side}_hip_JNT`, `{side}_legSettings_LOCShape`, `{side}_bankIn_LOCShape`, `_bankOut_`, `_heel_` | ribbons `{side}_legUpper00..`, `{side}_legLower00..`, `{side}_legAnkleSkinning_JNT`, `{side}_legBallSkinning_JNT`; correctivas `thighFront`, `thighBack`, cadera (cone) | `{side}_legSettings_CTL` (`Ik_Fk`), FK, pivotes de pie `{side}_<pivote>_CTL` (GRP/SDK) con `Roll_Break_Angle`, `Roll_Straight_Angle`, `{side}_legRootIk_CTL`, `{side}_legPv_CTL`, bendys; `STRETCHY`, `EXTRA_ATTRIBUTES`/`Pin`, `CORRECTIVES_SEP` | `leg_module/{side}_hip_JNT`, `_knee_JNT`, `_ankle_JNT`, `_legIk`, `_hipFk`, `_legPv`, `_rootIk`; consume `spine_module/local_hip_ctl` | activo |
| `leg_module_custom.py` (943) | misma firma | idem | anade `{side}_legToeSkinning_JNT` | `Curvature`, `AutoBend`, `Volume` | `leg_module/*` | LEGACY: no lo llama `build_rig` |
| `spine_module.py` (610) | `make(side, spine_skinning_jnts, spine_controllers)` | cadena `C_spine00_JNT`, `C_chest_JNT` | `C_spineNNSkinning_JNT` (uno por guia), `C_localHipSkinning_JNT`, `C_localChestSkinning_JNT` | `C_body_CTL`, `C_localHip_CTL`, `C_localChest_CTL`, IK `C_spineNN_CTL` + tangentes `C_spineNNTan_CTL`, FK `C_spineNNAttatchedFk_CTL` (sic); attrs `spineStretch`/`Min`/`Max`, `spineOffset`, `volumePreservation`, `spineFalloff`, `spineSquashMaxPos`, `FK`, `FK_Vis`, `IK_Vis`, `Hip_Vis`, `follow`, `tanControllers`, `tanVisibility`, `maxStretch*`, `volume` | `spine_module/local_hip_ctl`, `body_ctl`, `local_chest_ctl`, `last_spine_jnt` | activo (IK spline + FK adjunto, no de Boor) |
| `neck_module_de_boor.py` (284) | `make(side, skinning_joints_number, controllers_number, mGear_integration=False)` | cadena `C_neck00_JNT` | ribbon `C_neckSkinning00..`, `C_headSkinning_JNT`, `C_throatSkinning_JNT` | `C_face_CTL` (`FACE_VIS`), `C_neck_CTL`, `C_head_CTL`, `C_throat_CTL`, `C_headSquash_CTL` (`Volume`) | `neck_module/head_ctl`, `neck_ctl`, `head_guide_matrix`, `face_ctl`, `head_squash_ctl`; en modo mGear: `head_ctl`, `face_ctl`, `head_guide_matrix`, `mGear` | activo |
| `clavicle_module.py` (217) | `make(side, floating=False)` | `{side}_clavicle_JNT` (+ `{side}_shoulder_JNT` para la longitud) | `{side}_clavicleSkinning_JNT` | `{side}_clavicle_CTL` (GRP/OFF); con `floating`: NURBS `{side}_clavicleFloating_NRB` y attrs `FLOATING_SEP`/`Floating` | `clavicle_module/{side}_clavicle` | activo (build sin floating) |
| `fingers_module.py` (233) | `make(side)` | `{side}_{thumb,index,middle,ring,pinky}00_JNT` (cadenas) | las guias renombradas `*Skinning_JNT` | FK por falange; SDK Curl/Spread/Twist/Fan/Cup en `attributes_setup` (`_CUP_WEIGHTS`, `_CUP_MAX_RZ = -45`) | nada; consume `arm_module/{side}_wrist_JNT` | activo |
| `wing_module.py` (152) | `make(side, chains, joints_along=None, joints_across=None, controls_per_gap=3)` | ninguna: recibe cadenas ya construidas | rejilla `{name}_JNT` pineada por `uvPin` a una NURBS lofteada y skinneada (`surface_pin`) | controles de membrana por hueco | `{side}_wing_module/membrane_ctls`, `surface` | EXPERIMENTAL: no lo llama `build_rig`; test propio |

### 2.4 Cara

Todos consumen `neck_module/head_ctl`, `face_ctl`, `head_guide_matrix` y
`basic_structure/preferences_ctl`, y cuelgan sus joints de `*head_ENV` en el
export. El numero de joints sale del numero de guias o CVs, no del `.build`.

| Fichero | `make` | Guias | Joints de skin | Controles y atributos | Publica / consume | Estado |
|---|---|---|---|---|---|---|
| `jaw_module_nurbs.py` (1348) | `make(side)` | `C_jaw_JNT`, `C_jaw_NURBShape`, `C_upperLipLinear_CRVShape`, `C_lowerLipLinear_CRVShape` | `C_jawSkinning_JNT`, `C_upperJawSkinning_JNT`, labios por CV `{R,C,L}_{upper,lower}Lip{NN}_JNT` y `...NonRot_JNT`, `{side}_cornerLip_JNT` | `C_jaw_CTL`, `C_upperJaw_CTL`, `C_upperLip_CTL`, `C_lowerLip_CTL`, `{side}_lipCorner_CTL`, control main de boca; attrs `EXTRA_ATTRIBUTES`/`Auto_Collision`, `Roll`, `Height`, `PushOut`, `StretchVolume`, `mouthHeight`, `StickyLips`, `StickyRange`; vis `Jaw`, `Lips` | publica `jaw_module/jaw_ctl`, `upper_jaw_ctl`, `main_mouth_ctl`, `local_jaw_mmx`, `local_upper_jaw_mmx` | activo. Deformers: skinCluster sobre curvas y NURBS (`C_{part}Nurbs_SKIN`, `C_{part}LipOffset_SKIN`), `uvPin` |
| `jaw_module_bezier.py` (1944) | `make(side)` | idem | labios por bezier; `C_midLips_BS` | `Zip`, `Tan_Controllers_Visibility` | publica solo `jaw_ctl`, `upper_jaw_ctl` | LEGACY: no lo llama `build_rig`. OJO: define `class JawModule` DOS veces en el mismo fichero (lineas 19 y 992); la segunda pisa a la primera |
| `eyelid_module.py` (1090) | `make(side, sockets=True, surface=False)` | `{side}_eye_JNT`, `{side}_eyelidUpperLinear_CRVShape`, `_eyelidLowerLinear_`, `{side}_socket_CRVShape` o joints de socket | `{side}_eyeSkinning_JNT`, `{side}_{upper,down}Eyelid0{i}Skinning_JNT`, sockets `...Skinning_JNT` | `C_eyeMain_CTL`, `{side}_eye_CTL`, `{side}_eyeDirect_CTL`, un control por CV; `EYE_ATTRIBUTES`: `Upper_Blink`, `Lower_Blink`, `Blink_Height`, `Fleshy`, `Fleshy_Corners`, `Auto_Socket`; vis `Eyes`, `Sockets` | publica `eyelid_module/{side}_lower_socket_ctl`; consume `eyebrow_module/{side}_main_eyebrow_ctl` | activo. Deformers: blendShapes de blink entre curvas, skinCluster de curvas reconstruidas |
| `eyebrow_module.py` (558) | `make(side)` | `{side}_eyebrow_CRVShape` (nuevo) o `{side}_eyebrowMain_JNT` (fallback), `C_eyebrowMid_JNT`, `C_eyebrowSlide_NURBShape` | `{side}_eyebrow{NN}_JNT`, ribbon `{side}_eyebrowSkinning00..`, `C_eyebrowMidSkinning_JNT` | `{side}_eyebrowMain_CTL`, `C_eyebrowMid_CTL`, `{side}_eyebrow<Nombre>_CTL`; `autoTangent`, `EXTRA_ATTRIBUTES`/`browCurve`, `slide`; vis `Brows` | publica `eyebrow_module/{side}_main_eyebrow_ctl` | activo |
| `cheekbone_module.py` (203) | `make(side)` | `{side}_cheekbone_JNT`, `{side}_cheek_JNT` | uno por guia (`create_controllers`) | controles con el nombre de la guia; vis `Cheekbones`, `Cheek` | consume `eyelid_module/{side}_lower_socket_ctl`, `neck_module/mGear` | activo |
| `nose_module.py` (178) | `make(side)` (se llama L y R) | `C_noseMain_JNT`, `C_noseTip_JNT`, `C_nose_JNT`, `{side}_nose_JNT`, `{side}_nosetril_JNT` (sic) | uno por guia | `C_baseNose_CTL` + uno por guia; vis `Nose` | - | activo |
| `ear_module.py` (141) | `make(side)` | cadena `{side}_ear00_JNT` | uno por guia | uno por guia; vis `Ears` | - | activo |
| `tongue_module.py` (126) | `make(side)` | cadena `C_tongue00_JNT` | `{ctl}Skinning_JNT` por eslabon | uno por eslabon (GRP/ANM); vis `Tongue` | consume `jaw_module/local_jaw_mmx` | activo |
| `teeth_module.py` (127) | `make(side)` | `C_upperTeeth_JNT`, `C_lowerTeeth_JNT` | `C_upperTeeth_JNT`, `C_lowerTeeth_JNT` (rigidos) | `C_upperTeeth_CTL`, `C_lowerTeeth_CTL`; vis `Teeth` | consume `jaw_module/local_upper_jaw_mmx`, `local_jaw_mmx` | activo |
| `facial_correctives_module.py` (631) | `make()` sin lado | ninguna: comprueba nodos ya construidos (`C_lowerLip00_JNT`, `C_upperLip00_JNT`...) y salta cada bloque con warning si falta | leaf joints correctivas colgadas de los joints de skin faciales | host `C_face_CTL` bajo `CORRECTIVES_SEP`: `Enable` y amounts/rangos por bloque | publica `facial_correctives/host`, `joints`; consume `neck_module/face_ctl`, `basic_structure/masterwalk_ctl` | activo. Bloques: jaw open, smile/frown, corner 4D, brow inner + ceno, blink, pucker. Drivers = controles (en la cara el control es la pose) |

## 3. Datos que lee y escribe

- Del `.build`: `spine_skinning_jnts`, `spine_controllers`, `neck_skinning_jnts`,
  `neck_controllers`, `arm_skinning_jnts`, `leg_skinning_jnts`,
  `mGear_integration`. Los amounts de correctivas tuneados van a
  `character_extras` (`.claude/rules/datos-y-versionado.md`).
- Guias: cada `get_guides("<nombre>")` de las tablas de arriba. Los nombres
  de guia son el contrato con el `.guides` del personaje; el nombre del joint
  de skin se deriva de ellos (`replace("_JNT", "Skinning_JNT")`).
- Cache: claves de las tablas. `basic_structure` publica `modules_GRP`,
  `skel_GRP`, `masterwalk_ctl`, `character_ctl`, `preferences_ctl`, `rig_GRP`,
  `character_name`.

## 4. Estado hoy

- Activos y llamados por `build_rig`: arm, leg, spine, neck_module_de_boor,
  clavicle, fingers, jaw_module_nurbs, eyelid, eyebrow, cheekbone, nose, ear,
  tongue, teeth, facial_correctives.
- Legacy sin llamar: `arm_module_custom`, `leg_module_custom`,
  `jaw_module_bezier`. Experimental con test: `wing_module`.
- Nombres con erratas que ya son contrato en escenas y `.skc`: `AttatchedFk`
  (spine), `nosetril` (nose). Cambiarlos exige migrar guias y pesos.
- `corrective_setup` de arm y leg: ver `.claude/skills/corrective-joints/references/repo-y-qa.md`.

## 5. Como probarlo

- Build completo de un biped (anne, thaiz...) por el Asset Manager y menu
  RIGGING > CREATE RIG. Despues: ROM con ANIMATION > Test Rig
  (`pose_tester`), `cycleCheck -e on`, masterwalk a escala y lejos del origen.
- `mayapy maya_tools/scripts/tools/tests/test_wing_module.py` para el ala
  (usa cache falso y cadenas sinteticas; no necesita personaje).
- Un modulo suelto: en una escena con guias importadas y `basic_structure`
  hecha, `XxxModule().make("L", ...)`; el cache `biped.cache` tiene que tener
  `basic_structure` (lo escribe `create_rig.basic_structure`).

## 6. Do not

- No leer `rotate` local de joints ni controles FK del cuerpo para drivers:
  matrices mundo (`bend_driver`, `bend_factor`). En la cara si se lee el
  control.
- No crear un modulo sin `append_data` al final ni sin leer `basic_structure`
  en `__init__`.
- No poner joints correctivas en el skin del body: van en el skin apilado
  con `corrective` en el nombre.
- No renombrar guias de un modulo sin actualizar las tablas de arriba, el
  `.guides` de todos los personajes y `build_rig`.
- No extender los ficheros `_custom` ni `jaw_module_bezier`: se migra lo que
  haga falta al activo.
