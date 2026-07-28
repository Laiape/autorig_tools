# Cómo se riggea la ropa en un estudio profesional

Esta referencia da el marco de **producción** que usa un estudio (cine/VFX/animación y juegos) para
resolver la ropa. La idea no es "qué técnica mola" sino **por qué se elige una técnica y no otra**
dentro de un pipeline con roles, plazos y entregables. Léela para que cada recomendación tenga
sentido de producción, no solo técnico.

## 1. Dónde vive la ropa en el pipeline

La deformación de una prenda casi nunca la resuelve una sola persona ni una sola etapa. En un
estudio se reparte en capas con **dueño claro**:

```
Modelado ─► Rigging (TD) ─► Skinning ─► CFX / Character FX ─► Tech-Anim (por plano) ─► Render
             │  deformación    │ pesos      │ simulación         │ arreglos de contacto
             │  base + controles          (secundario, arrugas)  (interpenetración, poses)
```

- **Rigging TD** construye la **deformación base** y los controles: lo que hace que la prenda siga
  al cuerpo de forma sólida y *art-directable*. Es tu terreno principal.
- **CFX / Character FX TD** añade el **secundario y las arrugas** con simulación cuando la calidad lo
  pide (personaje hero, primer plano).
- **Tech-Anim** arregla lo que falla **por plano** (una rodilla que asoma en una pose concreta).

**Principio clave**: separar *deformación base* (rig, barata e interactiva) de *refinamiento* (sim/
correctivos, caros) de *arreglo de plano* (tech-anim). Cada capa tiene un coste y un dueño distintos.
Elegir método = decidir **qué capa aporta la precisión que falta** sin encarecer las demás.

## 2. Cine/VFX vs Juegos: dos mundos, dos criterios

El mismo problema se resuelve distinto según el destino, porque cambian las restricciones:

| | Cine / VFX / anim offline | Juegos / tiempo real |
|---|---|---|
| Restricción dura | Calidad de imagen; el tiempo de cálculo se tolera | Presupuesto de rendimiento (huesos, drawcalls, ms/frame) |
| Método típico prenda suelta | Simulación (nCloth/Qualoth/Vellum/Marvelous) + cache | Bone-cloth + colisión del engine, o cloth del engine (Chaos/Unity) |
| Método típico prenda ajustada | Skin + wrap + correctivos PSD | Skin limpio + wrinkle/normal maps por tensión |
| Secundario | Simulado | Aproximado (dinámica de huesos, ML deformer) |
| Control del animador | Se recupera cacheando la sim a un asset | Se prioriza; la física es acotada |

Cuando recomiendes, **fija primero el destino**: es lo que más recorta el abanico.

## 3. Art-direction vs simulación (la tensión central)

La decisión más importante y más olvidada: **¿quién manda sobre la forma de la tela, el animador o la
física?**

- La **simulación** da realismo de contacto y pliegues, pero **quita control**: el animador no puede
  "poner" la tela donde el plano la necesita sin luchar contra el solver. Es cara de dirigir.
- El **rig** (joints, ribbons, correctivos) da **control total** y es interactivo, pero la precisión
  de arrugas y contacto tiene techo.

En producción se decide por el tipo de plano:
- **Hero, primer plano, tela protagonista** → merece sim (o sim + correctivos).
- **Personaje de acción, muchos planos, tela secundaria** → rig art-directable; la sim molesta más
  que ayuda.
- **Multitud / fondo** → lo más barato que aguante la distancia de cámara.

Un buen rig mecánico bien resuelto **muchas veces gana** a una sim mal dirigida. No vendas la sim por
defecto.

## 4. El bucle que no se puede romper: sim → asset controlable

Si entra simulación, en un estudio **siempre** se cierra el círculo para no romper el pipeline de
animación:

- **Cache a Alembic** (`.abc`) del resultado de sim, que reemplaza la malla en el plano.
- o **transferir la sim a un deformador controlable**: hornear a blendshapes por frame, o esculpir
  **correctivos PSD** a partir de poses simuladas (la sim como *referencia*, no como entrega final).
- o **ML Deformer**: usar muchas sims como datos de entrenamiento para un deformador que aproxima la
  sim en tiempo interactivo.

Una sim que no vuelve a un asset dirigible es un callejón sin salida en un pipeline de personaje. Si
propones sim, propón **cómo se reintegra**.

## 5. Entregables, resoluciones y LOD

Un "rig de ropa" profesional no es solo la deformación: es un **paquete** con contrato claro.

- **Controles** con nomenclatura y jerarquía coherentes con el resto del rig (en tu caso: `_ctl`,
  `_grp`, `_jnt`, prefijos `C_/L_/R_`, grupos de guías). La ropa no debe romper el estándar del rig.
- **Malla de simulación / proxy** de baja resolución para simular rápido, y **malla de render** de
  alta a la que se transfiere el resultado (wrap/UV transfer). Nunca se simula la de render.
- **Setup de cache** documentado (qué se cachea, a qué frame-range, dónde).
- **Puntos de colisión** definidos (colliders del cuerpo) y su presupuesto.
- **LODs** si va a juego: versión con menos huesos/arrugas para lejos.

## 6. QC: cómo se valida una prenda antes de entregarla

Un estudio no entrega "parece que va bien". Se pasa por poses de estrés y checks:

- **Poses de estrés**: sentadilla, brazos arriba, torsión de torso, rodilla al pecho, andar. Ahí
  aparece la interpenetración y el estiramiento feo.
- **Interpenetración**: la prenda no debe atravesar el cuerpo en ninguna pose del rango.
- **Preservación de volumen**: sin colapsos ni pérdida de grosor en codos, rodillas, cadera.
- **Deslizamiento coherente**: la tela resbala donde debe y se ancla donde debe (cinturón, costuras).
- **Turntable / playblast** de revisión para aprobación (review de supervisor).
- **Continuidad con el estándar del rig**: naming, límites de influencias, normalización de pesos,
  sin dobles transforms (tu `auto_collision` ya usa grupos offset por esto).

## 7. Reusabilidad: que no sea un one-off

Lo que separa un TD de estudio de un artista suelto es que su solución es **reutilizable**. Un setup
de falda debería poder aplicarse a otro personaje cambiando parámetros, no rehaciéndolo. Piensa en:

- **Modularidad** coherente con tu autorig (un "clothing module" que encaje como los demás módulos).
- **Datos fuera del código**: colliders, pesos y parámetros guardados/versionados (como ya haces con
  `SkinManager` y `.skc`), no hardcodeados.
- **Parametrización**: nº de joints, radio de colisión, rigidez, como atributos, no valores fijos.

## 8. Cómo usar este marco al recomendar

Antes de proponer un método, sitúalo en este marco y dilo explícitamente:

1. **¿Qué capa** falla y hay que reforzar (base / refinamiento / plano)?
2. **¿Qué destino** (cine vs juego) fija las restricciones?
3. **¿Cuánto control** necesita el animador frente a la física?
4. **¿Se cierra el círculo** hasta un asset controlable si entra sim?
5. **¿Encaja** en el estándar y la modularidad del rig del usuario, o es un one-off?

Si la recomendación responde a esas cinco, es una decisión "de estudio" y no un capricho técnico.
