# Desafíos reales de animación y rigging en producción — Unreal Fest Chicago 2026

**Ponente:** Stéphane Biava (Solutions Architect, Epic Games)
**Vídeo:** https://www.youtube.com/watch?v=XYMad1EutcA
**Contexto:** enfocado a contenido lineal/cinemáticas, pero casi todo aplica a runtime. Muchas features son de **UE 5.8** (y alguna de 5.7).

---

## 1. RIGGING

### 1.1 Precisión de pesos de skinning `[2:09]`
- Si el **editor mesh y el render mesh se ven distintos** (artefactos al renderizar que no ves en el editor), la causa típica es superar el límite de influencias.
- UE maneja por defecto **8 influencias por vértice**. Configurable en **Project Settings** y en el **Skeletal Mesh Editor**.
- Hay un umbral para activar **unlimited bone influences** cuando lo superas.
- En el Skeletal Mesh Editor puedes seleccionar un vértice y **ver cuántas influencias tiene** — si en la zona con artefactos hay más de 8, es eso.
- Checkbox **High Precision Skin Weights** → usa **pesos de 16 bits** en el render mesh (más influencias, respeta el skinning que traes de otro DCC).
- **5.8:** icono de **candado por joint** en el outliner del Skeletal Mesh Editor → **bloquea joints y pesos** para que la auto-normalización NO redistribuya a zonas aleatorias cuando pintas. (Clave al refinar por zonas.)

### 1.2 Optimización de asset `[4:31]`
- **Joints sin uso** (sin skinning, "por si acaso") penalizan rendimiento. **5.8:** right-click → **remove all unused bones** de una vez.
- Si necesitas lógica extra sin ensuciar el asset compartido: **spawnea joints proceduralmente en el Construction Event de Control Rig**.
- Varios skeletal mesh en una escena/plano pesan; vigílalo antes de culpar a otra cosa.
- **Morph targets:** demasiados hunden el rendimiento. Para cinemáticas puedes ir alto (MetaHuman: >800 en cara+cuerpo); para runtime sé comedido. Combinar joints + morphs está bien.
- **5.8:** el Skeletal Mesh Editor permite **crear/gestionar morph targets dentro de UE**, incluyendo **flip y mirror** — sin round-trip al DCC.

### 1.3 Optimización de Control Rig `[7:30]`
- **Execution Stack** = tu mejor amigo: orden real de ejecución del forward solve, qué corre y cuándo.
- **5.7+: Preview Nodes** — como el preview del shader graph: pausas la ejecución en un punto y avanzas con **F10** para ver dónde rompe.
- **Profiling** (microsegundos por nodo/función): actívalo siempre que dudes.
- Regla de oro: **lo que se pueda cachear va al Construction Event**, no al Forward Solve (error habitual: lógica de setup en el solve).
- **For Each** para empaquetar ejecución repetida.
- **Dependency Viewer**: seleccionas un joint/control y ves sus conexiones (grafo read-only — no puedes romper nada). Ideal para heredar el rig de otra persona.
- **Highlight occurrences** (right-click, medio escondido): resalta cuántas veces repites un nodo → la repetición es el enemigo → conviértela en **funciones**.
- Máximo rendimiento: **Rig Units** (nodos en C++) en vez de funciones.

### 1.4 Inline bones (huesos intermedios en cadena) `[11:58]`
- El mannequin resuelve twist/correctivos con **leaf joints** (fuera del flujo jerárquico); sobre eso se montan **ribbon/bendy controls**.
- En contenido lineal suele venir una **cadena real** con huesos intermedios de orientación "rara" → el IK two-bone estándar se confunde (sobre todo la orientación del último item).
- Truco barato: **Full Body IK node** especificando solo los items que quieres + **preferred angles** como pole vector → setup limpio **sin crear una cadena IK adicional**.
- Mensaje general: Control Rig trae toneladas de nodos — reutiliza antes de montar setups custom complejos.

### 1.5 Switch IK/FK `[14:36]`
- Trampa clásica: funciona en el asset de Control Rig y su viewport pero **se comporta distinto en Sequencer** → hay que comunicar ambos.
- El setup simple (retener posición del solver por defecto) da **snaps** en Sequencer.
- Solución: todo **condicionado con booleans** — comprobar el estado del solver activo y **resetear los valores del lado "dormido"** para poder keyearlo.
- Cuidado con **Send Event sin condicionar**: parece que va, pero al mover el body empieza a **temblar y congelarse**.
- Cubierto en detalle en el **Rigging Workshop gratuito (10+ horas)** de Epic.

### 1.6 Deformers (Deformer Graph) desde Control Rig `[16:40]`
- Flujo completo: **Skeletal Mesh Editor** → pintas la zona con **polygroups** (o una skin layer secundaria) → **Deformer Graph** con **kernel nodes** (función del deformer en **HLSL**, editable; vienen funciones de serie, p.ej. **squash & stretch**) → expones variables → en **Control Rig** usas **Add Deformer** (right-click **refresh variables** para verlas) → conectas control/joint y expones **animation channels**.
- **Read Skin Mesh node al principio** del graph: imprescindible para **apilar varios deformers**.
- Puedes exponer settings del deformer al animador y **animarlos en Sequencer** (ejemplo: física en pestañas + curvas de material para ojo/pupila).
- **LIMITACIÓN y su solución** `[20:15]`: con un solo Control Rig NO puedes **grabar** el resultado a un Animation Sequence. Para grabar: **segundo Control Rig** con el Add Deformer, mapeado a un **Animation Blueprint** asignado al skeletal mesh; el Control Rig principal solo autorea la animación. Hay que mapearlo a un joint (aunque no tenga skinning).

### 1.7 RBF / pose-driven (correctivos) `[21:34]`
- La vía Animation Blueprint (pose assets + Pose Driver node) es engorrosa y sin visualización.
- En Control Rig: **Spherical Pose node (beta)** — salida **normalizada** que conectas a **Set Curve Value** (blendshapes) o a **offset transform** (joints). Especificas el driver item (p.ej. muñeca) y tienes **debug visual** (línea + cono del ángulo). RBF visual y ajustable en vivo.

### 1.8 Modularidad — 3 capas `[22:54]`
1. **Funciones públicas + Variants** `[23:27]`: un asset de Control Rig como librería de funciones; **variants = tags** (de serie + propios, con colores, en Project Settings). Con **Bulk Edit** propagas la **versión actualizada de una función a todo el proyecto** (o por asset). Gestión de versiones de rigging en producción.
2. **Modular Control Rig** `[24:44]`: módulos drag & drop → rig en segundos. Ideal para juniors o layout (primer pase rápido). **5.8: módulos de física** (p.ej. cola dinámica de un cuadrúpedo en dos clicks).
3. **Data-driven** `[25:42]` (la capa "escondida" y más potente):
   - **Structure asset** (opcional) para predefinir variables → **Primary Data Asset** → **Data Asset** donde defines TODO: nombres de joints, **metadata name**, forma/escala/offset de controles, booleans por personaje (dos patas, cuatro, cola…).
   - El Data Asset se **asigna en el Skeletal Mesh Editor** (Asset Details).
   - En Control Rig: **Get User Data node en el Construction Event** → cacheas → for-each → función custom que **spawnea controles dinámicamente** y los resuelve en FK.
   - **Import Skeleton node** para ser 100% procedural con cualquier skeletal mesh entrante (cambias el preview mesh y ya).
   - Añades joints en el Data Asset → save + **compile** del Control Rig → aparecen los controles (el compile se puede **blueprintear**).
   - El TA gestiona todo desde el Data Asset sin tocar el graph.

### 1.9 Física en Control Rig `[30:55]`
- **5.8: Control Rig Dynamics** — física con **3 nodos**:
  - Construction Event: **Spawn Solver** + **Spawn Physics Chain** (defines primer item y **terminator item** para acotar la cadena).
  - Forward Solve: **Step Physics Solver — SIEMPRE AL FINAL** (depende del orden de ejecución).
- Se apila sobre lógica existente (ejemplo: física encima del IK del brazo; otra cadena en la columna).
- Todo expuesto: fuerza, etc. Y el input de **curvas**: valores por posición en la cadena (item 1 fuerza 5, último 0.5 → 2.5…). Outputs recuperables en el solve para comportamiento runtime.

### 1.10 Pelo / Groom `[33:35]`
- Nuevo workflow con **Dataflow assets**: **física + control manual simultáneos** sobre el groom (gestionas skin info, la proyectas al asset y montas un Control Rig encima).
- Ejemplo descargable en el **sample pack gratuito de Fab** (chica con coleta).
- Detalle técnico: charla de **Mikael Foucault** (ingeniero de la feature, Unreal Fest del año pasado).

### 1.11 Recurso clave
- **Rigging Workshop de Epic: 10+ horas de contenido gratuito** — la referencia para profundizar en Control Rig.

---

## 2. ANIMACIÓN (lo relevante para rig/pipeline)

### 2.1 Adopción y estructura `[35:28]`
- Estructura: **UProject → UMap (contenedor de UAssets) → Level Sequence** (shots, animación, cinemática).
- **Sequence Navigator**: visualiza toda la jerarquía profunda de un sequencer de producción en un click.

### 2.2 Animation Mode `[37:48]`
- Al seleccionar un control se activa: curve editor, **constraining tab** (space switches, constraints), **sets** con colores por personaje.
- **5.8: timeline compacta** sobre el curve editor — entorno familiar tipo DCC; curve editor justo debajo; layouts guardables (Window tab); **tab de keyboard shortcuts** mapeable.

### 2.3 Constraints `[40:27]`
- Se crean desde el constraining tab: seleccionas control → tipo de constraint → item padre.
- **Usa spawnable actors** (viven dentro del sequencer) → más estable que actores normales.
- Más robusto aún: **constrainar a JOINTS en vez de controles** (el control puede estar oculto o aún no spawneado → comportamiento raro).
- **Offset de constraints**: con la timeline nueva es trivial (desde el scrub head, offset de todo lo posterior). En la vista clásica: si no seleccionas TODAS las keys implicadas, **rompes el constraint** — no uses las barras superiores (no arrastran toda la sección), escóndelas y selecciona keys.
- **5.8:** mejorada la estabilidad de constraints en render (diferencias render vs viewport en assets pesados).

### 2.4 Rendimiento en shots con muchos rigs `[43:26]`
- Muchos Control Rigs activos hunden el framerate. Workarounds: view modes, scalability (ojo: recompila shaders).
- **5.8: Auto-baking (icono de llama en Sequencer)** — bakea a **linked animation sequence** y conmuta en un click entre track de Control Rig ↔ track de anim sequence. Ocultas el track de CR → **gran ganancia de rendimiento**; vuelves al CR, ajustas, y el linked sequence **se actualiza solo**.

### 2.5 Herramientas custom `[45:11]`
- **Editor Utility Widgets**: la vía para tooling de animación.
  - **Anim picker**: no hay template de serie, pero es fácil — parte de diseño + graph de repetición (select control, combos shift/alt para multi-selección).
- **SAM (Solo Animation Mode)** — herramienta gratuita del ponente (con sample pack y docs):
  - Aísla el personaje del shot (focus mode): entorno temporal con **iluminación plana** (cámara temporal + lighting map), sin emisividad de controles, sombras opcionales.
  - Oculta **sprites** (iconos de actores), toggle entre su cámara y las camera cuts del sequencer, **modo silueta** y background personalizables, **actor tags** para operar por tags en vez de selección.

---

## 3. Ideas aplicables a nuestro pipeline (autorig_tools → UE)

- El enfoque **data-driven** (Data Asset → Construction Event → spawn de controles) es el análogo UE de nuestro build por guides + `.build`: la tabla especie→parámetro→valor del TFG puede VIVIR en un Data Asset al portar el caballo.
- Los **inline bones** son exactamente nuestros ribbons/twist de Boor: al exportar, decidir si van como leaf joints (estilo mannequin) o cadena real + Full Body IK en CR.
- El patrón del **switch IK/FK condicionado** aplica si portamos el switch del leg_module a Control Rig.
- **Control Rig Dynamics** (5.8) cubre colas/cadenas dinámicas del cuadrúpedo sin plugin.
- El flujo de **deformers con segundo Control Rig + ABP para grabar** es la referencia si queremos squash/stretch o correctivos por deformer en cinemática.
- Morph targets con **flip/mirror en 5.8**: menos round-trip Maya↔UE para correctivas faciales.
