# Fundamentos y metodología de skinning

## Por qué "shape objetivo" y no "pesos bonitos"

Los pesos no son el resultado, son el medio. El resultado es la SILUETA que la malla
dibuja en cada pose extrema. Por eso el flujo es siempre: pose de test → comparar la
silueta con la anatomía o la referencia fotográfica → ajustar pesos → repetir. Nunca se
pinta en bind pose "a ojo" y se da por bueno: una distribución que parece perfecta en
la A-pose puede colapsar a 90° de flexión.

## Orden de capas (qué resuelve cada una)

1. **Skinning base (esta skill)**: volumen general, bisagras, transiciones. Resuelve el
   80% de la deformación.
2. **Twists/bendys**: reparto de torsión y arcos suaves. En este repo YA vienen del
   autorig (ribbons de Boor con swing-twist por cuaternión) — el trabajo del skinner no
   es crearlos, es dar pesos a esos joints en bandas regulares para que el gradiente
   que el rig calcula llegue a la malla.
3. **Correctivas** (skill `corrective-joints`): volumen perdido en poses extremas,
   bulges musculares, contactos. NUNCA arreglan un skinning sucio — si la base pellizca
   o candy-wrappea, se arregla la base primero. Una correctiva sobre skin sucio suma
   dos errores.

## Metodología: bloque → gradiente → pulido en pose

1. **Bind inicial por bloques**: cada loop de la malla 100% a su joint "lógica" — lógica
   anatómica, no euclídea (la ingle está cerca del muslo contrario en distancia, pero
   no en anatomía; Maya no lo sabe, tú sí). Con bloques rígidos el rig ya se mueve y se
   ve DÓNDE hacen falta transiciones. En este repo no hay bind automático en el build:
   el primer bind se hace a mano en escena (smooth bind a los joints de skin del
   módulo, SIN los `*Corrective_JNT`) o transfiriendo de otro personaje
   (`auto_skin_transfer` / `copy_skin_cluster`).
2. **Gradientes solo en las bandas de transición**: suaviza únicamente alrededor de
   cada articulación, con la longitud que pida la zona (corta en el lado del pliegue de
   una bisagra, larga en bolas hombro/cadera). El resto de la malla se queda en bloque.
3. **Twists en escalera**: bandas cilíndricas solapadas y uniformes a lo largo de los
   joints del ribbon (p. ej. cada anillo de vértices ~60/40 entre dos joints
   consecutivos). La regularidad ES el anti-candy-wrapper. Forma rápida de pintarlas:
   selecciona el anillo de vértices (doble clic en edge loop → convertir a vértices) y
   asigna el peso numéricamente en el Component Editor o con Paint Skin Weights en
   modo Replace con valor exacto — más fiable que pintar a pulso. ngSkinTools2 (capas
   y mirror en vivo) también vale para trabajar: solo recuerda exportar el `.skc`
   clásico al final, que es lo que el build importa.
4. **Pulido en pose**: recorre las poses de test del catálogo y pinta EN LA POSE,
   mirando la silueta de perfil y en el ángulo de cámara donde más se verá el
   personaje.
5. **Mirror + export al final de cada sesión**, no al principio: pinta un lado
   completo, mirrorea, exporta `.skc` versionado.

## Reglas de higiene (evitan el 90% del dolor)

- Normalización SIEMPRE activa (interactive); jamás pesos negativos.
- **Prune** de pesos < 0.001 antes de exportar: quita ruido de influencias lejanas que
  luego "flotan" con el masterwalk.
- Máximo de influencias por vértice consciente: 4 si el destino es engine/juego, 8
  para film. Menos influencias = deformación más predecible. (El `.skc` guarda
  `maxInfluences` por skinCluster.)
- Nada de flood smooth global sobre toda la malla: destruye los bloques rígidos
  (falanges, cráneo, pelvis, caja torácica).
- Pinta SUMANDO peso del joint que debe dominar, no restando del que sobra — restar
  reparte el resto entre influencias imprevisibles por normalización.
- Un lado se pinta, el otro se mirrorea. Los vértices de la línea central se dejan
  perfectamente simétricos (mirror de pesos con la malla en bind pose).
- El skinCluster del body es UNO por malla; las correctivas van en skinCluster APILADO
  aparte con `corrective` en el nombre (p. ej. `C_corrective_SKC`) — el build lo
  localiza y lo exporta bien (ver `flujo-pesos-y-qa.md`).

## Cómo leer una deformación mala (diagnóstico → causa → arreglo)

| Síntoma | Causa probable | Arreglo |
|---|---|---|
| Colapso/pellizco en el pliegue | Transición demasiado corta o pesos cruzados (vértices del lado A con peso del hueso B) | Alarga la banda; limpia pesos invasores |
| Pérdida de volumen en la cara exterior de una bisagra | El exterior no sigue al hueso distal | Sube peso del hijo por el dorso (olécranon/rótula) |
| Candy-wrapper en un twist | Bandas de twist irregulares o joint del ribbon sin peso | Rehaz las bandas en escalera uniforme |
| La malla "flota"/se arrastra lejos de la articulación | Influencias lejanas con pesos residuales | Prune + revisa a qué joints está pesado ese loop |
| Crease en mitad de un hueso | Frontera de bloques mal colocada | Mueve la banda de transición a la articulación |
| Todo tiembla o se dobla "blando" | Demasiadas influencias por vértice, todo suavizado | Reduce influencias, vuelve a bloques + bandas |
| La zona deforma bien en local pero mal con masterwalk lejos/escalado | Pesos residuales o (si es un skin de correctivas) falta `localize_corrective_skin` | Prune; re-lanza el build o la localización |

## Dual quaternion — cuándo sí y cuándo no

El `.skc` guarda `skinningMethod` y blend weights, así que la decisión persiste. Linear
clásico colapsa en twists extremos; dual quaternion (DQ) mantiene volumen en twist pero
"hincha" bisagras y engorda hombros/caderas. En este repo los ribbons ya reparten el
twist, que es justo lo que DQ vendría a arreglar — por eso el default razonable es
**linear clásico**, y si una zona concreta lo pide, weight-blended (pintar el blend
solo ahí). No actives DQ global como parche de un twist mal pintado.
