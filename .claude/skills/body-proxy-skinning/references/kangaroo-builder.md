# Kangaroo Builder — las tools de skinning que el usuario ya usa

Kangaroo Builder (https://kangaroobuilder.com/, de **Thomas Bittner**) es el toolkit de rigging
de Maya que el usuario tiene integrado en su pipeline: su `character_manager` lo lanza desde el
menú Tools (`import createShelfKangarooBuilder`). El usuario dice que **sus scripts de copy
skin "suelen funcionar bien"** — úsalo como referencia de comportamiento deseado al recomendar
o construir transferencias de pesos.

Datos generales (contrastados a fecha 2026-07): toolkit de rigs de cuerpo y cara, gestión de
skinning y autoría de blendshapes. Gratis para uso **no comercial**; licencias perpetuas Indie
(~220$, <85k$/año) y Studio (desde ~400$). v5.19 soporta Maya 2023+ (Windows/macOS) y 2024+
(Linux). La web bloquea el fetch automatizado (403): para detalle fino, pide al usuario abrir
la página o pegar el texto.

## Sus tools de skinning (página `tools/toolsSkinCluster/`)

- **Copy/Paste de pesos**: seleccionas un vértice origen → Copy; seleccionas vértices destino →
  Paste. El Paste respeta **soft selection** y **funciona sobre otra malla distinta**. Este es
  el "copy skin de Kangaroo" que el usuario usa para ropa: copiar la zona buena del cuerpo y
  pegarla en la prenda con caída suave.
- **Flood**: asigna pesos por **joint más cercano a cada vértice** y suaviza encima (Smooth
  Steps controlable). Puede tocar varias influencias a la vez y añadir al skinCluster joints
  que aún no estaban.
- **Distribute Weights** (dentro de Flood): recoge todo el peso ya asignado a los joints
  seleccionados y lo **redistribuye** por joint más cercano por vértice — potente para
  redistribuir una región sin tocar el resto (el peso existente actúa de máscara).
- **Bind to Closest & Expand**: pesos limpios en **loops de joints** donde cada joint cae en un
  vértice (labios, párpados); con atributo Distribute que usa el peso existente como máscara.
- **Smooth**: promedia pesos (típico en botones) y puede promediar **islas por separado**
  (varios botones combinados en una sola malla).

## Change Model (página `modelChange/`)

Sustituir la malla conservando el rig: "**Load Best Fitting SkinClusters**" para variaciones de
malla, opción de blendShape para updates, `warpXforms` si la topología no cambia, y **Landmark
Warp** (2026) para transferir blendshapes entre mallas de **topología distinta** (transfer por
landmarks, sin necesidad de topología común).

## Cómo encaja con las recomendaciones de esta skill

- El **Flood** de Kangaroo es de la familia *closest joint* — funciona bien porque siempre se
  aplica **por regiones con máscara** (Distribute/peso existente) y con smooth encima, no como
  bind global a ciegas. Esa es la diferencia con el "assign closest joint" global que cruza
  influencias: la lección es **acotar la región y suavizar**, no el algoritmo en sí. Para el
  bind INICIAL del cuerpo sigue valiendo la recomendación de esta skill (Geodesic Voxel).
- Su **Copy/Paste con soft selection sobre otra malla** es un transfer manual por proximidad —
  la versión artesanal de lo que `tools/cloth_skin_transfer.py` hace automático (closest point
  + baricéntricas + inpainting). Recomienda Kangaroo para retoques dirigidos por el artista y
  la tool del repo para el pase automático inicial; se complementan.
- **Bind to Closest & Expand** es la referencia a citar para loops faciales (labios/párpados),
  donde el autorig del usuario tiene módulos con joints sobre vértices.
- **Landmark Warp / Change Model** cubren el caso "cambió la malla": alternativa comercial al
  flujo proxy + re-transfer de esta skill; si el usuario tiene licencia, puede ser el camino
  corto para blendshapes.

## Fuentes

- Tools de skinning: https://kangaroobuilder.com/tools/toolsSkinCluster/
- Change Model: https://kangaroobuilder.com/modelChange/ · FAQ: https://kangaroobuilder.com/FAQ/
- Landmark Warp (cobertura): https://www.cgchannel.com/2026/02/kangaroo-builder-for-maya-now-supports-topology-transfer/
  y https://digitalproduction.com/2026/02/12/kangaroo-builder-learns-to-move-faces-between-meshes/
