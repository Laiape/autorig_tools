# Catálogo de métodos para Proxy Skinning del cuerpo

> Referencia de la skill *body-proxy-skinning*. Objetivo: skinnear el cuerpo de forma **eficiente** y que **quede bien**, evitando el cruce de influencias entre partes anatómicas próximas. Aterrizado en el pipeline del usuario: autorig modular en Maya + Python (cmds/OpenMaya), rig por matrices, build data-driven, ngSkinTools2, `auto_skin_transfer.py`, `skincluster_surface.py`, `proxy_locator.py`, `model_checker`, `SkinManager` (.skc/.json versionado), AdonisFX y Delta Mush.

---

> **Cómo leer este catálogo.** No hace falta leerlo entero. Lee primero **§1 (por qué el
> closest-joint no es preciso)** y la **§2 tabla-resumen**, y baja solo a la(s) familia(s) que
> aplican al caso. Al final tienes la **§8 receta recomendada end-to-end** y la **§9 recursos**.

> ⚠ **`auto_skin_transfer.py` está actualmente NO OPERATIVO** (el usuario lo confirma roto). **No
> lo recomiendes** para el paso de transferencia. El transfer nativo por defecto es
> **`copySkinWeights -uvSpace <src> <dst> -influenceAssociation label`** (o `skincluster_surface`,
> o `VertexTransferMode.vertexId` de ngSkinTools2 si la topología coincide). Las menciones a
> `auto_skin_transfer` de abajo se conservan como documentación de la técnica, no como recomendación.

## 1. Por qué el "closest-joint" no es preciso

El "assign closest joint" de ngSkinTools (y el `bindMethod=0`, *closest distance*, de Maya) asigna a cada vértice el joint más cercano midiendo la **distancia euclídea en línea recta**, atravesando el aire. Esa métrica no tiene noción de "dentro del cuerpo": el rayo de medida cruza el hueco entre dos partes anatómicas como si no existiera. Por eso, en toda **zona de contacto**, el hueso equivocado queda a pocos centímetros en recta y captura la influencia:

- Cara interna del muslo → coge el fémur de **la otra pierna**.
- Axila → coge costillas / **pecho**.
- Dedos → se **pegan entre sí**.
- Barbilla / mentón → coge clavícula o pecho.

Además su falloff es duro y no continuo, así que, aparte de cruzar, deja escalones. El resultado obliga a repintado masivo.

**La solución no es repintar más ni tapar con Delta Mush.** El Delta Mush suaviza promediando vértices vecinos: enmascara el síntoma pero *no cura* la asignación errónea (si el peso ya cogió la otra pierna, el mush sigue moviendo la carne equivocada, y de hecho puede arrastrar más contaminación al promediar). La solución es **cambiar el inicializador** por uno cuya métrica de proximidad respete la separación anatómica:

- **Volumen interior** (Geodesic Voxel Binding): la distancia se mide caminando por dentro del volumen voxelizado; para ir de la axila al pecho hay que rodear por el hombro, así que la influencia cae.
- **Difusión** (heat map / bone heat): el calor solo conduce por la geometría, no por el aire.
- **Energía biharmónica sobre un volumen tetraedralizado** (BBW): pesos suaves, acotados y con máximos localizados que no saltan a partes desconectadas.
- **Espacio UV / paramétrico** (tu `auto_skin_transfer`, `skincluster_surface`): dos superficies pegadas en 3D caen en islas o coordenadas UV distintas, así que nunca son "vecinas".

**Regla de oro del flujo:** inicializa con un bind volumétrico que no cruce por construcción → afina con ngSkinTools2 por capas *sobre esa base limpia* (nunca uses su "assign closest joint" para inicializar) → transfiere del proxy a la alta por un método consciente de topología/UV → refina con Delta Mush/DDM solo donde comprime → hornea a skin lineal para dejarlo eficiente → correctivos por pose en las zonas problema.

---

## 2. Tabla-resumen

| Método | Familia | Calidad | Eficiencia | ¿Cruza influencias? | Esfuerzo | DCC / Tool |
|---|---|---|---|---|---|---|
| Closest distance (`bindMethod=0`) | Inicialización | Baja | Alta | **Sí** (anti-patrón) | Bajo | Maya, ngSkinTools |
| Closest distance in hierarchy (`bindMethod=1`) | Inicialización | Baja-media | Alta | Sí (menos) | Bajo | Maya |
| Surface heat map diffusion (`bindMethod=2`) | Inicialización | Media-alta | Media | Parcial (difunde en superficie) | Bajo | Maya, Blender |
| **Geodesic Voxel Binding (`bindMethod=3`)** | Inicialización | Alta | Media | No* (según resolución) | Bajo | Maya nativo |
| Bounded Biharmonic Weights (BBW) | Inicialización | Alta | Baja | No | Alto | libigl (no nativo) |
| Bind interactivo / cápsulas | Inicialización | Alta | Media | No (si se ajusta) | Medio | Maya, mGear |
| ML / campos geométricos (RigNet, etc.) | Inicialización | Media | Media | Parcial | Alto | Research/PyTorch |
| Proxy low-res retopológico | Flujo proxy | Alta | Alta | Parcial (según transfer) | Medio | Maya + tooling |
| Proxy segmentado por islas | Flujo proxy | Alta | Alta | No | Medio | Maya, ngSkinTools |
| Jaula / Lattice (FFD) | Flujo proxy | Media | Media | No | Bajo | Maya, Houdini |
| Superficie NURBS (De Boor 2D) | Flujo proxy / Transfer | Media-alta | Alta | No | Medio | `skincluster_surface.py` |
| copySkinWeights por superficie | Transfer | Media | Alta | Parcial (closestPoint cruza) | Bajo | Maya nativo |
| copySkinWeights `-uvSpace` | Transfer | Alta | Alta | No (si UV separa) | Medio | Maya nativo |
| ngSkinTools2 transfer (vertexId / closestPoint) | Transfer | Alta | Media | Parcial | Medio | ngSkinTools2 |
| ~~`auto_skin_transfer.py` (UV esqueleto + KNN/IDW)~~ **⚠ roto** | Transfer | — | — | — | — | Tuyo (no operativo) |
| **`copySkinWeights -uvSpace -label`** (transfer nativo por defecto) | Transfer | Alta | Alta | No (si UV/label separan) | Bajo | Maya nativo |
| Robust Skin Weights Transfer (inpainting) | Transfer | Alta | Media | No | Medio | Repo/Maya (comunidad) |
| cvWrap (deformación) | Transfer | Alta | Media (runtime) | No | Medio | Plugin (Chad Vernon) |
| proximityWrap (Maya 2020+) | Transfer | Media | Media (runtime) | No (si falloff ajustado) | Bajo | Maya nativo |
| Wrap clásico | Transfer | Media | Baja | No | Bajo | Maya nativo |
| uvPin / follicle | Transfer (tweaks) | Media | Alta | No | Bajo | Maya nativo |
| **Delta Mush** | Refinado | Media-alta | Media (runtime) | Parcial (enmascara) | Bajo | Maya nativo |
| Direct Delta Mush (DDM) | Refinado / Runtime | Alta | Alta | Parcial | Medio | Plugin comunidad |
| Tension deformer / TensionMap | Refinado | Media | Media | No | Medio | Maya nativo + comunidad |
| ngSkinTools2 por capas | Refinado (afinado) | Alta | Alta | No | Alto (manual) | ngSkinTools2 |
| Dual Quaternion / weighted skinning | Refinado (en el bind) | Media-alta | Alta | No | Medio | Maya nativo |
| **dm2skin** (DM → skin) | Bake | Alta | Alta | Parcial | Medio | Repo + numpy/scipy |
| **bakeDeformer** (Maya 2017 U3+) | Bake | Alta | Alta | Parcial | Bajo | Maya nativo |
| Dem-Bones / SSDR | Bake | Alta | Alta | Parcial | Alto | Librería EA (C++/CLI) |
| Maya ML Deformer (2024+) | Bake / Runtime | Alta | Alta | No (no es LBS) | Alto | Maya nativo |
| Optimización skinCluster (prune/clamp/normalize) | Bake (acabado) | Media | Alta | No | Bajo | Maya nativo |
| Blendshapes correctivos + invertShape | Correctivos | Alta | Alta | No | Alto | Maya, SHAPES |
| PSD / RBF (weightDriver, poseInterpolator) | Correctivos | Alta | Alta | No | Alto | Maya nativo / braverabbit |
| Helper joints pose-driven | Correctivos | Media-alta | Alta | Parcial | Medio | Maya, mGear |
| AdonisFX (músculo/grasa/piel) | Correctivos | Alta | Baja (sim) | No | Alto | Plugin (Inbibo) |
| Maya Muscle (cMuscle) / Ziva VFX | Correctivos | Alta | Baja | No | Alto | Maya / plugin |

\* *"No" condicionado a la resolución de voxelización (GVB) o a que el layout UV / la componente U esqueleto-relativa separe realmente las partes. No es una garantía absoluta a cero: validar por QC.*

---

## 3. Familia — Inicialización del binding

El paso que resuelve tu queja de raíz. Jerarquía práctica de calidad/robustez para producción: **GVB** (nativo, un clic, base recomendada) ≥ **Heat/BBW** (más suaves, más setup) > **binding por cápsulas** (control manual explícito) > **closest-in-UV** (imbatible para *transferir*, ver familia 4) >> **closest-joint** (a evitar como inicializador).

### 3.1 Closest distance (`bindMethod=0`) — la línea base a evitar

- **Qué es:** el método por defecto que te falla. Asigna cada vértice al joint/segmento de hueso más cercano en distancia euclídea, con falloff radial (`dropoffRate`).
- **Cómo funciona:** distancia recta por el aire al hueso más próximo → influencia dominante → resto por dropoff radial. `bindMethod` es un **entero** (`0`), no una cadena; no existe un valor string `closestDistance`/`closestPoint`.
- **Calidad:** baja. **Eficiencia:** alta. **Esfuerzo:** bajo. **¿Cruza?** Sí, en toda zona de proximidad.
- **Límites reales:** cruza siempre que dos partes se tocan; falloff duro con escalones; obliga a repintado masivo. El "assign closest joint" de ngSkinTools2 **es exactamente esto**.
- **Cuándo usarlo:** solo props/mallas simples muy separadas (un cilindro, un tentáculo aislado) o como arranque instantáneo que vas a repintar entero. Nunca como inicializador de un cuerpo con contactos.
- **Encaje en tu pipeline:** documéntalo como anti-patrón. Si `skin_manager_ng.py` lo invoca para poblar, cámbialo por GVB. Sirve como "peor caso" para validar que los demás métodos mejoran.

### 3.2 Closest distance in hierarchy (`bindMethod=1`)

- **Qué es:** variante barata del closest que respeta la **jerarquía** del esqueleto al asignar, reduciendo parte del cruce respecto a `bindMethod=0`.
- **Calidad:** baja-media. **Eficiencia:** alta. **¿Cruza?** Sí, pero algo menos: al considerar la cadena de huesos, no salta tan libremente a un hueso lejano no emparentado.
- **Límites reales:** sigue razonando por proximidad; no es una solución volumétrica. Método intermedio, no recomendado como base final.
- **Encaje:** útil solo como fallback rápido cuando GVB no está disponible; sigue necesitando afinado.

### 3.3 Surface heat map diffusion (`bindMethod=2`)

- **Qué es:** bind nativo de Maya que difunde la influencia de cada hueso resolviendo la ecuación de calor **sobre la SUPERFICIE de la malla** (no sobre un volumen tetraedralizado). En Blender es el "Automatic Weights" (bone heat); Pinocchio es el standalone de referencia.
- **Cómo funciona:** fija temperatura 1 en el hueso y 0 en el resto, resuelve el estado estacionario de difusión y la temperatura de equilibrio de cada vértice es su peso.
- **Aclaración importante:** es `bindMethod=2` (un **método de bind**), no un "dropoff/falloff" del skinCluster —el dropoff es el parámetro numérico `dropoffRate`, independiente. **No es un hermano volumétrico de GVB:** al difundir sobre la superficie, **puede cruzar/sangrar** en zonas de autocontacto (partes pegadas, malla no-watertight, auto-intersección). Precisamente por eso Autodesk migró a GVB.
- **Calidad:** media-alta (falloffs suaves de serie). **Eficiencia:** media. **¿Cruza?** Parcial (sí en autocontactos).
- **Límites reales:** el bone-heat clásico lanza el típico "failed to find solution" en mallas no-watertight o con partes pegadas; menos robusto en producción que GVB.
- **Encaje:** alternativa nativa a GVB cuando quieres suavidad extra o estás fuera de Maya. En Maya moderno, prefiere GVB; menciónalo para explicar *por qué* GVB es mejor.

### 3.4 Geodesic Voxel Binding — GVB (`bindMethod=3`) — la base recomendada

- **Qué es:** bind nativo de Maya (desde 2015) que mide la distancia a los huesos caminando **por el interior del volumen voxelizado**, no por el aire. Reemplazo directo del closest-joint.
- **Cómo funciona:** voxeliza el modelo (vóxeles de esqueleto / interior / frontera), rasteriza los huesos dentro del volumen y calcula la distancia geodésica desplazándose solo por vóxeles interiores/frontera. Como no puede atravesar el aire entre dos partes, el muslo interior no coge la otra pierna y la axila no coge el pecho. Robusto a malla no-manifold, no-watertight, con auto-intersección y multi-componente.
- **Calidad:** alta. **Eficiencia:** media. **Esfuerzo:** bajo. **¿Cruza?** No\*, pero con matiz: **reduce muchísimo** el sangrado, no lo garantiza a cero. En huecos más finos que el vóxel (dedos juntos, membranas, párpados, axila cerrada) sigue mezclando → sube la resolución (256 → 512 → 1024) y valida por QC.
- **Límites reales:** pesos algo blandos/globosos que necesitan afinado posterior; resolución alta consume memoria/tiempo; requiere joints dentro del volumen y normales hacia fuera; en cavidades cerradas puede sangrar.
  - **Automatización data-driven:** `cmds.skinCluster` **no expone** un flag de resolución de vóxel. La resolución de GVB se ajusta en las opciones de *Bind Skin* vía **optionVar** antes del bind, no como argumento del comando. En mayapy/standalone la voxelización puede requerir contexto de viewport/GPU: fija la optionVar y valida el resultado.
- **Cuándo usarlo:** inicializador **por defecto** de cualquier cuerpo/criatura, y en especial del proxy low-res.
- **Encaje en tu pipeline:** sustituye la fase "assign" de `skin_manager_ng.py` por `cmds.skinCluster(tsb=True, bindMethod=3, mi=4)`. Pasa antes `model_checker` para garantizar malla cerrada y normales correctas. Bind GVB en el proxy → afinar con ngSkinTools2 → transferir con `auto_skin_transfer.py`.

### 3.5 Bounded Biharmonic Weights (BBW)

- **Qué es:** los pesos más suaves y limpios del sector: minimizan la energía biharmónica sobre un volumen tetraedralizado con restricciones de acotación 0..1, no-negatividad, partición de la unidad y localidad. Referencia académica de calidad y el **estándar moderno de pesos de cage/jaula**.
- **Cómo funciona:** sobre una tetraedralización (TetGen) resuelve una optimización convexa que minimiza la energía de flexión de cada campo de pesos. Soporta huesos, puntos y cages. Precálculo en bind; deform lineal en runtime.
- **Calidad:** alta. **Eficiencia:** baja (precálculo pesado). **Esfuerzo:** alto. **¿Cruza?** No (salvo que el tet mesh pegue dos partes en autocontacto fuerte).
- **Límites reales:** necesita un volumen tetraedralizado **limpio**; mallas sucias/no-watertight complican la tetraedralización. **No es nativo en Maya**: se integra vía libigl (C++/Python, `igl.bbw`) offline o en Houdini.
- **Cuándo usarlo:** máxima suavidad y control fino (mezclar huesos, cages, puntos), o para un binder offline propio. Overkill si GVB ya cumple. Cítalo como *peer* conceptual de GVB.
- **Encaje:** candidato a un "binder offline" en tu ecosistema Python/C++ que produzca el `.skc` inicial versionado con tu SkinManager. Encaja con tu filosofía de precálculo + skin lineal para runtime eficiente.

### 3.6 Binding interactivo / por volumen (cápsulas y envelopes)

- **Qué es:** defines el volumen de influencia de cada joint con primitivas manipulables (cápsulas/esferas) y asignas pesos por inclusión y falloff. Eliminas el cruce **por diseño**.
- **Cómo funciona:** cada joint lleva una cápsula editable; los vértices dentro reciben peso según un falloff interno; ajustas interactivamente tamaño/forma/orientación para abrazar la anatomía sin invadir la parte contigua. El *Interactive Skin Bind* de Maya lo construye sobre el heat map con manipuladores en vivo.
- **Calidad:** alta. **Eficiencia:** media. **Esfuerzo:** medio. **¿Cruza?** No (condicionado al ajuste; con cápsulas por defecto vuelve a cruzar).
- **Límites reales:** manual y tedioso en personajes con muchos joints; el falloff de primitiva puede ser tosco en articulaciones; no sustituye al afinado fino, lo complementa.
- **Cuándo usarlo:** ideal en el proxy low-res (pocos vértices, cápsulas rápidas) y para delimitar a mano zonas donde GVB/heat cruzan (entrepierna, axila, entrededos).
- **Encaje:** encaja con `proxy_locator.py` para colocar volúmenes/joints; luego transfieres al high-res con `auto_skin_transfer.py`.

### 3.7 Binding por aprendizaje / campos geométricos (emergente, a vigilar)

- **Qué es:** métodos que predicen o resuelven pesos con redes neuronales (RigNet, Neural Blend Shapes) o campos geométricos robustos (*Robust Biharmonic Skinning using Geometric Fields*, 2024), evitando la tetraedralización frágil de BBW.
- **Cómo funciona:** RigNet aprende de datasets a predecir pesos por vértice; los campos geométricos resuelven la energía biharmónica **sin tet mesh**, robustos a mallas sucias/self-contact.
- **Calidad:** media. **Eficiencia:** media. **Esfuerzo:** alto. **¿Cruza?** Parcial.
- **Límites reales:** no nativo en Maya; requiere entorno ML/GPU; difícil de versionar de forma determinista (caja negra); sobreingeniería para un biped estándar donde GVB + afinado ya cumplen.
- **Encaje:** baja hoy en tu pipeline; a vigilar. Como inicializador offline de mallas problemáticas que exporta un `.skc` y luego afinas.

---

## 4. Familia — Flujo proxy y transferencia proxy → alta

Concentras el trabajo de precisión en un intermediario controlable (low-res, cage, NURBS) y luego, o la alta **sigue** al proxy en vivo (wrap, para previz/LOD/sim), o **transfieres** los pesos y horneas. Regla práctica: escoge un método cuyo criterio de vecindad **no** sea la distancia euclídea 3D cruda (usa geodésica, islas, UV o superficie).

### 4.1 Proxy low-res retopológico ("sock puppet")

- **Qué es:** una malla low-res limpia (quads, loops en articulaciones) que representa el cuerpo. Skinneas y pintas ahí, y transfieres a la alta. Metodología documentada por Kiel Figgins y Chris Lesage.
- **Cómo funciona:** retopologizas a pocos miles de vértices con edge loops en codo/rodilla/hombro/cadera/cuello; bindas con **GVB** (no closest-joint crudo); pintas cómodo (20× menos vértices, smooth y flood instantáneos); transfieres a la alta con un método consciente de topología/UV. Al compartir esqueleto, el mapeo de joints es directo.
- **Calidad:** alta. **Eficiencia:** alta. **Esfuerzo:** medio. **¿Cruza?** Parcial: **el proxy solo resuelve el cruce si el transfer también lo respeta**. Si transfieres por punto más cercano 3D crudo, reintroduces el cruce.
- **Cuándo usarlo:** personaje hero de cuerpo entero, iteración rápida, alta demasiado densa para pintar, o topología de la alta que cambiará mientras el proxy se mantiene estable.
- **Encaje:** construyes el proxy, lo bindas GVB, exportas con SkinManager a `.skc` versionado, y transfieres con `auto_skin_transfer.py`. El proxy vive como asset reutilizable. Valida qué región coge cada control con `proxy_locator.py`.

### 4.2 Proxy segmentado por islas anatómicas

- **Qué es:** el proxy dividido en **islas separadas** por partes (torso, cada brazo, cada pierna, cada dedo como shell). Cualquier "closest" o flood queda confinado a su isla → imposible que el muslo interior salte a la otra pierna.
- **Cómo funciona:** cada región es una shell desconectada; al transferir por punto más cercano *dentro de la misma shell* o al usar smoothing "associate by surface" (no by volume) en ngSkinTools, la búsqueda de vecinos nunca cruza el hueco de aire. Es imponer la separación anatómica como **topología**.
- **Calidad:** alta. **Eficiencia:** alta. **¿Cruza?** No.
- **Límites reales:** en las costuras entre islas hay que fundir a mano o con un smooth acotado; mantener alineación con la alta requiere disciplina; es una **estrategia**, hay que combinarla con un método de transfer.
- **Encaje:** el smoothing/relax por **superficie** de ngSkinTools respeta islas; `auto_skin_transfer` puede correrse por partes con máscaras. La segmentación puede derivarse de `proxy_locator` o de sets por módulo del autorig.

### 4.3 Jaula / Lattice (FFD) como proxy

- **Qué es:** el proxy es una **jaula** (lattice/FFD o cage) que envuelve el cuerpo. Skinneas la jaula y la alta interpola dentro por coordenadas de cage.
- **Cómo funciona:** la alta se ata por coordenadas baricéntricas/armónicas (mean value / harmonic coordinates); cada punto es combinación local de los puntos de la jaula que lo contienen. La calidad de referencia de estos pesos de cage la dan las **Bounded Biharmonic Weights** (ver 3.5).
- **Calidad:** media. **Eficiencia:** media. **¿Cruza?** No (interpolación local a las celdas).
- **Límites reales:** baja resolución = poco detalle; capa gruesa, no skin final; alinear celdas a articulaciones es tosco; difícil de portar a motor sin hornear.
- **Cuándo usarlo:** formas voluminosas suaves (barriga, masas musculares), previz, bloqueo de volumen antes del skin fino.

### 4.4 Superficie NURBS como proxy (redistribución De Boor 2D) — `skincluster_surface.py`

- **Qué es:** el proxy es una superficie NURBS suave; los pesos se redistribuyen según el punto UV más cercano en ella usando pesos de **De Boor 2D**. Es tu `split_with_surface`.
- **Cómo funciona:** una rejilla 2D de joints (filas U × columnas V) asociada a la NURBS. Para cada vértice buscas su UV más cercano y evalúas los pesos de De Boor bidimensionales (producto de bases B-spline en U y V). La métrica es la **parametrización de la superficie**, no la distancia 3D, así que el reparto sigue la forma del cuerpo y no salta a partes vecinas. La partición de la unidad garantiza pesos que suman 1 y soporte local.
- **Calidad:** media-alta. **Eficiencia:** alta. **¿Cruza?** No.
- **Límites reales:** requiere una NURBS bien parametrizada por región (no práctico envolver todo un cuerpo con una sola); en torsión fuerte la UV se estira; es redistribución/suavizado, **no un binding inicial**.
- **Encaje:** ya implementado (`skincluster_surface.py` + `de_boor_core.py`). Zonas tubulares/laminares (cuello, torso, cola, labios, tentáculos). Úsalo tras el transfer, antes del Delta Mush. Comparte `de_boor_core` con `skincluster_curve.py`.

### 4.5 copySkinWeights por superficie (surfaceAssociation + influenceAssociation)

- **Qué es:** el comando nativo de Maya que copia pesos de un skinCluster origen a otro destino, resolviendo de qué punto del proxy toma cada vértice (`surfaceAssociation`) y cómo empareja influencias (`influenceAssociation`).
- **Cómo funciona:** `surfaceAssociation` = `closestPoint` / `rayCast` / `closestComponent`. `influenceAssociation` = `closestJoint` / `closestBone` / `label` / `name` / `oneToOne` (se puede pasar hasta 3 en cascada de fallback). El destino debe tener ya un skinCluster con las mismas influencias.
- **Calidad:** media. **Eficiencia:** alta. **Esfuerzo:** bajo. **¿Cruza?** Parcial.
- **Aclaración crítica sobre el cruce** (hay dos cruces distintos, no los confundas):
  1. **Cruce de superficie** (axila→pecho, muslo→muslo, ambos del mismo lado): lo produce el muestreo por proximidad. **`closestComponent` NO lo evita** —muestrea el vértice más cercano por distancia euclídea, exactamente el mismo criterio que `closestPoint`, así que cruza igual en cavidades. Solo lo evita de verdad **`-uvSpace`** (ver 4.6) o `rayCast` con normales limpias.
  2. **Swap izquierda/derecha** (a nivel de joint): lo evita `influenceAssociation='label'` (requiere labels type/side correctos en los joints) o `'name'`. Es un problema **distinto** al de superficie.
- **Límites reales:** el transfer es tan bueno como el origen; `rayCast` depende de normales limpias; sin control de `maxInfluences` en el propio comando; suele necesitar smoothing o Delta Mush después.
- **Encaje:** fallback natural sin plugins. Envuélvelo en tu API para forzar **siempre** `influenceAssociation='label'` (tus joints tienen naming `C_/L_/R_`) y evitar el `closestJoint` por defecto. Integra con SkinManager y `model_checker`.

### 4.6 copySkinWeights en espacio UV (`-uvSpace`)

- **Qué es:** mismo comando pero la asociación de superficie se hace en el espacio **UV**: el punto muestreado en el proxy es el que coincide en coordenada UV, no el más cercano en el mundo. Es, conceptualmente, la versión nativa de tu `auto_skin_transfer`.
- **Cómo funciona:** se pasan los UV sets: `cmds.copySkinWeights(..., uvSpace=(srcUVSet, dstUVSet), influenceAssociation='name', surfaceAssociation='closestPoint')`. Como dos partes que se tocan en 3D están **separadas en el layout UV**, el muestreo por UV no cruza.
  - **Corrección de flag muy importante:** el transfer por UV se activa con **`-uvSpace <srcUVSet> <dstUVSet>`**. **NO existe** un `sampleSpace=UV` en `copySkinWeights` —su `-sampleSpace` solo acepta `world`/`local`. El valor UV=2 pertenece a **`transferAttributes`**, otro comando. Si pones `sampleSpace` esperando UV, obtienes proximidad en mundo y **reintroduces el cruce**.
- **Calidad:** alta. **Eficiencia:** alta. **¿Cruza?** No (si el UV separa las partes).
- **Límites reales:** depende por completo de la calidad y correspondencia del layout UV; solapes (UDIM overlapping) rompen el "closest"; en las costuras UV puede haber discontinuidad que hay que suavizar.
- **Encaje:** alternativa nativa a `auto_skin_transfer` cuando el UV de producción ya separa partes. Puedes generar UVs temporales por proyección (como hace tu `UVMatchingModule`) y luego llamar `-uvSpace` para algo 100 % Maya sin numpy.

### 4.7 ngSkinTools2 — transferencia por API (InfluenceMappingConfig + VertexTransferMode)

- **Qué es:** el motor de transferencia de ngSkinTools2, que copia la **pila de capas** (no solo el skin plano), con emparejamiento de influencias y modo de muestreo de vértices configurables.
- **Cómo funciona:** `InfluenceMappingConfig` casa influencias (`use_name_matching`, distance matching); `VertexTransferMode` casa vértices: `vertexId` (misma topología, 1:1, exacto y rapidísimo) o `closestPoint` (topología distinta, muestreo espacial). Al transferir capas conservas máscaras y orden, y puedes re-editar.
- **Calidad:** alta. **Eficiencia:** media. **¿Cruza?** Parcial: en modo `closestPoint` hereda el riesgo de proximidad; `vertexId` exige misma topología.
- **Corrección de atribución:** tu `skin_manager_ng.py` usa **`VertexTransferMode.vertexId`** (por índice de vértice, dependiente de topología/orden), **no por UV**. Sí usa `InfluenceMappingConfig.transfer_defaults()` con `use_name_matching`. El transfer topology-independent por UV vive en `auto_skin_transfer.py`, no aquí.
- **Encaje:** estandariza: pinta y limpia el proxy por capas → transfiere con `vertexId` si la topología coincide, `closestPoint` (+ máscaras por isla) si no. Un manager guarda capas ng (JSON), otro el skin plano `.skc`.

### 4.8 `auto_skin_transfer.py` — UV esqueleto-relativa + KNN + IDW ⚠ **actualmente NO OPERATIVO**

> ⚠ **Roto según el usuario: no lo recomiendes ni lo uses.** Se documenta aquí solo como *técnica*
> (el concepto de transfer por UV esqueleto-relativa es válido). Para transferir de verdad, usa
> **`copySkinWeights -uvSpace -influenceAssociation label`** (§4.7) o el inpainting robusto (§4.9).

- **Qué es:** tu sistema propio de transferir el skin del proxy a la alta **sin depender de topología**, proyectando ambos a un espacio UV relativo al esqueleto y haciendo lookup por KNN + IDW.
- **Cómo funciona:** 5 módulos. `UVMatchingModule` genera el UV set `skinTransfer_UV` (modo skeleton por defecto: U = índice DFS del hueso + t a lo largo del segmento, V = ángulo alrededor del eje; cylindrical/planar de respaldo). `SkinSamplingModule` construye `SkinUVMap` (uv N×2, weights N×J). `JointMappingModule` mapea joints origen↔destino por nombre/proximidad. `WeightProjectionModule` busca los K=4 vecinos en UV y mezcla por distancia inversa (IDW, 1/dist²), renormaliza y aplica con `MFnSkinCluster.setWeights`. `RefinementModule` limita influencias (argpartition), suaviza y da pasadas extra en flex zones. Como la U es esqueleto-relativa, dos partes pegadas en 3D caen en U distinta (huesos distintos) → **no cruza** como el closest-point 3D.
- **Calidad:** alta. **Eficiencia:** alta. **Esfuerzo:** medio. **¿Cruza?** No\*, con un matiz honesto: la separación se garantiza en **U** (huesos distintos), pero dos zonas del **mismo hueso** separadas solo por **V** (cara interna vs externa del muslo, entre dedos de la misma mano) pueden mezclarse porque V es angular y continua. Ahí conviene subir K con cuidado, penalizar saltos de V, o refinar por capas.
- **Límites reales:** depende de un buen mapeo de joints (naming `C_/L_/R_` ayuda); degrada donde el esqueleto es escaso (barriga, mejillas) o en zonas equidistantes entre dos huesos; IDW con K alto puede sobre-suavizar bordes de máscara; requiere numpy en Maya.
- **Cuándo usarlo:** proxy y alta con topología distinta (retopo, resimulado, cambio de resolución) que comparten esqueleto; reusar `.skc` entre personajes de proporciones parecidas.
- **Encaje:** es tuyo y ya versiona por `.skc` (`build_map_from_skc` puede leer sin skin en escena). Mejoras concretas: (1) término anti-cruce en V para manos/muslos; (2) usar `VertexTransferMode.vertexId` de ngSkinTools cuando la topología coincida y reservar este método para topología distinta; (3) cachear `SkinUVMap` por personaje. El clamp de `maxInfluences=4` aquí ya prepara el bake lineal.

### 4.9 Robust Skin Weights Transfer via Weight Inpainting (estado del arte, 2023)

- **Qué es:** transferencia proxy→alta topología-independiente que ataca directamente el problema de **vértices sin correspondencia fiable**: transfiere donde hay match claro y **rellena (inpainting) por difusión** los pesos de los vértices restantes resolviendo un problema tipo Laplace en la malla destino. Funciona incluso con prendas no ceñidas.
- **Cómo funciona:** para cada vértice destino busca el punto más cercano válido en el origen (con umbral de distancia/normal); los que superan el umbral quedan "sin asignar" y se resuelven por un inpainting suave que respeta la conectividad de la malla, evitando los saltos del closest-point crudo.
- **Calidad:** alta. **Eficiencia:** media. **¿Cruza?** No (el inpainting difusivo respeta adyacencia).
- **Encaje:** complemento/competidor moderno de `auto_skin_transfer` y `copySkinWeights` para el paso 3. Hay implementaciones para Maya (comunidad) y código de referencia de los autores (Epic Games). Vale la pena evaluarlo como mejora del transfer en zonas donde tu KNN/IDW deja huecos.

### 4.10 cvWrap — wrap por deformación (GPU, rebindeable)

- **Qué es:** deformador wrap open-source (Chad Vernon) más rápido que el nativo, con implementación GPU, rebindeable y con soporte de blendshapes invertidos front-of-chain. La alta **no tiene skin propio**: la deforma el proxy skinneado.
- **Cómo funciona:** bindea cada vértice de la alta a un triángulo del proxy con coordenadas baricéntricas + offset; al deformar el proxy (skinneado limpio con GVB + ngSkinTools), la alta lo sigue. Como es puramente geométrico, **no reasigna ni cruza influencias**: si el proxy no cruza, la alta tampoco.
- **Calidad:** alta. **Eficiencia:** media (coste por frame). **¿Cruza?** No.
- **Límites reales:** es una capa de runtime, no un skin lineal → no exporta a motor/USD sin hornear; requiere compilar/instalar plugin por versión de Maya; el detalle fino solo aparece si el proxy lo tiene.
- **Encaje:** complemento ideal de AdonisFX: proxy con músculo/piel → alta con cvWrap → Delta Mush opcional → `bakeDeformer` a skin lineal. Como es plugin, ofrécelo como opción con fallback a `proximityWrap`/`copySkinWeights` (coherente con tu estándar de no depender de plugins).

### 4.11 proximityWrap (nativo, Maya 2020+)

- **Qué es:** deformador wrap nativo moderno que deforma la alta según los drivers/proxy cercanos con caída suave por distancia. Sin plugin.
- **Cómo funciona:** cada punto de la alta se influye por los del driver dentro de un radio, con `smoothInfluences`, `falloffScale`, `maxDrivers` y modos (Snap/Rigid/Object).
- **Calidad:** media. **Eficiencia:** media (runtime). **¿Cruza?** Parcial: en zonas cóncavas donde dos superficies del proxy están cerca puede "coger" del driver equivocado si el radio es grande → ajusta `falloffScale`/`maxDrivers`.
- **Límites reales:** **requiere Maya 2020+** (en 2019 o anterior no existe: usa wrap clásico o cvWrap); coste por frame; menos detalle que cvWrap en altas con mucho desplazamiento.
- **Encaje:** opción nativa por defecto para wrap (cumple tu estándar sin plugins). Úsalo sobre proxy y hornea con `bakeDeformer`. Es lo que ya implementa tu `efficient_cloth_skin.py` (proximityWrap → bakeDeformer) para ropa, trasladable al cuerpo.

### 4.12 Wrap clásico (Maya), uvPin / follicle, shrinkWrap (acondicionamiento)

- **Wrap clásico:** la abuela de cvWrap/proximityWrap. Robusto mesh-space ante rotaciones pero lento y pesado. Fallback de compatibilidad; siempre horneable.
- **uvPin / follicle:** no transfieren pesos de un cuerpo entero; **fijan puntos/objetos** a la superficie del proxy por UV. `uvPin` (2020+) devuelve matrices en coordenadas UV → conéctalas a `offsetParentMatrix` (encaja perfecto con tu **rig por matrices**, sin dobles transforms). Úsalo para joints de tweak/detalle o para pegar props, no como transfer de cuerpo.
- **shrinkWrap:** deformador de **acondicionamiento** (proyecta una malla sobre la superficie más cercana de otra). Útil para conformar un proxy genérico a la silueta de la alta *antes* de un transfer por UV/KNN, reduciendo deriva. No mueve pesos.

---

## 5. Familia — Refinado de la deformación

El paso que ya haces con Delta Mush: **no** produce el bind, lo pule. Orden correcto: bind que no cruce → afinado por capas en ngSkinTools2 → suavizado no destructivo (DM/DDM) solo donde comprime → correctivos donde el suavizado aplana → bake. **El refinado no arregla un bind malo:** si el bind cruzó, el DM lo enmascara pero al promediar puede arrastrar aún más la contaminación.

### 5.1 Dual Quaternion / weighted skinning — ataca el candy-wrapper EN EL BIND

- **Qué es:** el propio `skinCluster` tiene `skinningMethod`: `0` = classic linear (LBS), `1` = dual quaternion (DQS), `2` = weight blended (mapa `blendWeights` pintable por vértice). DQS **reduce el candy-wrapper y el colapso de torsión en el propio bind**, sin deformador extra.
- **Cómo funciona:** DQS interpola las rotaciones como cuaterniones duales, evitando el colapso de volumen del LBS en rotaciones grandes (muñeca, antebrazo, hombro). El modo weighted decide DQ vs lineal por vértice con un mapa pintable.
- **Por qué importa aquí:** reducir los artefactos en el bind significa **menos iteraciones de Delta Mush** después = menos aplanado de volumen. Es una palanca *antes* del refinado, no solo enmascararlo con DM.
- **Calidad:** media-alta. **Eficiencia:** alta. **¿Cruza?** No.
- **Límites reales:** DQ puede **hinchar/abultar** en articulaciones; sus `blendWeights` hay que pintarlos; **no bakea 1:1 a lineal** (muchos motores solo garantizan LBS) → `bakeDeformer`/`dm2skin` lo aproximan por muestreo, y el residuo de twist se compensa con twist joints bien distribuidos (encaja con tu rig por matrices) + correctivos.
- **Encaje:** combina por zonas (DQ/blend en muñecas/hombros con torsión, lineal + DM en el resto). Fija `skinningMethod` en el `.skc` y documenta la decisión.

### 5.2 Delta Mush (clásico, iterativo)

- **Qué es:** deformador que suaviza el resultado del skin promediando iterativamente las posiciones (smooth Laplaciano) y devolviendo un delta precalculado en reposo, quitando artefactos del LBS (candy-wrapper, colapsos, superficie hervida). Tu refinado actual.
- **Cómo funciona:** en bind guarda, por vértice, `delta = posición original − posición suavizada` en un frame local (tangente/normal/binormal del 1-anillo). En pose aplica N iteraciones de smooth sobre el skin y re-suma el delta reconstruyendo el frame → suavidad del Laplaciano + silueta de detalle. Nodo nativo `deltaMush` (desde 2016) con `smoothingIterations`, `smoothingStep`, `distanceWeight` y `weightMap` pintable.
- **Calidad:** media-alta. **Eficiencia:** media (coste por frame ∝ iteraciones × vértices). **¿Cruza?** Parcial (enmascara, no cura).
- **Corrección importante sobre qué preserva:** Delta Mush **preserva el DETALLE de superficie de la pose de reposo** (vía deltas), **no el volumen**. Al contrario: el suavizado Laplaciano tiende a **perder volumen** en flexiones fuertes ("derrite" zonas). La conservación de volumen real requiere músculo/correctivos, no Delta Mush.
- **Límites reales:** con muchas iteraciones aplana y come detalle (redondea nudillos); no genera arrugas ni tensión; sensible a topología sucia; **no corrige cruces graves**, solo los disimula.
- **Encaje:** deformador POST al final de la cadena, **después** del skinCluster y de los músculos/AdonisFX (no antes, o suavizarás la sim). Píntale el `weightMap` para limitarlo a zonas de compresión (codo/rodilla interior, ingle, axila) y dejar fuera cara/manos. Guarda el skin base en SkinManager antes de meter DM. Ordénalo para que evalúe en GPU (ver Wardlaw sobre deformation layering).

### 5.3 Direct Delta Mush (DDM)

- **Qué es:** reformulación del Delta Mush (Le & Lewis, 2019) que **precomputa** el suavizado como matrices por vértice, evaluándose en una sola operación directa (sin iterar por frame), apta para tiempo real y para bakear.
- **Cómo funciona:** colapsa el operador de smoothing (matriz de vecindad elevada a N iteraciones) en una combinación cerrada de las transformaciones de las influencias y la vecindad. Variantes v0..v4 troquelan precisión vs memoria/cómputo.
- **Calidad:** alta. **Eficiencia:** alta. **¿Cruza?** Parcial (hereda el límite conceptual del DM).
- **Corrección de matiz:** DDM **aproxima** el resultado del DM iterativo, **igualándolo o mejorándolo en las variantes de más calidad** (v3/v4), con un trade-off precisión/memoria por variante. No está garantizado "idéntico"; v0 es la más tosca.
- **Límites reales:** **no es nativo en Maya** → dependes de un plugin/nodo custom de la comunidad (auditar mantenimiento y versión; ninguno es oficial de Autodesk); coste de memoria alto en variantes de calidad; sigue siendo suavizado (no crea arrugas ni cura un bind que cruza); recomputar si cambia la topología/bind.
- **Encaje:** sustituto directo del DM cuando el frame-rate importe, o base estable para hornear a skin lineal. Para export a motor que solo acepta LBS, igual necesitas hornear; DDM brilla en pipeline de cine/Maya interno.

### 5.4 Tension deformer / Tension Map

- **Qué es:** refinado dirigido por el **estiramiento/compresión** de la malla: mide arista a arista cuánto se alarga/encoge respecto al reposo y usa ese valor para suavizar o disparar un correctivo donde hay tensión.
- **Cómo funciona:** ratio de longitud de aristas del 1-anillo entre malla original y deformada (>1 estiramiento, <1 compresión). El **deformador nativo Tension de Maya** relaja donde se estira (complementa al DM, que trabaja mejor en compresión). El **nodo comunitario `TensionMap`** emite el ratio como colorSet/atributo para usarlo como máscara pintable (pesar un DM, disparar un blendshape de arrugas, alimentar shading).
- **Correcciones:** **no existe** un nodo `brStressMap` —braverabbit (prefijo `br`) no publica ningún stress/tension map (sus nodos son `weightDriver` y `brSmoothWeights`). El nodo `TensionMap` de la comunidad es de **MoonShineVFX**. El deformador Tension y Bake Deformer se introdujeron en **Maya 2017 Update 3**; no atribuyas un "originalGeometry desde 2020".
- **Calidad:** media. **Eficiencia:** media. **¿Cruza?** No.
- **Límites reales:** solo reacciona a estiramiento local de aristas (no entiende anatomía); puede introducir hervido si se abusa; por sí solo no arregla nada, es un modulador/medidor.
- **Encaje:** alimenta un `weightMap` que pesa tu Delta Mush o dispara correctivos de `corrective_blendshape_manager`. Con AdonisFX, deriva la tensión de la piel simulada para modular arrugas.

### 5.5 Afinado por capas en ngSkinTools2 (relax/smooth/mirror/flood no destructivo)

- **Qué es:** refinado manual **no destructivo**: descompone el skin en capas (estilo Photoshop) con máscaras e influencias por capa, con smooth/relax **real** (promedia pesos por **adyacencia de malla**, no por distancia) y mirror no destructivo. La herramienta para **afinar**, no para inicializar.
- **Cómo funciona:** cada capa guarda pesos e influencias; el smooth promedia los pesos de vértices **adyacentes en la malla** (conectividad real) → reparto anatómicamente coherente, no por distancia euclídea. El mirror trabaja sobre un buffer separado. API: `ngst_api` (`layers.init_layers`, `Layer.add`, `set_weights` por logical index, `configure_mirror`).
- **Calidad:** alta. **Eficiencia:** alta. **Esfuerzo:** alto (manual). **¿Cruza?** No (el smooth por adyacencia respeta la anatomía).
- **Punto crítico para tu queja:** **no uses su "assign closest joint" como inicializador** —es exactamente el closest-joint que te cruza. Inicializa con GVB y usa ngSkin **solo** para afinar por capas encima. Al terminar, aplana capas y guarda en SkinManager.
- **Límites reales:** trabajo manual; el relax es smooth de **pesos**, no reconstruye volumen como el DM (combínalo con DM/DDM para artefactos globales de silueta).
- **Nota de licencia (actualizada):** desde la **v2.4.0 (mayo 2025), ngSkinTools2 es GRATUITO**, incluido uso comercial, y se eliminó la gestión de license keys. El consejo de hornear a un skinCluster plano al final sigue siendo válido **por rendimiento/portabilidad e independencia de plugin** en render/anim, **no por coste de licencia**.
- **Encaje:** ya integrado (`skin_manager_ng.py`). Úsalo para separar a mano las zonas que aún duden tras el GVB (entrepierna, axila, cuello) con capas + máscaras, y para el mirror final L/R. Complemento: **`brSmoothWeights`** (braverabbit, gratuito) para flood/smooth por topología respetando `maxInfluences`.

---

## 6. Familia — Bake / eficiencia final

Convierte un resultado rico (DM, wrap, correctivos, incluso sim) en un `skinCluster` **lineal** barato, normalizado y con `maxInfluences` acotado, exportable a motor/USD. Clave: no exportas el deformador, exportas los **pesos** que reproducen su resultado. Solo se hornea bien lo que es **función de la pose del esqueleto**; lo dinámico (jiggle, colisión, inercia, sim de AdonisFX) **no** se hornea a skin lineal por definición, solo se aproxima por pose con correctivos o se deja como capa de runtime.

### 6.1 dm2skin (Delta Mush → skin por optimización)

- **Qué es:** optimizador (numpy + scipy) que calcula los pesos de skin lineal que mejor reproducen el resultado del Delta Mush en un conjunto de poses, **sin añadir huesos**, sobre el mismo esqueleto.
- **Cómo funciona:** partes de un **skinCluster inicial existente** + la malla con Delta Mush + poses de muestreo que ejercitan cada articulación. Para cada vértice resuelve por mínimos cuadrados (con bounds y suma=1) los pesos que, aplicados por LBS con las matrices de los joints en cada pose, minimizan la distancia al objetivo mushed, con clamp de `maxInfluences`.
  - **Corrección:** no requiere partir de "una influencia por vértice"; optimiza desde **cualquier skinCluster inicial** hacia el objetivo mushed. (Verifica el README de `duncanskertchly/dm2skin`.)
- **Calidad:** alta. **Eficiencia:** alta. **¿Cruza?** **Parcial**, no "no" rotundo: el no-cruce lo garantiza el **binding volumétrico de origen** y el **acotado de influencias candidatas por región** antes de optimizar; si el set de influencias no está acotado, dm2skin puede heredar el sangrado del DM. Marca "no, **solo si** el set de influencias por vértice está acotado a la región".
- **Límites reales:** depende totalmente del set de poses (articulaciones no ejercitadas quedan mal); solo reproduce lo que el DM produce (función suave de la pose; twist/doble-bisagra que necesitan más huesos dejan residuo); nada dinámico se hornea; el repo es antiguo (numpy/scipy empaquetados, pensado para Maya 2016) → puede requerir port a Python 3.
- **Encaje:** cierre de tu flujo actual: GVB → ngSkin → `auto_skin_transfer` → Delta Mush → **dm2skin** → `.skc` versionado en SkinManager → `model_checker`. Mejor hornear en el proxy/media res y transferir si la alta es muy densa.

### 6.2 bakeDeformer nativo (Maya 2017 Update 3+)

- **Qué es:** comando nativo que aproxima **cualquier cadena de deformadores** (DM, wrap/proximityWrap, blendshapes, lattice) a un `skinCluster` lineal por mínimos cuadrados, con `maxInfluences` objetivo. Sin plugins externos.
- **Cómo funciona — corrección clave del mecanismo:** bakeDeformer **NO toma un frame range que tú keyframeas**. **Auto-genera su propio set de ejemplos articulando el esqueleto por su rango de movimiento (ROM)** y resuelve el problema de mínimos cuadrados sobre esas poses auto-generadas. Esa es la diferencia práctica con dm2skin (donde sí keyframeas tú las poses extremas).
  - **Consecuencia importante:** solo captura deformación que sea **función de la pose del esqueleto**. Es "agnóstico al deformador" **solo si** esos deformadores están gobernados por los joints. Un wrap driveado por una malla animada independiente, o blendshapes disparados por controles que no son joints, **no** se verán reflejados al mover solo el esqueleto.
- **Requisito operativo:** la malla destino debe estar **ya bindada** a los mismos joints; bakeDeformer **optimiza los pesos de un skinCluster existente**, no crea el bind desde cero.
- **Calidad:** alta. **Eficiencia:** alta. **Esfuerzo:** bajo. **¿Cruza?** Parcial: si le dejas elegir libremente entre huesos vecinos puede meter una influencia anatómicamente equivocada y **reintroducir cruce** que el GVB había evitado → acota las influencias por región.
- **Límites reales:** aproximación lineal (pierde no-lineal fuerte); nativo solo desde Maya 2017 U3; históricamente con bugs por versión → valida siempre.
- **Encaje:** consolidador final sin dependencias (cumple tu política sin plugins): proxy limpio → wrap/DM → bakeDeformer con `maxInf` acotado → `.skc` → `model_checker`. Ya lo usa tu `efficient_cloth_skin.py`.

### 6.3 Dem-Bones / SSDR (descomposición example-based)

- **Qué es:** dada una **secuencia** de malla animada (cache, Alembic, sim), descompone la deformación en un conjunto de **huesos** (transformaciones rígidas) + pesos LBS sparse que la reconstruyen. A diferencia de dm2skin/bakeDeformer, **puede inventar huesos auxiliares** para capturar lo que el esqueleto base no representa.
- **Cómo funciona:** optimización con restricciones (pesos convexos ≥0 suman 1, sparse por `maxInfluences`, rotaciones ortogonales) resuelta por descenso por coordenadas en bloque, alternando resolver transformaciones de huesos y resolver pesos. Puede partir de un esqueleto existente ("bind to existing joints") + huesos extra.
- **Correcciones de atribución:**
  - El algoritmo base es **SSDR — "Smooth Skinning Decomposition with Rigid Bones", de Binh Huy Le & Zhigang Deng (SIGGRAPH Asia 2012)**. **No** es "Le & Lewis" (ese par es el de *Direct Delta Mush*, 2019). Es fácil cruzar la autoría porque Binh Le firma ambos.
  - **Dem-Bones (Electronic Arts)** es una **librería C++ + ejecutable de línea de comandos**, implementación robustecida de esa familia. La integración en Maya/Houdini/Blender es vía **wrappers/ports de la comunidad**, no plugins oficiales de EA.
- **Calidad:** alta. **Eficiencia:** alta. **¿Cruza?** Parcial.
- **Límites reales:** añade huesos **matemáticos** (no anatómicos) que hay que integrar y drivear; requiere una secuencia representativa; los pesos pueden ser menos editables a mano; lo dinámico solo se aproxima pose a pose.
- **Encaje:** el borde **sim → rig**: cachea la piel/músculo de AdonisFX, corre Dem-Bones para obtener joints+pesos, reimporta como skinCluster + joints extra en tu grafo de matrices, guarda `.skc`. Estándar de facto para el bake a skin portable (USD/juego) desde deformación arbitraria.

### 6.4 Maya ML Deformer (nativo, 2024+) — capa de runtime barata

- **Qué es:** entrena una red que reproduce la deformación rica (incluida buena parte del **residuo no-LBS** y hasta el look de una pose de sim) y se evalúa barata en runtime. Nodos nativos desde Maya 2024. También hay aproximadores ML en plugins de sim (AdonisFX incorpora herramientas ML; ex-Ziva RT/ZRT).
- **Cómo funciona:** aprende, a partir de ejemplos (geometry-cache driven), un mapeo pose→deformación que aproxima el deformador caro.
- **Calidad:** alta. **Eficiencia:** alta. **¿Cruza?** No (aprende la deformación objetivo).
- **Límites reales:** su salida **no es un skinCluster LBS puro** → igual que DDM, **no exporta a motores que solo aceptan skin lineal**; caja negra, difícil de versionar de forma determinista; requiere entrenamiento.
- **Encaje:** competidor moderno directo del bake para el residuo que el lineal no captura; lístalo junto a DDM como "capa de runtime barata" cuando el destino es Maya/cine, no motor LBS.

### 6.5 Optimización estándar del skinCluster (prune / clamp / normalize / remove unused) — acabado que SIEMPRE se aplica

- **Qué es:** el acabado tras cualquier bake: podar pesos minúsculos, limitar influencias por vértice al presupuesto (4/8 según motor), renormalizar a suma=1, quitar influencias no usadas.
- **Cómo funciona:** (1) `prune` (`skinPercent -pruneWeights`, umbral ~0.005); (2) `clamp maxInfluences` (conservar las N mayores); (3) `normalize` (`skinPercent -normalize`); (4) `removeUnusedInfluences`. Determinista y automatizable por módulo.
- **Calidad:** media (no añade calidad, limpia). **Eficiencia:** alta. **¿Cruza?** No.
- **Límites reales:** un clamp agresivo puede introducir facetas donde había reparto suave entre muchas influencias (revisa transiciones); el prune con umbral alto recorta aportes legítimos en blending; la renormalización desplaza ligeramente respecto al deformador original.
- **Encaje:** es tu paso de QC: función reutilizable del autorig al final del build de skin de cada módulo, antes de escribir el `.skc` y validar con `model_checker` (normalizado=1, `maxInf`≤N, sin influencias huérfanas, sin pesos negativos).
- **IO alternativo:** para portabilidad sin depender del formato propio `.skc`, considera **`deformerWeights` nativo** (Deform > Export/Import Weights, XML) como estándar de intercambio.

---

## 7. Familia — Correctivos para que "quede bien"

Se montan **encima** del skin base (LBS/DQ + Delta Mush) para recuperar el volumen que el lineal pierde en las articulaciones. Anatomía común: un **lector de pose** (ángulo/swing-twist/matriz local del joint, o tensión) + un **corrector** (blendshape, helper joint, o activación de músculo). El coste real no es el runtime, es la **autoría**. Orden recomendado: cierra el skin → helper joints pose-driven para el 80 % del volumen → blendshapes correctivos (disparados por RBF) para el 20 % que el joint no alcanza → combos/in-betweens → sim solo en héroes o para hornear.

### 7.1 Blendshapes correctivos front-of-chain (esculpir en pose + invertir)

- **Qué es:** un blendshape esculpido a mano que arregla la forma en una pose concreta (codo a 120°) y se aplica como delta. Como se esculpe sobre el modelo ya deformado, hay que **invertir** la deformación para obtener el target neutro.
- **Cómo funciona:** pones la pose → esculpes → inviertes el delta con `invertShape` (nativo desde Maya 2016.5) o `cvShapeInverter` → conectas a un blendShape y disparas su peso por un lector de pose (SDK/RBF/poseInterpolator). El delta es local y aditivo.
- **Calidad:** alta. **Eficiencia:** alta (runtime). **Esfuerzo:** alto. **¿Cruza?** No.
- **Corrección de orden en la cadena** (el razonamiento habitual está invertido): si el correctivo va **front-of-chain** (aguas arriba del skin) y el Delta Mush evalúa **después** (back of chain), el DM **sí** procesa y suaviza el resultado del blendshape, comiéndose el detalle. Para que el DM **no** relaje la corrección:
  - **(a)** coloca el correctivo **aguas abajo del Delta Mush** (back of chain), **o**
  - **(b)** si lo dejas front-of-chain, esculpe/invierte **con el Delta Mush ya presente** en la cadena para precompensar su suavizado. Ojo: **`invertShape` solo invierte a través del `skinCluster`, no del `deltaMush`**.
- **Límites reales:** autoría cara; las correcciones no combinan bien entre sí (de ahí los combos); **muy frágil ante cambios de modelo** (topología/proporciones rompen los targets); no aporta dinámica.
- **Encaje:** el blendShape va sobre la malla de alta; el peso lo maneja el lector de pose. Integra con `corrective_blendshape_manager.py` y con SkinManager. Si esculpes en el proxy, transfiere el delta con `auto_skin_transfer`/wrap. Herramientas: `invertShape`, `cvShapeInverter`, **SHAPES** (braverabbit, crea nodos Maya estándar).

### 7.2 Pose Space Deformation (PSD) y solvers RBF (weightDriver / poseInterpolator)

- **Qué es:** el marco que unifica blendshapes y skeleton-driven deformation: cada corrección es una muestra (pose → delta) y una interpolación de datos dispersos (**RBF**) mezcla suavemente entre poses. Donde el SDK interpola 1D lineal, PSD interpola N-dimensional con falloff radial.
- **Cómo funciona:** defines un espacio de poses (DOF de uno o varios joints), esculpes en poses clave, y en runtime el solver interpola el delta correcto. Lectores/solvers: **`weightDriver`** (braverabbit, modos RBF y vector-angle/cone), **`poseInterpolator`** nativo de Maya (Pose Editor), o `poseDeformer` (Comet).
- **Calidad:** alta. **Eficiencia:** alta. **Esfuerzo:** alto. **¿Cruza?** No.
- **Aclaración weightDriver vs poseInterpolator:** ambos usan **RBF** y tienen **calidad de deformación equivalente**; la diferencia real es de **ergonomía/tooling** (SHAPES vs Pose Editor) y control de kernel, no de calidad. El `poseInterpolator` nativo tiene la ventaja de **cero plugins** (data-driven nativo, serializable). El doc de Epic "Authoring RBF in Maya" describe un **workflow** RBF; MetaHuman usa su **propio** solver RBF (RBFSolver/DNA), no corre sobre el `poseInterpolator` de Maya.
- **Clave en tu rig por matrices:** alimenta el lector con la **descomposición de la matriz LOCAL del joint (swing/twist)**, no con eulers globales, para evitar gimbal/flip.
- **Límites reales:** requiere buen parametrizado del espacio de poses; muchas muestras = coste de autoría y riesgo de overshoot/ondas; `weightDriver` es plugin compilado (el repo original de IngoClemens está discontinuado → usa la build de SHAPES o el fork `mGear_weightDriver`); sigue siendo estático (sin inercia).
- **Encaje:** creas los solvers por código y guardas las poses como datos versionados. Se integra tras el bake base y con `corrective_blendshape_manager.py`.

### 7.3 Combination shapes e in-betweens

- **Qué es:** correcciones de segundo orden. Cuando dos correctivos se activan a la vez (hombro arriba + brazo adelante), su suma lineal produce una forma mala; la combo shape solo se activa cuando **ambos** drivers están activos y arregla ese residuo. Los in-betweens hacen lo mismo en 1D.
- **Cómo funciona:** el peso de la combo = producto (AND suave) de los pesos base; su delta = diferencia entre lo deseado en la pose combinada y lo que la suma de los base ya aporta. SHAPES lo automatiza (nodo `combinationShape` nativo).
- **Calidad:** alta. **Eficiencia:** media. **Esfuerzo:** alto. **¿Cruza?** No.
- **Límites reales:** **explosión combinatoria** (O(N²) combos, O(N³) triples); cada cambio en un shape base obliga a revisar sus combos; la parte más cara y frágil. Haz solo las combos que realmente se ven.
- **Encaje:** hombro, cadera, muñeca, cuello, raíz de dedos. Versiona combos como parte del set de correctivos del módulo.

### 7.4 Set Driven Keys por ángulo / cone readers (vector-angle)

- **Qué es:** el corrector más barato: una curva de driven key que dispara un shape o mueve un helper joint según un ángulo o un lector de cono. Es PSD degenerado a 1D, sin plugin.
- **Cómo funciona:** mides un ángulo (o proyectas un vector del joint contra un eje de referencia = cone reader, para evitar eulers) y guías con ese valor 1D el peso de un shape o la traslación de un bulge joint.
- **Calidad:** media. **Eficiencia:** alta. **Esfuerzo:** bajo. **¿Cruza?** No.
- **Límites reales:** solo 1D → no captura acoplamiento entre ejes; en articulaciones multi-DOF apilas muchos SDK que interfieren (lo que RBF/PSD resuelve); usa siempre lectura por vector/matriz, no eulers.
- **Encaje:** primera capa correctiva barata (bulge de bíceps por flexión de codo, pliegue de rodilla) antes de invertir en RBF/shapes. Trivial de generar por código en tu autorig.

### 7.5 Helper joints pose-driven (bulge/twist/half joints)

- **Qué es:** en vez de un blendshape, corriges añadiendo **joints extra** al skin cuya transformación la dispara un RBF/SDK. El volumen lo recupera el propio skin al mover ese joint.
- **Cómo funciona:** helper joint pintado (con pesos de blend); un pose-reader conduce su traslación/escala/rotación. Es PSD donde el "delta" es una **transformación de joint**, no una shape, así que se deforma correctamente al seguir animándose.
- **Calidad:** media-alta. **Eficiencia:** alta. **Esfuerzo:** medio. **¿Cruza?** Parcial: si el helper pisa otra zona anatómica, sus pesos de blend pueden reintroducir cruce.
- **Límites reales:** hereda las limitaciones del skin (no da pliegues finos ni silueta exacta como un shape esculpido → para héroe se combina con shapes); pintar bien los pesos de blend es delicado; añade joints al conteo (relevante en juegos).
- **Encaje:** ideal en tu rig por matrices: se generan por módulo, se conducen por matrices/RBF, sobreviven mucho mejor a cambios de modelo que los blendshapes (se re-pintan, no se re-esculpen), y el bake final (dm2skin/bakeDeformer) los absorbe si el destino es juego. Cubren el 80 % del volumen.

### 7.6 Correctivos por tensión / strain de la malla

Ver **5.4** (Tension deformer / TensionMap). Como corrector, la tensión enmascara/dispara un blendshape de arrugas donde hay compresión (codo interior, axila, ingle, cuello) o modula el envelope de un DM. Automático (data-light) pero menos controlable artísticamente; complemento de los correctivos por pose, no sustituto.

### 7.7 Correctivos volumétricos por simulación de músculo/piel

- **Qué es:** el volumen lo **genera** una simulación en vez de esculpirlo: músculos volumétricos que se contraen, fascia/grasa que desliza, piel que reacciona. Máxima fidelidad porque el volumen y el deslizamiento salen de física.
- **Opciones:**
  - **AdonisFX (Inbibo):** framework de **anatomía digital** con solvers de **músculo, grasa y tejido/piel** (soft tissue), sucesor de facto de Ziva VFX. Deformers: `AdnMuscle`, `AdnRibbonMuscle`, `AdnSkin` (piel que sigue targets internos vía constraints pintables). **No es un solver de tela/cloth** —para tela iría nCloth/Qualoth/Marvelous/Vellum. **AdonisFX 2.0 (2026)** añadió self-collision y solver anisótropo, y corre también en **Houdini**, no solo Maya.
  - **Maya Muscle nativo (`cMuscle`):** capa correctiva volumétrica/jiggle **sin plugin de terceros**, alternativa más ligera.
  - **Ziva VFX:** el otro gran sim volumétrico de referencia (contexto/comparación; venta descontinuada).
- **Cómo funciona:** sobre el skin base defines la pila de deformers; la activación de músculos se conduce por pose (RBF/SDK desde los joints) y la sim resuelve dinámica, deslizamiento y preservación de volumen frame a frame.
- **Calidad:** alta. **Eficiencia:** baja (sim, no interactiva; necesita cache). **Esfuerzo:** alto. **¿Cruza?** No.
- **Límites reales:** coste de setup y cómputo alto; no apto para juego ni iteración rápida sin hornear; dependencia de plugin/licencia; determinismo requiere cuidado (substeps, colisiones).
- **Encaje:** tu stack de músculo/piel. Conduce activaciones desde los joints por RBF; para producción eficiente **cachea o hornea** la sim a shapes/PSD (ver 7.8). Delta Mush como suavizado final. **Ojo:** `AdnSimshape` es un deformer de **simulación FACIAL** (calcula activación por vértice para emular el cambio de rigidez de la piel de la cara), **no** una herramienta de horneado de sim muscular de cuerpo a shapes; no lo metas en el flujo de bake de correctivos de cuerpo.

### 7.8 Horneado de correctivos/sim a PSD-shapes (pose-sweep)

- **Qué es:** método puente para dejarlo eficiente: capturas un comportamiento caro (sim de AdonisFX, o un rig con muchos deformers) como un set de blendshapes correctivos disparados por RBF, para reproducir ~la misma forma con LBS + shapes ligero.
- **Cómo funciona:** barres el rig por poses representativas (swing/twist de cada articulación y combinaciones); en cada pose capturas la malla del sistema caro, restas la contribución del skin base + correctivos presentes, e **inviertes el residuo** a un target front-of-chain (`invertShape`); conectas cada target a un `poseInterpolator`/`weightDriver`.
- **Precisión de herramientas:** el **bake a la BASE** (skin lineal, pesos) lo hacen `bakeDeformer`/`dm2skin`; el **bake a shapes correctivos** es el **pose-sweep + invertShape + conexión RBF**. Son dos deliverables distintos: `bakeDeformer`/`dm2skin` **no** producen targets PSD.
- **Calidad:** alta. **Eficiencia:** alta. **Esfuerzo:** alto. **¿Cruza?** No.
- **Límites reales:** solo captura lo que muestreas; comportamiento **dinámico** (inercia, jiggle) **no** se reproduce con shapes estáticos; elegir el set de poses es un arte (pocas = subajuste, muchas = coste/overshoot); rehacer si cambia el modelo/rig; requiere buen tooling propio.
- **Encaje:** cierra el flujo (proxy → pintar → transferir → refinar → **correctivos** → bake). Automatizable en tu build data-driven, versionable con SkinManager + set de targets.

### 7.9 Jiggle / dinámica secundaria

Para la **inercia** que ningún shape estático da (pecho, barriga, grasa): `jiggle` deformer nativo, o dinámica driveada por nCloth/Vellum sobre un proxy. Es capa de runtime (o se aproxima/hornea con ML deformers, ver 6.4). No exportable a LBS puro sin perder la dinámica.

---

## 8. Receta recomendada end-to-end

Flujo de estudio para un proxy skinning del cuerpo **eficiente y que quede bien**. Regla de oro que atraviesa todo: **el cruce se resuelve en el paso 1 (binding volumétrico), no en el refinado.** El Delta Mush tapa ruido, no arregla un peso que ya cogió la pierna equivocada.

1. **QC de malla previo.** `model_checker`: malla cerrada, normales hacia fuera, UVs coherentes, topología limpia. GVB y los transfers dependen de esto.

2. **Construye el proxy low-res.** Retopo limpia (quads, edge loops en codo/rodilla/hombro/cadera/cuello), o proxy segmentado por islas si el cruce es tu problema central. Comparte esqueleto con la alta.

3. **Binding volumétrico en el proxy (NO closest-joint).** `cmds.skinCluster(tsb=True, bindMethod=3, mi=4)` (Geodesic Voxel). Ajusta la **resolución de vóxel por optionVar** antes del bind y súbela en dedos/orejas/axila. Alternativas: heat map (`bindMethod=2`) si quieres suavidad extra; BBW offline para máxima calidad; cápsulas (Interactive Bind) para delimitar a mano zonas conflictivas. Considera `skinningMethod=dualQuaternion` (o weighted por zonas) en muñecas/hombros con torsión para reducir el candy-wrapper desde el bind.

4. **Afina con ngSkinTools2 por capas** sobre esa base limpia: smooth por adyacencia, flood, mirror no destructivo, máscaras por región (entrepierna, axila, cuello). **Nunca** su "assign closest joint" para inicializar. Complementa con `brSmoothWeights`. Valida cruces por zona con `proxy_locator.py`. Guarda las capas y el `.skc` en SkinManager.

5. **Transfiere a la alta** con un método consciente de topología/UV (⚠ **NO** `auto_skin_transfer`, está roto):
   - **Por defecto** → **`copySkinWeights -uvSpace <src> <dst> -influenceAssociation label`** (nativo, sin numpy; el UV/label separan las partes → no cruza). Es lo que usa el botón *Proxy Skinning* (`tools/proxy_skinning.py`).
   - Sin UV coherente → `copySkinWeights -surfaceAssociation closestComponent -influenceAssociation label`, o `skincluster_surface.py` (De Boor 2D) sobre una superficie.
   - Topología con huecos difíciles → inpainting robusto (Abdrashitov et al., §4.9).
   - Misma topología → `ngSkinTools2` `VertexTransferMode.vertexId`.
   - Necesitas que la alta siga al proxy/sim en vivo antes de hornear → **cvWrap** (plugin) o **proximityWrap** (nativo 2020+).
   - **Nunca** `copySkinWeights closestPoint/closestComponent` sin más entre partes que se tocan: reintroduce el cruce.

6. **Redistribuye/suaviza zonas tubulares** con `skincluster_surface.py` (De Boor 2D sobre NURBS) en cuello/torso/cola/labios: gradiente continuo determinista antes del Delta Mush.

7. **Refina con Delta Mush** (o **DDM** si el frame-rate importa), **después** del skin y de los músculos/AdonisFX, con `weightMap` limitado a zonas de compresión. Recuerda: preserva **detalle de superficie**, no volumen (usa DQ/correctivos/músculo para el volumen). Tension/TensionMap para modular arrugas.

8. **Hornea a skin lineal** para eficiencia y portabilidad:
   - **dm2skin** para reproducir tu Delta Mush con el esqueleto actual (acota las influencias por región antes de optimizar).
   - **bakeDeformer** (nativo) para colapsar cualquier cadena; recuerda que **auto-genera las poses por ROM** y solo captura lo que es función de la pose del esqueleto; el destino debe estar ya bindado.
   - **Dem-Bones/SSDR** si vienes de una sim/cache y aceptas huesos auxiliares.
   - **ML Deformer / DDM** como capa de runtime barata si el destino es Maya/cine (no exportan a LBS puro).
   - Termina **siempre** con prune / clamp `maxInfluences` / normalize / removeUnused → `model_checker` → `.skc` versionado en SkinManager (o `deformerWeights` XML para portabilidad).

9. **Correctivos en zonas problema** (hombro, cadera, muñeca, ingle, axila): helper joints pose-driven para el grueso del volumen + blendshapes correctivos (esculpir en pose + `invertShape`) para el detalle, disparados por **RBF** (`poseInterpolator` nativo o `weightDriver`) leyendo la **matriz local descompuesta** del joint (swing/twist), no eulers. Combos/in-betweens solo donde se vean. Coloca el correctivo **back-of-chain respecto al Delta Mush** (o esculpe con el DM presente) para que no se lo coma. Para héroe con sim de AdonisFX, hornea la sim a PSD-shapes por pose-sweep. Jiggle/dinámica para la inercia.

---

## 9. Recursos
> **Antes de pasar un enlace al usuario, verifícalo** con `web_search`/`web_fetch`. Varias URLs
> van marcadas como *"buscar por título"*, *"adaptar versión"* o *"verificar"* porque no había
> enlace fiable o dependen de la versión de Maya. No des por buena una URL sin comprobarla.


> URL solo con alta confianza. Cuando no la fijo, describo el recurso sin inventar el enlace: búscalo por título/dominio.

### Docs (Autodesk / DCC / plugins)

- **Maya `skinCluster` — flag `bindMethod`.** Valores reales: `0`=closest distance, `1`=closest distance in hierarchy, `2`=surface heat map diffusion, `3`=geodesic voxel. **No existe `bindMethod=4`.** help.autodesk.com (Command Reference de tu versión; ver también "Bind methods for smooth skinning").
- **Maya Help — Geodesic Voxel binding.** Requisitos (joints dentro del volumen, normales hacia fuera) y opciones de resolución. URL de ejemplo (adaptar versión): `https://help.autodesk.com/cloudhelp/2019/ENU/Maya-CharacterAnimation/files/GUID-5EFDB81B-E332-4D6C-B1BB-0B989AD2F2C7.htm`
- **Maya Help — Interactive Skin Bind.** Manipuladores de volumen (cápsulas). Buscar en help.autodesk.com.
- **Maya `copySkinWeights` — Command Reference.** Flags `surfaceAssociation` (closestPoint/rayCast/closestComponent), `influenceAssociation` (closestJoint/closestBone/label/name/oneToOne), **`uvSpace <srcUVSet> <dstUVSet>`**. (Recuerda: `sampleSpace` solo es world/local; el UV=2 es de `transferAttributes`.)
- **Maya — Set joint labels** (Skin > Edit Influences > Set Labels): requisito para `influenceAssociation='label'`.
- **Maya Help — Proximity Wrap deformer** (Maya 2020+): `falloffScale`, `smoothInfluences`, `maxDrivers`. Buscar "proximityWrap Maya".
- **Maya Help — Delta Mush / Tension deformer.** `smoothingIterations`, `distanceWeight`, `weightMap`. Tension deformer + Bake Deformer llegaron en **Maya 2017 Update 3**. Ej.: `https://help.autodesk.com/view/MAYAUL/2022/ENU/?guid=GUID-A8FB24DA-14C3-4230-A6B3-D4FACCB3A3B5`
- **Maya Help — `bakeDeformer` / Bake Deformer tool.** `https://help.autodesk.com/cloudhelp/2018/ENU/Maya-Tech-Docs/Commands/bakeDeformer.html` y `https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-DD430C9B-95E7-4EBB-8D2B-A566018B4AC4`
- **Maya Help — Pose Editor / `poseInterpolator`.** `https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-2AB6C4C3-75AC-4094-A65C-C232739AFB30`
- **Maya Help — Blend Shape options** (Front of / After chain, post-deformation). `https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-C954C197-6D56-4EB8-BEA0-70DD1BBBAD6B`
- **Maya Help — Maya Muscle (`cMuscle`)**, **Bake Deformation to Skin Weights**, **Export/Import Weights (`deformerWeights`, XML)**. Buscar en help.autodesk.com.
- **ngSkinTools2 — documentación y API.** `https://www.ngskintools.com/documentation/` — Layers, Mirroring, `api/layers/`, `api/transfer/` (`InfluenceMappingConfig`, `VertexTransferMode`). **Gratuito desde v2.4.0 (2025).** Verifica las rutas exactas contra el sitio antes de fijarlas.
- **Epic Games — Authoring RBF in Maya (MetaHuman docs).** `https://dev.epicgames.com/documentation/en-us/metahuman/authoring-rbf-in-maya` (workflow RBF en Maya; MetaHuman usa su propio RBFSolver, no el `poseInterpolator`).
- **AdonisFX (Inbibo) — Docs.** `AdnSkin`, `AdnMuscle`, `AdnRibbonMuscle` en `https://inbibo.co.uk/docs/adonisfx/` (`AdnSimshape` es **facial**). AdonisFX 2.0 (2026): self-collision, solver anisótropo, Houdini.

### Charlas / artículos prácticos

- **Chris Evans — "Geodesic Voxel Binding in Maya 2015"** (Stumbling Toward Awesomeness): `http://www.chrisevans3d.com/pub_blog/geodesic-voxel-binding-maya-2015/`. Divulgación práctica de un TD; **no es autor del paper** (autores: Dionne & de Lasa).
- **Kiel Figgins — "Painting Weights and Skinning: A Straightforward Approach"** (proxy low-res "sock puppet"): `https://www.3dfiggins.com/writeups/paintingWeights/`. Scripts: `https://www.3dfiggins.com/PublicResources/Scripts/`
- **Chris Lesage — "Using Proxy Geometry For Better Skinning Results"** (Rigmarole): `https://chrislesage.com/character-rigging/using-proxy-geometry-for-better-skinning-results/`
- **Rigmarole Studio — "ngSkinTools Skinning Tips":** `https://rigmarolestudio.com/ngskintools-skinning-tips/`
- **Charles Wardlaw — "Deformation Layering in Maya's Parallel GPU World":** `https://medium.com/@kattkieru/deformation-layering-in-mayas-parallel-gpu-world-15c2e3d66d82`
- **Mason Smigel — "Deformation Cage":** `https://www.masonsmigel.com/post/deformation-cage`
- **lesterbanks** — walkthroughs de Tension deformer / TensionMap node / Bake Deformer tool (buscar por título en lesterbanks.com).
- **EA SEED — "SIGGRAPH 2019: Direct Delta Mush":** `https://www.ea.com/seed/news/siggraph2019-direct-delta-mush`. Charla en vídeo: `https://www.youtube.com/watch?v=T9mCIwxRG2Q`

### Papers

- **Dionne & de Lasa — "Geodesic Voxel Binding for Production Character Meshes"** (Autodesk, **SCA 2013**): `https://dl.acm.org/doi/10.1145/2485895.2485919`
- **Baran & Popović — "Automatic Rigging and Animation of 3D Characters"** (SIGGRAPH 2007, heat weighting): `https://www.cs.toronto.edu/~jacobson/seminar/baran-and-popovic-2007.pdf`
- **Jacobson, Baran, Popović, Sorkine — "Bounded Biharmonic Weights for Real-Time Deformation"** (SIGGRAPH 2011): `https://igl.ethz.ch/projects/bbw/`
- **Mancewicz, Derksen, Rijpkema, Wilson — "Delta Mush: Smoothing Deformations While Preserving Detail"** (Rhythm & Hues, DigiPro 2014): ACM DL, `https://dl.acm.org/citation.cfm?id=2614144`
- **Le & Deng — "Smooth Skinning Decomposition with Rigid Bones" (SSDR)** (SIGGRAPH Asia 2012): `https://binh.graphics/papers/2012sa-ssdr/`. (Base algorítmica de Dem-Bones. **No** confundir con Le & Lewis.)
- **Le & Lewis — "Direct Delta Mush Skinning and Variants"** (SIGGRAPH 2019): `https://binh.graphics/papers/2019s-DDM/` — ACM TOG 38(4) art.113: `https://dl.acm.org/doi/10.1145/3306346.3322982`
- **Lewis, Cordner, Fong — "Pose Space Deformation"** (SIGGRAPH 2000): DBLP `https://dblp.org/rec/conf/siggraph/LewisCF00.html`
- **Kavan, Collins, Žára, O'Sullivan — "Skinning with Dual Quaternions"** (I3D 2007): ACM DL / página de Ladislav Kavan.
- **Abdrashitov, Raichstat, Monsen, Hill, Levin — "Robust Skin Weights Transfer via Weight Inpainting"** (Epic Games, SIGGRAPH Asia 2023 Technical Communications): DOI `10.1145/3610543.3626180`.
- **Shepard (1968) — "A two-dimensional interpolation function for irregularly-spaced data"** (IDW/Shepard, base del blend de `auto_skin_transfer`).
- **Piegl & Tiller — "The NURBS Book"** (algoritmo de De Boor, knot vectors; base de `de_boor_core`).

### Repos / tools

- **`chadmv/cvwrap`** — wrap deformer GPU rebindeable: `https://github.com/chadmv/cvwrap`. Blog: `https://www.chadvernon.com/blog/creating-a-gpu-driven-wrap-deformer-released/`
- **`chadmv/cvshapeinverter`** — invertir shapes a través de la cadena: `https://github.com/chadmv/cvshapeinverter`. Blog: `https://www.chadvernon.com/blog/cvshapeinverter/`
- **`duncanskertchly/dm2skin`** — Delta Mush → skinCluster por optimización (numpy/scipy): `https://github.com/duncanskertchly/dm2skin`
- **`electronicarts/dem-bones`** — skinning decomposition de producción (librería C++/CLI; integración DCC vía wrappers de comunidad): `https://github.com/electronicarts/dem-bones`
- **`TomohikoMukai/ssdr`** y **`dalton-omens/SSDR`** — implementaciones de referencia de SSDR (esta última port a Maya/Python).
- **`WebberHuang/DeformationLearningSolver`** — plugin Maya de descomposición/aprendizaje de deformación desde ejemplos.
- **`zhan-xu/RigNet`** — rigging/skinning neural (SIGGRAPH 2020): `https://github.com/zhan-xu/RigNet`
- **"Robust Biharmonic Skinning Using Geometric Fields" (2024):** `https://arxiv.org/abs/2406.00238`
- **`libigl/libigl`** — geometry processing con `igl::bbw` (binder BBW offline): `https://github.com/libigl/libigl`
- **`pmolodo/Pinocchio`** — heat weighting de referencia: `https://github.com/pmolodo/Pinocchio`
- **Robust Skin Weights Transfer — código de referencia:** repo `rin-23/RobustSkinWeightsTransferCode` y ports para Maya de la comunidad (buscar "maya robust weight transfer"). Verificar mantenimiento antes de integrar.
- **Direct Delta Mush** — reimplementaciones open-source (nodos OpenMaya en GitHub, sin nodo oficial en Maya): auditar versión/mantenimiento.

### Tools comerciales / gratuitas (braverabbit / Ingo Clemens)

- **SHAPES — Blend Shape Editor for Maya:** `https://www.braverabbit.com/shapes/` (crea nodos Maya estándar; gestiona correctivos, combos, in-betweens, drivers).
- **weightDriver (RBF / vector-angle):** `https://braverabbit.gumroad.com/l/weightDriverMaya`. Repo original (discontinuado) `https://github.com/IngoClemens/weightDriver` (wiki con modos RBF/cone). Fork `https://github.com/mgear-dev/mGear_weightDriver`.
- **`IngoClemens/brSmoothWeights`** — smooth de pesos por topología respetando `maxInfluences` (gratuito): `https://github.com/IngoClemens/brSmoothWeights`
- **mGear** — framework modular con helper joints y RBF: `https://github.com/mgear-dev/mgear4`

### Código propio del usuario (repo)

- **`auto_skin_transfer.py`** — `/home/user/autorig_tools/scripts/tools/auto_skin_transfer.py` (UV esqueleto-relativa + KNN/IDW + refinado; 5 módulos).
- **`skincluster_surface.py`** + **`de_boor_core.py`** — `/home/user/autorig_tools/scripts/utils/` (redistribución De Boor 2D desde NURBS, `split_with_surface`).
- **`skin_manager_ng.py`** — `/home/user/autorig_tools/scripts/tools/` (ngst_api, `InfluenceMappingConfig`, `VertexTransferMode.vertexId`, daisy-chain de capas).
- **`skin_manager_api.py`** — `.skc` versionado.
- **`proxy_locator.py`** — `/home/user/autorig_tools/scripts/tools/` (`assign_all_proxy_locators`, QC visual de qué región coge cada control).
- **`model_checker.py`** — QC de malla previo al bind.
- **`corrective_blendshape_manager.py`**, **`matrix_manager.py`** (offsetParentMatrix para uvPin/RBF), **`mesh_data_exporter.py`** (poses de muestreo para el bake).