# Cómo elegir un método para riggear ropa

Esta guía te lleva del *"tengo esta prenda"* al *"usa esto"*. Léela al empezar cada encargo. La idea
es encuadrar el caso con pocas preguntas y luego usar el árbol de decisión para acotar familias del
catálogo (`metodos.md`).

## 1. Preguntas de encuadre

Pregunta solo lo que el usuario **no** haya dicho ya. Con estas variables tienes casi siempre
suficiente para recomendar:

| Variable | Por qué decide el método |
|---|---|
| **Tipo de prenda** | *Ajustada* (camiseta, leggings, guante) casi solo necesita seguir el cuerpo → skin/wrap + correctivos. *Suelta* (falda, vestido, capa, túnica, manga ancha) tiene volumen propio y secundario → pide rig mecánico o sim. |
| **Destino** | *Cine/offline*: puedes gastar en sim y correctivos. *Tiempo real/juego*: presupuesto de huesos/rendimiento; se tira de bone-cloth + wrinkle maps o cloth del engine. |
| **Qué falla hoy** | Cada síntoma apunta a una familia distinta (ver §3). "No es preciso" es ambiguo: hay que concretarlo. |
| **Control art-directable** | ¿El animador necesita posar la tela a mano (control total) o puede delegar a la física (menos control, más realismo)? La sim quita control; el rig lo da. |
| **Presupuesto de tiempo** | Correctivos y sim cuestan horas de autoría/cálculo. Un buen rig mecánico es más barato de iterar. |
| **DCC / dónde vive** | Maya (su autorig) por defecto; Houdini (Vellum) para CFX; engine (Unreal/Unity) si va a juego. Condiciona qué herramientas hay. |

**Concretar "no es preciso".** El copy skin weights falla de formas distintas; haz que el usuario (o
tú, mirando el caso) señale cuál:

- **Interpenetra** — la prenda atraviesa el cuerpo (rodilla, muslo, brazo). → contacto/colisión.
- **Sigue rígida** — se mueve *exactamente* como el cuerpo, sin vida propia. → secundario (dinámica/rig).
- **No arruga** — superficie lisa donde debería plegarse (codo, cadera, tela suelta). → correctivos/sim.
- **No desliza** — la tela debería resbalar sobre el cuerpo y en vez de eso está "pegada". → wrap/sim.
- **Estira/pincha** — el peso mal interpolado da estirones en costuras. → refinar skinning (ngSkin/Delta Mush).

## 2. Los ejes de comparación

Cuando compares métodos, hazlo siempre sobre estos ejes (son las columnas del catálogo):

- **Precisión** (baja/media/alta): cuán realista es el resultado (contacto, arrugas, deslizamiento).
- **Secundario** (ninguno/aproximado/simulado): si la tela tiene movimiento propio y de qué calidad.
- **Art-directable**: cuánto puede dirigir el animador el resultado a mano.
- **Tiempo real**: si sirve para un engine con presupuesto de rendimiento.
- **Coste**: tiempo de autoría + cálculo + dificultad de iterar.

**La precisión se sube por escalones, no de golpe.** El copy skin weights es el escalón 0. Cada
familia añade precisión a cambio de coste o de control. Recomienda el escalón más bajo que resuelve
el síntoma concreto, no el más alto.

## 3. Árbol de decisión (síntoma → familia candidata)

```
¿La prenda es AJUSTADA al cuerpo (sigue la piel)?
├── Sí → base = SKINNING refinado (Delta Mush / ngSkinTools) o WRAP sobre el cuerpo.
│        ¿Faltan arrugas en poses concretas (codo, cadera)?  → añade CORRECTIVOS PSD/RBF.
│        ¿Va a juego?                                          → wrinkle/normal maps por tensión.
│
└── No, es SUELTA (falda, vestido, capa, manga ancha):
     ¿Necesitas control TOTAL del animador y iterar rápido?
     ├── Sí → RIG MECÁNICO de joints (cadenas + ribbons) con COLISIÓN por distancia (tu auto_collision),
     │        + overlap/jiggle procedimental para el secundario aproximado.
     └── No / quieres realismo de contacto y pliegues:
          ¿Cine/offline?
          ├── Sí → SIMULACIÓN (nCloth/Qualoth en Maya, o Vellum en Houdini, o Marvelous).
          │        ¿Necesitas volver a un asset controlable? → FLUJO SIM→RIG (bake a Alembic /
          │        transferir a blendshape / esculpir correctivos desde la sim).
          └── No (tiempo real/juego) → CLOTH DEL ENGINE (Chaos Cloth / Unity Cloth) o
                   BONE-CLOTH + ML DEFORMER entrenado con sims.
```

Casi siempre la respuesta buena es una **pila de capas**, no un método único:

- **Ajustada, cine**: skin (Delta Mush) → wrap al cuerpo → correctivos PSD en las poses malas.
- **Ajustada, juego**: skin limpio → wrinkle maps por tensión → (opcional) huesos de arruga.
- **Suelta, cine, control**: rig de joints/ribbons + colisión → capa de sim solo para el secundario
  fino, cacheada y mezclada por regiones.
- **Suelta, cine, realismo**: sim (Vellum/nCloth) → bake → correctivos para pulir contactos.
- **Suelta, juego**: bone-cloth + colisión del engine, o ML deformer que aproxima una sim offline.

## 4. Errores comunes al recomendar

- **Saltar a la sim por defecto.** La sim es cara, poco interactiva y difícil de dirigir. Si el
  problema es interpenetración puntual, un wrap o unos correctivos son mejores.
- **Ignorar el control del animador.** Un rig "perfecto" que el animador no puede posar es inútil en
  muchos pipelines de personaje. Pregunta cuánto control hace falta.
- **No cerrar el bucle sim→asset.** Una sim que no vuelve a un asset controlable (cache/blendshape)
  rompe el pipeline de animación. Si propones sim, propón cómo se reintegra.
- **Recomendar en el vacío.** Conecta siempre con lo que el usuario ya tiene (ribbons de Boor,
  `auto_collision.py`, AdonisFX, skin manager) y con su DCC real.
