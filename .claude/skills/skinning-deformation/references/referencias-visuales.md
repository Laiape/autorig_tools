# Referencias visuales — flujo con fotos del usuario

El usuario va pasando fotos (renders/viewport de su personaje, una zona que deforma
mal, o una foto real que quiere igualar) y la skill devuelve REFERENCIAS FOTOGRÁFICAS
de la web de cómo debe deformar esa zona. La referencia manda: cuando hay foto real,
la shape objetivo es la foto, no la descripción del catálogo.

## Flujo cuando llega una foto

1. **Lee la imagen** (herramienta Read sobre el archivo si es local, o la imagen
   adjunta). Identifica:
   - **Zona**: hombro, codo, rodilla…? ¿En qué pose está (grados aprox de flexión)?
   - **Tipo de cuerpo**: realista/cartoon, musculado/delgado/pesado,
     humano/criatura/quadruped, con ropa o piel desnuda. La referencia útil debe
     coincidir en tipo — un codo de culturista no sirve para una niña cartoon.
   - **El defecto** (si es un render del rig): colapso, candy-wrapper, crease mal
     puesta… — diagnóstico con `fundamentos.md` §diagnóstico.
2. **Busca en la web** (WebSearch; si el usuario quiere resultados de imágenes de
   Google, construye también la URL directa
   `https://www.google.com/search?tbm=isch&q=<query>` para que la abra él). Queries en
   INGLÉS — hay muchísima más referencia. Combina: zona + pose + "anatomy reference" /
   "reference photo". Añade el tipo de cuerpo ("female", "heavyset", "cartoon style")
   cuando importe.
3. **Cura los resultados**: 3-5 enlaces máximo, y por cada uno di QUÉ mirar (p. ej.
   "fíjate en cómo la crease de la axila apunta hacia el pezón, no horizontal"). Un
   listado de links sin lectura no ayuda a pintar.
4. **Traduce a acción**: conecta lo visto con el catálogo (`catalogo-zonas.md`) — qué
   banda de pesos tocar para acercarse a la foto — o, si la foto ya deforma bien y
   falta volumen, deriva a correctivas.

## Recetas de búsqueda por zona

| Zona | Queries que funcionan |
|---|---|
| Hombro | `arm raised overhead deltoid armpit anatomy reference`, `shoulder abduction 180 degrees photo`, `armpit fold arm up reference` |
| Codo | `arm flexion 140 degrees elbow crease reference`, `elbow bent olecranon anatomy photo` |
| Antebrazo/muñeca | `forearm pronation supination twist anatomy`, `wrist flexion extension side view reference` |
| Mano/dedos | `closed fist knuckles reference photo`, `hand grip finger creases palm reference` |
| Pecho/columna | `torso side bend spine curve reference`, `torso twist 45 degrees photo`, `forward bend back stretch anatomy` |
| Cuello/cabeza | `head turned 80 degrees neck muscles reference`, `looking up neck throat stretch photo` |
| Cadera | `deep squat hip crease reference photo`, `high kick leg raised glute stretch reference`, `hip flexion seated side view` |
| Rodilla | `deep knee bend kneecap reference`, `kneeling calf thigh compression photo` |
| Tobillo/pie | `foot tiptoe achilles tendon reference`, `toe bend ball of foot crease photo` |
| Facial | `jaw open cheek stretch reference`, `smile nasolabial fold reference photo` |
| Quadruped | `horse fetlock flexion gallop reference`, `horse scapula shoulder movement photo`, `dog hind leg anatomy reference` |

Modificadores útiles: `écorché`, `bodybuilder` (músculo marcado), `ballet` / `yoga
pose` (ROMs extremos reales), `3d scan` (volumen sin ropa), `slow motion` (frames de
contacto), `animal locomotion muybridge` (quadruped clásico).

## Fuentes que suelen dar buen material

- Bancos de poses para artistas: line-of-action.com, quickposes.com, posespace.com
  (photo sets por pose), anatomy360.info (scans 3D).
- Muybridge (humano y animal en movimiento, dominio público).
- Papers/breakdowns de deformación: búsquedas tipo `"pose space deformation" elbow
  example`, `character deformation breakdown shoulder rig` (imágenes de antes/después
  que enseñan la shape objetivo mejor que una foto suelta).
- Para cartoon: stills del estilo objetivo (`"<película/estudio>" character arm bend
  still`) — en cartoon la referencia es el estilo, no la anatomía.

### Screencaps de animación (film 3D y sakuga 2D) — muy útiles

Un fotograma de una peli/serie enseña algo que la foto clínica no: la **intención** del
movimiento — cuánto se exagera la deformación, en qué frame la articulación "marca" el
gesto (el settle, el overlap de la mano tras el brazo), y qué silueta buscó un animador
profesional. Para un rig de estilo (no fotorrealista) suelen ser MEJOR objetivo que la
anatomía real, porque ya traen la estilización que quieres igualar.

- **Cómo enseñarlas al usuario**: cuando pida "screencaps de X", devuelve búsquedas de
  imágenes y frame-galleries, no solo una foto suelta. La deformación lateral/sutil
  (p. ej. desviación de muñeca) rara vez tiene un plano dedicado — aparece en frames de
  *settle/overlap* de un gesto de mano, así que dirige la búsqueda ahí.
- **Sitios**: sakugabooru.com (2D, pools por tema — hay pool "Hand Animation" nº 94) y
  sakugaa.com; film-grab.com y movie-screencaps.com (frames 3D de Disney/Pixar/DWA en
  alta resolución, navegables por película); animationresources.org y el canal
  "Endless Reference" (recopila reference de acción real por movimiento).
- **Queries que funcionan**: `sakugabooru hand animation`, `<película> hands screencap`,
  `film-grab <película>`, `<personaje> gesture animation still`, y para el gesto
  concreto `hand settle overlap animation frame`.
- **Ojo**: son referencia de INTENCIÓN, no de proporción anatómica exacta (compresión,
  motion blur, deformación smear intencionada). Úsalas para decidir la silueta objetivo
  y la exageración; para el reparto fino de pesos combínalas con foto/scan real.

## Si el usuario pasa MUCHAS fotos en tanda

Mantén una mini-tabla en la respuesta: foto → zona detectada → diagnóstico (si es
render) → referencia elegida → ajuste de pesos sugerido. Así la sesión de skinning
avanza foto a foto sin perder el hilo.
