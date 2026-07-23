# Catálogo por zonas — shape objetivo, joints del repo, reparto de pesos

Formato de cada zona: **Joints** (los que pintan la zona en este repo, lado L; R es
idéntico) · **Pose de test** · **Shape objetivo** (la silueta que hay que conseguir) ·
**Reparto de pesos** · **Errores típicos** · **Siguiente capa** (cuándo parar y pasar a
correctivas — ver skill `corrective-joints`).

Los nombres asumen defaults del `.build` (5 joints por segmento de extremidad, 8 de
spine). Con otros valores cambia el índice final (`…04` → `…0{n-1}`), no el patrón.

---

## HOMBRO (+ clavícula)

**Joints**: `L_armUpper00_JNT` (raíz del ribbon superior, frame non-roll — NO toma el
twist del hombro), `L_armUpper01-02_JNT`, `L_clavicleSkinning_JNT`,
`C_localChestSkinning_JNT` (borde del torso).

**Pose de test**: brazo en T → arriba 170° (abducción); delante 90°; atrás 40°;
encogerse de hombros (clavícula); brazo arriba + rotación interna/externa.

**Shape objetivo** (brazo arriba): el deltoides sube CON el brazo como masa redonda y
comprime contra el trapecio; la axila forma un pliegue limpio en V, no un colapso ni un
bulto; la escápula/espalda casi no se mueve; el pectoral se estira sin arrugarse. Al
encoger hombros, el trapecio sube con la clavícula.

**Reparto de pesos**: la cabeza del deltoides mayoritariamente a `L_armUpper00-01_JNT`
(pico ~0.8-0.9, dejando ~0.1-0.2 de clavícula en la cima del deltoides); transición
LARGA y difusa (4-6 loops, frente a los 2-3 de una bisagra) hacia
`L_clavicleSkinning_JNT` y el pecho — es una bola, no hay crease. El trapecio reparte clavícula↔cuello↔chest. El borde del
pectoral y del dorsal deben quedar con peso mixto brazo/torso para estirar sin
arrastrarse. La axila es la frontera: los loops interiores del torso NO deben llevar
peso de brazo.

**Errores típicos**: axila que se infla al subir el brazo (peso de brazo demasiado
adentro del torso); hombro "pinzado" (transición corta → pellizco); pecho entero que se
arrastra con el brazo; candy-wrapper en el deltoides (peso de `armUpper01+` demasiado
arriba — el twist crece hacia el codo, el hombro debe quedar en la parte sin twist).

**Siguiente capa**: pérdida de volumen del deltoides a 170° o pliegue de axila feo en
poses combinadas → correctiva de hombro con cone driver, no más pintura. (El cone
driver aún no existe como primitiva en `utils/correctives.py` — hay receta en la skill
`corrective-joints`, `references/drivers.md`.)

---

## CODO

**Joints**: frontera `L_armUpper04_JNT` (último del ribbon superior, param 0.95 — está
casi EN el codo) ↔ `L_armLower00_JNT`. El anillo `L_elbowRing00-03_JNT` existe pero es
correctiva (skinCluster aparte).

**Pose de test**: 0° → 140° de flexión; flexión + pronación del antebrazo a la vez.

**Shape objetivo** (a 140°): el olécranon (punta del codo) se marca afilado y NO pierde
volumen — viaja con el antebrazo; el interior pliega con UNA crease limpia en el
pliegue del codo; bíceps y antebrazo se comprimen al contacto (eso ya es capa de
correctiva). El antebrazo no se dobla por en medio.

**Reparto de pesos**: bisagra casi pura. Transición CORTA (2-3 loops) centrada en el
pliegue interior; por el exterior transición más LARGA para que el olécranon acompañe
al antebrazo (sube peso de `L_armLower00_JNT` por el dorso del codo).

**Errores típicos**: codo que se redondea/desinfla al flexionar (el exterior no sigue
al antebrazo); crease en mitad del antebrazo o del bíceps (frontera de bloques mal
puesta — muévela a la articulación); doble crease interior.

**Siguiente capa**: volumen del pliegue a >90° y bulge del bíceps → ya está montado en
el repo (`arm_module.corrective_setup`: biceps/triceps/elbowRing con driver de flexión).

---

## ANTEBRAZO + MUÑECA (twist)

**Joints**: `L_armLower00_JNT` (codo, twist 0) → `L_armLower04_JNT` (muñeca, twist
100%) — el ribbon YA interpola el twist gradualmente; `L_wristSkinning_JNT` (carpo/mano).

**Pose de test**: pronación/supinación completa (palma arriba↔abajo) con codo a 90°;
flexión/extensión de muñeca; desviación radial/cubital.

**Shape objetivo**: en el twist, la masa del antebrazo tuerce en ESPIRAL suave desde el
codo (que no gira) hasta la muñeca (que gira entera) — ningún anillo de vértices rompe
como tubo cortado. En flexión de muñeca: bisagra corta, la mano pivota sobre el carpo y
el antebrazo no se dobla.

**Reparto de pesos**: bandas cilíndricas solapadas y UNIFORMES entre
`L_armLower00→04_JNT` (p. ej. cada anillo de vértices 60/40 con el siguiente joint).
El twist gradual sale SOLO si las bandas son regulares — no te saltes joints. La mano
(carpo y metacarpos fuera de dedos) casi rígida a `L_wristSkinning_JNT`.

**Errores típicos**: candy-wrapper en la muñeca (bandas irregulares o toda la zona
distal pesada a `armLower04`); la muñeca que "rompe" en pronación (falta banda de
transición entre `armLower04` y `wristSkinning`); el codo que gira con la pronación
(peso de `armLower01+` invadiendo el codo).

---

## MANO Y DEDOS

**Joints**: `L_wristSkinning_JNT` (palma/carpo); por dedo, cadena
`L_index00Skinning_JNT` (metacarpo) → `L_index01-03Skinning_JNT` (falanges); pulgar
`L_thumb00-02Skinning_JNT`. Análogo `middle`, `ring`, `pinky`.

**Pose de test**: puño cerrado; abanico (Spread); pulgar en oposición; Cup de palma
(SDKs de `L_fingersAttributes_CTL`: Curl/Spread/Twist/Fan/Cup).

**Shape objetivo** (puño): los nudillos se MARCAN (el dorso mantiene el hueso), las
falanges pliegan con creases limpias alineadas con los pliegues reales de la palma; la
palma se ahueca ligeramente con el Cup (los metacarpos de ring/pinky rotan); la
membrana entre pulgar e índice estira sin colapsar.

**Reparto de pesos**: casi POR BLOQUE — cada falange rígida a su joint, transición de
1-2 loops justo en la articulación (lado palmar más corto que el dorsal, como toda
bisagra). Los metacarpos (`…00Skinning_JNT`) reparten la palma para el Cup. La membrana
interdigital reparte entre dedos adyacentes.

**Errores típicos**: dedos "de goma" (transiciones largas); nudillos que colapsan en el
puño (falta peso del hijo en el dorso del nudillo); palma plana como tabla (metacarpos
sin peso); la membrana del pulgar rasgada (transición demasiado corta ahí — es la
excepción: esa zona pide gradiente ancho).

---

## PECHO / COLUMNA / ABDOMEN

**Joints**: `C_spine01Skinning_JNT … C_spineNNSkinning_JNT` (def 8, con squash de
volumen en scaleX/Z), `C_localChestSkinning_JNT` (caja torácica), y abajo
`C_localHipSkinning_JNT` (pelvis).

**Pose de test**: flexión adelante (tocar puntas), extensión atrás, side-bend a ambos
lados, twist de torso 45-60°, y combinación twist+flexión.

**Shape objetivo**: la columna dibuja una CURVA CONTINUA — la flexión se reparte entre
todas las vértebras, jamás bisagra en una; en flexión el vientre comprime (ahí ayuda el
Auto Squash del spine) y la espalda estira; la caja torácica se mueve como bloque
semirrígido — el pecho/esternón NO se dobla por en medio; en el twist los hombros giran
más que las caderas con gradiente suave por el torso; la pelvis es rígida.

**Reparto de pesos**: bandas HORIZONTALES solapadas, una por `spineNNSkinning`, cada
anillo de vértices repartido entre 2-3 joints consecutivos. Pecho/esternón/costillas
altas casi rígidos a `C_localChestSkinning_JNT`; vientre más repartido (2-3 joints)
para comprimir; pelvis y glúteo alto a `C_localHipSkinning_JNT`.

**Errores típicos**: "manguera doblada" (una banda demasiado dominante → crease en una
vértebra); pecho de cartón que se pliega (el chest necesita más rigidez); la pelvis que
se arrastra al girar el torso (pesos de spine bajando demasiado); asimetría en el
side-bend por bandas torcidas (píntalas en anillos rectos en bind pose).

---

## CUELLO / CABEZA

**Joints**: `C_neckSkinning00-04_JNT` (ribbon, def 5), `C_headSkinning_JNT` (cráneo,
con squash desde `C_headSquash_CTL`).

**Pose de test**: mirar arriba (extensión) y abajo (flexión), ladeo, giro 80°, y giro +
mirar abajo combinado.

**Shape objetivo**: mini-columna — curva continua del cuello; en extensión la nuca
pliega y la garganta estira SIN colapsar; la cabeza entera (cráneo, orejas, mandíbula
cerrada, línea del pelo) es RÍGIDA a head; el trapecio hace de transición
cuello-hombros y absorbe el ladeo; la nuez/garganta no se estrangula en el giro.

**Reparto de pesos**: bandas horizontales solapadas `neckSkinning00→04`; base del
cráneo y mandíbula 100% `C_headSkinning_JNT` (la cara la pintan los módulos faciales
sobre esa base); base del cuello reparte con `C_localChestSkinning_JNT`/clavículas
(trapecio).

**Errores típicos**: crease en la garganta al mirar abajo (transición corta bajo la
barbilla); orejas o mandíbula que se quedan atrás al girar (peso de cuello subiendo al
cráneo); hombros que suben al girar la cabeza (pesos de neck invadiendo el trapecio).

---

## CADERA

**Joints**: `L_legUpper00_JNT` (raíz non-roll del muslo), `L_legUpper01-02_JNT`,
`C_localHipSkinning_JNT` (pelvis rígida).

**Pose de test**: pierna delante 90°+ (kick / sentarse), atrás 30°, abducción (split
lateral), y sentadilla (flexión cadera + rodilla a la vez).

**Shape objetivo**: pierna delante → el pliegue inguinal es LA crease (limpia, en la
ingle, no en mitad del muslo) y el glúteo se estira lateralmente manteniendo volumen;
pierna atrás → el glúteo comprime y sube, el frente de la cadera estira; abducción →
sin bulto en la cresta ilíaca, la masa del muslo rota alrededor de la bola; la pelvis
en sí NO se deforma.

**Reparto de pesos**: como el hombro — bola con transiciones LARGAS: el muslo alto
reparte con `C_localHipSkinning_JNT` en 4-6 loops; el glúteo con peso mixto
pelvis/fémur (más pelvis arriba, más fémur abajo); el vientre bajo no debe llevar peso
de pierna.

**Errores típicos**: cadera que colapsa en sentadilla (efecto "pantalón desinflado" —
transición corta); glúteo que desaparece al levantar la pierna; "pañal" (transición
demasiado ancha en la ingle que engorda la entrepierna); crease en mitad del muslo.

**Siguiente capa**: volumen de glúteo/cuádriceps en sentadilla profunda → correctivas
(el repo ya trae thighFront/thighBack con driver de rodilla; cadera pide cone driver).

---

## RODILLA

**Joints**: frontera `L_legUpper04_JNT` (param 0.95, casi en la rodilla) ↔
`L_legLower00_JNT`.

**Pose de test**: 0° → 140° (sentadilla profunda / talón al glúteo).

**Shape objetivo** (a 140°): la rótula se marca y viaja con la tibia — el frente se
mantiene firme y huesudo; el poplíteo (detrás) pliega con UNA crease; pantorrilla y
muslo comprimen al contacto (capa de correctiva); el muslo no pierde su línea frontal.

**Reparto de pesos**: espejo del codo — transición CORTA detrás (pliegue), LARGA
delante para que la rótula acompañe a la tibia (peso de `legLower00` subiendo por el
frente de la rodilla).

**Errores típicos**: rodilla redonda sin hueso (frente sin peso del hijo); crease
delantera (peso de tibia subiendo DEMASIADO por el muslo); doble pliegue detrás;
pantorrilla que atraviesa el muslo a 140° (eso no se arregla con pesos: correctiva).

---

## TOBILLO / PIE

**Joints**: `L_legLower04_JNT` (fin del ribbon de tibia — lleva ya el twist de tibia),
`L_legAnkleSkinning_JNT` (tobillo/talón), `L_legBallSkinning_JNT` (bola del pie Y
dedos: no hay joint de toe — los dedos son rígidos a la ball). El roll
(heel/ball/toe/bank) es mecánica del pie IK, no joints de skin extra.

**Pose de test**: puntera máxima (plantarflexión), flex (dorsiflexión), roll completo
talón→bola→punta con el atributo Roll, banking lateral.

**Shape objetivo**: talón + empeine casi RÍGIDOS al tobillo — el tobillo es bisagra
corta; el tendón de Aquiles se marca en puntera; el roll pliega el pie por la línea de
la BOLA (metatarsos), nunca por el arco; el arco no se deforma (salvo cartoon); los
dedos acompañan a la bola como bloque.

**Reparto de pesos**: transición de 1-2 loops en el tobillo (la pantorrilla baja lleva
`legLower03-04` para el twist de tibia); planta y empeine traseros a
`legAnkleSkinning`; crease limpia en la planta a la altura de los metatarsos hacia
`legBallSkinning`; dedos 100% ball.

**Errores típicos**: pie de plastilina (el arco se dobla — la frontera ankle/ball está
en el arco en vez de en los metatarsos); tobillo que estrangula en puntera (transición
corta + twist de tibia mal escalonado); talón que se estira con la puntera.

---

## FACIAL (breve — el detalle vive en los módulos y en `corrective-joints`)

La cara se pinta SOBRE la base rígida de `C_headSkinning_JNT`: primero cabeza 100%
rígida, después cada módulo roba peso localmente. Joints por módulo (inventario
completo en `esqueleto-deformacion.md` §faciales):

- **Mandíbula**: `C_jawSkinning_JNT` (mentón, labio inferior, papada baja) vs
  `C_upperJawSkinning_JNT`. Shape objetivo al abrir: la mejilla ESTIRA en gradiente
  (peso mixto jaw/cheek), el mentón rígido, el cuello no se abre con la boca.
- **Labios**: `{R|C|L}_upperLip00…_JNT` / `lowerLip…` (+ variantes NonRot). Shape: los
  labios ruedan sobre los dientes, comisuras con gradiente hacia mejilla.
- **Párpados**: `{side}_upper/downEyelid0{i}Skinning_JNT` — el párpado desliza sobre el
  globo (`{side}_eyeSkinning_JNT`), sin arrastrar ceja ni pómulo.
- **Cejas** (`{side}_eyebrowSkinning00…` + `C_eyebrowMidSkinning_JNT`), **pómulo/mejilla**
  (`{side}_cheek*Skinning_JNT`), **nariz** (aletas `{side}_nostrilSkinning_JNT`),
  **orejas**, **lengua** (cadena `C_tongue0NSkinning_JNT`), **dientes**
  (`C_upper/lowerTeeth_JNT`, rígidos).

Regla facial: transiciones MUY cortas (la cara es piel sobre hueso), y lo que el
skinning no alcance en expresiones lo resuelven las correctivas faciales (una por
shape esculpida — skill `corrective-joints`).

---

## QUADRUPED (horse, giraffe, spot…)

Mismos principios; cambia el inventario (detalle en `esqueleto-deformacion.md` §11):

- **Patas**: ribbons por segmento `L_frontLegUpperBendy00_JNT…`,
  `…MiddleBendy…`, `…LowerBendy…` + `L_frontLegFetlockSkinning_JNT` (menudillo),
  `L_frontLegPasternSkinning_JNT` (cuartilla), `L_frontLegTipSkinning_JNT` (casco).
  El menudillo es LA bisagra expresiva del galope: crease trasera limpia, frente firme.
  El casco es 100% rígido a Tip.
- **Escápula** (solo front): `L_frontLegScapulaSkinning_JNT` — en el quadruped la
  escápula SÍ desliza visiblemente por el costillar al dar el paso: peso propio con
  transición larga hacia el torso (equivale al hombro humano en importancia).
- **Spine/cuello/cola**: `C_spine00-0N_JNT`, `C_neck00…` (el último es
  `C_headSkinning_JNT`), `C_tail00-0N_JNT` — todo bandas solapadas tipo columna. En
  cuello largo (giraffe/horse) cuida el gradiente del ladeo y que la crin/garganta no
  colapse en extensión.
