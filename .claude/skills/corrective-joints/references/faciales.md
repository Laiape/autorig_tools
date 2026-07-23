# Correctivas FACIALES: una por cada shape del set (± las que hagan falta)

Cómo montar corrective joints en la cara de este rig (módulos eyebrow, eyelid, cheekbone,
jaw+lips, nose, teeth, tongue, ear), tomando como mapa el **set de expresiones esculpidas**
del personaje (las cabezas de referencia del modelador, estilo Sergi Caballer).

**La regla del set**: por cada shape/expresión esculpida existe, como punto de partida,
**UNA correctiva que la acompaña**. Pueden ser **más** (una expresión que rompe varias
zonas, o combinaciones problemáticas como smile+jaw open) o **menos** (donde los joints de
módulo ya deforman bien). No corrijas por corregir: cada correctiva se paga con un defecto
visible.

## 1. Modelo mental: el híbrido

En un rig facial joint-based (este), el reparto de capas es:

1. **Joints de módulo** → movimiento grueso de cada expresión (el lip corner sube, la ceja
   baja, la jaw abre).
2. **Corrective joints** → volumen y forma que el skinning no da: el pliegue nasolabial,
   el bulge del entrecejo, el párpado que envuelve la córnea, la barbilla que se estira.
3. **Corrective blendshapes** (CBS manager) → el detalle esculpido fino que ni la joint
   alcanza: arrugas, creases direccionales. (+ en otros pipelines, wrinkle maps en shader.)

Es el mismo reparto que MetaHuman/Snappers (shapes/joints base + capas correctivas).
Referencia de cantidades: facial de juego "bueno" ~20–30 correctivas; con un set de ~11
expresiones, el objetivo realista es **11 base + combos que rompan → 15–25 total**.

## 2. Drivers faciales de ESTE repo (plugs reales)

En la cara el control ES la fuente canónica (no hay FK/IK): leer controles o pesos de
blendshape es correcto aquí (a diferencia del cuerpo).

| Driver | Plug | Rango real observado |
|---|---|---|
| Apertura de jaw | `C_jaw_CTL.rotateX` (signo de apertura se mide en build, como hace el auto-sticky) o `C_jawLocal_MMT.matrixSum` | ~0–35° al hablar |
| Jaw lateral / thrust | `C_jaw_CTL.translateX` / `translateZ` (o rowFromMatrix del local) | — |
| Sonrisa / mueca | `{L\|R}_lipCorner_CTL.translateY` | 0→**+2** smile, 0→**−2** frown (separar con `condition`/`max`) |
| Comisura adentro (pucker parcial) | `{L\|R}_lipCorner_CTL.translateX` | 0→**−2.5** |
| Narrow / wide de labios | `{side}_lipNarrow_CLM.outputR`, `{side}_lipWide_CLM.outputR` | ya normalizados 0–1 |
| Roll de labios | `C_upperLip_CTL.Roll` / `C_lowerLip_CTL.Roll` | — |
| Ceño | `{L\|R}_eyebrowIn_CTL.translateX` | 0→**−1.8** |
| Ceja arriba/abajo | `{side}_eyebrowMain_CTL.translateY` (interno del browCurve) | — |
| Blink | `{side}_eyeDirect_CTL.Upper_Blink` / `Lower_Blink` | −1..1 |
| Mirada (fleshy) | rotación del `{side}_eyeDirect_CTL` | — |
| Pómulo | `{side}_cheekbone_CTL.translateY` (o su `Local_MMX.matrixSum`) | — |
| **Peso de un blendshape** | `C_facial_local_BLS.<alias_del_target>` | 0..1, conectable como cualquier float |
| Distancias (blink %, sello de labios) | `distanceBetween` entre joints — **divide por `C_masterwalk_CTL.globalScale`** | — |

**Peso de blendshape como driver** (la vía recomendada cuando la correctiva "acompaña" a un
shape esculpido): el pipeline ya lo usa (el target `C_closed_jaw_bls` de thaiz está
driveado por el peso de otro target). Ventaja: el CBS manager restaura las driven keys
control→peso en cada build, así que re-tunear la key re-tunea shape y joint a la vez.
Si no hay shape, cuelga la correctiva del control directamente (patrón thaiz).

```python
# correctiva que acompaña la sonrisa esculpida (peso ya 0..1 -> in_min=0, in_max=1)
correctives.corrective_push(
    "L_smileCheekCorrective", "L_cheekbone01Skinning_JNT",
    driver="C_facial_local_BLS.l_up_mouth_bls", in_min=0, in_max=1,
    axis=(0, 1, 0.4), amount_attr=f"{host}.SmileCheekAmount",
    enable_attr=f"{host}.SmileCheekEnable")
```

**Combinaciones**: producto de los dos pesos con `multiply` (`input[0]=wA, input[1]=wB`) —
es lo que hace MetaHuman Rig Logic — o el nodo nativo **`combinationShape`**
(`combinationMethod`: 0 Multiplication / 1 **Lowest weighting** (min — más estable como
gate, no infra-dispara) / 2 Smooth) → `outputWeight` al remap de la correctiva.

**Clamp obligatorio**: una driven key con infinity mal puesta puede sacar el peso de 0..1
→ siempre `remapValue` (auto-clamp, el `_remap01` de correctives.py ya lo hace) entre peso
y translate.

## 3. Catálogo por expresión (el mapa del set de cabezas)

Por cada expresión típica del set: qué corrige, qué joints añadir y su driver. AU = FACS
Action Unit. Módulo del repo entre corchetes.

### Smile (AU6+AU12) [cheekbone, nose, lips]
La sonrisa rompe 3 cosas que el skinning no da:
1. **Nasolabial fold**: 1 joint por lado EN la línea del pliegue (ala de nariz→comisura)
   que se hunde ligeramente y empuja la mejilla arriba para tallar el fold.
2. **Cheek raise**: 1 joint de pómulo que empuja la carne hacia el arco cigomático —
   *empujar contra el hueso*, no inflar como globo.
3. **Squint inferior** del ojo (AU6): sube/engrosa el párpado inferior (comparte driver).
Driver: `lipCorner_CTL.translateY` > 0 o el peso del shape de smile.

### Frown / sad (AU15 +AU1+AU4) [lips, eyebrow]
Comisura que baja y ligeramente adentro; posible joint de mentón (pliegue de marioneta).
Driver: `lipCorner_CTL.translateY` < 0 (sepáralo del smile con `condition`/`max(0,-x)`).

### Jaw open (AU26/27) [jaw, cheekbone, lips] — **la que más correctivas necesita**
1. **Mentón/mentalis**: la barbilla se estira y aplana → joint que preserva volumen.
2. **Mejillas**: la carne se tensa hacia abajo → joint que evita el hundimiento.
3. **Labio inferior que rueda** sobre los dientes (lip roll).
4. **Papada/submental**: la piel bajo la mandíbula se comprime → joint driveado por el
   **ángulo jaw↔neck** (bend_driver entre jaw y neck), no solo por la jaw — si el
   personaje habla con la cabeza inclinada, el driver correcto es ese ángulo.
Además, **toda expresión esculpida en boca cerrada se degrada al abrir** → combos (ver §4).
Driver: `C_jaw_CTL.rotateX` normalizado a 0..1 con remapValue.

### Blink (AU45) [eyelid]
El párpado debe **envolver la córnea**: el skinning lineal lo hace atravesar o separarse
del globo (eye bulge). Joints de párpado en serie progresiva: primer tramo del cierre →
translate hacia delante (alejándose del globo), tramo medio → hacia abajo, para que el
borde "resbale" sobre la esfera. Driver: `Upper_Blink`/`Lower_Blink` o `distanceBetween`
párpados (÷ globalScale). Nota: el módulo ya tiene `Fleshy` — no dupliques lo que ya hace.

### Wide eyes (AU5) [eyelid]
El párpado superior se retrae mucho: joint que lo rueda hacia arriba conformándose al
globo sin hundirse en la cuenca. Driver: `Upper_Blink` negativo / control de upper lid.

### Squint (AU6+AU7) [eyelid, cheekbone]
Párpado inferior sube + bolsa inferior; la mejilla empuja hacia el arco. Comparte driver
con smile (AU6 va con AU12 en la sonrisa Duchenne).

### Brow raise (AU1+AU2) [eyebrow]
La piel de la frente rueda hacia arriba y se pliega: 1–2 joints de frente por lado que
empujan arriba/afuera. AU1 (interna) y AU2 (externa) pueden ser correctivas separadas.
Driver: `eyebrowMain_CTL.translateY` > 0 o peso del shape.

### Brow furrow / angry (AU4) [eyebrow, nose]
Las cejas bajan y se juntan y aparece el **bulge de la glabella** (procerus+corrugator) —
el skinning junta las cejas pero no genera el abultamiento. 1 joint en el entrecejo
proyectando hacia fuera (+Z) y algo abajo. Driver: `eyebrowIn_CTL.translateX` (0→−1.8) o
peso del shape de ceño.

### Pucker / kiss (AU18) [lips]
Los labios se fruncen y **se proyectan hacia delante** — el skinning los junta pero no los
proyecta en 3D. Joint(s) de labios en +Z convergiendo al centro. Driver:
`lipNarrow_CLM.outputR` (ya 0-1) o peso del shape. Variante funnel (AU22): igual con
labios más abiertos.

### Sneer / nose wrinkle (AU9+AU10) [nose, cheekbone]
La nariz se arruga y el labio superior sube: joint en el ala/lateral de la nariz que sube,
+ joint de labio superior (marca el nasolabial superior). Driver: peso del shape de sneer
o control de nariz/labio superior.

### Cheek puff / suck (AD34/AU28) [cheekbone]
Volumen puro que el skinning no crea: joint de mejilla a lo largo de la normal (fuera =
puff, dentro = suck). Driver: peso del shape (suele ser correctiva "pura", no la mueve
ninguna otra expresión).

### Jaw lateral / thrust (AU30/AU29) — masticar [jaw, cheekbone]
Bulge del masetero del lado hacia el que se desvía la mandíbula, shear de la piel del
mentón. Driver: `C_jaw_CTL.translateX`/`translateZ` separados por dirección con
`condition`/`max(0,±x)`; combo lateral×open para masticación.

## 4. Combinaciones problemáticas (correctivas extra)

Solo las que rompen visiblemente — la combinatoria completa es inabordable e innecesaria:

| Combo | Problema | Driver |
|---|---|---|
| **smile × jaw open** | la sonrisa esculpida en boca cerrada se rompe al abrir | `multiply(smile_w, jawOpen_w)` |
| jaw open × cualquier shape de boca | ídem (la jaw degrada casi todo) | producto |
| blink × mirada abajo | el párpado no envuelve bien mirando abajo | `Upper_Blink` × rot. X del eyeDirect remapeada |
| pucker × jaw open | labios proyectados con boca abierta se interpenetran | producto |
| brow up × brow furrow | volúmenes de frente contradictorios | producto |

Prioridad: **los combos con jaw open primero** — la jaw es el pivote del movimiento facial.

## 5. Flujo cabeza-esculpida → corrective joint

Para cada cabeza del set de expresiones:

1. **Goal overlay**: carga la cabeza esculpida como blendShape temporal sobre la malla
   FINAL a peso 1 (alterna 0/1 o X-ray para comparar).
2. **Pose con módulos**: reproduce la expresión lo mejor posible solo con los controles de
   módulo (movimiento grueso).
3. **El delta restante ES la correctiva.** Localiza la zona de máximo delta (a ojo, o con
   Apply Mesh Compare de Maya 2026 — heat map de diferencia entre mallas).
4. **Crea la joint** en el centroide de esa zona (primitivas de `correctives.py`, colgada
   de la skinning joint del módulo), driver = peso/control de esa expresión (§2), amount a
   ojo hasta casar la silueta con el sculpt. Heurística de partida: push ≈ 10–20% de la
   distancia a la joint vecina del módulo, SIEMPRE como plug tunable.
5. **Pinta el peso** local (pico 0.2–0.5, robado del padre por normalización, parche de
   pocos anillos) en el skinCluster de correctivas (`*corrective*` → se localiza solo en
   build).
6. **Lo que la joint no alcance** (pliegue fino, arruga) → corrective blendshape con el
   CBS manager. Si un target esculpido cubre varias zonas, `blendshape.split_with_curve`
   lo trocea en targets driveables por separado.
7. Repite la comparación con el overlay hasta que la silueta case; después el combo-pass
   (§4) posando pares de expresiones a la vez.

## 6. Qué NO corregir en este rig (ya resuelto por diseño)

- **Teeth y tongue**: siguen la jaw por matriz (`local_jaw_mmx`) — no son correctivas.
- **Colisión del upper jaw**: attr `Auto_Collision` del `C_jaw_CTL`.
- **Fleshy eyelids** (el párpado sigue la mirada): attrs `Fleshy`/`Fleshy_Corners`.
- **Sticky lips**: sistema propio por matrices (`StickyLips`, `StickyRange`, `mouthHeight`
  en `C_jaw_CTL`) — si el sello de labios falla, tunea eso antes de añadir joints.
- **El pómulo empuja el párpado inferior**: `socketMovement_CON` ya conecta
  `cheekbone_CTL.translateY` al socket.

Si una de estas zonas sigue fallando tras tunear su sistema, entonces sí: correctiva
encima, con el driver del sistema existente (p.ej. el mismo `StickyLips` como enable).

## 7. Checklist facial

1. Set de expresiones identificado y descompuesto en AUs (tabla §3).
2. Cada expresión reproducida con módulos y comparada contra su sculpt.
3. Una correctiva por shape que rompa (± según §3/§4/§6) — no por costumbre.
4. Drivers = pesos de BLS o controles canónicos, con remapValue clampado.
5. Combos solo donde rompen; jaw open primero.
6. Naming `{L|R|C}_xxxCorrective_JNT` (export `_ENV` automático).
7. Mirror L→R (vector negado completo; pesos por copySkinWeights YZ; CBS manager para los
   shapes).
8. Pesos locales 0.2–0.5; skinCluster `*corrective*` apilado y localizado.
9. QA: rest = identidad, toggle Enable, masterwalk escalado/lejos del origen (ojo a los
   `distanceBetween`), ROM facial (jaw 0→35°, blinks, visemas) + las 11 expresiones.
