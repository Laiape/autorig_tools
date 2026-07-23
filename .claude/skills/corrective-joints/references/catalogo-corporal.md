# Catálogo corporal de corrective joints (bípedo + notas de cuadrúpedo)

Dónde se colocan, qué driver las activa, en qué dirección empujan y qué defecto corrigen.
Los rangos en grados son valores típicos de producción — varían por personaje y estilo.
En este repo: driver angular = `bend_driver`/`bend_factor`, twist = `extract_twist`,
multi-eje = cone driver (ver `drivers.md`); amounts por defecto = ~12% de la longitud del
hueso, expuestos como plugs.

## 1. Hombro / axila / deltoides / pectoral (la zona más difícil)

La articulación con más rango del cuerpo (~180° de elevación combinada). El reparto real es
el **ritmo escapulohumeral 2:1**: de 180° de abducción, ~120° glenohumerales y ~60° de
escápula; la clavícula se eleva ~25° (en rig, la auto-clav suele quedarse en 15–25°).
Este repo ya tiene `auto_clavicle()` en el arm module.

| Correctiva | Nº | Driver | Rango | Empuje | Corrige |
|---|---|---|---|---|---|
| Escápula | 1 | rot. clavícula + elevación húmero | shrug 0–40°, elev. 0–180° | desliza sobre las costillas | escápula hundida/inmóvil bajo la piel |
| Deltoides | 1 | abducción del húmero (cone driver) | 0→90/120° | fuera/arriba (bulge) | hombro plano con el brazo en T/arriba |
| Axila/lat | 1 | abducción | 0→90/120° | abre la axila (abajo/adentro) | interpenetración brazo-torso |
| Pectoral | 1 | aducción/flexión horizontal | ±60–90° | el pec viaja con el brazo | pecho congelado al cruzar el brazo |
| Trapecio/shrug | 1–2 | shrug clavícula + elevación >90° | 0–40° | arriba/adentro | trapecio congelado, hombro "cortado" del cuello |

Patrón MetaHuman de referencia: 4 correctivas cardinales por hombro (`upperarm_fwd/bck/
in/out`) alrededor de la cabeza del húmero + 2 twists de húmero. Total zona: 4–8 joints
por lado. El hombro es LA zona donde un solo eje euler no basta → cone driver o RBF
(nunca `bend_driver` a pelo — ver `drivers.md` §cone).

## 2. Codo, antebrazo y muñeca

| Correctiva | Nº | Driver | Rango | Empuje | Corrige |
|---|---|---|---|---|---|
| Bíceps (YA en el repo) | 1 | flexión codo (`bend_driver` eje Y) | repo: 0→-100° lineal desde 0 (sin dead zone; si ensucia poses casi neutras, sube in_min a ~20-30°) | arco: adelante +Z y sube -X hacia el hombro | brazo-tubo sin contracción |
| Tríceps (YA en el repo) | 1 | extensión codo | repo: 0→+100° | arco: atrás -Z, sube -X | perfil trasero del brazo |
| Anillo de codo (YA) | 4 | flexión | 0→-100° | radial hacia fuera | volumen del codo al flexionar |
| Pliegue interior | 2–3 | flexión | 30–145° | modela/apila la carne del pliegue | intersección bíceps-antebrazo |
| Olécranon | 1 | flexión | 0–145° | posterior (punta ósea) | codo redondo sin hueso |
| Muñeca inner/outer | 1–3 | flexión/extensión muñeca | flex ~80°, ext ~70° | palmar sale al flexionar; dorsal sostiene al extender | muñeca estrangulada |
| Twist antebrazo | (ribbon) | pronosupinación ±80–90° | — | reparto creciente hacia la muñeca | candy-wrapper |

ROM de codo: 0→~145° (test estándar a 140°). Correctiva de twist de muñeca: driver =
`extract_twist` (ver receta en `drivers.md`) — pendiente de instanciar en el repo.

## 3. Cadera / glúteo / muslo, rodilla, tobillo

La cadera es "el hombro de la pierna": esférica, multi-eje (flexión ~120°, extensión
~10–20°, abducción ~45–60°).

| Correctiva | Nº | Driver | Rango | Empuje | Corrige |
|---|---|---|---|---|---|
| ThighFront/cuádriceps (YA) | 1 | rodilla hacia delante, z+ (`bend_driver` eje Z) | repo: 0→+100° | arco: adelante +Y, sube -X | ingle/muslo colapsados |
| ThighBack/isquios (YA) | 1 | flexión, z− (al subir la rodilla se contrae) | repo: 0→-100° | rest detrás (-Y) y se contrae (-X,+Y) | masa trasera del muslo |
| Glúteo | 1 | flexión + extensión de cadera | 0–120° / 0→-30° | mantiene la masa atrás/arriba | "el culo desaparece" al sentarse (visible ~55°+) |
| Thigh out/in | 1–2 | abducción / aducción (cone) | 0–60° | trocánter fuera / protege interior | hachazo lateral, interpenetración de muslos |
| Rótula / knee bend | 1 | flexión rodilla (half-rotation 50%) | 0–150° | mantiene la rótula delante | rodilla-cuchillo |
| Hueco poplíteo | 1–3 | flexión rodilla | 60–150° | comprime/apila pantorrilla vs muslo | interpenetración en sentadilla |
| Gemelo | 1 | flexión rodilla / plantarflexión | 0–150° | posterior (bulge) | pantorrilla plana |
| Tobillo fwd/bck | 1–2 | dorsiflexión +20-30° / plantarflexión -40-50° | — | empeine sale; Aquiles se tensa | tobillo-manguera |

## 4. Torso, cuello, mandíbula-cuello

| Correctiva | Nº | Driver | Rango | Empuje | Corrige |
|---|---|---|---|---|---|
| Belly bulge | 1 | flexión acumulada de spine | 0–60° total | fuera al flexionar, dentro al extender | tripa-cilindro (sirve también para respiración) |
| Pecho/costillas | 1 | flexión spine superior | ±30° | mantiene el esternón rígido | caja torácica que se dobla |
| Costados/oblicuos | 0–2 | lateral bend ±30–40° | — | comprime el lado que pliega | pellizco del costado |
| Cuello (SCM) | 0–2 | giro de cabeza ±80–90° | — | marca el esternocleidomastoideo | cuello-tubo |
| Garganta/hioides | 1 | apertura de jaw (ángulo jaw↔neck) | 0–35° | baja/tensa la papada | garganta rígida al hablar |

## 5. Manos

| Correctiva | Nº | Driver | Empuje | Corrige |
|---|---|---|---|---|
| Metacarpos cup | 2–3 | atributo cup / flexión de meñique-anular | rotación + lateral del 5º metacarpo | palma-tabla (arco palmar) |
| Nudillos | 0–4 | flexión MCP 0–90° | dorsal (se marcan) | nudillos colapsados en puño |
| Thenar (pulgar) | 1 | oposición del pulgar | abomba el pulpejo | base del pulgar plana |

## 6. Notas de cuadrúpedo (giraffe, horse, spot…)

- **Escápula deslizante**: sin clavícula funcional, el tronco cuelga de las escápulas. La
  escápula es un joint con **traslación** dominante que desliza sobre las costillas,
  driveado por la posición del forelimb IK; 1–3 correctivas para el borde que asoma sobre
  la línea dorsal en la zancada.
- **Corvejón (hock)**: flexiones muy pronunciadas → half-rotation + correctiva de la cuerda
  del tendón (leaf joint que mantiene el "Aquiles" recto y tenso entre corvejón y muslo).
- **Muslo trasero**: al sentarse pliegan ~150° (sándwich pantorrilla-muslo-cuerpo) → varios
  push de pliegue.
- **Panza/papada**: jiggle/gravedad más que pose-driven.

## 7. Cómo priorizar

1. Codo y rodilla (ya hechas aquí) — el mayor retorno visual por esfuerzo.
2. Hombro completo (deltoides + axila + pec + escápula) — la más difícil; requiere cone
   driver o RBF.
3. Cadera/glúteo — squat y sentarse salen en cualquier animación.
4. Muñeca (twist + flexión) y tobillo.
5. Torso/cuello/manos — según personaje y cámara.

Presupuesto: económico ~10–16 joints extra; AAA 40–60+. Cada joint nueva debe pagarse con
un defecto visible que corrige.
