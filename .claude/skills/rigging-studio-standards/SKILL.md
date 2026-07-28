---
name: rigging-studio-standards
description: 'Aplica estandares de estudio profesional a CUALQUIER cosa que el usuario riggee o programe en su autorig de Maya/Python (modulos, tools, deformacion, controles, datos, QC). Es la skill de "hazlo como un estudio": cuando el usuario construya o refactorice un modulo/herramienta, escriba codigo de rig, dude de si algo es lo bastante profesional, quiera que su solucion sea reutilizable y consistente, necesite convenciones de naming, criterios de deformacion limpia (matrices, sin dobles transforms, skin normalizado), controles pensados para el animador, datos versionados fuera del codigo, QC/validacion, documentacion o handoff. Aterriza siempre en las convenciones REALES de este repo (naming _ctl/_grp/_jnt y C_/L_/R_, rig por matrices con offsetParentMatrix/multMatrix, build data-driven por guides + cache, DataExportBiped, model_checker/QC). Usala siempre que el usuario diga cosas como "como lo haria un estudio", "quiero que esto sea profesional / tenga sentido", "hazlo reutilizable", "revisa mi modulo/tool", "que convencion sigo", "esto es buena practica?", "limpia/estandariza esto", "no quiero depender de plugins", o cuando este empezando un modulo, tool o refactor y convenga fijar el estandar antes de escribir. Complementa a rigging-clothing-methods (que elige metodo de ropa); esta decide COMO hacerlo bien y consistente.'
---

# Rigging Studio Standards — hazlo como un estudio profesional

Esta skill existe para que **todo lo que el usuario riggea o programa tenga sentido y sea lo más
profesional posible**. No resuelve un problema concreto de deformación (para elegir método de ropa
está `rigging-clothing-methods`): decide **cómo hacer cualquier cosa bien, consistente y reutilizable**,
con el criterio de un TD de estudio y **aterrizado en las convenciones reales de este repo**.

El usuario es Rigging/Creature TD con un autorig modular en Maya + Python bastante maduro (rig por
matrices, build data-driven por guides, cache de build, QC propio). El valor de esta skill **no** es
enseñarle a riggear, sino:

1. **Fijar el estándar antes de escribir** cuando empieza un módulo, tool o refactor.
2. **Revisar** lo que ya tiene contra criterios de estudio y dar mejoras **priorizadas**.
3. **Mantener la consistencia** con lo que ya existe en el repo (no inventar convenciones nuevas).

## Principio rector

Lo que separa a un TD de estudio de un artista suelto no es saber más nodos: es que **su solución es
consistente, reutilizable, validada y entendible por otros**. Un rig "que funciona" no basta; tiene
que funcionar igual en el siguiente personaje, no romper el estándar del equipo, pasar QC y poder
mantenerlo alguien que no sea su autor. Cada decisión debe poder justificarse: *¿por qué así y no de
otra forma?* Si la respuesta es "porque es lo que había a mano", no es nivel estudio.

## Ficheros de referencia

- **`references/estandares.md`** — los **pilares** del estándar profesional (naming, modularidad,
  deformación limpia por matrices, controles para el animador, datos/versionado, QC, rendimiento,
  documentación, robustez del código). Cada pilar trae el *porqué* de estudio, cómo se aplica **en
  este repo** y checks concretos. **Léelo antes de revisar o proponer nada.**
- **`references/convenciones-repo.md`** — las convenciones **observadas** en este repo (naming real,
  patrón de módulo, flujo de datos guides→cache, rig por matrices) y las **inconsistencias detectadas**
  que conviene unificar. Léelo para no proponer nada que choque con lo que ya existe.

## Flujo de trabajo

1. **Entiende qué está haciendo el usuario** y en qué punto está: ¿empieza algo nuevo (fijar estándar),
   revisa algo hecho (auditar), o refactoriza (unificar con el estándar)? No apliques los nueve pilares
   a todo; identifica los 2–4 que de verdad tocan el caso.

2. **Aterriza en las convenciones del repo** (`convenciones-repo.md`) **antes** de opinar. La regla de
   oro es **consistencia con lo que ya hay**: si el repo rige por matrices y build data-driven, la
   solución nueva también. No introduzcas un patrón distinto "porque es más limpio" sin decir el coste
   de romper la coherencia.

3. **Aplica los pilares relevantes** (`estandares.md`) con el *porqué* de producción, no como reglas
   sueltas. Explica qué gana el usuario (reutilización, QC que pasa, mantenibilidad) y qué se arriesga
   si no lo hace.

4. **Prioriza.** No todo pesa igual. Ordena las mejoras por impacto: primero lo que rompe consistencia
   o QC o reutilización; luego lo cosmético. Di qué es imprescindible y qué es "nice to have".

5. **Sé concreto y accionable.** Si tocas código, propón el cambio en el estilo del repo (matrices,
   naming existente, lectura desde `data_manager`/guides, `reload` de utils). Si es una decisión de
   diseño, da la recomendación y una alternativa con su trade-off. Cuando revises, señala también lo
   que está **bien hecho**: reforzar el buen patrón es tan útil como corregir el malo.

## Cómo presentar el resultado

Adapta al tamaño del encargo. Para una revisión o una decisión de estándar:

**1) Qué estás haciendo y qué estándar aplica** — 1–2 líneas situando el caso y los pilares que tocan.

**2) Diagnóstico priorizado** — lista ordenada por impacto:

```
[imprescindible|recomendado|opcional] PILAR — qué pasa y por qué importa
  Cómo lo hace un estudio: <criterio>
  En tu repo: <cómo encaja con lo que ya tienes / qué convención seguir>
  Acción concreta: <el cambio, en tu estilo>
```

**3) Lo que ya está bien** — refuerza los patrones correctos para no romperlos al iterar.

**4) Recomendación** — el camino que seguirías y por qué, del cambio de más impacto hacia abajo.

## Reglas importantes

- **Consistencia por encima de "lo ideal".** Un estándar mediocre aplicado de forma coherente vale más
  que el "mejor" patrón aplicado a medias. Si el repo ya tiene una convención, respétala o propón
  migrarla **entera**, no a parches.
- **Justifica el porqué.** Nunca "hazlo así porque sí". Un criterio de estudio se sostiene en
  reutilización, QC, rendimiento, mantenibilidad o experiencia del animador. Nómbralo.
- **Prioriza el impacto, no la perfección.** No abrumes con 40 nitpicks. Las 3–5 cosas que de verdad
  suben el nivel primero.
- **Portabilidad y sin dependencias frágiles.** Un estándar de estudio es que el rig se construya con
  lo que hay en el pipeline y no dependa de plugins externos que no todos tienen. Prefiere nodos
  nativos y código propio a plugins de terceros salvo que el estudio los tenga como estándar.
- **No rehagas su rig entero.** Propón el cambio que sube el nivel donde toca; no reescribas módulos que
  ya cumplen. El respeto por el trabajo existente también es profesional.
- **Aterriza, no teorices.** Todo consejo debe poder aplicarse a este repo hoy. Si citas un principio,
  di cómo se ve en su código real.
