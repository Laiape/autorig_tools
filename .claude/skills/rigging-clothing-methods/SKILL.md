---
name: rigging-clothing-methods
description: 'Investiga y compara métodos para riggear ropa (prendas, tela, telas: faldas, vestidos, capas, túnicas, mangas, capuchas) y recomienda el más adecuado por precisión, control y coste, aterrizado en el pipeline del usuario (autorig modular en Maya + Python, ribbons de Boor, AdonisFX, colisión por distancia, y Vellum/CFX en Houdini). Va más allá del simple "copy skin weights / transferencia de pesos": cubre wrap/proximity, rigs mecánicos de joints con colisión, correctivos PSD/RBF, simulación (nCloth, Qualoth, Marvelous, Vellum, Ziva), flujos sim→rig, tela en tiempo real/juegos y deformadores por ML. Úsala siempre que el usuario quiera saber CÓMO riggear una prenda mejor, encontrar alternativas más precisas al copy skin, comparar técnicas de deformación de tela, o decidir qué método aplicar a un personaje/plano concreto. Dispara ante frases como "cómo riggeo esta falda/vestido/capa", "el copy skin weights no me convence / no queda preciso", "qué métodos hay para riggear ropa", "cómo hago que la tela se mueva/arrugue mejor", "alternativas a la transferencia de pesos", "sim vs rig para esta prenda" o cuando el usuario esté atascado con una prenda que interpenetra, sigue rígida al cuerpo o no arruga.'
---

# Rigging Clothing Methods — investigar y elegir cómo riggear ropa

Ayuda al usuario a **elegir con criterio cómo riggear una prenda**. El usuario es Rigging/Creature TD:
hoy resuelve la ropa sobre todo con **copy skin weights** (transferencia de pesos del cuerpo a la
prenda) y, para faldas/vestidos, con **cadenas de joints + colisión por distancia** (su
`scripts/tools/auto_collision.py`). Le molesta que el copy skin **"no es preciso"**: la prenda sigue
rígida al cuerpo, interpenetra y no arruga ni desliza. Esta skill existe para enseñarle el **abanico
completo de métodos** —muchos más precisos— y ayudarle a decidir cuál usar en cada caso.

El objetivo **no** es soltar una lista de nombres, sino **pensar como se piensa en un estudio
profesional** y trasladarlo a su rig:

1. **Encuadrar el caso concreto** (qué prenda, qué personaje, cine vs tiempo real, qué falla ahora) y
   situarlo en el pipeline de producción (deformación base → refinamiento → arreglo de plano).
2. **Explicar los métodos relevantes** con honestidad sobre precisión / control / coste.
3. **Recomendar** un método o —lo más habitual— una **pila de capas** (p. ej. skin base + wrap +
   correctivos, o sim + bake a rig), aterrizada en su pipeline de Maya/Houdini y en el estándar de su
   rig (naming, modularidad, datos versionados).
4. Si lo pide, dar un **plan de implementación** o prueba de concepto paso a paso.

Cada recomendación debe ser una **decisión de estudio**, no un capricho técnico: responde a qué capa
falla, qué destino fija las restricciones, cuánto control necesita el animador, cómo se cierra el
círculo si entra simulación, y si encaja en la modularidad del rig. Ese marco está en
`references/estudio-profesional.md`.

## Herramientas y red

Esta skill investiga combinando un **catálogo de referencia** ya curado con **búsqueda web en vivo**
para profundizar y encontrar tutoriales/tools actuales.

- Usa las herramientas nativas **`web_search` y `web_fetch`** para investigar en la web. **No uses
  scripts de Python con `requests`**: el proxy del entorno solo permite unos pocos dominios y los
  bloqueará.
- **Excepción para código**: el entorno **sí** permite `github.com`, `codeload.github.com` y
  `raw.githubusercontent.com`, así que los repos de GitHub (tools de rigging, nodos, ejemplos) **se
  pueden clonar con `git clone`** por bash para leerlos a fondo.
- El código del propio usuario está en este repo (`scripts/`): puedes leerlo para aterrizar las
  recomendaciones en lo que ya tiene montado (ribbons, colisión, AdonisFX, skin manager).

## Ficheros de referencia

Léelos según los necesites — no hace falta cargarlos todos de golpe:

- **`references/metodos.md`** — el **catálogo** de métodos por familia (qué es, cómo funciona,
  precisión, secundario, límites, cuándo usarlo y encaje en su pipeline), con tabla-resumen y
  recursos. **Es el backbone de la skill: léelo antes de recomendar nada.**
- **`references/como-elegir.md`** — árbol de decisión y preguntas de encuadre para pasar del "qué
  prenda tienes" al "usa esto". Léelo al principio de cada encargo.
- **`references/estudio-profesional.md`** — el marco de **producción**: cómo reparte un estudio la
  ropa en capas (rig / CFX / tech-anim), cine vs juego, art-direction vs sim, el bucle sim→asset,
  entregables/LOD, QC y reusabilidad. Léelo para que la recomendación tenga sentido de producción.
- **`references/investigar.md`** — cómo profundizar en vivo: plantillas de búsqueda, dónde vive la
  información buena (docs, charlas, papers, repos) y cómo leer una tool ajena. Léelo cuando el
  catálogo no cubra el caso o el usuario quiera lo último.

## Flujo de trabajo

1. **Encuadra el caso (una pasada corta).** Antes de recomendar, ten claro —preguntando solo lo
   imprescindible que el usuario no haya dicho ya— estas variables (detalle en `como-elegir.md`):
   - **Prenda**: ajustada al cuerpo (camiseta, leggings) vs suelta (falda, vestido, capa, túnica).
   - **Destino**: cine/offline (calidad máxima) vs tiempo real/juego (presupuesto de rendimiento).
   - **Qué falla hoy**: interpenetra, sigue rígida, no arruga, no tiene secundario, no desliza…
   - **Cuánto control art-directable** necesita el animador vs cuánto puede delegar a la física.
   - **DCC**: por defecto Maya (su autorig), pero puede pasar por Houdini (Vellum) o un engine.

   Si el usuario ya acotó el caso, **no interrogues**: tira hacia adelante con su perfil.

2. **Consulta el catálogo** (`references/metodos.md`) y quédate con las 2–4 familias que de verdad
   aplican al caso. No enumeres las ocho; céntrate en lo pertinente.

3. **Investiga en vivo si hace falta** (`references/investigar.md`): para el método candidato, busca
   tutoriales concretos, la charla/paper de referencia, la tool o el nodo que lo implementa, y
   confirma detalles de la versión de la DCC. Clona y lee repos de GitHub cuando aporten.

4. **Compara con honestidad.** Sitúa cada método candidato frente al **punto de partida del usuario
   (copy skin weights)**: qué gana en precisión, qué cuesta (tiempo, interactividad, art-direction),
   y dónde está el límite real. No vendas la sim como panacea ni desprecies un buen rig mecánico.

5. **Recomienda una pila concreta.** Lo normal en producción no es "un método" sino **capas**: una
   base que sigue al cuerpo + una capa que añade precisión (arrugas/secundario) donde importa.
   Propón la pila y di **por qué**, mapeada a lo que ya tiene (ribbons de Boor, `auto_collision`,
   AdonisFX, skin manager, Vellum).

6. **Si lo pide, aterriza en pasos.** Da un plan de implementación o prueba de concepto: qué nodos/
   deformadores/tools, en qué orden, qué comprobar, y cómo volver a un asset controlable (p. ej.
   bake de sim a Alembic/blendshape). Cuando sea Maya + Python, puedes esbozar el enfoque con
   `maya.cmds`/OpenMaya coherente con el estilo del repo, pero **no rehagas su rig entero**: propón
   el trozo que resuelve el problema.

## Cómo presentar el resultado

Estructura la respuesta así (adáptala al tamaño del encargo):

**1) Diagnóstico del caso** — en 2–4 líneas: qué prenda, qué destino, y por qué el método actual se
queda corto (el "no es preciso" concreto: interpenetración / rigidez / falta de arrugas…).

**2) Métodos candidatos** — para cada uno, conciso pero con sustancia:

```
MÉTODO — familia
Qué es y cómo funciona: <1–3 líneas>
Precisión: <baja/media/alta> · Secundario: <ninguno/aproximado/simulado> · Coste: <bajo/medio/alto>
Frente a copy skin: <qué gana, qué cuesta>
Límite real: <dónde deja de funcionar>
Encaje en tu pipeline: <cómo se monta con Maya/ribbons/AdonisFX/colisión/Vellum>
Para profundizar: <tutorial/charla/paper/repo/tool concretos>
```

**3) Recomendación** — la pila que usarías para *este* caso y por qué, del método más simple que
resuelve el problema hacia arriba. Si hay una alternativa razonable (p. ej. rig mecánico vs sim),
di cuándo elegirías cada una.

**4) Siguiente paso** (si aplica) — plan de implementación o prueba de concepto accionable.

## Reglas importantes

- **Honestidad técnica por encima de todo.** Di los trade-offs reales. Más preciso casi siempre
  significa más caro o menos interactivo; no lo escondas. Si el copy skin es *suficiente* para el
  caso, dilo en vez de sobredimensionar.
- **Recomienda el método más simple que resuelve el problema.** No lleves a una sim de Vellum si un
  proximityWrap + un par de correctivos ya arreglan la interpenetración. La precisión se sube por
  escalones, no de golpe.
- **Aterriza en su pipeline, no en el vacío.** Conecta cada recomendación con lo que ya tiene montado
  en `scripts/` (ribbons de Boor, `auto_collision.py`, AdonisFX/`copyWeightsAdonis`, skin manager) y
  con las DCC que usa (Maya principal, Houdini/Vellum para CFX).
- **No inventes.** Si citas un tutorial, charla, paper o tool, que exista de verdad; si no estás
  seguro de una URL o un dato de versión, dilo o verifícalo con `web_search`/`web_fetch` en vez de
  afirmarlo. Distingue lo que sabes de lo que infieres.
- **Código ajeno**: leer, entender y explicar tools de otros está bien; respeta su licencia y no
  copies archivos enteros al repo del usuario ni los presentes como suyos. Muestra fragmentos cortos
  para ilustrar una técnica.
- **El criterio es el producto.** Lo que pidió el usuario es *saber qué método usar y por qué*, no
  una enciclopedia. Prioriza la decisión bien argumentada sobre la exhaustividad.
