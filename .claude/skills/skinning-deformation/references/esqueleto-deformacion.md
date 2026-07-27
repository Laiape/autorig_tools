# Esqueleto de deformación — inventario exacto por módulo

Qué joints de skin genera cada módulo de este repo, con naming real. Lado `L` en los
ejemplos; `R` es idéntico. Índices con defaults del `.build`.

## 0. Convenciones globales

- **`skel_GRP`** (bajo `rig_GRP`) contiene los grupos de skinning de cada módulo
  (`{side}_{modulo}Skinning_GRP`). Ahí viven TODOS los joints que reciben skin. Raíz:
  `C_freeze_JNT`.
- **`skeletonHierarchy_GRP`**: esqueleto `_ENV` de export (raíz `C_freeze_ENV`),
  generado por `rig_manager.skeleton_hierarchy()` duplicando cada joint de skin.
  Conversión: `L_wristSkinning_JNT → L_wrist_ENV`, `L_armUpper00_JNT → L_armUpper00_ENV`.
- Los joints de ribbon de brazo/pierna llevan solo `_JNT` (sin "Skinning" en el
  nombre); los joints sueltos de módulo llevan `Skinning_JNT`. Ambos reciben skin.
- Los `*Corrective_JNT` / `*Ring0N_JNT` NO van en el skin del body: skinCluster
  apilado aparte (skill `corrective-joints`).
- **Números configurables por personaje** en `assets/<char>/build/<char>_v001.build`
  (leídos en `rig_manager.build_rig`, rango 1-20):

| setting | default | qué controla |
|---|---|---|
| `arm_skinning_jnts` | 5 | joints por segmento (upper Y lower) del brazo |
| `leg_skinning_jnts` | 5 | ídem pierna |
| `spine_skinning_jnts` | 8 | joints de skin del spine |
| `neck_skinning_jnts` | 5 | joints del ribbon de cuello |
| `tail_skinning_jnts` | 5 | joints del ribbon de cola (quad) |

Ojo con el padding: el ribbon nombra `{name}0{i}_JNT` con un solo dígito fijo, así que
con 10+ joints por segmento sale `…010_JNT`, `…011_JNT` (no `…10_JNT`).

## 1. Brazo (`biped/autorig/arm_module.py`)

Ribbons de Boor (`utils/ribbon.py::de_boor_ribbon`) con twist swing-twist por
cuaternión — sin cadenas de roll; todo por matrices.

- Segmento superior: `L_armUpper00_JNT … L_armUpper04_JNT`. El `00` tiene frame
  non-roll (NO toma el roll del hombro); el twist del húmero crece hacia el codo. El
  último va en param 0.95 (casi en el codo).
- Segmento inferior: `L_armLower00_JNT … L_armLower04_JNT`. Twist codo(0)→muñeca(100%)
  interpolado por el ribbon.
- `L_wristSkinning_JNT`: muñeca/carpo (blend FK/IK de la muñeca).
- Bendys por segmento: `L_armUpperMainBendy_CTL` (+ Up/Low en 0.25/0.75) — mueven los
  CVs del ribbon, no cambian pesos.
- Correctivas ya montadas (skin aparte): `L_bicepsCorrective_JNT`,
  `L_tricepsCorrective_JNT`, `L_elbowRing00-03_JNT`.

Total por brazo con defaults: 5+5+1 = **11 joints de skin**.

## 2. Pierna (`biped/autorig/leg_module.py`)

Mismo motor que el brazo.

- `L_legUpper00_JNT … L_legUpper04_JNT` (raíz non-roll en cadera; último en 0.95, casi
  en la rodilla).
- `L_legLower00_JNT … L_legLower04_JNT` (twist rodilla→tobillo).
- `L_legAnkleSkinning_JNT` (tobillo) y `L_legBallSkinning_JNT` (bola del pie).
- **NO hay joint de skin de toe** — los dedos del pie se pintan a la ball. El roll del
  pie IK (Heel/Ball/Toe/Bank en el ctl de pie) es mecánica, no influencias nuevas.
- Correctivas: `L_thighFrontCorrective_JNT`, `L_thighBackCorrective_JNT`.

Total por pierna con defaults: 5+5+2 = **12 joints de skin**.

## 3. Spine biped (`biped/autorig/spine_module.py`)

IK spline + FK adjunto (no de Boor) con preservación de volumen:

- `C_spine01Skinning_JNT … C_spineNNSkinning_JNT` (uno por guía; def 8). Reciben
  scaleX/Z del Auto Squash (`C_body_CTL.Auto Squash/Falloff/Max Pos`, porcentajes por
  joint en `C_spineSettings_TRN`).
- `C_localChestSkinning_JNT` — caja torácica (sigue a `C_localChest_CTL`).
- `C_localHipSkinning_JNT` — pelvis (sigue a `C_localHip_CTL`).

## 4. Cuello biped (`biped/autorig/neck_module_de_boor.py`)

- `C_neckSkinning00_JNT … C_neckSkinning04_JNT` (ribbon entre `C_neck_CTL` y
  `C_head_CTL`).
- `C_headSkinning_JNT` — cráneo rígido, con stretch/squash desde `C_headSquash_CTL`.
- Modo `mGear_integration=True`: no se construye el ribbon ni el head propio (la cara
  cuelga del head de mGear).

## 5. Clavícula (`biped/autorig/clavicle_module.py`)

- `L_clavicleSkinning_JNT` (con opción floating shoulder sobre NURBS). La
  auto-clavícula (`AutoClavicle/StartAngle/Factor` en `L_clavicle_CTL`) inyecta
  rotación cuando el hombro sube.

## 6. Dedos (`biped/autorig/fingers_module.py`)

Las guías se convierten en cadena de skin (renombradas `_JNT → Skinning_JNT`):

- Pulgar: `L_thumb00Skinning_JNT … L_thumb02Skinning_JNT`.
- Índice (y middle/ring/pinky): `L_index00Skinning_JNT` (metacarpo) →
  `L_index01-03Skinning_JNT` (falanges).
- Cuelgan de `L_wristSkinning_JNT` por parentMatrix. SDKs Curl/Spread/Twist/Fan/Cup en
  `L_fingersAttributes_CTL`. Sin twists/bendys en dedos.

## 7. Faciales

Todos crean `{module}Skinning_GRP` bajo `skel_GRP` y cuelgan de `*head_ENV` en export.
El nº de joints sale del nº de guías/CVs (no hay atributo).

| Módulo | Joints |
|---|---|
| Jaw (`jaw_module_nurbs.py`) | `C_jawSkinning_JNT`, `C_upperJawSkinning_JNT`; labios por CV: `{R\|C\|L}_upperLip{NN}_JNT`, `{…}_lowerLip{NN}_JNT` + variantes `…NonRot_JNT` |
| Eyelid | `{side}_eyeSkinning_JNT` (globo); `{side}_upperEyelid0{i}Skinning_JNT`, `{side}_downEyelid0{i}Skinning_JNT`; sockets opcionales `…Skinning_JNT` |
| Eyebrow | `{side}_eyebrowSkinning00_JNT …` (ribbon) + `C_eyebrowMidSkinning_JNT` (entrecejo) |
| Cheekbone | `{guide}Skinning_JNT` (`L_cheekboneSkinning_JNT`, `L_cheekSkinning_JNT`…) |
| Nose | `{guide}Skinning_JNT` (`C_noseSkinning_JNT`, `L_nostrilSkinning_JNT`…) |
| Ear | `{side}_ear{NN}Skinning_JNT` |
| Tongue | cadena `C_tongue00Skinning_JNT …` |
| Teeth | `C_upperTeeth_JNT`, `C_lowerTeeth_JNT` (rígidos) |

## 8. Quadruped (`quadruped/autorig/`)

- **Patas** (`FrontLegModule`/`BackLegModule`, prefijos `frontLeg`/`backLeg`): con
  `bendys=True` (default) un ribbon por segmento anatómico:
  `L_frontLegUpperBendy00_JNT …`, `…MiddleBendy…`, `…LowerBendy…` (n =
  `leg_skinning_jnts` por segmento). Extras: `L_frontLegFetlockSkinning_JNT`
  (menudillo), `L_frontLegPasternSkinning_JNT` (cuartilla),
  `L_frontLegTipSkinning_JNT` (casco). Solo front: `L_frontLegScapulaSkinning_JNT` y
  `…ScapulaEndSkinning_JNT`. Con `bendys=False`: cadena directa renombrada
  `Skinning_JNT`.
- **Spine**: `C_spine00_JNT … C_spine0{n-1}_JNT` (de Boor por longitud de arco) +
  `C_localHipSkinning_JNT` + `C_localChestSkinning_JNT`.
- **Cuello**: `C_neck00_JNT …`; el ÚLTIMO se renombra `C_headSkinning_JNT`.
- **Cola**: `C_tail00_JNT … C_tail0{n-1}_JNT` (los `C_tailIk0N_JNT` son mecánica, no
  skin).

## 9. Dónde mirar en el código

| Tema | Fichero |
|---|---|
| Motor de ribbons / creación de `{name}0{i}_JNT` | `scripts/utils/ribbon.py` (de_boor_ribbon), `scripts/utils/de_boor_core.py` |
| Build y orden de pasos | `scripts/utils/create_rig.py` (AutoRig.build) |
| Lectura del `.build`, skeleton_hierarchy, _ENV | `scripts/utils/rig_manager.py` |
| Grupos base (skel_GRP…) | `scripts/utils/basic_structure.py` |
| Twist por cuaternión | `scripts/utils/matrix_manager.py` (extract_twist) |
