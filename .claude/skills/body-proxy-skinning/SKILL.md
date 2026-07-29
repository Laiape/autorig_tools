---
name: body-proxy-skinning
description: 'Ayuda a skinnear el CUERPO de un personaje de forma eficiente y que quede bien, con enfoque de PROXY SKINNING (skinnear/pintar un proxy low-res y transferir a la malla de alta) y refinado. Resuelve la queja de que el "assign closest joint" de ngSkinTools no es preciso: el binding por joint/distancia más cercana CRUZA influencias entre partes anatómicas próximas (muslo interior con la otra pierna, axila con el pecho, entre dedos), y esta skill enseña los métodos volumétricos que NO lo hacen (Geodesic Voxel Binding, heat map, BBW) más el flujo proxy→alta, el refinado (Delta Mush, Direct Delta Mush, ngSkinTools por capas) y cómo dejarlo eficiente (bake a skin lineal con dm2skin/bakeDeformer) y con correctivos en las zonas problema. Aterrizada en el pipeline del usuario (autorig en Maya + Python, ngSkinTools2, copySkinWeights por UV/label, skincluster_surface, SkinManager, AdonisFX, Delta Mush) e implementada en el botón Proxy Skinning (tools/proxy_skinning.py). Úsala siempre que el usuario quiera skinnear el cuerpo, montar o mejorar un proxy skinning, arreglar un bind impreciso, elegir un binding que no cruce influencias, transferir pesos de un proxy a la alta, refinar un skin con Delta Mush, o dejar un skin eficiente y limpio. Dispara ante frases como "proxy skinning del cuerpo", "skinnear el cuerpo", "el closest joint no es preciso / me cruza influencias", "cómo hago un buen skin eficiente", "binding que no cruce", "transferir pesos del proxy a la alta", "refinar el skin con delta mush", "assign closest joint no me vale".'
---

# Body Proxy Skinning — skinnear el cuerpo eficiente y que quede bien

Ayuda al usuario a **skinnear el cuerpo con criterio**, con enfoque de **proxy skinning** (trabajar
el skin en un proxy low-res y transferirlo a la malla de alta) y a **refinarlo** bien. El usuario es
Rigging/Creature TD: hoy inicializa a veces con **"assign closest joint" de ngSkinTools** y refina
con **Delta Mush**. Su problema concreto: el closest-joint **no es preciso** porque **cruza
influencias entre partes anatómicas próximas** (el muslo interior recoge la otra pierna, la axila el
pecho, entre los dedos…). Esta skill enseña a arrancar de un **binding volumétrico que no cruza**, a
montar el **flujo proxy→alta**, a **refinar** (Delta Mush y más) y a dejarlo **eficiente y limpio**.

El objetivo **no** es soltar una lista de nombres, sino **decidir con criterio de estudio**:

1. **Encuadrar el caso** (qué malla, qué destino, dónde falla el bind actual, hay proxy o no).
2. **Elegir el binding** que no cruce influencias (el núcleo de la queja).
3. **Montar el flujo proxy** cuando aporta (iteración rápida, robustez ante cambios de topología).
4. **Refinar** (Delta Mush / ngSkin por capas) y, si hace falta, **bake a skin lineal eficiente** +
   **correctivos** en las zonas que un skin lineal no alcanza.

## Herramientas y red

Combina un **catálogo de referencia** curado con **búsqueda web en vivo** para profundizar.

- Usa **`web_search` y `web_fetch`** para investigar. **No uses Python con `requests`**: el proxy de
  red del entorno solo permite unos pocos dominios y lo bloqueará.
- **GitHub sí** está permitido (`github.com`, `raw.githubusercontent.com`): los repos de tools de
  skinning (cvWrap, dm2skin, ngSkinTools) **se pueden clonar con `git clone`** para leerlos.
- El código del usuario está en `scripts/`: léelo para aterrizar (ngSkinTools2 en
  `skin_manager_ng.py`, `auto_skin_transfer.py`, `skincluster_surface.py`, `SkinManager`).

## Ficheros de referencia

- **`references/metodos.md`** — el **catálogo** (binding, flujo proxy, transferencia a alta,
  refinado, bake eficiente, correctivos): qué es, cómo funciona, calidad, eficiencia, si cruza
  influencias, límites, cuándo usarlo y encaje en su pipeline, con tabla-resumen, **receta
  recomendada end-to-end** y recursos. **Es el backbone.** Empieza por la tabla-resumen y baja solo
  a la(s) familia(s) que aplican; consúltalo antes de recomendar nada.
- **`references/como-elegir.md`** — árbol de decisión y preguntas de encuadre (¿proxy sí/no?, ¿qué
  binding?, ¿qué transferencia?, ¿qué refinado?, ¿bake?). Léelo al principio de cada encargo.
- **`references/investigar.md`** — cómo profundizar en vivo (plantillas de búsqueda, dónde vive la
  info buena, cómo leer una tool ajena). Léelo cuando el catálogo no cubra el caso.
- **`references/kangaroo-builder.md`** — las tools de skinning de **Kangaroo Builder** (el toolkit
  que el usuario ya usa y cuyo copy skin "funciona bien"): Copy/Paste con soft selection entre
  mallas, Flood/Distribute, Bind to Closest & Expand, Change Model/Landmark Warp, y cómo se
  complementan con las recomendaciones de esta skill. Léelo cuando el usuario mencione Kangaroo o
  haya que comparar/elegir entre sus tools y las del repo.

## Flujo de trabajo

1. **Encuadra el caso (una pasada corta).** Antes de recomendar, ten claro —sin interrogar de más—
   (detalle en `como-elegir.md`):
   - **Qué malla** y densidad; si hay ya una **malla proxy** o hay que crearla.
   - **Destino**: cine (calidad) vs juego/tiempo real (skin lineal, pocas influencias).
   - **Dónde falla el bind hoy**: qué zonas cruzan influencias, dónde colapsa el volumen.
   - **Punto de partida**: closest-joint + Delta Mush (lo del usuario) — concreta qué no le gusta.

2. **Consulta el catálogo** (`references/metodos.md`) y quédate con lo pertinente. El eje central es:
   **arrancar de un binding volumétrico que no cruce** (Geodesic Voxel Binding), no del closest-joint.

3. **Investiga en vivo si hace falta** (`references/investigar.md`): confirma flags/versión de un
   nodo o comando, o busca la tool/tutorial concretos. Clona y lee repos de GitHub cuando aporten.

4. **Recomienda una receta, no un método suelto.** El patrón de estudio es una **cadena**:
   binding volumétrico → (proxy) → transferir a alta → **afinar con ngSkin por capas** → Delta Mush
   → (bake a skin lineal) → correctivos en zonas problema. Di **por qué** cada paso y mapea a lo que
   ya tiene (ngSkinTools2, `copySkinWeights -uvSpace -label`, `skincluster_surface`, `SkinManager`,
   AdonisFX). **Ojo: `auto_skin_transfer` está roto — no lo recomiendes;** el transfer por defecto es
   `copySkinWeights -uvSpace -label` (lo que usa el botón *Proxy Skinning*, `tools/proxy_skinning.py`).

5. **Si lo pide, aterriza en pasos.** Plan de implementación o snippet en el estilo del repo
   (`maya.cmds`/OpenMaya, rig por matrices, lectura por API). **No rehagas su pipeline entero**:
   propón el trozo que sube el nivel.

## Cómo presentar el resultado

**1) Diagnóstico** — 2–4 líneas: qué malla/destino y por qué el bind actual se queda corto (el
"no es preciso" concreto: qué zonas cruzan influencias).

**2) Métodos candidatos** — conciso pero con sustancia:

```
MÉTODO — familia
Qué es y cómo funciona: <1–3 líneas>
Calidad: <baja/media/alta> · Eficiencia: <baja/media/alta> · ¿Cruza influencias?: <sí/no/parcial>
Frente a closest-joint: <qué gana, qué cuesta>
Límite real: <dónde deja de funcionar>
Encaje en tu pipeline: <ngSkin / copySkinWeights -uvSpace -label / skincluster_surface / Delta Mush / bake>
Para profundizar: <tutorial/doc/repo/tool concretos>
```

**3) Recomendación (receta)** — la cadena que usarías para *este* caso y por qué, del paso más
simple que resuelve el problema hacia arriba.

**4) Siguiente paso** (si aplica) — plan de implementación o prueba de concepto accionable.

## Reglas importantes

- **Ataca la causa, no el síntoma.** Si el bind cruza influencias, el arreglo es un **binding
  volumétrico** (geodesic voxel) o una transferencia por UV/label, no pintar a mano ni tapar con
  Delta Mush. Delta Mush **suaviza**, no arregla un bind que asigna al joint equivocado.
- **Recomienda la cadena más simple que resuelve el problema.** No lleves a correctivos PSD si un
  buen bind + ngSkin + Delta Mush ya deja el cuerpo bien. La calidad se sube por escalones.
- **Aterriza en su pipeline.** Conecta cada recomendación con lo que ya tiene (`skin_manager_ng` con
  ngSkinTools2, `copySkinWeights -uvSpace -label` para transferir, `skincluster_surface`, `SkinManager`
  `.skc`, Delta Mush, el botón *Proxy Skinning* → `tools/proxy_skinning.py`) y con el rig por matrices.
  **`auto_skin_transfer` está roto: no lo propongas.** Ojo: `proxy_locator.py` es un **locator visual** de
  región de piel, no la tool de proxy skinning; no lo presentes como tal.
- **Honestidad técnica.** Di los trade-offs: más calidad suele costar autoría o evaluación. Si el
  bind volumétrico + Delta Mush ya basta, dilo en vez de sobredimensionar.
- **No inventes.** Si citas doc, tutorial, paper o tool, que exista; verifica flags/versión con
  `web_search`/`web_fetch` en vez de afirmar. Distingue lo que sabes de lo que infieres.
- **Código ajeno**: leer, entender y explicar tools de otros está bien; respeta su licencia y no
  copies archivos enteros al repo del usuario. Fragmentos cortos para ilustrar una técnica.
- **El criterio es el producto.** Lo que pidió el usuario es *saber cómo skinnear el cuerpo bien y
  eficiente y por qué*, no una enciclopedia. Prioriza la decisión bien argumentada.
