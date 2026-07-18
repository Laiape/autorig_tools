# Catálogo de métodos para riggear ropa

Backbone de la skill. Los métodos van del **escalón 0 (copy skin weights, el punto de partida del
usuario)** hacia arriba en precisión. Sube solo los escalones que el síntoma pide (ver
`como-elegir.md`); más preciso casi siempre cuesta más o quita control.

Ejes: **Precisión** (baja/media/alta) · **Secundario** (ninguno/aproximado/simulado) ·
**Art-directable** · **Tiempo real** · **Coste**.

## Tabla-resumen (de menos a más preciso)

| Método | Familia | Precisión | Secundario | Art-dir | Real-time | Coste | DCC / Tool |
|---|---|---|---|---|---|---|---|
| Copy skin weights | Transferencia | baja | ninguno | alta | sí | bajo | Maya (copy skin), tu `auto_skin_transfer`/`SkinManager` |
| Heat/geodesic bind + normalizar | Skinning | baja-media | ninguno | alta | sí | bajo | Maya (geodesic voxel), ngSkinTools |
| Delta Mush / Tension | Skinning refinado | media | ninguno | media | sí* | bajo | Maya `deltaMush`, `tension` |
| ProximityWrap / cvWrap | Envoltura | media | ninguno | media | sí* | medio | Maya `proximityWrap`, cvWrap |
| ShrinkWrap + skin base | Envoltura | media | ninguno | media | sí* | medio | Maya `shrinkWrap` |
| Rig de joints + colisión distancia | Mecánico | media | aproximado | **alta** | sí | medio | Maya (joints, ribbon), tu `auto_collision` |
| Ribbon / dynamic joints (overlap, jiggle) | Mecánico | media | aproximado | alta | sí | medio | Maya (nHair/de Boor, spring) |
| Correctivos / PSD / RBF | Correctivo | media-alta (arrugas) | ninguno | alta | sí* | medio-alto | SHAPES, `poseInterpolator`, mGear, RBF |
| Wrinkle/normal maps por tensión | Correctivo (juego) | media (visual) | ninguno | media | **sí** | medio | tensión→mapa (Maya/engine) |
| ML Deformer (entrenado con sim) | ML | alta | aproximado-simulado | media | **sí** | alto (setup) | Maya ML Deformer, Chaos ML Deformer |
| Cloth de engine (Chaos / Unity) | Tiempo real | media-alta | simulado | baja-media | **sí** | medio | UE Chaos Cloth, Unity Cloth |
| Simulación offline (nCloth/Qualoth/Vellum/Marvelous/Ziva) | Simulación | **alta** | simulado | baja | no | alto | Maya nCloth/Qualoth, Houdini Vellum, MD, Ziva |
| Sim → cache/PSD (híbrido) | Híbrido | **alta** | simulado | **alta**‡ | sí‡ | alto | Alembic, blendshape/PSD desde sim |

\* interactivo pero con coste de evaluación. ‡ recupera control y tiempo real al hornear la sim a un
asset dirigible.

---

## 0. Punto de partida — Copy skin weights (transferencia de pesos)

**Qué es**: copiar los pesos de skin del cuerpo a la prenda (closest point, por UV, o por jerarquía de
joints). Es lo que el usuario ya hace.

**Cómo funciona**: la prenda se skinnea a los mismos joints que el cuerpo y hereda pesos por
proximidad/superficie. La tela pasa a moverse **exactamente** como la piel de debajo.

**Precisión: baja. Por qué "no es preciso"**: la prenda queda *pegada* al cuerpo. No tiene movimiento
propio, no desliza, no arruga por contacto y **interpenetra** en zonas de flexión (rodilla, muslo,
codo) porque el peso interpolado no sabe de colisión ni de volumen de tela.

**Cuándo basta**: prenda muy ajustada (ropa interior, calcetín, guante fino) donde seguir la piel *es*
el resultado correcto. Ahí no hace falta subir escalón.

**Encaje en tu pipeline**: `auto_skin_transfer` + `SkinManager` (`.skc`). Es la **base** sobre la que
montar los siguientes escalones, no el final del camino.

---

## 1. Skinning refinado

Mejora la *base* sin cambiar de paradigma. Sigue sin dar secundario ni colisión, pero limpia el
resultado del copy skin.

**Heat map / geodesic voxel binding** — Bind que reparte pesos por distancia geodésica (rodea la
superficie) en vez de por línea recta, así una manga no coge peso del torso al que casi toca.
*Precisión baja-media; límite: sigue sin colisión ni secundario.*

**Delta Mush** — Deformador que **suaviza** el resultado del skin hacia la forma "relajada" del modelo,
matando los estirones y candy-wrappers sin repintar pesos. Barato y espectacular para limpiar bind
sucios. *Precisión media; límite: no añade arrugas nuevas ni contacto, solo suaviza; coste de
evaluación en mallas densas.* **Encaje**: capa encima de tu skin base, previa a correctivos.

**Tension / smooth** — Similar filosofía: suaviza y/o reacciona al estiramiento. Útil para quitar
pellizcos en costuras.

**ngSkinTools** — Sistema de pesos por **capas** (como Photoshop): flood, mirror, suavizado por capa.
No es un método de deformación distinto, es una forma mucho más limpia y reusable de **autorar** el
skin. *Encaje*: ya tienes `skin_manager_ng` — es el camino para pesos mantenibles.

---

## 2. Envoltura (wrap / proximity): seguir la malla, no los joints

La prenda sigue la **superficie deformada del cuerpo**, no directamente los joints. Captura mejor el
contacto porque "se apoya" en la piel ya deformada.

**ProximityWrap** — Deformador moderno de Maya: la prenda se deforma según los puntos más cercanos del
cuerpo, con falloff. Sustituye al wrap clásico, es más rápido y controlable. *Precisión media; da
deslizamiento/contacto mucho mejor que el copy skin; límite: interpenetración residual y sin secundario
dinámico.* **Encaje**: capa sobre skin base para vestidos/túnicas ajustadas.

**Wrap clásico / cvWrap** — Igual idea, más pesado (wrap nativo) o más eficiente y open-source
(`cvWrap` de Chad Vernon, un deformer en C++/Python). *Nota de portabilidad: cvWrap es un plugin; si
quieres evitar dependencias, `proximityWrap` nativo cubre el 90% del caso.*

**ShrinkWrap** — Proyecta la prenda sobre la superficie del cuerpo (útil para pegar una capa a otra, o
para ajustar una prenda al cuerpo antes de simular).

**BlendShape con target de cuerpo** — Conectar la forma del cuerpo como target para que la prenda lo
siga; más manual pero muy dirigible.

---

## 3. Rigs mecánicos por joints (faldas, capas, vestidos) — tu terreno

Control **total** del animador con secundario **aproximado**. En muchos planos de personaje esto gana a
la sim porque se posa a mano y es interactivo.

**Cadenas de joints** — Falda/vestido dividido en tiras verticales de joints, con FK/IK y controles.
Deformación predecible y ligera. *Precisión media, secundario aproximado; límite: arrugas finas y
contacto real limitados.*

**Ribbon / spline (de Boor, nHair-driven)** — Tiras de tela sobre ribbons NURBS: pocos controles mueven
muchos joints con interpolación suave. **Encaje directo**: reutiliza tu `de_boor_core`/`ribbon`; una
falda es un caso más de ribbon. Se le puede añadir dinámica (nHair como driver del spline) para
secundario automático art-directable.

**Dynamic joints / overlap / jiggle** — Dinámica procedimental (spring, delay) sobre las cadenas para
que la tela "coletee" al andar sin simular tela completa. Barato y controlable. *Secundario aproximado
de buena calidad para acción.*

**Colisión por distancia (push)** — Empuje de joints cuando una pierna se acerca, con falloff. **Es tu
`auto_collision.py`** (`distanceBetween → plusMinusAverage(min) → remapValue → translate` en un grupo
offset). *Aproxima* la colisión sin solver. *Límite honesto: no es contacto real, solo un empuje por
proximidad de puntos; por eso el plugin C++ de colisión te daba mejor resultado. La vía nativa para
subir calidad es más muestras de colisión / colisión contra superficie (closestPointOnMesh) en vez de
punto-a-punto, o ray/UV sampling — todo con nodos, sin plugin.*

---

## 4. Correctivos, PSD y arrugas dirigidas

Añaden **precisión de arrugas** encima de una base (skin/wrap). No son dinámicos: la arruga se define
por pose, no por física, pero son 100% art-directables y baratos en runtime.

**Correctivos (blendshape)** — Esculpes la forma correcta en una pose problemática (codo doblado) y se
mezcla con el ángulo. **Encaje**: ya tienes `correctives.py`, `blendshape.py`,
`corrective_blendshape_manager.py` — el sistema existe, se trata de aplicarlo a la prenda.

**Pose Space Deformation (PSD)** — El marco formal (Lewis et al.): asocias formas correctivas a poses
en un "espacio de poses" e interpolas entre ellas. Es como se hacen las arrugas de ropa dirigidas en
producción.

**Solvers RBF** — Interpolación por radial basis functions que dispara correctivos según uno o varios
drivers (ángulos de joint). Herramientas: **SHAPES** (Brave Rabbit), `poseInterpolator` nativo de Maya,
los RBF de **mGear**. *Encaje*: un RBF nativo (`poseInterpolator`) evita depender de plugins de pago.

**Wrinkle maps por tensión/ángulo** — Mapas de arruga que se activan por estiramiento/compresión de la
malla o por ángulo de joint; muy usado para arrugas de tela dirigidas y para juego (ver §7).

*Límite de toda la familia*: hay que **autorar** cada corrección; no reacciona a fuerzas ni a colisión
inesperada. Es precisión donde tú decides, no donde la física decide.

---

## 5. Simulación física offline — lo más preciso

Arrugas, contacto y deslizamiento **reales**. Es el techo de precisión y el estándar para tela suelta
hero en cine. A cambio: caro de calcular, **poco art-directable** y no interactivo.

**nCloth (Nucleus)** — Solver de tela de Maya. Integrado, colisiona con el cuerpo (nRigid), constraints
de costura/anclaje. Bueno y accesible dentro de Maya.

**Qualoth** — Solver de tela de terceros para Maya, muy usado en producción por calidad y control de
plegado. *Plugin: dependencia externa.*

**Marvelous Designer** — Software dedicado de patronaje/simulación; se simula ahí y se trae la malla.
Insuperable para telas complejas y drapeados; flujo aparte.

**Houdini Vellum (cloth)** — Solver de posición (XPBD) rápido y robusto; el estándar CFX moderno. **Tu
terreno de Houdini.** Simulas en Houdini y devuelves a Maya por Alembic (ver §6).

**Ziva Cloth / otros** — Soluciones de tela dentro de suites de creature (calidad alta, setup mayor).

*Encaje*: para tela suelta protagonista, la ruta natural en tu pipeline es **Vellum en Houdini** (o
nCloth si te quedas en Maya) + el bucle de §6 para reintegrar. Nunca simules la malla de render:
simula una **proxy** de baja y transfiere.

---

## 6. Flujos híbridos sim → rig (cerrar el círculo)

Combinan la precisión de la sim con el control de un asset. **Es lo que hace un estudio**: la sim no es
la entrega final, es el motor de un resultado dirigible.

**Bake a Alembic (`.abc`)** — Cachear la sim y sustituir la malla en el plano. Simple y robusto; el
animador ve el resultado sin recalcular. *Recupera tiempo real; límite: la caché es "tonta", no se
re-poza.*

**Sim → blendshape / PSD** — Usar la sim como **referencia** para esculpir correctivos por pose (§4):
recuperas control total y coste bajo en runtime, con arrugas de calidad-sim en las poses clave.

**Blend por regiones** — Rig mecánico (§3) para el grueso + capa de sim solo para el secundario fino,
cacheada y mezclada por máscara. Lo mejor de ambos donde cada uno aporta.

**Sim → ML Deformer** — Ver §8: la sim genera los datos de entrenamiento.

---

## 7. Tela en tiempo real / juegos

Precisión acotada por presupuesto de rendimiento. Se rigea a mano lo que se puede y se delega a la
física del engine lo justo.

**Chaos Cloth (Unreal)** — Sistema de tela de UE5: pintas propiedades sobre la malla, colisiona con
cápsulas del esqueleto. Buen secundario sin geometría extra. **Bone-cloth**: huesos de tela movidos por
física del engine, más barato y controlable.

**Unity Cloth** — Componente de tela de Unity (skinned cloth), similar filosofía con su presupuesto.

**Wrinkle / normal maps por tensión** — Para arrugas **sin** geometría: mapas de normal que se mezclan
según estiramiento/compresión, dando la *ilusión* de arruga a coste de textura. Es la vía estándar de
arrugas en personajes de juego (codos, axilas). *Precisión visual media, rendimiento excelente.*

*Encaje*: si un asset tuyo va a engine, la prenda ajustada = skin limpio + wrinkle maps; la suelta =
bone-cloth/Chaos Cloth con colisión del engine.

---

## 8. Deformadores por ML / data-driven

Buscan la **precisión de la sim al coste de un deformer** interactivo. Setup alto, runtime barato.

**ML Deformer (Maya)** — Entrenas un modelo con muchas poses simuladas (o con correctivos) y luego
aproxima esa deformación en tiempo casi real dentro del rig. Ideal para llevar calidad de sim a un
asset que el animador maneja.

**Chaos ML Deformer (Unreal)** — Equivalente en UE: aproxima deformación cara (incluida tela/músculo)
para tiempo real.

**Síntesis neuronal de arrugas** — Línea de investigación (papers) que genera arrugas de tela a partir
de la pose con redes; aún más de I+D que de pipeline estándar, pero es hacia donde va el detalle
data-driven.

*Límite*: dependes de la calidad y cobertura de los datos de entrenamiento; generaliza mal fuera del
rango entrenado; el setup (generar sims + entrenar) es una inversión.

---

## Recursos

> Nota: verifica los enlaces con `web_search`/`web_fetch` antes de pasárselos al usuario; aquí van las
> fuentes de referencia por tipo. (Esta sección se enriquece con la investigación en vivo.)

- **Docs oficiales** — Autodesk Maya: `proximityWrap`, `deltaMush`, nCloth/Nucleus, geodesic voxel
  bind, `poseInterpolator`; SideFX Houdini: Vellum cloth; Epic: Chaos Cloth; Unity: Cloth; Qualoth y
  Marvelous Designer.
- **Correctivos/RBF** — SHAPES (Brave Rabbit); RBF de mGear; paper *Pose Space Deformation* (Lewis,
  Cordner, Fong, 2000).
- **Wrap/skin open-source** — cvWrap y otros deformers de Chad Vernon (GitHub) — útiles para leer la
  técnica; recuerda que son plugins.
- **CFX/Vellum** — tutoriales de SideFX y charlas de producción sobre Vellum cloth y flujos a Maya.
- **Tiempo real** — docs y charlas de Chaos Cloth (Epic) y de wrinkle/tension maps.
- **ML** — docs de Maya ML Deformer y de Chaos ML Deformer; papers de deep/neural cloth wrinkles.

Cuando recomiendes, cita el recurso **concreto** que aplica al caso, no la lista entera.
