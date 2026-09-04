# Plan: aplicar el workflow de Factory Hub al autorig

> Analisis de `weelko_factory_hub` (carpeta `.cursor` + `como_funciona.md` por
> area) y plan por fases para llevar ese mismo patron a `autorig_tools`.
> Fecha: 2026-09-04. Texto ASCII (sin acentos) a proposito: ver Fase 0.
>
> Estado: Fase 0 decidida con las recomendaciones (castellano ASCII, sin espejo
> `.cursor`, gate de git; `cache/` en git se decide en Fase 4). Fase 1 HECHA el
> 2026-09-04: `CLAUDE.md`, `como_funciona.md` raiz, `.claude/rules/` (5 reglas),
> `.claude/skills/como_funciona.md`, `maya_tools/scripts/criterios_naming.md` y
> dedupe de naming en tres skills. Fase 2 HECHA el 2026-09-04: nueve hojas
> `como_funciona.md` (quadruped, utils, tools, biped, assets, maya_tools, ui,
> adonis, ue_tools) escritas desde el codigo, con indice raiz, `CLAUDE.md` y
> skills apuntando a ellas. Fase 3 HECHA el 2026-09-04: `maya_tools/mapa_datos.md`,
> `maya_tools/scripts/quadruped/autorig/criterios_solvers.md` y
> `maya_tools/scripts/utils/criterios_build.md`. Siguiente: Fase 4 (higiene).

---

## 0. Resumen en diez lineas

Factory Hub se mantiene limpio porque separa TRES cosas y las mantiene cortas:

1. **Reglas de comportamiento** (`.cursor/rules/*.mdc`): 7 ficheros de 18-43
   lineas, uno por tema, casi todos `alwaysApply`. Dicen COMO trabajar, no que
   hace el codigo.
2. **Documentacion por area** (`como_funciona.md` en cada carpeta): un arbol
   navegable con `Parent:` arriba, tablas de enrutado ("si necesitas X, lee Y")
   y punteros a ficheros concretos. Se actualiza EN LA MISMA TAREA que el codigo.
3. **Fuentes de verdad declaradas** (`criterios-ui.md`, `criterios_carga.md`,
   `mapa_datos.md`, `vision/como_funciona.md`): el sitio unico donde viven las
   decisiones, los numeros y "donde va cada dato", con listas "Do not".

El autorig ya tiene la capa de CONOCIMIENTO (6 skills en `.claude/skills`, muy
buenas) pero no tiene ni reglas de comportamiento, ni docs por area, ni un
indice de entrada. Las convenciones del repo estan repetidas dentro de tres
skills distintas (riesgo de contradiccion). El plan: crear `CLAUDE.md` raiz +
`.claude/rules/` (5 reglas), un `como_funciona.md` por carpeta de codigo y de
assets, dos ficheros de criterios y un mapa de datos, y mover a esos sitios lo
que hoy esta duplicado en las skills.

---

## 1. Anatomia del workflow de Factory Hub (que lo hace limpio)

### 1.1 `.cursor/rules/*.mdc` - reglas cortas, una por tema

| Fichero | Tipo | Lo que aporta |
|---|---|---|
| `factory-hub-context.mdc` | enrutado | "Flujo obligatorio": identificar area -> leer SU `como_funciona.md` -> seguir dependencias -> el codigo manda -> actualizar docs en la misma tarea. Tabla "Area -> lee primero". Convencion de rutas (siempre desde la raiz, sin `../`). Comandos de validacion. Esperar aprobacion antes de `git add`/commit/push/deploy. |
| `ejecutar-sin-rodeos.mdc` | comportamiento | Ejecutar en cuanto la peticion esta clara; leer solo lo necesario; lecturas en paralelo; no pedir confirmacion si se puede resolver; no ampliar alcance. |
| `product-vision.mdc` | fuente de verdad | 10 recordatorios + puntero al doc completo. "No inventes otra historia de producto". |
| `criterios-ui.mdc` | fuente de verdad | Idem para UI: orden fijo de tiles, chrome, colores. Puntero a `frontend/criterios-ui.md`. |
| `language-english.mdc` | convencion | Un idioma, y donde aplica (UI, API, docs, logs). |
| `ascii-acentos.mdc` | convencion | "Este fichero es LA UNICA politica de acentos, no la repitas". Tabla de excepciones explicitas. |
| `i18n-translations.mdc` | convencion con `globs` | Solo se carga al tocar `frontend/src/locales/**`. |

Patrones a copiar:

- **Una regla = un tema = < 45 lineas.** Si crece, pasa a ser un doc y la regla
  queda como recordatorio + puntero.
- **"Este fichero es la unica politica de X"**: evita que la misma regla viva en
  tres sitios y se desincronice.
- **Recordatorios cortos + puntero al doc largo**: la regla cabe en contexto
  siempre; el detalle se lee solo cuando toca.
- **Gate de git**: nada de commit/push sin aprobacion explicita.

### 1.2 `como_funciona.md` por carpeta - el arbol de documentacion

Estructura observada (identica en 15 ficheros):

```
# Titulo del area
Parent: `ruta/al/indice/padre.md`        <- siempre, primera linea
Vision / UI / Data map: `...`             <- docs relacionados obligatorios
Page: `frontend/src/.../page.tsx`         <- punteros a FICHEROS concretos
Store: `...`  Packer: `...`

## 1. Purpose / Overview      que es y para que existe (con tabla de orden fijo)
## 2. Layout / Nav            como esta montado
## 3. Scope                   quien ve que (reglas duras)
## 4. Data today              que datos hay HOY y de donde salen (mock vs real)
```

Reglas del arbol:

- **Raiz** (`como_funciona.md`): overview + diagrama mermaid + seccion "Which
  folder to read: Read X if you need..." + tabla resumen. Es el unico punto de
  entrada.
- **Indices intermedios** (`modulos/como_funciona.md`, `.cursor/skills/como_funciona.md`):
  solo una tabla "Area -> Read". No repiten detalle.
- **Hojas**: el detalle. Nombran ficheros de codigo exactos, estado actual
  ("mock hasta que...", "not wired yet"), y listas "Do not".
- **Docs guian, el codigo manda**: si difieren, el codigo es la verdad y se
  arregla el doc en esa misma tarea.
- **Rutas desde la raiz del repo**, en backticks, sin `../` ni rutas absolutas.

### 1.3 Fuentes de verdad y criterios

- `frontend/criterios-ui.md` (264 lineas): "source of truth" del chrome. Mapa de
  navegacion, "una color = un significado", seccion final **"12. Do not"**.
- `modulos/suppliers/manufacturing/criterios_carga.md`: numeros de negocio
  (vehiculos, palets, kg). Cabecera: **"Este fichero es el sitio para cambiar
  las reglas de carga. Cuando un numero cambie aqui, actualiza el codigo que lo
  espeja (`cajas.ts`, packer) en la misma tarea"** + "8. Constants cheat sheet".
- `modulos/vision/mapa_datos.md`: tabla "si el dato es X -> se muestra en Y ->
  lo usa Z". Seccion "Do not put here". Columna "Sources (later)" que se rellena
  al cablear cada fuente. Objetivo: **no inventar pantallas nuevas**.
- `modulos/vision/briefs/`: plantillas con columnas fijas para que gente no
  tecnica rellene, y procedimiento de ingesta (Excel -> md -> ruta).

### 1.4 Skills, ops y git

- `.cursor/skills/como_funciona.md`: indice "Tarea -> SKILL.md" + fuentes de los
  packs de terceros. Skills versionadas con el repo.
- `despliegue/como_funciona.md`: cuando recargar vs rebuild, "never `docker
  compose down`", script `reload_docker.py`, `.env.example` comentado.
- `.gitignore` por secciones con cabecera (`# -- Secrets --`, `# -- Editor --`).
- `docs/imported-conversations/`: transcripciones de sesiones utiles como
  memoria del proyecto.
- Commits: una linea, en imperativo, dicen QUE cambia y para que.

---

## 2. Estado del autorig frente a ese patron

### 2.1 Lo que ya esta bien (no tocar)

- **Skills** (`.claude/skills/*`): 6 skills con `SKILL.md` + `references/` +
  `evals/` en dos de ellas. Formato correcto, descripciones con disparadores,
  flujo de trabajo y "Reglas NO negociables". Es la capa de conocimiento de
  dominio y esta por encima de lo que tiene Factory Hub.
- **Datos fuera del codigo**: `assets/<char>/{build,guides,curves,skin_clusters,
  corrective_blendshapes,picker,models}` versionados `_vNNN`.
- **Build data-driven**: guides -> `.build` -> `create_rig.AutoRig.build()`.
- **Tests headless** en `maya_tools/scripts/tools/tests/` (mayapy +
  `maya.standalone`, cache falso para no pisar `cache/biped.cache`).
- **Commits descriptivos en castellano** (ej. "PawFoot activo por datos:
  foot_type (hoof/paw) + FK de dedos funcionando").

### 2.2 Lo que falta (mapa de huecos)

| Hueco | Consecuencia hoy |
|---|---|
| Sin `CLAUDE.md` ni `.claude/rules/` | Cada sesion re-descubre el repo; no hay gate de git, ni politica de idioma/ASCII, ni "lee X antes de tocar Y". |
| Sin `como_funciona.md` por carpeta | El "como funciona" vive dentro de las skills (`convenciones-repo.md`, `repo-y-qa.md`, `repo-deformers.md`, `esqueleto-deformacion.md`, `flujo-pesos-y-qa.md`). Solo se lee si dispara la skill. |
| Convenciones repetidas en 3 skills | Naming/sufijos/nodos 2024+ estan en `rigging-studio-standards`, `corrective-joints` y `custom-deformers` con tablas distintas. Ya hay divergencias (`_MMT` vs `_MMX`/`_MM`; `_SKIN`/`_SC`/`_SKC`). |
| Sin indice de skills | No hay `.claude/skills/como_funciona.md` que diga "para X lee Y". |
| Estado "roto/comentado" solo en prosa de skills | `auto_skin_transfer` roto, `apply_delta_mush` y `_auto_transfer_from_source` comentados: nadie lo ve si no dispara la skill. |
| Decisiones medidas solo en commits | "rp_rp resultado negativo medido", "PV caudal por defecto - matriz 6 solvers x 2 lados", "reciprocal_coupling por especie": son criterios de estudio que no estan en ningun doc. |
| Claves del `.build` sin documentar | `Rig_Type`, `*_skinning_jnts`, `*_controllers`, `solver_*`, `mGear_integration`, `character_extras`, `foot_type`: solo se descubren leyendo `rig_manager.create_rig_settings`. |
| Higiene | `horse/guides/*.bak*`, `models/.mayaSwatches/` commiteados, `cache/*.cache` commiteado (estado del ultimo build), `ue_tools/scripts/_init_.py` (deberia ser `__init__.py`), `.gitignore` de 4 lineas. |
| Inconsistencias ya detectadas por las skills | `_JNT` vs `_jnt`, `data_manager` con `split("\scripts")` (solo Windows), imports accidentales. |

---

## 3. Mapeo `.cursor` -> Claude Code (verificado en docs oficiales)

| Factory Hub (Cursor) | Autorig (Claude Code) | Nota |
|---|---|---|
| `.cursor/rules/x.mdc` con `alwaysApply: true` | `.claude/rules/x.md` SIN frontmatter `paths` | Se carga siempre al arrancar. |
| `.cursor/rules/x.mdc` con `globs:` | `.claude/rules/x.md` con frontmatter `paths: ["glob", ...]` | Se carga solo al tocar esos ficheros. Soporta subcarpetas y symlinks. |
| `factory-hub-context.mdc` (indice de entrada) | `CLAUDE.md` en la raiz | Siempre cargado. Admite `@ruta/fichero` para importar. |
| `como_funciona.md` por carpeta | `como_funciona.md` por carpeta (mismo nombre) | Claude lo lee via la tabla del `CLAUDE.md`. Opcional: un `CLAUDE.md` de 2 lineas en la subcarpeta que diga "lee `como_funciona.md` de aqui" (se carga solo al leer ficheros de esa carpeta). |
| preferencias personales | `CLAUDE.local.md` (gitignored) | Rutas locales, puertos, etc. |
| `.cursor/skills/` | `.claude/skills/` (ya existe) | Mismo formato SKILL.md. |

Si el autorig tambien se abre en Cursor: espejar `.claude/rules/*.md` a
`.cursor/rules/*.mdc` anadiendo `description` + `alwaysApply` en el
frontmatter. Mismo contenido; no mantener dos versiones distintas.

---

## 4. Plan por fases

### Fase 0 - Decisiones (15 min, antes de escribir nada)

| Decision | Recomendacion |
|---|---|
| Idioma de docs/reglas | Castellano (como skills y commits). |
| ASCII o acentos | **ASCII en codigo, comentarios, logs, commits y docs nuevas** (Maya en Windows + PowerShell `charmap`; los commits ya lo hacen). Las skills existentes se dejan como estan: no reescribir por acentos. |
| Espejo `.cursor/rules` | Solo si se usa Cursor con este repo. Si no, no. |
| `cache/*.cache` en git | Sacarlo del repo (`.gitignore`) y dejar un `cache/README` de 3 lineas: es estado del ultimo build, se regenera. Si se prefiere mantener como ejemplo, renombrar a `*.cache.example`. |
| Nombre de los docs | Mantener `como_funciona.md` (ya es el habito). |
| Gate de git | Copiar la regla de Factory Hub: sin `git add`/commit/push sin aprobacion explicita en esa conversacion. |

### Fase 1 - Cimientos (1 sesion)

Crear:

1. **`CLAUDE.md`** (raiz). Contenido: que es el repo en 5 lineas, flujo
   obligatorio (identificar area -> leer su `como_funciona.md` -> codigo manda ->
   actualizar docs en la misma tarea), convencion de rutas desde la raiz, tabla
   de entrada (seccion 4.2 abajo), validacion (como lanzar un build y los tests).
2. **`.claude/rules/`** (5 reglas, < 45 lineas cada una):
   - `ejecutar-sin-rodeos.md` - copia casi literal de la de Factory Hub.
   - `idioma-y-ascii.md` - castellano; ASCII en codigo/logs/commits/docs nuevas;
     "este fichero es la unica politica de acentos".
   - `convenciones-rig.md` - LA fuente unica de: prefijos `L_/R_/C_`, tabla de
     sufijos (un solo caso: `_JNT/_CTL/_GRP`...), matrices en vez de constraints
     (`offsetParentMatrix`, `multMatrix`, grupos offset), nodos math/matrix Maya
     2024+ (nada de `multiplyDivide`/`plusMinusAverage` en codigo nuevo),
     `ss=True`, datos por `data_manager`/guides/`.build` (nunca nombres a mano),
     nada de plugins por defecto, `reload()` de utils al importar, `_ENV` para
     export. Termina con "Las skills enlazan aqui; no repiten esta tabla".
   - `datos-y-versionado.md` - layout de `assets/<char>/`, regla `_vNNN`
     (exportar crea la siguiente, importar coge la mas alta, nunca se pisa una
     version), nada de `.bak` en assets, LFS para `.ma` grandes, `.build` es
     el contrato por personaje, `cache/` es efimero.
   - `deformacion-y-skin.md` con `paths: ["maya_tools/scripts/**"]` - orden fijo
     del stack (BLS correctivo frontOfChain -> skin body -> skin correctivas
     localizado -> [deltaMush]), `localize_corrective_skin` obligatorio en skins
     apilados, `.skc` como unico formato que importa el build, correctivas solo
     en skin aparte con `corrective` en el nombre, escala global por masterwalk.
3. **`.claude/skills/como_funciona.md`** - tabla "Tarea -> skill" para las 6
   skills + nota: "las convenciones del repo viven en
   `.claude/rules/convenciones-rig.md`, las skills solo enlazan".
4. **`como_funciona.md`** (raiz) - overview, diagrama del pipeline de build,
   "Which folder to read", tabla resumen. Plantilla en seccion 5.

Dedupe en la misma sesion: en `rigging-studio-standards/references/convenciones-repo.md`,
`corrective-joints/references/repo-y-qa.md` seccion 4 y `custom-deformers/references/repo-deformers.md` seccion 7
sustituir la tabla de naming por una linea "Naming y nodos: `.claude/rules/convenciones-rig.md`".
Las skills conservan lo que es SUYO (API de correctivas, catalogo de zonas...).

### Fase 2 - `como_funciona.md` por area (2-3 sesiones, por orden de churn)

| Orden | Fichero | Contenido minimo | De donde sale hoy |
|---|---|---|---|
| 1 | `maya_tools/scripts/quadruped/autorig/como_funciona.md` | Modulos y que guias los activan (`L_frontLegShoulder_JNT`...), `leg_impl` self/reference, presets de solver (`solver_mode`, `solver_front_leg`, `solver_back_leg`), `foot_type` hoof/paw (PawFoot), `UNIFORM_SPINE_CHARS`, `reciprocal_coupling` por especie, tests (`test_build_horse_leg_self.py`). | `rig_manager.build_rig`, `leg_module_self.py`, commits recientes |
| 2 | `maya_tools/scripts/utils/como_funciona.md` | Tabla fichero -> responsabilidad -> funciones clave. Secuencia exacta de `AutoRig.build()`. `rig_manager` (rutas de asset, versiones, dispatch por guias + `Rig_Type`, `skeleton_hierarchy`/`_ENV`, `apply_character_extras`, space switches). `guides_manager` (cache con guard de `reload`). `data_manager` (contrato del cache + bug de `split("\scripts")`). | `create_rig.py`, `rig_manager.py`, skill refs |
| 3 | `maya_tools/scripts/tools/como_funciona.md` | Tabla tool -> entrada de menu -> estado (**funciona / roto / solo visual**): `auto_skin_transfer` roto, `proxy_locator` es visual, `mcp_listener` puerto 9877, `model_checker`, `skin_manager_api` vs `skin_manager_ng`. Seccion "Tests: `mayapy maya_tools/scripts/tools/tests/test_x.py`". | menu de `auto_rig_UI`, skills |
| 4 | `maya_tools/scripts/biped/autorig/como_funciona.md` | Patron de modulo (clase, `__init__` lee `data_manager`, `make(side, ...)`, `load_guides`, `corrective_setup`, `append_data`). Tabla modulo -> guias -> joints de skin -> que publica en cache -> estado (activo / legacy: `arm_module_custom`, `leg_module_custom`, `jaw_module_bezier` vs `nurbs`, `wing_module`). | `esqueleto-deformacion.md` de la skill skinning (moverlo aqui y dejar puntero) |
| 5 | `maya_tools/assets/como_funciona.md` | Contrato de carpeta por personaje. Tabla personaje -> `Rig_Type` -> que tiene (solo guias / skin / correctivas / picker) -> notas (`jamal` con formatos legacy `.weights`/`.shp`, `source` = origen de transfers, `spot` solo guias). Claves del `.build` con defaults. `character_extras` con ejemplo. | listado de assets, `rig_manager.create_rig_settings` |
| 6 | `maya_tools/como_funciona.md` | `self_module.mod`, `userSetup.py` (menu, shelf, puertos VS Code 4434/7001/7002, numpy, proxy_locator, MCP 9877), `icons/`, `plugin/` C++ (estado), `cache/`. | `userSetup.py`, `.mod` |
| 7 | `maya_tools/scripts/ui/como_funciona.md` | Secciones del menu (PIPELINE / MODELING / RIGGING / ANIMATION / CORRECTIVES / SKINNING / SIMULATION) -> funcion. Como anadir un boton al shelf (ya comentado en `auto_rig_shelf.py`). | `auto_rig_UI.py` |
| 8 | `maya_tools/scripts/adonis/como_funciona.md` | `copyWeightsAdonis`: tipos Adn*, 4 pestanas, sin fichero versionado propio. | `repo-deformers.md` seccion 4 |
| 9 | `ue_tools/como_funciona.md` | Que hay (solo docs; `scripts/_init_.py` vacio y mal nombrado), contrato de export (`_ENV` + morphs), puntero a las notas de Unreal Fest, donde ira el codigo UE. | `ue_tools/docs/` |

Cada hoja lleva la cabecera de la plantilla (seccion 5) y una seccion final
**"Do not"** con lo que NO se debe hacer en esa area (ej. en biped: "no leer
`rotate` local de joints; no crear un modulo sin `append_data`").

### Fase 3 - Criterios y mapa de datos (1 sesion)

1. **`maya_tools/mapa_datos.md`** (analogo de `mapa_datos.md`): tabla "si el dato
   es X -> vive en Y -> lo escribe Z -> lo lee W":

   | Dato | Vive en | Escribe | Lee |
   |---|---|---|---|
   | posiciones/orientacion de guias | `assets/<c>/guides/<c>_vNNN.guides` | Export Guides | `guides_manager.get_guides` |
   | parametros de build por personaje | `assets/<c>/build/<c>_vNNN.build` | Rig settings UI | `rig_manager.build_rig` |
   | formas de control | `assets/<c>/curves/` | Export All Controllers | `curve_tool` |
   | pesos de skin (stack completo) | `assets/<c>/skin_clusters/*.skc` | `SkinManager.export_skins` | `import_weights` |
   | blendshapes correctivos | `assets/<c>/corrective_blendshapes/*.json` | CBS manager | `import_corrective_blendshapes` |
   | attrs tuneados a mano | `character_extras` del `.build` | a mano | `apply_character_extras` |
   | nombres de nodos entre modulos | `cache/*.cache` | `append_data` | `get_data` |
   | esqueleto de export | `skeletonHierarchy_GRP` (`_ENV`) | `skeleton_hierarchy` | engine |

   Mas la tabla **"Do not put here"**: posiciones hardcodeadas en modulos,
   nombres de nodo pasados a mano, pesos que solo existen en escena, valores
   tuneados sin volcar a `character_extras`.

2. **`maya_tools/scripts/quadruped/autorig/criterios_solvers.md`** (analogo de
   `criterios_carga.md`): las decisiones MEDIDAS que hoy solo estan en commits:
   PV caudal por defecto, matriz solver x lado, `rp_rp` descartado y por que,
   `reciprocal_coupling` por especie, `fetlock_spring`, escapula automatica.
   Cabecera: "Este fichero es el sitio para cambiar un criterio de solver;
   cuando cambie, actualizar `leg_module_self.py` y el `.build` de la especie en
   la misma tarea". Cierra con "Constants cheat sheet" (valores por especie).

3. **`maya_tools/scripts/utils/criterios_build.md`**: orden del build y por que
   (fast session, `localize` justo tras `import_weights` en pose neutra,
   deltaMush comentado y motivo, `cycleCheck` apagado en build -> validar en QA).
   Poses de QA canonicas (ROM del catalogo de skinning) como checklist.

### Fase 4 - Higiene que las reglas exigen (1 sesion)

- `.gitignore` por secciones: Python, Maya (`*.swatches`, `.mayaSwatches/`,
  `*.bak*`), cache (`maya_tools/cache/*.cache` segun Fase 0), secrets
  (`CLAUDE.local.md`, `.env`), editor, OS. Mantener la nota de LFS.
- Borrar `assets/horse/guides/*.bak*` (git guarda el historial) y los
  `.mayaSwatches`.
- Renombrar `ue_tools/scripts/_init_.py` -> `__init__.py`.
- `README.md` raiz de 10 lineas que apunte a `como_funciona.md` (GitHub lo
  muestra; `como_funciona.md` es para trabajar).
- Opcional: `CLAUDE.md` de 2 lineas en `maya_tools/scripts/{biped,quadruped}/autorig/`
  y `utils/` que digan "antes de editar aqui lee `.../como_funciona.md`" (se
  cargan solo al leer ficheros de esa carpeta).
- Arreglar lo que las skills ya senalan y una regla nueva prohibe: `split("\scripts")`
  en `data_manager` -> `pathlib`; unificar `_JNT`/`_jnt` (migracion entera, no a
  parches; primero contar ocurrencias con `grep -rn "_jnt" maya_tools/scripts`).

### Fase 5 - Mantenimiento (continuo)

- La regla "actualiza el `como_funciona.md` afectado en la misma tarea" es lo
  que evita que esto se pudra. Va en `CLAUDE.md`, no en una skill.
- Al cerrar una sesion larga con decisiones, volcar la conclusion en el
  `criterios_*.md` del area (no en el chat).
- Cada skill nueva: entrada en `.claude/skills/como_funciona.md` + evals.
- Revision mensual de 20 min: `grep -rn "TODO\|roto\|comentado" maya_tools/scripts/**/como_funciona.md`
  y comprobar contra el codigo.

---

## 5. Plantillas

### 5.1 Regla (`.claude/rules/<tema>.md`)

```markdown
---
paths:            # OMITIR este bloque si la regla aplica siempre
  - "maya_tools/scripts/**"
---

# <Tema en una linea>

Este fichero es la unica politica de <tema>. No la repitas en skills ni docs.

## Regla
- <maximo 8-10 bullets, cada uno una frase>

## Excepciones
| Ambito | Aplica |
|---|---|
| ... | si/no |

Detalle: `ruta/desde/la/raiz/como_funciona.md`.
```

### 5.2 Hoja de area (`<carpeta>/como_funciona.md`)

```markdown
# <Area>

Parent: `como_funciona.md`            (o el indice intermedio)
Reglas: `.claude/rules/convenciones-rig.md`
Skill relacionada: `.claude/skills/<x>/SKILL.md`
Entrada: `maya_tools/scripts/utils/create_rig.py`   (ficheros concretos)

## 1. Que es y para que existe
## 2. Como esta montado          (tabla fichero -> responsabilidad -> funciones)
## 3. Datos que lee y escribe    (guias, .build, cache, .skc...)
## 4. Estado hoy                 (activo / legacy / roto / comentado, con motivo)
## 5. Como probarlo              (menu, mayapy test, pose de QA)
## 6. Do not
```

### 5.3 Criterios (`<carpeta>/criterios_<tema>.md`)

```markdown
# Criterios: <tema>

Parent: `<carpeta>/como_funciona.md`
Fuente de los numeros: <de donde salen, fecha>

Este fichero es el sitio para cambiar <tema>. Cuando un valor cambie aqui,
actualiza en la misma tarea: `fichero1.py`, `fichero2.py`, `assets/<c>/build/*.build`.

## 1. Decisiones (con la medida que las sostiene)
## 2. Lo descartado y por que
## 3. Constants cheat sheet
```

### 5.4 Tabla de entrada para `CLAUDE.md`

| Area o cambio | Lee primero |
|---|---|
| Vision general del repo | `como_funciona.md` |
| Arranque de Maya, `.mod`, menu, shelf, MCP | `maya_tools/como_funciona.md` |
| Build, managers, matrices, ribbons | `maya_tools/scripts/utils/como_funciona.md` |
| Un modulo biped | `maya_tools/scripts/biped/autorig/como_funciona.md` |
| Un modulo quadruped o un solver | `maya_tools/scripts/quadruped/autorig/como_funciona.md` + `criterios_solvers.md` |
| Una tool o un test | `maya_tools/scripts/tools/como_funciona.md` |
| UI / menu | `maya_tools/scripts/ui/como_funciona.md` |
| AdonisFX | `maya_tools/scripts/adonis/como_funciona.md` |
| Un personaje, sus versiones, su `.build` | `maya_tools/assets/como_funciona.md` |
| Donde vive un dato | `maya_tools/mapa_datos.md` |
| Naming, nodos, matrices | `.claude/rules/convenciones-rig.md` |
| Skinning, correctivas, deformers, ropa, estandares | `.claude/skills/como_funciona.md` |
| Export a Unreal | `ue_tools/como_funciona.md` |

---

## 6. Que NO copiar de Factory Hub

- `language-english.mdc` e `i18n-translations.mdc`: el autorig es castellano y
  no tiene UI traducida.
- `criterios-ui.md`, `product-vision.mdc`, `briefs/`: son de producto web. Su
  EQUIVALENTE en rig es `criterios_solvers.md`, `criterios_build.md` y
  `mapa_datos.md`, no una copia.
- `despliegue/` con Docker: el equivalente es `maya_tools/como_funciona.md`
  (`.mod`, `userSetup`, versiones de Maya, tests con mayapy).
- `docs/imported-conversations/`: opcional. Mas util volcar conclusiones a
  `criterios_*.md` que guardar transcripciones enteras.

---

## 7. Orden de ejecucion sugerido (sesiones)

1. Fase 0 + Fase 1 completa (reglas, `CLAUDE.md`, indices, dedupe de skills).
2. Fase 2 filas 1-3 (quadruped, utils, tools) - donde hay mas churn.
3. Fase 2 filas 4-9 + Fase 3.
4. Fase 4.

Criterio de "hecho" por fase: una sesion nueva de Claude, sin contexto previo,
puede localizar el fichero correcto para una tarea de cada area usando solo
`CLAUDE.md` y los `como_funciona.md`, y sabe que NO debe hacer git sin permiso.
