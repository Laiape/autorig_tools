# Criterios: naming de nodos

Parent: `como_funciona.md` (raiz). Regla: `.claude/rules/convenciones-rig.md`.
Fuente de los numeros: censo con grep sobre `maya_tools/scripts/**/*.py`
(2026-09-04) de `createNode("<tipo>", name="..._SUF")`.

Este fichero es el sitio para cambiar un sufijo. Cuando cambie, migrar TODAS las
ocurrencias del sufijo antiguo en la misma tarea (no a parches) y, si es un
sufijo basico, actualizar `.claude/rules/convenciones-rig.md`.

---

## 1. Sufijos basicos (DAG y atributos)

| Que | Sufijo | Usos | Notas |
|---|---|---|---|
| transform de grupo | `_GRP` | 329 | `_grp` 3 (legacy) |
| grupo offset de control (animable) | `_ANM` | 2 | `curve_tool.create_controller(name, offset=["GRP", "ANM"])`; lo usan los controles base (`C_character`, `C_masterwalk`) |
| grupo offset de control (estatico) | `_OFF` | 2 | `curve_tool.create_controller(name, ["GRP", "OFF"])` |
| transform de settings | `_TRN` | 10 | ej. `C_spineSettings_TRN` |
| joint | `_JNT` | 429 | `_jnt` 1 (legacy) |
| joint de export | `_ENV` | 32 | los crea `rig_manager.skeleton_hierarchy` |
| control | `_CTL` | 300 | `_ctl` 10 (legacy) |
| guia | `_GUIDE` | 46 | `_Guide` 2 (legacy) |
| curva | `_CRV` | 45 | |
| NURBS surface | `_NRB` | 4 | |
| locator | `_LOC` | 7 | |
| atributo separador (enum lockeado) | `_SEP` | 26 | niceName `--- NOMBRE ---` o `NOMBRE ------` |

Ficheros con restos en minusculas: `quadruped/autorig/digits_module.py`,
`biped/autorig/fingers_module.py`, `utils/basic_structure.py`,
`tools/auto_skin_transfer.py`.

## 2. Sufijos por tipo de nodo utilitario

Canonico = el mas usado. Los legacy no se usan en codigo nuevo y se migran al
tocar el fichero.

| Tipo de nodo | Canonico | Usos | Legacy visto |
|---|---|---|---|
| multMatrix | `_MMX` | 75 | `_MMT` 34, `_MM` 4, `_MMS` 4, `_OFX` 1 |
| blendMatrix | `_BLM` | 38 | `_BMT` 12, `_BMX` 7 |
| aimMatrix | `_AMX` | 14 | `_AIM` 9, `_AMT` 7 |
| composeMatrix | `_CMP` | 17 | `_CMX` 10, `_CM` 3 |
| decomposeMatrix | `_DCM` | 4 | `_DEC` 1 |
| fourByFourMatrix | `_FBF` | 34 | `_FFX` 5 |
| parentMatrix | `_PMX` | 17 | `_PM` 2, `_PMT` 2 |
| pickMatrix | `_PKM` (propuesto) | 2 | `_PMX` 7 colisiona con parentMatrix; `_PCM` 2 |
| rowFromMatrix | `_RFM` | 39 | `_RMF` 6 |
| rotationFromMatrix | `_RTM` (propuesto) | 0 | `_RFM` 2 colisiona con rowFromMatrix |
| translationFromMatrix | `_TFM` | 1 | |
| inverseMatrix | `_IMT` | 3 | `_INV` 3, `_IVM` 1 |
| wtAddMatrix | `_WAM` | 2 | `_WTA` 1 |
| multiplyPointByMatrix | `_MPM` | 1 | |
| multiply | `_MUL` | 92 | `_MLT` 1, `_Mult` 2; `_NEG` 3 (usar nodo `negate`) |
| sum | `_SUM` | 20 | `_SMM` 3 |
| subtract | `_SUB` | 17 | |
| divide | `_DIV` | 18 | |
| power | `_POW` | 8 | |
| negate | `_NEG` | 10 | |
| reverse | `_REV` | 19 | |
| clamp | `_CLM` | 9 | `_CLP` 9 (empate; `_CLM` por coherencia con `clampRange`), `_CLAMP` 1 |
| condition | `_COND` | 31 | `_CON` 3, `_CND` 2 |
| remapValue | `_RMV` | 18 | |
| distanceBetween | `_DBT` | 16 | `_DIST` 1 |
| normalize | `_NRM` | 4 | |
| length | `_LEN` | 3 | |
| min / max | `_MIN` / `_MAX` | 2 / 3 | |
| floatConstant | `_FLC` | 6 | `_FCN` 3, `_FC` 1, `_FCF` 1 |
| floatMath | `_FLM` | 2 | preferir multiply, sum, subtract, divide |
| blendTwoAttr | `_BTA` | 9 | |
| blendColors | `_BLC` | 2 | |
| vectorProduct | `_VPR` | 2 | `_DOT` 2, `_VCP` 2 (empate; `_VPR` es el generico) |
| motionPath | `_MTP` | 15 | `_MPT` 1 |
| closestPointOnSurface | `_CPS` | 7 | `_CPOS` 2 |
| pointOnSurfaceInfo | `_POSI` | 2 | |
| nearestPointOnCurve | `_NPC` | 1 | |
| curveInfo | `_CIN` | 1 | |
| uvPin | `_UVP` | 3 | |
| quatToEuler / quatNormalize / axisAngleToQuat | `_QTE` / `_QTN` / `_AAQ` | 1 cada uno | |
| sin / cos / acos | `_SIN` / `_COS` / `_ACOS` | 1 cada uno | |
| pairBlend | `_PBA` | 1 | |
| network | `_NET` | 1 | |

## 3. Deformers y ficheros de pesos

| Que | Sufijo | Usos | Notas |
|---|---|---|---|
| skinCluster de modulo (curvas, NURBS) | `_SKIN` | 26 | firma tipica: `toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1` |
| skinCluster del body via `skin_manager_ng` | `_SC` | 9 | |
| skinCluster de correctivas | contiene `corrective` (`C_corrective_SKC`) | 3 | el build lo localiza por el nombre |
| blendShape | `_BLS` | 4 | `_BS` 2 (legacy) |
| deltaMush | `_DMH` | 2 | |
| uvPin | `_UVP` | 3 | |
| fichero de pesos | `.skc` | | `assets/<p>/skin_clusters/<p>_vNNN.skc` |

## 4. Prohibidos en codigo nuevo

`multiplyDivide` (`_MDV`), `plusMinusAverage` (`_PMA`), `multDoubleLinear`,
`addDoubleLinear`. Sobreviven en `tools/auto_collision.py` y algun modulo
legacy: migrar al tocar el fichero, nunca copiar el patron.

## 5. Como hacer una migracion de sufijo

1. `grep -rn "_MMT" maya_tools/scripts --include=*.py` y cambiar todas las
   ocurrencias (tambien las que derivan nombres por `replace`).
2. Rebuild de un biped y un quadruped; comprobar consola limpia y
   `skeletonHierarchy_GRP`.
3. Un commit unico: `naming: _MMT -> _MMX en multMatrix`.
4. Actualizar la tabla de arriba (usos y legacy) en la misma tarea.
