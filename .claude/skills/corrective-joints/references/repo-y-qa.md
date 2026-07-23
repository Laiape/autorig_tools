# El repo: API de correctivas, integración en el build, persistencia y QA

Chuleta técnica de `autorig_tools` para escribir código de correctivas SIN romper el build.

## 1. API de `scripts/utils/correctives.py`

Todos los parámetros de cantidad aceptan **número o plug** (`_set_or_connect`); el rango
del driver pasa por `_remap01` (remapValue 0..1 con auto-clamp).

| Función | Qué hace | Notas |
|---|---|---|
| `corrective_push(name, base_joint, driver, in_min, in_max, axis, amount_attr, enable_attr=None)` | 1 joint hija de `base_joint` que se empuja por `axis` (local, normalizado) cuando el driver recorre in_min→in_max | translate/jointOrient a 0 al nacer |
| `corrective_extra(joint, name, driver, in_min, in_max, axis, amount_attr, enable_attr=None)` | segundo empuje (otro rango/eje) sobre una correctiva YA creada | usar canales de translate NO usados por el push principal |
| `corrective_ring(name, base_joint, count, radius, driver, in_min, in_max, amount_attr, normal_axis="X", enable_attr=None)` | anillo de N joints alrededor del hueso que inflan radialmente | plano ⟂ a normal_axis (= eje del hueso) |
| `corrective_offset_push(...)` | como push pero nace con `rest_offset` (translate = rest + empuje) | p.ej. isquios: parte detrás y se contrae |
| `corrective_arc(name, base_joint, driver, in_min, in_max, forward_axis, up_axis, forward_limit, up_limit, enable_attr=None, rest_offset=(0,0,0), up_power=2.0)` | trayectoria en arco: forward lineal + up con progreso^up_power ("sube tarde") | forward/up_limit son LÍMITES en unidades → pásalos como plug |
| `bend_driver(name, upper_joint, lower_joint, axis, sign=1.0)` | ángulo de flexión por matrices mundo, FK/IK-agnóstico, rest a 0, eje de bisagra primero en el rotate order | devuelve plug en grados; NO para multi-eje |
| `localize_corrective_skin(skin_cluster)` | conecta `bindPreMatrix[i]` al padre de cada influencia → mata la doble transformación del skin apilado | llamar UNA vez, en pose neutra; el build lo hace solo para `*corrective*` |

En `matrix_manager.py`: `bend_factor(m0,m1,m2,name)` (flexión 0-1 por dot, sin flips —
sus args son nodos con `.outputMatrix` tipo blendMatrix, NO joints),
`extract_twist(source_plug, ref_plug, axis, name)` (swing-twist por quats),
`segment_volume(...)` (squash/stretch respetando globalScale — el patrón a imitar para
drivers por distancia), `local_mmx(ctl, grp)` (la matriz local rest-relativa facial).

## 2. Ejemplos reales (copiar el patrón, no inventar otro)

`arm_module.corrective_setup()` (llamado al final de `make()`):

```python
base  = f"{side}_armUpper02_JNT"          # joint media del ribbon
driver = correctives.bend_driver(f"{side}_elbowBend",
                                 f"{side}_armUpper00_JNT", f"{side}_armLower00_JNT", "Y")
push_dv = round(upper_len * 0.12, 1)      # 12% del hueso, escala-independiente
def _ax(v): return v if side == "L" else (-v[0], -v[1], -v[2])   # mirror: vector COMPLETO

# attrs en el bendy CTL bajo separador CORRECTIVES_SEP:
#   {prefix}Enable (bool dv=1), {prefix}PushForward, {prefix}PushUp (float dv=push_dv)
correctives.corrective_arc(f"{side}_bicepsCorrective",  base, driver, 0, -100,
                           _ax((0,0,1)),  _ax((-1,0,0)), pf, pu, enable_attr=en)
correctives.corrective_arc(f"{side}_tricepsCorrective", base, driver, 0,  100,
                           _ax((0,0,-1)), _ax((-1,0,0)), pf, pu, enable_attr=en)
correctives.corrective_ring(f"{side}_elbowRing", lower, 4, radius, driver, 0, -100,
                            push_dv, normal_axis="X")
```

`leg_module`: rodilla eje Z, `thighFrontCorrective` (arc, rodilla adelante z+ 0→100, con
attrs vía `arc_attrs`) y `thighBackCorrective` (offset_push, flexión z− 0→-100 — amount
NUMÉRICO y sin Enable: solo ThighFront tiene attrs bajo `CORRECTIVES_SEP`). Rangos de
driver en producción: **0→±100°**; host de attrs: bendy CTL del módulo, fallback
`settings_ctl`.

Mejoras pendientes detectadas (hazlas si tocas esa zona): el ring del codo y el
`thighBackCorrective` pasan `push_dv` numérico (y el thighBack no tiene Enable) →
conviértelos a attrs para que sean tuneables/persistibles; `_ax` duplicada en arm/leg →
`correctives.mirror_axis(v, side)`; el docstring de `bend_driver` sobre `sign=-1` en R
está obsoleto (las llamadas reales usan sign=1 en ambos lados).

## 3. Integración en el build

Pipeline: `create_rig.AutoRig.build()` → `basic_structure` → `rig_manager.build_rig`
(módulos según guías) → `label_joints` → `import_weights` (`.skc`, skinClusters con
`multi=True` = apilables) → **`localize_correctives()`** (todo skinCluster con
`corrective` en el nombre) → `import_corrective_blendshapes()` → picker.

- **Comunicación entre módulos**: `data_manager.DataExportBiped()` —
  `append_data("modulo", {...})` / `get_data("modulo", "clave")` (cache
  `cache/biped.cache`). Los plugs útiles ya publicados: `jaw_module/local_jaw_mmx`,
  `neck_module/face_ctl`, `basic_structure/masterwalk_ctl`…
- **Dónde va el código nuevo**: método `corrective_setup()` al final del `make()` del
  módulo (patrón arm/leg). Para faciales: mismo patrón en el módulo facial, o un módulo
  `facial_correctives` que corra tras todos los faciales (necesita sus drivers ya
  creados).
- **Export skeleton**: `skeleton_hierarchy()` duplica joints como `*_ENV`; toda joint con
  `corrective`/`ring` en el nombre se excluye del encadenado normal y **se cuelga del
  `_ENV` de su joint padre** — el naming es lo único que lo activa.
- **Orden del stack de deformación**: BLS correctivo (frontOfChain) → skinCluster body →
  skinCluster correctivas (localizado) → (deltaMush opcional).
- El build corre en "fast session" (cycleCheck off, EM off) — los ciclos no avisan en
  build: compruébalos en QA.

## 4. Naming y convenciones

- Joints: `{L|R|C}_nombreCorrective_JNT`, anillos `{L|R|C}_nombreRing##_JNT`. El prefijo
  de lado es obligatorio (label_joints y mirrors dependen de él).
- Nodos: sufijos del repo — `_MUL` multiply, `_SUM` sum, `_SUB` subtract, `_DIV`, `_POW`,
  `_RMV` remapValue, `_CLM` clamp, `_COND`, `_MM/_MMX/_MMT` multMatrix, `_DEC/_DCM`
  decomposeMatrix, `_RFM` rowFromMatrix, `_FBF` fourByFourMatrix, `_BMX` blendMatrix,
  `_PMT` parentMatrix, `_DOT/_VPR` vectorProduct, `_DBT` distanceBetween, `_NRM`
  normalize, `_QTE` quatToEuler… Siempre `ss=True`.
- Nodos math: familia Maya 2024 (`multiply` con `input[0..n]`, `sum.input[i]`,
  `subtract.input1/input2`). El repo asume **Maya 2025+** (usa `parentMatrix`). NO usar
  `multiplyDivide`/`multDoubleLinear` en código nuevo.
- Attrs: separador enum lockeado (`CORRECTIVES_SEP`, niceName "CORRECTIVES"), luego
  `{Prefix}Enable` (bool dv 1) + `{Prefix}Push*`/`{Prefix}Amount` (float, dv proporcional
  al hueso).

## 5. Skinning de la correctiva

1. Skin aparte con `corrective` en el nombre (p.ej. `C_corrective_SKC`) sobre la malla —
   el build lo localiza automáticamente. Añadir influencias con weight 0 + lock.
2. Pintar CON la pose del defecto activa; volver a rest a menudo para confirmar identidad.
3. Bloquear las influencias que no participan → la normalización intercambia peso solo
   entre la correctiva y su padre ("la correctiva roba % del padre"; Enable a 0 devuelve
   exactamente el skinning base).
4. Valores: pico **0.2–0.5**, falloff en 1–3 anillos de edges. Un helper con peso ~1.0 es
   de facto un joint estructural (mal).
5. Mirror: `copySkinWeights mirrorMode="YZ" influenceAssociation=["oneToOne","name","closestJoint"]`.
6. Prune < 0.001, export `.skc` (versionado en `assets/<char>/skin_clusters/`).

## 6. Persistencia de amounts por personaje

Los amounts son plugs → se tunean en vivo, pero el build los resetea. El mecanismo de
persistencia es el bloque `character_extras` del `.build`
(`assets/<char>/build/<char>_vNNN.build`), aplicado por `apply_character_extras`.
**Formato: listas de DICTS con claves separadas** (con pares `[plug, valor]` el build
revienta), y los nombres de attr son los reales de `arc_attrs` — `BicepsPushForward`,
`BicepsEnable`… sin "Corrective":

```json
{
  "Rig_Type": 0,
  "character_extras": {
    "set_attrs": [
      {"node": "L_armUpperMainBendy_CTL", "name": "BicepsPushForward", "value": 3.4},
      {"node": "R_armUpperMainBendy_CTL", "name": "BicepsPushForward", "value": 3.4}
    ],
    "add_attrs": []
  }
}
```

(`assets/anne/build/anne_v001.build` tiene un ejemplo real.) `add_attrs` usa dicts
análogos (`node`/`name`/`type`/`min`/`max`/`default`). La clave `node` acepta también
`"modulo/clave"` del data manager. Flujo: tunear en vivo → volcar los attrs bajo
`CORRECTIVES_SEP` al `.build` → el build los reaplica. (Un helper
`dump_corrective_attrs()` que recorra esos attrs sería trivial y aún no existe.)

## 7. Errores comunes (causa → fix)

- **Pop en rest**: la correctiva no es identidad en bind. → translate 0 (o rest_offset
  exacto) en build; skin localizado; verificación automática.
- **Doble transformación**: skin apilado sin localizar. → naming `*corrective*` para que
  `localize_corrective_skin` corra en build; no llamarla dos veces fuera de pose neutra.
- **Dispara fuera de rango**: falta clamp. → `remapValue` siempre (auto-clamp); nada de
  extrapolación.
- **Driver desde control FK del cuerpo**: muere en IK. → `bend_driver`/matrices (la cara
  es la excepción: control = fuente canónica).
- **Driver sobre `joint.rotate` local**: vale 0 (todo va por offsetParentMatrix). → matrices.
- **Asimetría L/R**: vector no negado completo, o negado el driver que no había que tocar.
  → regla del repo (drivers.md §4) + verificación numérica.
- **Ciclo**: leer una joint descendiente de lo que escribes, o leer la malla deformada. →
  leer del esqueleto, escribir solo en hojas; `cycleCheck -e on` en QA (el build lo apaga).
- **Ignora escala global / lejos del origen**: lecturas world sin relativizar,
  `distanceBetween` sin dividir por `globalScale`. → matrices relativas + normalizar
  distancias.
- **`corrective_extra` sobre el mismo canal**: conectaría dos veces translate{comp} →
  usar canales libres.

## 8. Checklist de QA (antes de dar por buena una tanda de correctivas)

1. **Rest-identity**: en bind, `translate` de toda `*Corrective*`/`*Ring*` = 0 (o su
   rest_offset) y diff de vértices malla vs modelo ≈ 0 (tolerancia 1e-4).
2. **Toggle**: todos los `*Enable` a 0 → malla idéntica al skinning base (A/B).
3. **ROM completa** de nuevo (no solo la pose que motivó la correctiva): codo/rodilla
   0→140°, twists ±90°, poses combinadas (squat, brazos arriba/cruzados); facial: jaw
   0→35°, blinks, las expresiones del set y sus combos.
4. **Masterwalk**: escala 0.1x/2x/10x, a 1000 unidades, rotado 90/180° — con un ciclo
   sonando.
5. **Mirror numérico**: pose simétrica y comparar translates L vs R.
6. **`cycleCheck -e on`** tras el build + consola limpia.
7. **Export**: build completo → cada correctiva nueva cuelga de su `_ENV` padre en
   `skeletonHierarchy_GRP` (si no, el naming está mal).
8. **Performance**: fps con correctivas ON vs OFF.
9. `.skc` y `.build` (character_extras) exportados y versionados.
