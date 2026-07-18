# Pilares del estándar profesional de rigging

Nueve pilares que usan los estudios para que un rig sea *nivel producción*. Cada uno trae el **porqué**
(qué gana el estudio), **en tu repo** (cómo se ve aquí) y **checks** concretos. No apliques los nueve a
todo: elige los que tocan el caso.

Orden aproximado de impacto: 1–3 son los que más suben el nivel; 4–9 lo consolidan.

---

## 1. Consistencia y naming

**Por qué**: un nombre es un contrato. En un estudio, mil nodos tienen que decir de un vistazo *lado +
módulo + propósito + tipo*, y las herramientas derivan nombres por patrón. Un naming inconsistente
rompe scripts (un `replace` que falla) y obliga a leer cada nodo para saber qué es. La consistencia es
lo que hace que otro TD pueda tocar tu rig sin miedo.

**En tu repo**: prefijos `C_/L_/R_`, sufijos `_GRP/_JNT/_CTL/_MMT`, nombres derivados por
`replace("_JNT","_CTL")`. Ojo a la mezcla mayúsculas/minúsculas (ver `convenciones-repo.md` §Inconsis.).

**Checks**:
- Un nombre único identifica lado, módulo, propósito y tipo, sin ambigüedad.
- Un **solo** caso de sufijo en todo el repo (elige y migra; no mezcles `_JNT` y `_jnt`).
- Idealmente, un helper central que **construya** nombres (`build_name(side, module, part, kind)`) en
  vez de `replace` disperso, para que el naming sea imposible de romper.

---

## 2. Modularidad y reutilización

**Por qué**: lo que distingue a un TD de estudio es que su solución sirve para el **siguiente**
personaje sin rehacerla. Un one-off es deuda técnica; un módulo parametrizado es un activo. Los
estudios construyen a partir de módulos y datos, no de escenas artesanales.

**En tu repo**: arquitectura por módulos (`*_module.py`), build data-driven por `guides` + `cache`,
utils compartidos. Un buen añadido nuevo (p. ej. un *clothing module*) **encaja como un módulo más**.

**Checks**:
- Lo nuevo, ¿es un módulo/tool coherente con la estructura, o una escena/función suelta?
- ¿Parametrizado (nº de joints, radios, rigidez como argumentos/atributos) o con valores fijos?
- ¿Generaliza a otro personaje cambiando datos, o está atado a un asset concreto?

---

## 3. Deformación limpia (matrices, sin dobles transforms, skin sano)

**Por qué**: la deformación es el producto. Un rig con dobles transforms, canales sucios o skin sin
normalizar da bugs sutiles que aparecen en el peor plano. Lo limpio es lo que aguanta poses de estrés
y lo que se puede depurar.

**En tu repo**: rig por matrices (`offsetParentMatrix`, `multMatrix`/`_MMT`, `worldInverseMatrix`),
grupos offset para no ensuciar canales (patrón de `auto_collision`), ribbons de Boor.

**Checks**:
- **Grupos offset** entre el padre y el nodo movido → nada de valores acumulados en canales que deben
  estar a cero.
- Skin **normalizado**, con `maxInfluences` controlado y sin pesos residuales (tu `SkinManager` ya
  guarda estos ajustes: úsalos como fuente de verdad).
- Matrices frente a constraints cuando aporta (más limpio y rápido); sin `decomposeMatrix` innecesario.
- Sin history sucia ni nodos huérfanos tras el build.

---

## 4. Controles pensados para el animador

**Por qué**: el rig lo usa un animador, no un TD. Un control ilegible, con canales que no deberían
tocarse abiertos o pivotes mal puestos, ralentiza cada plano. En estudio, la ergonomía del control es
parte de la entrega, no un extra.

**Checks**:
- Formas de control legibles y con escala/orientación coherente por zona; color por lado
  (`C_/L_/R_`).
- Canales que no se usan **bloqueados y ocultos**; los que se usan, a valores por defecto limpios
  (0/1), sin transform "colgado".
- Pivotes y ejes correctos; SDK/atributos custom con nombres claros y rangos con sentido.
- Jerarquía de selección predecible (picker coherente — ya tienes `picker.py`).

---

## 5. Datos fuera del código y versionado

**Por qué**: hardcodear posiciones, pesos o rutas hace el rig imposible de mantener y de reusar.
Los estudios separan **datos** (guías, pesos, correctivos, colliders) del **código** que construye, y
lo versionan para poder volver atrás.

**En tu repo**: `guides` (`.guides` versionado), `cache/biped.cache`, `SkinManager` (`.skc` v001…).
Es un patrón ya bueno; extiéndelo a lo nuevo.

**Checks**:
- ¿Lo que cambia entre personajes está en **datos** (JSON/guías/skc) y no en el código?
- **Versionado** con vuelta atrás (como tus `_vNNN`).
- Rutas **portables** (`pathlib`/`os.path`), no separadores de una sola plataforma.
- Nada de nombres de nodo pasados a mano entre módulos: publícalos por `data_manager`.

---

## 6. QC y validación

**Por qué**: un estudio no entrega "parece que va". Se valida contra checks y poses de estrés antes de
pasar el asset a animación. El QC evita que un fallo llegue al plano, donde cuesta 10× arreglarlo.

**En tu repo**: `model_checker.py` (basado en *Modeling QC Standards*). Amplía esa idea al rig.

**Checks**:
- **Poses de estrés** en el rango real (sentadilla, brazos arriba, torsión) para cazar
  interpenetración, pérdida de volumen y estiramientos.
- Checks de escena: sin nodos non-manifold/history/transforms congelados a medias, naming válido,
  pesos normalizados, límites de influencias.
- Un **rebuild limpio** desde guías reproduce el rig sin pasos manuales (si no, no es fiable).
- Turntable/playblast de revisión para aprobación.

---

## 7. Rendimiento y evaluación

**Por qué**: un rig lento mata la productividad del animador y revienta en batch/render. En estudio se
cuida el grafo: menos nodos, evaluables en paralelo, sin recomputar lo mismo.

**En tu repo**: ya piensas en esto (el cache de `guides_manager` evita releer disco de red en cada
build). Lleva esa mentalidad al rig en runtime.

**Checks**:
- Grafo DG lo más ligero posible; evita cadenas de constraints caras si una matriz lo resuelve.
- Compatible con evaluación en paralelo (sin ciclos, sin dependencias raras script-node).
- Cachea cálculos repetidos; no releas datos en bucle.
- Presupuesto de nodos/huesos consciente si el asset va a tiempo real.

---

## 8. Documentación y handoff

**Por qué**: el rig lo mantiene y lo usa gente que no eres tú (o tú dentro de seis meses). Sin docs, un
módulo brillante es una caja negra que nadie se atreve a tocar. La documentación es lo que hace el
trabajo **transferible**, que es la definición de profesional.

**En tu repo**: docstrings en utils/tools (buen punto de partida). Mantén el nivel en lo nuevo.

**Checks**:
- Docstrings que digan **qué hace, argumentos y cómo se usa** (como en `copyWeightsAdonis`).
- Un módulo nuevo explica cómo se construye, qué publica en el cache y qué entrega.
- Notas de decisiones no obvias (por qué matrices y no constraint, por qué este orden).
- Para el animador: qué controla cada control y qué **no** tocar.

---

## 9. Robustez y portabilidad del código

**Por qué**: un tool que depende del estado global, de la selección o de un plugin que no todos tienen,
falla en producción en el peor momento. La robustez es lo que hace que el pipeline no se caiga con un
personaje distinto o una máquina distinta.

**En tu repo**: fallback `PySide2`/`PySide6` (bien). Aplica la misma prudencia al resto.

**Checks**:
- **Idempotencia**: correrlo dos veces no duplica nodos ni rompe; un rebuild parte de limpio.
- No depender de la **selección** ni de estado implícito; recibe lo que necesita por argumentos.
- Manejo de errores con mensajes claros (qué falló y en qué nodo), no fallos mudos.
- **Sin dependencias de plugins externos** salvo que sean estándar del pipeline: prefiere nodos
  nativos de Maya y código propio. Un autorig que solo va si está instalado el plugin X es frágil y no
  portable. (Este criterio es justo el que pide evitar depender de plugins de terceros.)

---

## Cómo elegir qué aplicar

- **Empieza algo nuevo** → fija 1 (naming), 2 (modularidad), 5 (datos) *antes* de escribir.
- **Revisas deformación** → 3 (limpia), 4 (controles), 6 (QC).
- **Preparas entrega/handoff** → 6 (QC), 8 (docs), 4 (animador).
- **Tool o refactor** → 9 (robustez), 1 (naming), 7 (rendimiento).

Siempre prioriza por impacto y justifica el porqué. Tres mejoras bien elegidas valen más que cuarenta
nitpicks.
