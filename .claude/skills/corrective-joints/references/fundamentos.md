# Fundamentos: qué son las corrective joints, qué hacen y cuándo ponerlas

## 1. Qué son

**Corrective joints** (helper joints, support joints, driven joints, muscle bones) son
joints **adicionales** del esqueleto de deformación con un único propósito: **mejorar la
deformación de la malla**. Reciben pesos en el skinCluster como cualquier otra joint, pero:

- **No se animan a mano**: su translate/rotate/scale está **conducido proceduralmente** por
  la pose del esqueleto principal (ángulo del codo, twist de la muñeca, peso de un shape
  facial…).
- Son **hojas** (leaf joints): nada cuelga de ellas, nada las lee. Solo aparecen como
  influencias del skin.
- El término engloba varias familias: twist/roll joints, correctivas de pose
  (translate/scale driven por ángulo), muscle bones (origen–inserción con stretch), joints
  de pliegue/crease y joints de skin sliding.

Referencia histórica: Jason Parks (GDC 2005, *Helper Joints: Advanced Deformations on
Run-Time Characters*) — todos los engines soportan joints, así que añadir joints extra es
la vía más barata para deformación avanzada en runtime.

## 2. El problema: limitaciones del linear blend skinning (LBS)

LBS calcula cada vértice como media ponderada lineal de las transformaciones de sus
influencias. Interpolar linealmente transformaciones rígidas **no produce una rotación**:
el vértice "corta el arco" en línea recta. Artefactos clásicos:

- **Candy-wrapper**: twist de ~90–180° en antebrazo/muñeca → los vértices con pesos ~50/50
  colapsan hacia el eje y el miembro se estrangula.
- **Colapso de volumen en el bend**: codos/rodillas a 90–140° pierden volumen exterior y se
  interpenetran por dentro ("manguera doblada"). Hombro con brazo >90° → deltoides/pecho
  colapsan.
- **Pérdida de silueta**: glúteo que desaparece al sentarse (visible desde ~50–60° de
  flexión de cadera, grave a 90°+), trapecio que se esfuma en el shrug.
- **Interpenetraciones**: bíceps contra antebrazo en flexión completa, muslo contra gemelo
  en squat.

Conclusión de producción unánime: **el skinning solo nunca es suficiente**. La corrección
viene de tres sitios: más joints (correctivas), shapes esculpidas (corrective
blendshapes/PSD) o deformadores/sims (film).

### Dual quaternion skinning (DQS)

DQS elimina el candy-wrapper de serie, pero introduce **bulging** en flexiones fuertes, es
más caro y **no es estándar en engines** (Unity no; UE5 solo vía Deformer Graph). Regla:
**DQS reduce la necesidad de twist-fixes, no la de correctivas de volumen/silueta**. Este
repo trabaja sobre LBS + deltaMush opcional → las correctivas son necesarias siempre.

## 3. Qué hacen (funciones concretas)

1. **Preservar volumen**: empujar la malla donde el LBS colapsa (detrás de la rodilla,
   glúteo, cara interna del codo).
2. **Simular bulge muscular**: bíceps al flexionar, deltoides al elevar, gemelo en
   plantarflexión. Translate (+ opcional scale) driven por el ángulo.
3. **Mantener la silueta**: glúteo en squat, trapecio en shrug, perfil del tríceps.
4. **Evitar interpenetraciones**: joints de pliegue en la cara interna de codo/rodilla
   (patrón clásico: 2–3 joints en el crease).
5. **Skin sliding**: rótula que sube al estirar, escápula que desliza bajo la piel.
6. **En la cara**: acompañar cada expresión — tallar el pliegue nasolabial en la sonrisa,
   el bulge del entrecejo en el ceño, envolver la córnea en el blink (ver
   `faciales.md`).

## 4. Familias: twist joints ≠ correctivas de pose

| | Twist / roll joints | Correctivas de pose |
|---|---|---|
| Qué corrigen | artefacto **continuo** de torsión (candy-wrapper) | defecto **local** en una región del pose space (codo>90°, brazo arriba) |
| Función del driver | lineal de UN canal (el twist) | no lineal, con dead zone y rampa |
| Cuándo se instalan | **siempre, de serie** (1–3 por segmento) | **bajo demanda**, por evidencia |
| En este repo | ribbons De Boor de brazo/pierna ya reparten el roll (`extract_twist`) | `corrective_push/arc/ring/offset_push` |

Distribución del twist: la fracción de cada twist joint = su posición normalizada a lo
largo del hueso. Antebrazo: crece hacia la muñeca (0% junto al codo — el codo es bisagra
pura). Húmero: invertido — el joint pegado al hombro NO twistea (counter-twist) para que el
deltoides no se enrosque.

## 5. Corrective joints VS corrective blendshapes

| Criterio | JOINTS | BLENDSHAPES / PSD |
|---|---|---|
| Detalle | limitado: 1 transform rígido + falloff de pesos | máximo: forma exacta esculpida por vértice |
| Coste | barata (skinning normal) | memoria + evaluación por shape |
| Export a engine | **trivial: viajan con el esqueleto en FBX** | los morphs viajan pero la lógica de driving NO |
| LODs | excelente (se dejan de pesar) | hay que mantener morphs por LOD |
| Reutilización | alta (mismo setup entre personajes) | baja (por malla) |
| Autoría | rápida de instalar, indirecta de "esculpir" | tediosa en volumen, directa |
| Riesgos | doble transform, flips del driver | inversión de pose (invertShape), suma de volumen |

**Cuándo elegir cada una** (regla práctica, y la de este repo):
- **Primero intenta SIEMPRE la joint** — más barata, editable en vivo, exportable.
- **Blendshape solo para lo que la joint no alcanza**: pliegue fino, arruga, forma
  esculpida direccional. En este repo → `corrective_blendshape_manager` (targets
  frontOfChain + driven keys, export/import/mirror ya resueltos).
- **Híbrido = lo normal**: joints para el movimiento grueso y el volumen estructural;
  shapes para el último 10% de detalle. Es como funcionan Naughty Dog, MetaHuman o
  Snappers, y como está montada la facial de este repo.

## 6. Cuándo añadir una correctiva: la regla de oro

Orden de trabajo (no te lo saltes):

1. **Topología y placement correctos** (edge loops de bend, pivotes anatómicos).
2. **Skinning limpio** joint a joint, probando rangos completos.
3. **Twists de serie** (aquí: los ribbons ya lo hacen).
4. **Solo entonces**, correctivas **donde el skinning + twists no llegan**. Cada correctiva
   es coste (setup, pesos, export): se añade **por evidencia, no por costumbre**.

**Evidencia = ROM test + silueta**:
- ROM: cada articulación por su rango completo, sola y combinada (squat profundo, brazos
  arriba >150°, twist ±90°, puño, brazos cruzados, codo/rodilla a ~140°).
- Revisar **en silueta** (shaded plano): la pérdida de volumen se ve antes que en shaded
  normal.
- Umbrales típicos que disparan correctiva: codo/rodilla desde ~90° de flexión, hombro
  elevado >90°, muñeca a ±60°, cadera >90° (squat).
- La correctiva suele estar "muerta" el primer tercio del rango y rampar después (dead
  zone ~20–30°, 100% a 90–130°): evita ensuciar poses neutras.

**En la cara**, la evidencia es la comparación contra el set de expresiones esculpidas:
reproduce la expresión con los controles → el delta contra el sculpt es la correctiva
(flujo completo en `faciales.md`).

## 7. Presupuestos orientativos

- Rig de juego económico: ~10–16 helper joints corporales extra.
- AAA (MetaHuman/Paragon): 40–60+ (patrón MetaHuman: 4 correctivas cardinales por
  hombro/cadera + 2 twists por segmento). El coste también cuenta en runtime: los
  correctives se desactivan en LODs bajos.
- Facial de juego "bueno": ~20–30 correctivas sobre 60–80 shapes primarios; techo de gama
  MetaHuman ~128 corrective morphs (orden de magnitud, no cifra exacta).
- Este repo hoy: codo (bíceps + tríceps + anillo de 4), rodilla (thighFront + thighBack),
  hombro (deltoid + armpit + pec + shoulderBack por cone_driver), cadera (glute + groin +
  hipOut por cone_driver) y el set facial de `facial_correctives_module` (~25 joints).
  Pendiente: muñeca/tobillo/torso/manos y los pesos de skin de las zonas nuevas.
