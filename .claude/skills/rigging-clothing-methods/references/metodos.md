# Catálogo de métodos para riggear ropa

*Referencia técnica para Rigging/Creature TD. Pipeline base: autorig modular en Maya + Python (cmds/OpenMaya), ribbons propios, AdonisFX (músculo/piel/grasa), colisión por distancia (remapValue) y CFX en Houdini (Vellum). Personajes tipo Anne/Freya, vestidos largos y faldas.*

---

> **Cómo leer este catálogo.** No hace falta leerlo entero. Empieza por la
> **tabla-resumen** (ordena los métodos de menos a más preciso) y baja solo a la(s)
> **familia(s)** que aplican al caso. Cada método trae *qué es, cómo funciona, precisión
> y por qué, secundario, límites, cuándo usarlo y encaje en tu pipeline*. Al final hay una
> **recomendación transversal** y **recursos** por familia.

## Punto de partida: por qué el copy skin weights "no es preciso"

Tu flujo actual —transferir pesos del cuerpo a la prenda con `copySkinWeights` en modo *closest point*, más una colisión por distancia con `remapValue` para las faldas— tiene un techo estructural, no un bug. El skinning es una **función determinista de las poses de los joints**: la prenda queda *pegada* a una superficie que se mueve como el muslo. No desliza sobre la piel, no colisiona de verdad, no conserva volumen dinámico y no añade movimiento secundario. En una falda holgada es donde peor funciona, porque la tela justamente **no debería** seguir la pierna de forma rígida. Además, `closestPoint` salta influencias entre partes anatómicas próximas (un vértice frontal recoge peso de la pierna equivocada).

Este catálogo ordena las opciones por lo que **ganas en precisión** al subir de escalón, desde afinar el propio skinning hasta la simulación física real y sus derivados en tiempo real y por ML. La idea rectora de producción: **asignar la precisión donde el ojo la pide y baratear el resto**, montando capas sobre un buen skin base o sustituyéndolo en los planos que lo exigen.

Una nota de lectura sobre las columnas:
- **Precisión** = fidelidad al comportamiento real de la tela (arrugas, contacto, pliegue, deslizamiento), no solo suavidad de deformación.
- **Secundario** = si aporta inercia/lag/vuelo (ninguno / aproximado / simulado).
- **Tiempo real** = evaluable/exportable a motor sin caché. Ojo: varios métodos son "interactivos en viewport de Maya" pero **no** corren en engine sin hornear; se aclara en cada ficha.

---

## Tabla-resumen (de menos a más preciso)

| Método | Familia | Precisión | Secundario | Art-directable | Tiempo real | Coste | DCC/Tool |
|---|---|---|---|---|---|---|---|
| Copy Skin Weights (closest point) | Transferencia/skinning | Baja | Ninguno | Sí | Sí | Bajo | Maya `copySkinWeights` |
| Heat Map binding | Transferencia/skinning | Media | Ninguno | Sí | Sí | Bajo | Maya / Blender (bone heat) |
| Transferencia baricéntrica propia (copyWeightsAdonis) | Transferencia/skinning | Media | Ninguno | No | Sí | Medio | OpenMaya |
| Dual Quaternion / weight-blended | Transferencia/skinning | Media-alta | Ninguno | Sí | Sí | Bajo | Maya `skinCluster` |
| Geodesic Voxel Binding | Transferencia/skinning | Alta (binding) | Ninguno | Sí | Sí | Bajo | Maya `geomBind` |
| Bounded Biharmonic Weights (BBW) | Transferencia/skinning | Alta (binding) | Ninguno | No | Sí | Medio | libigl |
| ngSkinTools (capas) | Transferencia/skinning | Alta (afinado) | Ninguno | Sí | Sí | Medio | ngSkinTools 2 |
| Delta Mush | Transferencia/skinning | Media (refinado) | Ninguno | No | No (hornear) | Bajo | Maya `deltaMush` |
| Direct Delta Mush | Transferencia/skinning | Alta (refinado) | Ninguno | Sí | Sí | Medio | plugin IGL/Eigen |
| Tension (smooth corrector) | Transferencia/skinning | Media (refinado) | Ninguno | Sí | No | Bajo | Maya `tension` |
| bakeDeformer (a skin lineal) | Transferencia/skinning | Alta (traslada) | Ninguno | No | Sí | Medio | Maya `bakeDeformer` |
| SSDR / skinning decomposition | Transferencia/skinning | Alta (traslada) | — | No | Sí | Medio | custom (Le & Deng) |
| Shrinkwrap (proyección) | Envoltura/wrap | Media | Ninguno | Sí | No | Bajo | Maya `shrinkWrap` |
| Proximity Pin / uvPin | Envoltura/wrap | Alta (anclaje) | Ninguno | Sí | No | Bajo | Maya `proximityPin` |
| Proximity Wrap | Envoltura/wrap | Alta | Ninguno | Sí | No (hornear) | Medio | Maya `proximityWrap` |
| Wrap clásico | Envoltura/wrap | Media | Ninguno | Sí | No | Alto | Maya `wrap` |
| cvWrap | Envoltura/wrap | Media (=wrap; +rápido) | Ninguno | Sí | No | Medio | cvWrap (Chad Vernon) |
| Point Deform SOP (Houdini) | Envoltura/wrap | Alta | Ninguno | Sí | No | Medio | Houdini |
| Ray SOP (Houdini) | Envoltura/wrap | Media | Ninguno | Sí | No | Bajo | Houdini |
| BlendShape con target del cuerpo (PSD sobre prenda) | Envoltura/wrap | Alta | Aproximado | Sí | Sí | Alto | Maya blendShape+RBF |
| Jerarquía FK por gajos | Rigs por joints | Media | Ninguno | Sí | Sí | Bajo | Maya / mGear |
| Ribbon (NURBS + follicles / uvPin) | Rigs por joints | Media (silueta) | Ninguno | Sí | Sí | Medio | Maya |
| Aim / twist chains | Rigs por joints | Media | Ninguno | Sí | Sí | Bajo | Maya |
| Overlap / lag procedimental | Rigs por joints | Media | Aproximado | Sí | Sí* | Bajo | Maya |
| Jiggle / muelle procedimental | Rigs por joints | Media | Simulado | Sí | Sí (caché si scrub) | Bajo | Maya jiggle/spring |
| FK/IK híbrido | Rigs por joints | Alta (contacto) | Ninguno | Sí | Sí | Medio | Maya / mGear |
| Cadena proxy + wrap a hero | Rigs por joints | Media-alta | Ninguno | Sí | Sí (hornear) | Bajo | Maya |
| Spline IK + nHair (curva dinámica) | Rigs por joints | Media | Simulado | Sí | No (sim) | Medio | Maya nHair |
| Colisión por distancia / push (tu auto_collision) | Rigs por joints | Media | Aproximado | Sí | Sí | Medio | Maya remapValue/keepout |
| Colisión por shrinkwrap contra el cuerpo | Rigs por joints | Media | Ninguno | Sí | No | Bajo | Maya `shrinkWrap` |
| Spring bones en motor (Kawaii Physics) | Rigs por joints / RT | Media | Simulado | Sí | Sí | Bajo | UE/Unity |
| Correctivos PSD / RBF por ángulo | Correctivo / pose-space | Alta | Ninguno | Sí | Sí | Alto | Maya poseInterpolator/SHAPES/mGear |
| Combination / combo shapes | Correctivo / pose-space | Alta | Ninguno | Sí | Sí | Alto | Maya `combinationShape` |
| In-between targets | Correctivo / pose-space | Media-alta | Ninguno | Sí | Sí | Medio | Maya blendShape |
| Driven keys por ángulo (1D) | Correctivo / pose-space | Media | Ninguno | Sí | Sí | Bajo | Maya SDK/remapValue |
| Correctivos por tensión de malla | Correctivo / pose-space | Alta | Ninguno | Sí | Sí | Medio | Maya + shader |
| Deformador procedural de arrugas (WrinkleMatic) | Correctivo / pose-space | Media | Ninguno | Sí | Sí (viewport) | Bajo | WrinkleMatic |
| Nodo PSD/RBF propio (OpenMaya) | Correctivo / pose-space | Alta | Ninguno | Sí | Sí (hornear) | Alto | OpenMaya |
| Ropa skinneada a huesos a mano | Tiempo real / juegos | Media | Ninguno | Sí | Sí | Bajo | Maya |
| Wrinkle/tension normal maps | Tiempo real / juegos | Media | Ninguno | Sí | Sí | Bajo | UE/Unity shader |
| Sim horneada a huesos (sim-to-bone / SSDR) | Tiempo real / juegos | Media | Simulado | No | Sí | Bajo | Houdini/Maya + FBX |
| Cloth de Unity / NvCloth (legacy) | Tiempo real / juegos | Media | Simulado | Sí | Sí | Bajo-medio | Unity / PhysX |
| Vertex Animation Textures (VAT) | Tiempo real / juegos | Alta | Simulado | No | Sí | Bajo | Houdini + shader |
| UE5 Deformer Graph (Optimus) | Tiempo real / juegos | Media-alta | Ninguno | Sí | Sí | Medio | Unreal |
| Chaos Cloth (Unreal) | Tiempo real / juegos | Alta | Simulado | Sí | Sí | Medio | UE5 |
| ML Deformer (Maya nativo) | ML / data-driven | Media | Ninguno | No | Sí (solo viewport) | Medio | Maya 2025.2 |
| ML Deformer / ML Cloth (Unreal) | ML / data-driven | Media-alta | Simulado | No | Sí | Alto | UE 5.3+ |
| Delta Mush como capa correctiva | Correctivo / híbrido | Media | Ninguno | No | No (hornear) | Bajo | Maya |
| Maya nCloth (Nucleus) | Simulación física | Alta | Simulado | Sí | No | Medio | Maya |
| Houdini Vellum Cloth (XPBD) | Simulación física | Alta | Simulado | Sí | No | Medio | Houdini |
| Qualoth / Syflex | Simulación física | Alta | Simulado | Sí | No | Alto | Maya plugin |
| Marvelous Designer (patronaje) | Simulación física | Alta | Simulado | Sí | No | Medio | MD |
| Ziva Cloth (FEM, fascia/piel) | Simulación física | Alta (piel, no prenda) | Simulado | No | No | Alto | Maya (legacy) |
| Sim guiada por skin (inputMeshAttract) | Híbridos / capas | Alta | Simulado | Sí | No | Medio | Maya |
| Blend por regiones (sim ↔ rig) | Híbridos / capas | Alta | Simulado | Sí | No | Medio | Maya/Houdini |
| Pase de tech-anim / CFX por plano | Híbridos / capas | Alta | Simulado | Sí | No | Alto | Houdini/Maya |
| Multi-capa con colisión jerárquica | Híbridos / capas | Alta | Simulado | Sí | No | Alto | Houdini/Maya |
| Subspace Neural Physics / HOOD / SNUG | ML / data-driven | Media-alta | Simulado | No | Sí | Alto | research/PyTorch |

\* La variante spring del overlap evalúa por frame; la variante frame-delay necesita caché.

---

## Familia 1 — Transferencia de pesos y skinning

Es tu punto de partida y su techo natural. Todo aquí es **skinning estático**: mejora la distribución y la suavidad de la deformación, pero la prenda sigue pegada al cuerpo, sin deslizamiento ni colisión ni vuelo reales. La progresión: mejorar el *binding* (heat map → geodesic voxel → BBW), organizar el *afinado* (ngSkinTools), refinar de forma no destructiva (Delta Mush / Direct Delta Mush / Tension) y, para juego, **hornear** cualquier deformación compleja a un skinCluster lineal.

### Copy Skin Weights (closest point / rayCast / closestComponent / UV)
- **Qué es.** Copiar los pesos de un skinCluster (el cuerpo) a otra malla (la prenda) por asociación de superficie. Tu flujo actual.
- **Cómo funciona.** `copySkinWeights` empareja cada punto destino con una posición origen según `-surfaceAssociation`, que admite **solo tres valores: `closestPoint`, `rayCast`, `closestComponent`** (el default es `closestComponent`, no `closestPoint`). La transferencia por UV es un flag **aparte**, `-uvSpace <srcUVset> <dstUVset>`, clave cuando la topología difiere pero las UV están alineadas. `-influenceAssociation` (`closestJoint`/`closestBone`/`label`/`oneToOne`) decide cómo mapear joints entre skins. *(Correcto para scriptearlo en el autorig: la firma real importa.)*
- **Precisión y por qué.** Baja. Hereda los defectos del binding del cuerpo; con proximidad salta influencias entre partes anatómicas cercanas. No es impreciso por bug, sino por definición: transfiere una función de piel a algo que no es piel.
- **Secundario.** Ninguno.
- **Límites reales.** En faldas holgadas es donde peor va. Solo evita interpenetrar si offset y pesos casan a la perfección.
- **Cuándo usarlo.** Como **semilla** de pesos, no como resultado final.
- **Encaje en tu pipeline.** Cambio inmediato: usa `-uvSpace` cuando exista UV coherente cuerpo-prenda, e `-influenceAssociation label` (etiquetando joints) para no cruzar lados. Encapsúlalo como paso automatizable.

### Heat Map binding (difusión de calor)
- **Qué es.** Binding automático que reparte pesos resolviendo una difusión de calor sobre la malla, tratando cada joint como fuente.
- **Cómo funciona.** Equilibrio de calor (Laplace) donde el hueso visible más cercano actúa como fuente; el peso es la temperatura de equilibrio. El **Automatic Weights de Blender implementa esta familia (bone heat / difusión de superficie), NO BBW.**
- **Precisión.** Media. Respeta mejor la conectividad que la distancia euclídea, pero sigue pegando la prenda.
- **Límites reales.** Requiere mallas cerradas y limpias; falla con no-watertight, intersecciones y múltiples componentes (justo lo que abunda en prendas con costuras). Puede filtrar calor entre superficies próximas (pierna-falda). Superado en robustez por geodesic voxel.
- **Cuándo usarlo.** Concepto/legado; en la práctica lo sustituyes por geodesic voxel.
- **Encaje.** Poco relevante hoy; útil como referencia mental del comportamiento del auto-weights.

### Geodesic Voxel Binding
- **Qué es.** Binding automático robusto de Maya que voxeliza el personaje y mide distancias geodésicas dentro del volumen.
- **Cómo funciona.** Clasifica vóxeles (esqueleto/interior/frontera) y mide por el interior del volumen (no en línea recta), así no cruza influencias entre partes cercanas y tolera geometría sucia. `Bind Skin > Geodesic Voxel`, resolución 256/512/1024.
- **Precisión y por qué.** Alta (para ser binding). Al medir por dentro del volumen evita el *bleed* entre piernas de una falda.
- **Secundario.** Ninguno.
- **Límites.** Sigue pegando; resolución baja = bleed; prendas muy holgadas/multicapa piden binding por piezas.
- **Cuándo usarlo.** Debería ser tu **binding base por defecto**, en lugar de closest-point.
- **Encaje.** Bindea la prenda directamente a la cadena de joints de la falda con GVB a resolución alta y afina con ngSkin; también da mejores pesos como semilla para `copySkinWeights`.

### Bounded Biharmonic Weights (BBW)
- **Qué es.** Pesos suaves, no negativos y de soporte local por optimización biharmónica sobre el volumen, con handles de hueso, punto o jaula.
- **Cómo funciona.** Minimiza la energía Laplaciana al cuadrado sobre una tetraedralización con partición de la unidad, no-negatividad y acotación. **Implementación de referencia: libigl. No es nativo de Maya, Blender ni Houdini; en la práctica solo llega vía libigl o plugins que lo envuelvan** (el auto-weights de Blender **no** es BBW: es bone heat).
- **Precisión.** Alta. Pesos predecibles, sin oscilaciones.
- **Límites.** Necesita tetraedralizar (mallas cerradas/limpias); prendas abiertas/multicapa complican el mallado. No hay tool lista; implica integración con libigl.
- **Cuándo usarlo.** "De laboratorio", cuando geodesic voxel no basta y quieres control matemático.
- **Encaje.** Con tu perfil de tool dev: envolver libigl en un nodo/comando OpenMaya para pesos base de altísima calidad o jaulas de vestido.

### ngSkinTools (skinning por capas)
- **Qué es.** Plugin de afinado por capas no destructivas, con pintado por capa, mirror en cualquier pose, flood y un *relax/smooth* real.
- **Cómo funciona.** Pila de capas sobre el skinCluster (opacidad + máscara) combinadas hacia los pesos finales. Trabaja sobre cualquier bind previo. Tiene API Python.
- **Precisión.** Alta (afinado), no dinámica.
- **Límites.** Es trabajo artesanal; dependencia de plugin/versión. El resultado se hornea al skinCluster estándar (sin coste extra en runtime).
- **Cuándo usarlo.** Convertir el binding base en pesos limpios: dobladillos, cinturas, zonas donde el copy weights cruza influencias.
- **Encaje.** Su API Python se automatiza en el autorig (capas base, mirror, export). Complementa geodesic voxel + Delta Mush.

### Delta Mush
- **Qué es.** Suavizado que quita artefactos del skinning (pinchamientos, candy-wrapper, colapsos) sin destruir el detalle.
- **Cómo funciona.** En bind guarda por vértice el delta entre la posición original y su versión suavizada (Laplaciano) en frame local; cada frame vuelve a suavizar la malla deformada y re-aplica el delta.
- **Precisión.** Media (refinado). Solo suaviza; no añade dinámica, no colisiona, no desliza.
- **Límites.** Puede aplanar detalle con muchas iteraciones; coste por vértice/frame (hornear para juego); no arregla un binding malo de raíz. En tela holgada aporta poco: el problema no es rugosidad, es falta de dinámica.
- **Cuándo usarlo.** Capa de acabado estándar sobre skin de cuerpo y prenda.
- **Encaje.** Barato de añadir; hornear con bakeDeformer para juego. Combina con AdonisFX como suavizado.

### Direct Delta Mush (DDM)
- **Qué es.** Generalización directa (no iterativa) del Delta Mush: precalcula por vértice matrices que combinan las transformaciones de los joints.
- **Cómo funciona.** Precomputa variantes (v0..v4) en bind; en runtime la deformación es combinación lineal directa. Calidad de Delta Mush a coste de tiempo real; permite pesos por hueso y rigidez.
- **Precisión.** Alta (refinado, tiempo real).
- **Límites.** Precómputo pesado y memoria por vértice; recomputar si cambia topología/influencias; en Maya depende de plugins de comunidad (build IGL/Eigen).
- **Cuándo usarlo.** Cuando quieres calidad Delta Mush evaluable en tiempo real o horneable a juego.
- **Encaje.** Compilar el plugin y envolverlo en el autorig; útil para el cuerpo bajo la ropa y prendas ajustadas.

### Tension (deformador de smooth corrector)
- **Qué es.** Deformador de **suavizado corrector que modula el smoothing según el estiramiento/compresión de aristas**, preservando volumen (relaja zonas estiradas, conserva detalle en las comprimidas). Es un Delta Mush "inteligente".
- **Cómo funciona.** Compara longitudes de arista respecto al bind. **Importante: el nodo nativo `tension` NO emite un mapa de tensión paintable para disparar arrugas.** Ese mapa se construye aparte (colorSet / `polyColorPerVertex`, o atributos de rig/nCloth).
- **Precisión.** Media (refinado). No es binding ni resuelve la deformación base; solo modula lo que ya hace el skin.
- **Límites.** Coste por frame; no aporta dinámica ni colisión.
- **Cuándo usarlo.** Reducir colapsos/candy-wrapper de forma dirigida.
- **Encaje.** Para conducir arrugas necesitas generar la máscara de tensión por tu cuenta (OpenMaya) y alimentar blendshapes/smooth.

### Transferencia baricéntrica propia (copyWeightsAdonis generalizado)
- **Qué es.** Tu transferencia en OpenMaya: para cada punto destino, triángulo más cercano en el origen e interpolación por coordenadas baricéntricas, con control total de filtrado, normalización y remapeo.
- **Cómo funciona.** `MMeshIntersector`/closestPoint da faceId + baricéntricas; interpolas los pesos de los 3 vértices y escribes con `setWeights`. Puedes enmascarar por UV, limitar maxInfluences, remapear por label y suavizar bordes. Más preciso que el closest-*vertex* de Maya porque interpola dentro de la cara.
- **Precisión.** Media. Sigue siendo proximidad: hereda errores del binding origen.
- **Límites.** Cruza influencias igual que copySkinWeights si el alineamiento es malo; mantenimiento de código; no supera a un binding volumétrico en geometría compleja.
- **Cuándo usarlo.** Semilla de prendas ajustadas dentro del autorig, luego afinar con ngSkin.
- **Encaje.** Súbela de nivel: de closest-vertex a baricéntrico por cara, remapeo por label, máscara por UV, normalización robusta. Integra bien con AdonisFX al ser código propio.

### Dual Quaternion / weight-blended skinning
- **Qué es.** No es una transferencia sino el **algoritmo con que se interpretan los pesos**. DQS evita el colapso de volumen del Linear Blend en torsiones.
- **Cómo funciona.** LBS interpola matrices linealmente (colapsa al girar); DQS interpola rotaciones como cuaterniones duales (preserva volumen, con ligero *bulging*). Maya: `skinCluster -skinMethod` 0 linear / 1 DQ / 2 weight-blended (mapa pintable).
- **Precisión.** Alta como mejora de calidad, con los mismos pesos.
- **Límites.** No arregla malos pesos ni añade dinámica; DQS abulta articulaciones y sufre con escalados no uniformes.
- **Cuándo usarlo.** Cintura de vestido, muñecas: cambiar a DQ o weight-blended mejora sin tocar pesos.
- **Encaje.** Decisión por defecto codificable en el autorig por zona; compatible con engines.

### Bake Deformer to Skin Weights (bakeDeformer)
- **Qué es.** Aproxima una cadena de deformación compleja (Delta Mush, correctivos, wraps, incluso sim) a un único skinCluster lineal por mínimos cuadrados sobre poses muestreadas.
- **Cómo funciona.** Evalúa el rig en un rango de poses y resuelve por vértice los pesos (con maxInfluences objetivo) que mejor las reproducen. Resultado: skinCluster estándar que corre en cualquier engine.
- **Precisión.** Alta, pero **traslada** precisión, no la crea.
- **Límites.** Solo captura deformación función-de-pose; lo dinámico (vuelo, colisión, secundario) **no** se puede hornear a pesos lineales.
- **Cuándo usarlo.** Paso final de export de LOD de juego: monta lo mejor offline y hornéalo.
- **Encaje.** Para faldas dinámicas, el bake solo captura la parte "que sigue al cuerpo".

### SSDR / Skinning Decomposition *(método que faltaba)*
- **Qué es.** *Smooth Skinning Decomposition with Rigid Bones* (Le & Deng, **SIGGRAPH Asia 2012**): descompone una deformación arbitraria (sim, correctivos, cache de vértices) en **pesos de skinCluster Y transformaciones de huesos** por mínimos cuadrados.
- **Cómo funciona.** A diferencia de bakeDeformer —que exige una jerarquía de joints ya existente y solo captura función-de-pose—, SSDR puede **resolver también los huesos** que reproducen la animación de vértices.
- **Precisión.** Alta (traslada). Ideal para cine→juego.
- **Límites.** Es investigación/implementación propia; el nº de huesos limita la fidelidad de pliegues finos.
- **Cuándo usarlo.** Cuando quieres hornear una sim de tela a un rig de huesos + pesos para runtime.
- **Encaje.** Encaja de lleno con tu perfil tool dev y con el objetivo de tela horneada; es la base teórica del sim-to-bone de la familia de tiempo real.

---

## Familia 2 — Deformadores de envoltura (wrap / envelope)

Aquí la prenda toma su deformación de la **superficie ya deformada del cuerpo** (skin + músculo/grasa de AdonisFX), no de re-skinnear a los mismos joints. Capturan **contacto y volumen real** y respetan de forma nativa la salida de AdonisFX y de los correctivos. Coste: dependencia fuerte de topología y de bind (mallas coincidentes en pose neutra), velocidad, e **interpenetración residual en cóncavos** que se resuelve con una capa de corrección. En tu pipeline el wrap es la técnica puente ideal y la **malla guía** para envolver la hero o arrancar Vellum.

### Proximity Wrap (Maya)
- **Qué es.** Deformador moderno (2020+) que envuelve prendas sobre uno o varios drivers por distancia a superficie. Sustituto recomendado del wrap clásico.
- **Cómo funciona.** En bind asocia cada vértice a puntos del driver dentro de un radio; cada frame lee posición/normal/rotación ya deformadas (incluida la salida de AdonisFX). **Parámetro real: `wrapMode` con dos modos, `Offset` y `Surface`** (Surface aplica suavizado de normales) — **no existen modos "Rigid/Non-rigid"**. Falloff start/end, curva/exponente, *smooth influences* y pesos pintables. Acelerable por GPU.
- **Precisión.** Alta (contacto/volumen), no dinámica.
- **Secundario.** Ninguno.
- **Límites.** Bind en misma pose sin transformaciones; falloff mal puesto coge drivers del lado opuesto; interpenetración residual en axilas/entrepierna; caro con driver denso.
- **Cuándo usarlo.** Prendas ajustadas, cinturones, correas, cadera de falda que deben seguir el volumen real.
- **Encaje.** `cmds.deformer type='proximityWrap'` tras el skin, con el cuerpo (AdonisFX evaluado) como driver. Capa base y semilla de una sim de Vellum.

### Wrap deformer clásico (Maya)
- **Qué es.** Wrap histórico: la prenda hereda la deformación de un *influencer* por interpolación de caras/puntos. *(aka: wrap node, Point/Vertex o Face wrap — NO "CV wrap", que es el plugin de Chad Vernon, otra entrada.)*
- **Cómo funciona.** Genera un `baseShape` neutro; liga cada punto a caras/puntos cercanos dentro de max distance (baricéntricas + offset por normal). Modos por Puntos (más suave/caro) o por Caras.
- **Precisión.** Media.
- **Límites.** Lento y pesado; sensible a densidad/topología del influencer; sticky en cóncavos. Se sustituye por proximityWrap o cvWrap por rendimiento.
- **Cuándo usarlo.** Versiones sin proximityWrap, o "highres sigue a lowres" simulado.
- **Encaje.** Vestir el mesh de render sobre un proxy de Vellum.

### cvWrap (Chad Vernon)
- **Qué es.** Wrap open source, más rápido, re-bindable, con evaluación GPU y correctivos front-of-chain.
- **Cómo funciona.** Bind por punto más cercano con frame local (baricéntricas + offset); reconstruye desde el driver deformado. Comandos de rebind e import/export del binding.
- **Precisión.** **Comparable al wrap nativo (no superior).** Su ventaja es **velocidad y flujo de trabajo (binding reproducible/versionable)**, no exactitud de la envoltura; el wrap nativo en modo Puntos puede ser incluso más suave.
- **Secundario.** Ninguno.
- **Límites.** Plugin compilado (mantener por versión/OS); misma interpenetración residual; rebind si cambia topología.
- **Cuándo usarlo.** Cuando el wrap nativo va lento en producción y necesitas playback interactivo.
- **Encaje.** Sustituto directo en el autorig; su binding exportable encaja con un autorig reconstruible.

### Shrinkwrap (Maya)
- **Qué es.** Proyecta los vértices de la prenda sobre la superficie del target con offset.
- **Cómo funciona.** Modos closest point / along normal / inside / vertex-UV. Offset por normal; *keep borders* relaja aristas. Recalcula cada frame contra el target deformado.
- **Precisión.** Media.
- **Límites.** Es proyección, no wrap: distorsiona topología con curvatura fuerte; ignora rotación tangencial; salta de región en cóncavos; sensible a normales sucias.
- **Cuándo usarlo.** Segunda piel (mallas, licra, guantes) o **paso anti-interpenetración** (empuja la prenda justo por fuera).
- **Encaje.** Encadenado tras un proximityWrap con offset pequeño para garantizar que la prenda quede fuera de la piel.

### Proximity Pin / uvPin
- **Qué es.** Deformador/constraint que fija componentes a la superficie del cuerpo por punto más cercano o UV, heredando posición **Y** orientación. Evolución del follicle/rivet.
- **Cómo funciona.** Registra UV (o closest point) + frame de orientación; cada frame devuelve una matriz que arrastra los puntos/objetos anclados. No envuelve toda la malla: fija anclas.
- **Precisión.** Alta (anclaje).
- **Límites.** No resuelve el drapeado entre anclas; depende de UVs limpias/estables; closest point salta de región en cóncavos.
- **Cuándo usarlo.** Anclar cintura de falda, tirantes, hebillas, o **la raíz de tus cadenas de joints** a la cadera.
- **Encaje.** Reemplazo moderno de follicles: `proximityPin`/`uvPin` da la matriz de la cadera y tu ribbon + colisión por distancia cuelgan de ahí, ganando el deslizamiento real de la piel en el arranque.

### Point Deform SOP (Houdini) *(método que faltaba — el hueco más grave de la familia)*
- **Qué es.** El nodo de wrap canónico de Houdini para "highres sigue a lowres" (captura por puntos + reconstrucción).
- **Cómo funciona.** Binda la hi-res a una malla low-res (a menudo simulada en Vellum) por vecindad de puntos y la reconstruye desde la low-res deformada.
- **Precisión.** Alta.
- **Límites.** Pierde pliegues que no existan en la low-res; requiere correspondencia estable.
- **Cuándo usarlo.** Envolver la prenda de render sobre un proxy de Vellum **dentro de Houdini**, sin round-trip a Maya.
- **Encaje.** Siendo tu CFX Vellum en Houdini, es el wrap natural para alimentar/hornear sim; complementa al proximityWrap del lado Maya.

### Ray SOP (Houdini) *(método que faltaba)*
- **Qué es.** Equivalente del shrinkwrap: proyección por punto más cercano / a lo largo de normal.
- **Cómo funciona.** Reproyecta la prenda fuera del cuerpo para resolver interpenetración.
- **Precisión.** Media.
- **Cuándo usarlo.** Limpieza de intersección **en el lado Houdini**, complementando al Point Deform.
- **Encaje.** Paso barato anti-clip en el CFX antes de devolver la sim a Maya.

### BlendShape con target del cuerpo (envoltura por combinación / PSD sobre la prenda)
- **Qué es.** Transferir la deformación del cuerpo a la prenda como **blendShapes por pose** (PSD), en vez de un deformer de proximidad en vivo.
- **Cómo funciona.** Envuelves temporalmente la prenda al cuerpo (wrap/transferAttributes), horneas poses extremas (flexiones, respiración, contracción muscular de AdonisFX) como targets, y las disparas con SDK o un pose reader (RBF). En runtime la prenda interpola shapes correctos sin evaluar el wrap en vivo.
- **Precisión.** Alta; **secundario aproximado** solo si lo esculpes.
- **Límites.** Laborioso; interpolación pobre entre poses lejanas; mantenimiento alto si cambia el modelo.
- **Cuándo usarlo.** Hero shots con arrugas exactas por pose y ruta a runtime (los blendShapes viajan mejor que un wrap).
- **Encaje.** Usas un wrap para **generar** los targets (esculpes la corrección, la inviertes front-of-chain con cvShapeInverter) y el rig final corre con blendShapes disparados por poses. Combina con tus pose readers RBF.

---

## Familia 3 — Rigs de ropa basados en joints/controles (mecánico, art-directable)

Es lo que ya haces. La fortaleza no es batir a la sim en microdetalle, sino **control, ligereza, cacheabilidad y transferencia a motor**. Un rig mecánico bien construido cubre el 80-90% de planos de personaje; la sim se reserva para hero shots.

**Matiz de determinismo (corrección importante):** la promesa "el mismo frame da siempre el mismo resultado" **solo** vale para las capas puramente cinemáticas/DG (FK, ribbon, aim, FK/IK, colisión por push, PSD). **NO** vale para Spline IK + nHair, jiggle/muelle ni spring bones en motor: son solvers dependientes de historia/framerate y necesitan caché o *play-from-start*.

### Jerarquía FK por gajos
- **Qué es.** Dividir la falda en N tiras verticales con cadenas FK de 2-5 segmentos; la prenda se skinnea a esas cadenas, no al cuerpo.
- **Cómo funciona.** Joints raíz radiales bajo una cintura que sigue a la pelvis; control master + control por tira; pesos suaves entre gajos (un ribbon/lattice encima suaviza costuras).
- **Precisión.** Media. Todo es keyframe salvo lo que hereda de la cadera.
- **Secundario.** Ninguno.
- **Límites.** Sin dinámica no hay inercia; sin colisión atraviesa piernas; pocos gajos = facetado.
- **Cuándo usarlo.** Esqueleto de control base sobre el que montar las demás capas; imprescindible para posar la silueta a mano (acting, sentarse, contacto con manos). Sustituto superior al copy skin porque **separa el movimiento de la tela del muslo**.
- **Encaje.** Módulo `skirt` en Python (nº gajos, segmentos, radio) que genera joints+controles+skin. Exporta limpio a cualquier motor.

### Ribbon (NURBS + follicles / uvPin) para tiras y bajos
- **Qué es.** Superficie NURBS por tira con follicles que llevan joints deslizantes; curvatura continua sin facetado. *(El nombre "ribbon de Boor" es nomenclatura tuya interna: el método reconocido en la industria es "ribbon NURBS+follicles"; "Boor" no es un estándar citable.)*
- **Cómo funciona.** Follicles en U (V=1) con joint bind; 3+ controles deforman la superficie; twist en U con up-vector estable.
- **Precisión.** **"Alta" referida a continuidad de curvatura/silueta, no a fidelidad de tela** (sigue sin colisión ni pliegue propios). En clave "tela real" es media.
- **Secundario.** Ninguno.
- **Límites.** Muchas tiras = coste de eval/setup; shear si la superficie se estira.
- **Cuándo usarlo.** Cintas, fajas, colas, tiras del corpiño, capas, mangas colgantes; superior al FK por gajos cuando la continuidad de curvatura importa.
- **Encaje.** Reutiliza tus setups como submódulo; si cambias follicle por `uvPin`/matrix nodes, exporta y evalúa mejor y llega a tiempo real bakeado.

### Overlap / lag procedimental
- **Qué es.** Retardo automático a lo largo de la cadena: los joints inferiores siguen a los superiores con desfase (follow-through sin simular).
- **Cómo funciona.** (a) Delay temporal (frameCache/expression) atenuado hacia el bajo; (b) muelle en cascada. Sliders de lag/amount por nivel.
- **Precisión.** Media (aproximación estilizada del follow-through, no física).
- **Secundario.** Aproximado.
- **Límites.** El delay por frames depende del framerate/playback (no evalúa en scrub arbitrario sin caché); "nada" en anim muy rápida.
- **Cuándo usarlo.** Bajo del vestido que arrastra de forma legible y dirigible sin nucleus.
- **Encaje.** Capa opcional por gajo. Variante spring bakea a motor; variante frame-delay conviene cachearla. **Herramientas a verificar:** las reconocidas son *Overlappy* (aTools/animBot) y add-ons recientes; evita citar tools no confirmables.

### Jiggle / muelle procedimental
- **Qué es.** Dinámica de muelle-amortiguador ligera en los joints (o vértices con el jiggle deformer): rebote y temblor evaluados por frame, sin nucleus.
- **Cómo funciona.** Cada joint persigue su objetivo con masa/stiffness/damping, integrando por frame; weight por joint (más rebote en el bajo).
- **Precisión.** Media. Modela inercia/rebote, no colisión ni pliegue.
- **Secundario.** Simulado (determinista pero **con estado**: reset en teletransportes; no da el mismo resultado en scrub sin play-from-start).
- **Límites.** La tela atraviesa la pierna si no se combina con push; muelle lineal lejos de un solver real; sin auto-colisión.
- **Cuándo usarlo.** "Vida" de tela ligera controlable; motor de la variante spring del overlap.
- **Encaje.** Nodo de muelle por joint (mass/stiffness/damp/weight); bakea 1:1 a Alembic/FBX. *(No mezclar aquí AdonisFX: es un solver FEM con estado, no un muelle DG determinista; su sitio es la familia de simulación.)*

### Colisión por distancia / push — tu `auto_collision`
- **Qué es.** Detectar la proximidad de la pierna a cada joint y empujarlo hacia fuera para aproximar el choque, sin solver.
- **Cómo funciona.** Mides la distancia con `distanceBetween` (o el ángulo de la pierna). **Ojo: `closestPointOnSurface`/`closestPointOnMesh` NO devuelven distancia**, dan el punto/parámetro más cercano; la magnitud del push necesita un `distanceBetween` o `length` del vector diferencia adicional. Esa distancia entra en `remapValue` (falloff 0-1) y un `multiplyDivide` la traduce en push. Variante robusta: el nodo **`keepout`** (push vectorial multi-dirección por `inDirection` al penetrar un radio).
- **Precisión.** Media. Solo evita penetración por punto de referencia; no reproduce el contacto ni el pliegue que forma la pierna al presionar.
- **Secundario.** Aproximado.
- **Límites.** Funciona en faldas redondeadas y algo rígidas; falla en telas finas/plegadas; ajustar remap por joint es tedioso; sin auto-colisión tela-tela; piernas cruzadas problemáticas; popping con falloff brusco.
- **Cuándo usarlo.** Evitar clip en tiempo real controlable; complemento de las capas FK/dinámica.
- **Encaje.** Módulo procedimental distance→remap→push. Migra de closest-point por ángulo a **`keepout`** para push direccional; con keepout la exportación a motor requiere hornear (el nodo no existe fuera de Maya).

### Colisión por shrinkwrap contra el cuerpo *(método que faltaba)*
- **Qué es.** Resolver el keep-out **pegando la tela a la piel** por proyección, en vez de empujar un joint.
- **Cómo funciona.** Un `shrinkwrap`/`proximityWrap` con offset proyecta los vértices en riesgo justo por fuera de la superficie del cuerpo deformado.
- **Precisión.** Media; evita parte del *popping* del remap.
- **Cuándo usarlo.** Alternativa/complemento al push por distancia donde quieres deslizamiento sobre el mesh en lugar de empuje por punto.
- **Encaje.** Barato de scriptear tras la cadena; combina con la red remap para las zonas que el shrinkwrap no cubre.

### Aim / twist chains
- **Qué es.** Cada tira apunta con `aimConstraint` a un objetivo (gravedad/viento/locator) y distribuye twist.
- **Cómo funciona.** Aim del joint raíz con up-vector estabilizado; twist por `multiplyDivide` o ribbon en U. Un solo target reorienta toda la falda.
- **Precisión.** Media (dirección/orientación de silueta).
- **Secundario.** **Ninguno** (es 100% cinemático; el "secundario" solo aparece si se combina con la capa de overlap/aim-lag, que es otro método).
- **Límites.** Riesgo de flip si el up-vector no está resuelto; control global, poco detalle local.
- **Cuándo usarlo.** Dirigir la caída global hacia gravedad/viento con un control; orientación limpia del bajo.
- **Encaje.** Exponer un "wind/gravity target"; todo constraint/DG, bakea a motor.

### FK/IK híbrido con blend
- **Qué es.** FK (pose libre por gajo) + IK (spline IK o 2-huesos) que fija el bajo a un control mundo, con blend.
- **Cómo funciona.** Cada cadena tiene versión FK y IK con switch; en IK un control posiciona el extremo. El mismo blend mezcla con dinámica o jiggle. Se hornea el modo activo.
- **Precisión.** Alta (contacto dirigido).
- **Secundario.** Ninguno.
- **Límites.** Más nodos/estados; el switch necesita match; spline IK puede estirarse.
- **Cuándo usarlo.** Contactos precisos: sentarse y apoyar la falda, mano que recoge el vestido, borde clavado al suelo.
- **Encaje.** Flag `fkik` del módulo de falda; bakea a joints → Alembic/FBX → motor.

### Cadena proxy (driver cage) + wrap a la hero *(método que faltaba)*
- **Qué es.** Un anillo de joints/ribbon deforma una *cage* ligera y un wrap propaga a la prenda densa.
- **Cómo funciona.** Control barato sobre pocos puntos + suavizado del wrap; exporta horneado.
- **Precisión.** Media-alta (según la cage).
- **Cuándo usarlo.** Pilar mecánico muy usado para dar control barato con acabado suave.
- **Encaje.** Convive con el skin como capa base; en la ficha FK aparecía solo de refilón ("lattice/wrap para suavizar"), pero merece ser método propio.

### Spline IK + nHair (curva dinámica)
- **Qué es.** Cada gajo gobernado por una curva dinámica de nHair: inercia, gravedad, drag y rebote reales sin escribir un solver.
- **Cómo funciona.** Curva CV → `Make Curves Dynamic` → la curva dinámica maneja un Spline IK; stiffness/drag/mass/damp/gravity en el nHairSystem; blend FK↔dinámica (start curve attract); el nucleus colisiona la curva contra un proxy de piernas.
- **Precisión.** Media.
- **Secundario.** Simulado (con estado: **caché obligatoria** para review estable; scrub no instantáneo).
- **Límites.** Depende de framerate/substeps; colisión curva-vs-mesh aproximada y cara; jitter con substeps bajos; sin pliegues finos; "gomea" si no se afina.
- **Cuándo usarlo.** Inercia y lag creíbles en el bajo con poco setup, sin salir de Maya.
- **Encaje.** El módulo genera curvas+nHair+splineIK+blend por gajo; cachea a Alembic; el bake sí llega a runtime.

### Spring bones / bone dynamics en motor
- **Qué es.** Equivalente en engine de la cadena dinámica: los mismos huesos con un solver de muelle-colisión en el AnimGraph.
- **Cómo funciona.** Kawaii Physics / AnimDynamics (UE), Dynamic Bone / Magica Cloth / VRM SpringBone (Unity): muelle por hueso con stiffness/damping/gravedad y colisión contra esferas/cápsulas.
- **Precisión.** Media (aproximación estilizada; sin pliegues por compresión).
- **Secundario.** Simulado.
- **Límites.** Colisión por primitivas (clip en poses extremas); look por tuning. **Matiz:** la independencia de framerate y la ejecución en el hilo de animación son propias de **Kawaii Physics** (y Magica Cloth); **AnimDynamics es dependiente del framerate y menos estable**. *(No atribuir títulos de juegos concretos sin fuente verificable.)*
- **Cuándo usarlo.** Estándar de industria para faldas/pelo/capas secundarios en tiempo real; reutiliza directamente tus cadenas de joints.
- **Encaje.** Exportas las cadenas por FBX y el motor las anima. Un solo skeleton sirve para cine (dinámica cacheada en Maya) y juego (spring bones). Razón para mantener el rig de falda como joints limpios.

### Correctivos pose-space / driven keys por ángulo de pierna
*(Se desarrolla a fondo en la Familia 4; aquí como capa del módulo de falda: lo mecánico da la silueta, el PSD/RBF añade el pliegue por compresión que la sim ganaba.)*

*(Método que faltaba en la familia: **deformador wire / curvas-driver para bordes y bajos (hem)** — control directo de la silueta del borde con una curva, habitual en faldas/capas y complementario al ribbon.)*

---

## Familia 4 — Deformación correctiva y pose-space

No reemplaza al skinning/wrap: lo **corrige**. Sobre una base deformada, añade una capa de forma esculpida que se dispara por **pose** (ángulo de joint, vector, combo) o por **tensión de malla**. Es la vía canónica de cine para arrugas deterministas, repetibles y art-directables en zonas de flexión, y **es el estándar exportable a tiempo real** por ángulo de joint. Su límite: **no es dinámica** y la autoría es cara. El diferenciador interno es **cómo se interpola** (driven keys 1D, PSD nativo, RBF N-dimensional) y **qué dispara** (ángulo vs. tensión vs. combo).

### Blendshapes correctivos esculpidos por pose
- **Qué es.** Formas de corrección esculpidas sobre la prenda ya deformada en una pose; el ladrillo base de la familia.
- **Cómo funciona.** Pones la pose problemática, esculpes cómo debería verse, calculas el delta contra el skin/wrap y lo guardas como target aplicado **después** del skinning. *Sculpt-on-top / edit-in-place* para que el correctivo aporte solo la diferencia.
- **Precisión.** Alta. **Secundario: ninguno.**
- **Límites.** No dinámico; esculpir cada pose y mantenerla; interpolación pobre con SDK 1D (popping en poses intermedias → de ahí PSD/RBF).
- **Cuándo usarlo.** Pliegue exacto y repetible en una pose de plano; pulir mangas, axilas, codos, corpiño, cintura.
- **Encaje.** Al final de la pila de deformadores; generar/conectar por Python; exportable a motor como morph targets. *(ZBrush/Mudbox son herramientas de autoría del sculpt, no DCC que hospeden el rig correctivo.)*

### Pose Space Deformation nativo de Maya (poseInterpolator)
- **Qué es.** PSD integrado: un `poseInterpolator` lee la transformación de un joint, la compara con poses registradas y mezcla los correctivos, normalizando.
- **Cómo funciona.** `Deform > Pose Space Deformation`; poses (neutral + extremas), kernel RBF interno, poses mutuamente exclusivas; cubre poses intermedias sin popping.
- **Precisión.** Alta.
- **Límites.** No dinámico; UI más tosca que SHAPES/mGear; el interpolador por joint individual complica combos multi-joint (ahí RBF N-dim es superior).
- **Cuándo usarlo.** PSD robusto sin plugins; arrugas de flexión de mangas/codos/hombro.
- **Encaje.** Nativo, sin dependencias; `cmds.poseInterpolator` scriptable. **Precisión sobre MetaHuman:** el RBF del Pose Editor de MetaHuman conduce **principalmente JOINTS** (RBF + SwingTwist), no morph targets; para llevar correctivos de blendshape a Unreal hay que **hornear a morph targets y reconstruir el driver (PoseDriver) en el AnimBP** — Unreal no lee el `poseInterpolator` directamente.

### Solver RBF con weightDriver / SHAPES (brave rabbit)
- **Qué es.** SHAPES + el nodo `weightDriver` de Ingo Clemens: RBF N-dimensional o *vector angle reader*. Estándar de facto para correctivos por pose a escala.
- **Cómo funciona.** Modo *vector angle* (ángulo entre un vector del joint y una referencia) y modo *RBF* (N poses en espacio M-dimensional). SHAPES orquesta targets, poses, split con RampWeights, todo como nodos inspeccionables.
- **Precisión.** Alta.
- **Límites.** Licencia SHAPES (el weightDriver suelto es gratuito); no dinámico; poses de driver duplicadas rompían el solver; curva de aprendizaje de kernels/regularización.
- **Cuándo usarlo.** Muchos correctivos y combos multi-joint (hombro+brazo, cadera+pierna).
- **Encaje.** `weightDriver` scriptable e integrable; horneable a morph targets + curvas para motor.

### RBF Manager de mGear
- **Qué es.** Herramienta open source de mGear para correctivos RBF con UI de poses, gratuita y versionable.
- **Cómo funciona.** Defines driver, atributos driver, driven (blendshapes/transforms/weights) y registras poses ("Add Pose"). Es un Set Driven Key de siguiente nivel (N drivers, M driven, interpolación radial).
- **Precisión.** Alta.
- **Límites.** No dinámico; autoría por pose. **Correcciones de versión (mGear 5.1 / RBF Manager 2.0):** el solver nuevo **ya gestiona correctamente las posiciones de driver duplicadas** (el caveat de "poses duplicadas rompen el solver" aplica a versiones <2.0); y mGear pasó a un **fork propio `mGearWeightDriver`** (derivado del de Ingo Clemens), **no** empaqueta ya el nodo de SHAPES (instalable aparte).
- **Cuándo usarlo.** Autorig apoyado en mGear, correctivos sin coste de licencia, versionables en Git.
- **Encaje.** Python abierto (`rbf_manager_ui.py`), llamable desde tu builder; salidas horneables a motor.

### Driven keys por ángulo de joint / vector angle reader
- **Qué es.** El disparador más simple: correctivos con curvas 1D ligadas al ángulo de flexión, sin RBF.
- **Cómo funciona.** Ángulo del joint (o *vector angle reader*) → `remapValue`/curva → peso del blendshape. Reutiliza tu patrón mental de remapValue de colisión.
- **Precisión.** Media.
- **Límites.** 1D: mal en combos de varios joints (popping en diagonales); escala mal con muchas arrugas.
- **Cuándo usarlo.** Arrugas simples de una sola articulación; prototipo antes de invertir en PSD/RBF.
- **Encaje.** Trivial de automatizar; exportable como curvas de morph.

### Correctivos y wrinkle maps dirigidos por tensión de malla
- **Qué es.** Disparar por la **tensión local** (estiramiento/compresión de aristas), no por ángulo; conduce blendshapes de arruga y/o blend de normal/displacement maps.
- **Cómo funciona.** Calculas una máscara de tensión (longitud de aristas/área vs. reposo) —construida a mano/utility propia, **no** salida del nodo `tension`— y la usas para mezclar shapes de compresión/estiramiento y/o interpolar wrinkle maps en el shader.
- **Precisión.** Alta.
- **Secundario.** **Ninguno** (la tensión es función instantánea de la pose actual, sin historia temporal; no hay inercia).
- **Límites.** Depende de la base skin/wrap; mapeo delicado (parpadeo); el detalle vía maps es de shading (no cambia silueta salvo displacement real).
- **Cuándo usarlo.** Arrugas que reaccionan a la deformación real, más orgánicas que ligar a un joint; primeros planos con normal/displacement.
- **Encaje.** Máscara de tensión por OpenMaya + blendshapes + shader; el blend de wrinkle maps por tensión exporta directo a UE/Unity.

### Deformador procedural de arrugas por compresión (WrinkleMatic)
- **Qué es.** Genera pliegues/líneas de tensión de forma procedural según compresión/estiramiento y volumen, sin esculpir ni simular.
- **Cómo funciona.** Analiza la deformación local y sintetiza folds/tension lines con parámetros de escala/frecuencia/"memoria" (persistencia de forma).
- **Precisión.** Media (menos control que un correctivo esculpido).
- **Secundario.** **Ninguno** (evalúa cada frame independiente, sin caché ni sim; la "memoria" es persistencia de forma, no inercia).
- **Límites.** No dinámico ni colisión; depende de topología/UVs y tuning; puede verse "de goma"; dependencia de plugin.
- **Cuándo usarlo.** Arrugas de compresión rápidas en muchas zonas, base antes de refinar con correctivos esculpidos.
- **Encaje.** Se apila como deformer; **interactivo en viewport de Maya, no exportable a motor sin hornear** (a diferencia de blendshape/PSD/RBF de morph target).

### Nodo PSD/RBF propio en OpenMaya (custom scripted deformer)
- **Qué es.** Tu propio nodo de interpolación por poses (RBF/kernel a medida) con `MPxNode`/`MPxDeformerNode`.
- **Cómo funciona.** Entrada = vector de pose (ángulos/quaterniones/medidas de tensión); salida = pesos de targets resolviendo un sistema RBF (kernel, regularización). Decides espacio de poses (swing/twist separados), normalización y horneado.
- **Precisión.** Alta.
- **Secundario.** Ninguno.
- **Límites.** Desarrollo/mantenimiento alto; matemática RBF (mal condicionamiento con poses cercanas); autoría manual; riesgo de reinventar weightDriver/mGear.
- **Cuándo usarlo.** Control total, cero licencias, comportamiento que las tools de caja no dan (interpolación en quaterniones, drivers de tensión custom).
- **Encaje.** Máximo encaje con tu autorig; **"tiempo real" = evaluación interactiva en viewport, NO ejecución en motor**: para engine requiere hornear (vertex cache o morphs+curvas). Referencia: cvwrap como plantilla de `MPxDeformerNode`.

### Métodos que faltaban en esta familia
- **Combination / combo shapes (`combinationShape`).** Correctivos disparados por el **producto de varios pesos de blendshape** (co-activación), no por ángulo ni tensión. Es un **eje de disparo entero** que faltaba; canónico para combos (hombro+codo, cadera+pierna) y para encadenar correctivos que solo deben aparecer juntos.
- **Delta Mush como capa correctiva.** Suaviza el skin base y **reduce drásticamente el nº de correctivos a esculpir**; método canónico, a menudo previo a PSD/RBF.
- **In-between (inbetween) targets.** Sculpts intermedios a lo largo de **un único driver** para arreglar la interpolación 1D en el punto medio; alternativa barata a un PSD completo.
- **Vector/pose reader por swing-twist (half-angle joint).** Descompone la rotación en swing y twist para evitar el problema de interpolar Euler; técnica reutilizable por sí misma, no solo dentro del nodo custom o de MetaHuman.

---

## Familia 5 — Simulación física de tela (offline / cine)

Resuelve la tela como sistema físico (position-based/XPBD o FEM) con **colisión y contacto reales**. Es **lo más preciso** para arrugas, pliegues, contacto, deslizamiento y stretch, porque la forma emerge de la dinámica y del patronaje, no de una interpolación de pesos. Precio: cómputo, art-direction indirecta (una sim no se "posa" a mano) y no interactividad en el rig. El nudo del trabajo es el flujo **SIM→RIG**. Recomendación de encaje: seguir simulando en **Vellum** (rápido, colisiones robustas, substeps controlables) sobre el skin de Maya en Alembic, y devolver a Maya vía Alembic + wrap/blendshapes; **nCloth/Qualoth** cuando el plano deba resolverse íntegro en Maya; **Ziva** solo como capa fina de piel/fascia.

### Houdini Vellum Cloth (XPBD)
- **Qué es.** Solver basado en posiciones (XPBD) del framework Vellum. El más iterativo y controlable, y encaja con tu CFX.
- **Cómo funciona.** Malla triangulada con constraints de stretch/shear/bend (y area/volume); XPBD resuelve por proyección iterativa con stiffness por tipo; colisión SDF/point-based + self-collision. Precisión por **substeps** e **iteraciones**; pin/attach y rest/attach para mezclar con el skin.
- **Precisión.** Alta. **Secundario: simulado.**
- **Límites.** Round-trip (no interactivo en el rig); art-direction indirecta (rest shapes/pins); tuning de material/substeps; self-collision cara en telas muy plegadas.
- **Cuándo usarlo.** Iterar rápido con contacto preciso; faldas/vestidos largos de Anne/Freya donde el choque con las piernas debe ser real.
- **Encaje.** Exporta el skin como collider Alembic, simula en Vellum, devuelve a Maya (wrap/blendshape) o entrega el cache. **Sustituye con creces tu colisión por distancia.**

### Maya nCloth (Nucleus)
- **Qué es.** Solver **basado en posiciones/constraints** del framework Nucleus, dentro de Maya. *(Corrección: no es "mass-spring" clásico; es una red de partículas enlazadas resuelta por relajación tipo Verlet, position-based, en el mismo espíritu que PBD. La diferencia con Vellum es de implementación/robustez/control —substeps, XPBD stiffness independiente—, no una clase de solver distinta.)*
- **Cómo funciona.** La prenda pasa a nCloth; stretchResistance/bendResistance/rigidity; nRigid como collider; Substeps y Max Collision Iterations; Space Scale; constraints e input attract/rest para mezclar con la pose animada.
- **Precisión.** Alta. Secundario: simulado.
- **Límites.** Menos wrinkling fino que Qualoth/FEM; tendencia a estirarse si el tuning no compensa; más lento de iterar que Vellum; self-collision cara.
- **Cuándo usarlo.** Plano resuelto íntegro en Maya, o prototipar antes de decidir pipeline.
- **Encaje.** Cachea (nCache/Alembic) y devuelve a un asset controlable; convive con AdonisFX (ambos en Maya, solvers separados).

### Qualoth (FXGear) / Syflex
- **Qué es.** Plugins de tela de calidad de largometraje para Maya. Qualoth destaca en wrinkling y aguante bajo compresión; **Syflex** *(método que faltaba)* es un solver clásico muy estable para movimiento rápido, usado en largometrajes (King Kong, Superman Returns, Spider-Man 3).
- **Cómo funciona.** Qualoth calcula energía de deformación (stretch/shear/bend) sobre polígonos triangulados con damping, fricción, drag e histéresis (plasticidad), colisión robusta + self-collision de calidad, subframes.
- **Precisión.** Alta. Secundario: simulado.
- **Límites.** Licencia comercial (coste alto); tuning de materiales; no interactivo (round-trip); menos iterativo que Vellum.
- **Cuándo usarlo.** Máxima calidad de arruga en Maya: vestidos de gala, telas gruesas, primeros planos.
- **Encaje.** Vive en Maya como nCloth: flujo SIM→RIG idéntico (cache Alembic + wrap/blendshape).

### Marvelous Designer (patronaje + sim)
- **Qué es.** Diseño por patronaje 2D cosido en 3D con sim integrada. La precisión nace del **corte real** de la prenda.
- **Cómo funciona.** Patrones 2D → costuras alrededor del avatar → drape; presets físicos (algodón/seda/cuero); avatar animado en Alembic → grabar sim → exportar cache o malla cosida.
- **Precisión.** Alta. Secundario: simulado.
- **Límites.** No es solver de plano final orientado a rig; la topología de costura puede necesitar retopo; round-trip de avatar con timing exacto; interfaz distinta.
- **Cuándo usarlo.** Construir la prenda con topología y drape correctos, y como fuente de la malla + rest para simular en Vellum.
- **Encaje.** Fuente ideal del rest; MD para modelar/drape, Houdini/Qualoth para la sim final. Reduce interpenetraciones de partida.

### Ziva Cloth (FEM, capa fina de fascia/piel)
- **Qué es.** Solver de la línea Ziva VFX. *(Corrección importante: la propia doc de Ziva indica que zCloth "no es una solución general de tela todavía; sirve para fascia y piel". Reencuadrar estrictamente como **detalle de epidermis/fascia acoplado a carne**, NO como solver de prendas.)*
- **Cómo funciona.** Usa el modelo **Baraff-Witkin** (no un FEM de tela genérico) **acoplado por FEM al tejido subyacente** (fat); al comprimirse/estirarse el tejido, la naturaleza acoplada produce arrugas.
- **Precisión.** Alta para piel; faldas/vestidos amplios quedan **fuera de alcance**.
- **Límites.** No idóneo para tela suelta; coste/complejidad FEM; **disponibilidad: Unity discontinuó toda la línea Ziva el 2 de abril de 2024 (cese de venta y soporte); la IP pasó en licencia exclusiva a DNEG.** No hay ruta de licenciamiento nueva.
- **Cuándo usarlo.** Segunda piel acoplada a carne (uso no soportado como tela general); referencia conceptual junto a AdonisFX.
- **Encaje.** Conceptualmente análogo a AdonisFX (FEM acoplado); salida cacheable a Alembic.

*(Método que faltaba: **solver FEM/Cloth nativo de Houdini pre-Vellum** —Cloth Object / Finite Element en DOPs—, la vía FEM real dentro de Houdini; Vellum es XPBD, no FEM.)*

### SIM → CACHE: bake a mesh cache Alembic
- **Qué es.** El flujo de salida más directo: bakear la sim a `.abc` (posición por vértice/frame, topología constante) para entregar el plano.
- **Precisión.** Alta (traslada la sim exacta). **Secundario: simulado.** No editable.
- **Límites.** Re-simular si cambia la anim; pesado en disco; topología constante; no sirve como rig entregable.
- **Cuándo usarlo.** Plano aprobado → entregar CFX a lighting/render.
- **Encaje.** Es literalmente cómo devuelves Vellum a Maya; agnóstico de solver.

### SIM → RIG: correctivos por pose (cache-to-blendshape / PSD)
- **Qué es.** Devolver la sim a un asset **controlable**: capturar formas representativas y montarlas como correctivos PSD/RBF sobre el skin.
- **Cómo funciona.** Skin base como capa 0; delta skin↔sim en poses clave → target (`Bake Topology To Targets`); conectados a drivers (ángulos/RBF). Se pueden limpiar a mano.
- **Precisión.** Media (aproxima función-de-pose, no dinámica). **Secundario: aproximado.**
- **Realtime.** **Interactivo/determinista en el viewport de Maya, no realtime garantizado en motor** (con muchos targets + deltaMush cae por debajo).
- **Límites.** No hay inercia/swing salvo capa dinámica extra; muchos targets = trabajo; generalización según muestreo.
- **Cuándo usarlo.** Calidad de sim en un rig deformable, re-editable y sin resim por plano.
- **Encaje.** El **salto natural sobre tu copy skin**: Vellum como verdad-terreno, correctivos disparados por tu autorig (Python/RBF).

### SIM → RIG: upres por wrap/proximity (low-res sim + detalle)
- **Qué es.** Simular una low-res estable y transferir su movimiento a la hero por wrap/proximity, con detalle fino encima.
- **Cómo funciona.** Sim low-res; hi-res capturada (`wrap`/`proximityWrap` en Maya; **Cloth Capture + Cloth Deform** en Houdini); micro-arrugas por displacement/wrinkle maps/sim de detalle.
- **Precisión.** Alta. Secundario: simulado.
- **Límites.** El wrap solo interpola (si la low-res no tiene la arruga, tampoco la hero); coste de captura; sliding si la low-res es basta.
- **Cuándo usarlo.** Malla de render pesada/inestable; iterar dinámica en low-res.
- **Encaje.** Sim low-res en Vellum → cache Alembic → prenda de render wrapeada en Maya; añade detalle sin re-simular.

### Colisiones, constraints y calidad de solver (transversal)
- **Qué es.** Metodología que determina cuán precisa es **cualquier** sim: colisión con grosor (thickness/offset) para penetración y deslizamiento; self-collision; pins/attach/weld; **substeps** (contra tunelización a alta velocidad), **iteraciones** (rigidez/limpieza) y resolución de malla (tamaño mínimo de arruga).
- **Precisión.** Alta. Crítico en faldas rápidas que golpean piernas (donde tu remapValue falla).
- **Límites.** Coste crece con substeps/self-collision; explosiones si el rest interpenetra; tuning delicado.
- **Encaje.** **Reemplaza conceptualmente tu push por distancia**: ajustar substeps y collision thickness sobre el collider Alembic del skin es exactamente el control que hoy te falta.

### Guiar/art-direct la sim (rest shapes, goal, blend con skin)
- **Qué es.** Hacer art-directable una sim: rest shapes animadas, goal/target weights y mezcla con el skin, sin perder el look físico.
- **Cómo funciona.** Forma objetivo (rest animado o el skin como goal) con peso por vértice/tiempo; Vellum (rest animado/attach con stiffness variable), nCloth (input attract/rest con mapas), Qualoth (target/rest). Weight map: cintura sigue al cuerpo, bajo vuela libre.
- **Precisión.** Alta. Secundario: simulado.
- **Límites.** Goal alto mata la dinámica; goal bajo no dirige; necesita buenas rest shapes; pintado por plano.
- **Cuándo usarlo.** Silueta/acción concreta que la sim libre no da; estabilizar zonas; mezclar keyframe con dinámica.
- **Encaje.** Usa tu skin/ribbons como goal de la prenda y pinta pesos; puente entre rig controlable y sim física.

---

## Familia 6 — Tela en tiempo real y juegos

Cada personaje tiene un presupuesto de milisegundos y de huesos/partículas, así que **casi nunca se simula toda la prenda**. Estrategia dominante: **híbrida** —skinning/huesos para la deformación principal, y solo la parte que necesita vida dinámica delegada al motor—. Cuatro bloques: (1) solvers nativos (Chaos, NvCloth legacy, Unity Cloth), (2) huesos con física (spring bones), (3) horneado de sim offline a datos ligeros (sim-to-bone, VAT, ML), (4) trucos de superficie (wrinkle/tension maps, PSD/RBF). Regla: cuanto más cerca de cámara y menos instancias, más presupuesto para solver o correctivos; para multitudes, huesos con muelle o VAT.

### Chaos Cloth (Unreal Engine)
- **Qué es.** Solver nativo de UE (XPBD, partículas + constraints), autorable en el motor (Panel Cloth / Dataflow). Sustituye a APEX.
- **Cómo funciona.** Prenda como Skeletal Mesh → Cloth Asset; `max distance` pintado (0 = pegado al skin, alto = libre); backstop anti-penetración; colisión contra cápsulas/esferas de la Physics Asset; substeps/iteraciones; viento, self-collision, LOD de sim; malla de render envuelta a la de sim.
- **Precisión.** Alta. **Secundario: simulado.**
- **Límites.** Coste por personaje (no escala a multitudes); depende del pintado y del tuning; malla de sim bien topologizada; determinismo limitado entre plataformas/framerates; colisión por cápsulas (pincha en poses extremas).
- **Cuándo usarlo.** Protagonistas/cinemáticas in-engine donde el vestido debe volar y chocar con las piernas de forma creíble.
- **Encaje.** Preparas la malla de sim en Maya (Houdini para modelar/retopo la malla de sim, no "vía SideFX Labs"), exportas a UE; tu autorig da casi directa la Physics Asset. **Reemplaza tu colisión por distancia por colisión nativa**; deja tus ribbons para la silueta base y Chaos solo para el vuelo.

### NvCloth / APEX Clothing (PhysX, legacy)
- **Qué es.** Solver de NVIDIA, estándar en UE antes de Chaos y en muchos engines propios / Unity vía PhysX. PBD ligero.
- **Cómo funciona.** Partículas con constraints; `max distance` pintado + coeficientes de colisión; gravedad/viento/inercia del hueso raíz; colisión contra esferas/cápsulas.
- **Precisión.** Media. Secundario: simulado.
- **Límites.** En retirada en Unreal; self-collision limitada; solo primitivas; integrar NvCloth a mano es trabajo de programación.
- **Cuándo usarlo.** UE4/Unity/engine propio con muchos personajes baratos.
- **Encaje.** Flujo de export desde Maya casi idéntico al de Chaos; el conocimiento se transfiere. Menos indicado si ya estás en UE5.

### Cloth de Unity (componente Cloth + SkinnedMeshRenderer)
- **Qué es.** Sistema de tela de Unity (PhysX) acoplado al Skinned Mesh Renderer.
- **Cómo funciona.** Partículas en vértices; Max Distance y Surface Penetration por vértice; Capsule/Sphere colliders; self/inter-collision; corre en CPU cada FixedUpdate mezclando con la pose skinneada.
- **Precisión.** Media. Secundario: simulado.
- **Límites.** Frágil: solo cápsulas/esferas, tuning tedioso, jitter con framerate variable, no escala a multitudes; muchos estudios lo sustituyen por **Obi Cloth / Magica Cloth** o huesos con muelle.
- **Cuándo usarlo.** Unity con vestidos de personaje jugable/cinemáticas, aceptando limitaciones del stock.
- **Encaje.** Falda de Maya con skinning + componente en Unity con cápsulas de piernas (equivalente a tu colisión por distancia); NPCs a huesos con muelle, componente Cloth para heroes cercanos.

### Bone-chain physics / spring bones en engine
*(Desarrollado en la Familia 3.)* Reemplazo natural y más robusto de tu push por remapValue: exportas la cadena y Kawaii/AnimDynamics hace la física y la colisión en engine. **Kawaii Physics** es frame-rate independiente y corre en el hilo de animación; **AnimDynamics** es dependiente del framerate y menos estable.

### Ropa skinneada a huesos animados a mano (sin física)
- **Qué es.** La prenda se skinnea a huesos que se mueven a mano; 100% determinista, sin solver.
- **Cómo funciona.** Rig de falda con FK o atributos swing/twist; colisión resuelta a mano o con tu push por distancia; en engine solo skinning.
- **Precisión.** Media. **Secundario: ninguno.**
- **Límites.** Todo balanceo/arruga hay que animarlo (carísimo en tela larga); no reacciona a fuerzas; sin correctivos se ve "de goma".
- **Cuándo usarlo.** Control artístico total: cinemáticas, poses hero, gameplay scripteado, plataformas de bajísimo presupuesto.
- **Encaje.** Es tu estado actual llevado a engine; documentarlo sirve para saber cuándo es correcto (control) y cuándo subir a huesos-con-muelle o solver.

### Simulación offline horneada a huesos (sim-to-bone)
- **Qué es.** Simular con un solver de calidad y hornear a una cadena de huesos: el engine reproduce animación skinneada barata con look de sim real.
- **Cómo funciona.** Sim en Houdini/Maya → fitting de huesos a la malla → bone baking (rotación/traslación por frame que mejor reproduce la deformación; base teórica: **skinning decomposition, Le & Deng, SIGGRAPH Asia 2012**) → skin de la prenda a esos huesos → export de clips. Ciclos representativos (idle/run/turn) para gameplay libre.
- **Precisión.** Media. Secundario: simulado.
- **Límites.** No interactivo (solo reproduce lo horneado); huesos capturan mal pliegues finos; el nº de huesos limita fidelidad; re-hornear si cambia el diseño.
- **Cuándo usarlo.** Look de Vellum/Qualoth sin simular en runtime: multitudes, móvil, cámara fija, ciclos de locomoción.
- **Encaje.** Aprovecha directamente tu CFX; escribe en Python la herramienta de solve huesos-desde-mesh (OpenMaya). Puente natural offline→runtime. *(Es justo el flujo de Kiel Figgins "sim, bake nCloth onto rigs" que la familia menciona pero no formalizaba como método.)*

### Vertex Animation Textures (VAT)
- **Qué es.** Hornear la sim (posiciones/normales por vértice/frame) en texturas; un shader de vértices las lee y desplaza la malla exactamente como la sim, en GPU.
- **Cómo funciona.** SideFX Labs VAT ROP → EXR/PNG (posición en RGB, normales en otro mapa; eje X = vértice, Y = frame) → material WPO en engine. Coste casi fijo, independiente de la complejidad.
- **Precisión.** Alta (reproduce pliegues nuevos). Secundario: simulado.
- **Límites.** Pre-horneado, no interactivo; topología/orden de vértices congelados; memoria/ancho de banda; mezclar clips es más difícil que con huesos; no art-directable.
- **Cuándo usarlo.** Detalle exacto de sim a coste mínimo para muchas instancias: multitudes, banderas, capas de NPC, bucles.
- **Encaje.** Simula el vestido en Houdini y exporta VAT a UE/Unity; complementa el sim-to-bone (VAT para pliegue fino; huesos para mezclar animaciones).

### Wrinkle / tension normal maps
- **Qué es.** Blendear normal maps esculpidos (comprimido/estirado) controlados por tensión de malla o ángulo de hueso: ilusión de pliegues sin geometría.
- **Cómo funciona.** Peso de tensión por región (cambio de longitud de aristas, o ángulo de hueso) → interpola normal maps por región enmascarada en el shader. *(Corrección: la técnica **no** procede del talk de The Order: 1886 —ese trata de morph rig, desgarro y blending de materiales, no de tension/wrinkle blending—; la tension technique se popularizó en pipelines faciales de otros estudios. Base útil: literatura de arrugas por tensión de rostro, arXiv 2210.03529.)*
- **Precisión.** Media. **Secundario: ninguno.**
- **Límites.** Es ilusión: no cambia silueta ni contorno; requiere esculpir mapas y enmascarar; el driver por tensión cuesta en runtime.
- **Cuándo usarlo.** Prenda ajustada con flexiones donde el skinning se ve liso; complemento casi obligado de todos los métodos, escala a cualquier nº de personajes.
- **Encaje.** Sobre el skin/huesos que ya montas; genera los pesos de tensión con OpenMaya. "La última milla" de realismo de arrugas que el copy skin nunca dio.

### Correctivos PSD / blendshapes por pose (RBF pose driver en engine)
- **Qué es.** Blendshapes correctivos disparados en runtime por ángulo de hueso (RBF/PoseDriver): **aquí sí cambia la geometría** (arrugas/pliegues reales, deterministas).
- **Cómo funciona.** Esculpes por pose en Maya; en engine un RBF Solver/Pose Driver activa el peso según cercanía a las poses ejemplo; malla = skin + suma de correctivos.
- **Precisión.** Alta. Secundario: ninguno.
- **Límites.** Solo poses esculpidas; sin dinámica; autoría cara; memoria/GPU con muchos.
- **Cuándo usarlo.** Zonas de flexión críticas y repetibles, look idéntico y art-dirigido.
- **Encaje.** Replicas los correctivos que haces para el cuerpo, exportados con drivers de ángulo a UE (RBF Solver/AnimGraph) o Unity. *(Herramientas: mGear, SHAPES, poseInterpolator nativo — evitar "ePose", que no corresponde a ninguna tool conocida.)*

### UE5 Deformer Graph (Optimus) *(método que faltaba)*
- **Qué es.** Deformadores de malla en **compute** en runtime para corregir volumen/arrugas sin ML ni solver de partículas.
- **Cómo funciona.** Grafo de deformación que evalúa en GPU sobre el Skeletal Mesh; infraestructura distinta del ML Deformer y del custom GPU cloth.
- **Precisión.** Media-alta. Secundario: ninguno.
- **Cuándo usarlo.** Correctivos/superficie en runtime con más flexibilidad que morph targets.
- **Encaje.** Bloque de correctivos runtime, complementario a spring bones y wrinkle maps.

### ML Deformer / neural cloth en engine
*(Desarrollado en la Familia 7; en runtime UE aprende pose→offsets. **secondaryMotion: ninguno** —es pose-driven, sin entrada de velocidad—; captura mal la inercia y **no reemplaza un solver** para vuelo. Complementa con bone-chain para la parte inercial.)*

### Tela GPU personalizada (PBD/XPBD en compute / Niagara)
- **Qué es.** Solver propio en compute shaders o sistema de partículas GPU, para casos que los solvers de caja no cubren o para control total del coste a escala.
- **Cómo funciona.** Malla como partículas en GPU; kernel integra y resuelve constraints (distancia/flexión/colisión) en paralelo; colisión SDF/cápsulas; Niagara o plugin de compute.
- **Precisión.** Alta. Secundario: simulado.
- **Límites.** Coste de desarrollo/depuración alto; GPU elevado; menos art-directable; portabilidad; mantenimiento.
- **Cuándo usarlo.** Escalas/comportamientos que Chaos/Unity no dan; territorio de graphics/tech programmer.
- **Encaje.** Solo con engine propio y programación gráfica; para tu caso, Chaos o huesos con muelle cubren casi todo más barato. Útil como techo de lo posible.

*(Método que faltaba: **sim en proxy low-res transferida a la hero por wrap/mesh deformer (LBS wrap)** — patrón estándar en juegos, aplicable también a sim horneada y a solvers de terceros, no solo como subpaso interno de Chaos.)*

---

## Familia 7 — Métodos por Machine Learning / data-driven

Buscan la **precisión de una sim con el coste de un deformador**. Patrón en tres fases: (1) generar datos (simular con nCloth/Qualoth/Vellum/MD o captura 4D), (2) entrenar un modelo (MLP, GAN, PCA+red, GNN) que mapea pose/forma/estado a geometría o a detalle, (3) inferir en milisegundos. Tres intenciones: **aproximar sim/deformadores** (ML Deformer Maya/UE, deformador propio), **aprender dinámica en subespacio/grafo** (Subspace Neural Physics, HOOD, SNUG/PBNS) y **sintetizar solo el detalle** (DeepWrinkles, TailorNet, Deep Detail Enhancement). Límites estructurales compartidos: dependen del dataset, generalizan mal fuera de lo entrenado y exigen infraestructura de entrenamiento. **Encaje inmediato para ti:** usar tus sims de Vellum/nCloth como ground truth para entrenar un deformador ligero (ML Deformer nativo o propio), reservando la sim real para el render.

### ML Deformer de Maya (Autodesk)
- **Qué es.** Deformador nativo (Maya **2025.2+**) que aproxima deformaciones complejas (nCloth/Vellum cacheada, wraps, correctivos) desde una animación de entrenamiento, para playback interactivo.
- **Cómo funciona.** Nodo `mlDeformer` delante de los deformadores caros; rango de movimiento (mocap/keyframes/Pose Generation) → evalúa el sistema pesado → **entrena sobre PyTorch** *(corrección: el backend es PyTorch, no TensorFlow)*; toggle para volver al deformador original en render.
- **Precisión.** Media. **Secundario: ninguno** (deformación por pose; cualquier balanceo debe venir de otro sistema salvo que codifiques inputs de velocidad).
- **Realtime.** Interactivo **dentro de Maya**; **no se exporta ni corre en engine**. Autodesk lo posiciona explícitamente para casos "donde la precisión no es crítica" (fondo, crowds, previz).
- **Límites.** Solo aproxima; generaliza mal fuera del rango; re-entreno si cambia rig/prenda.
- **Cuándo usarlo.** Playback interactivo de la falda para animación mientras Vellum se reserva para render.
- **Encaje.** Menor fricción para empezar en ML sin salir de Maya.

### ML Deformer Framework / Chaos ML Cloth (Unreal)
- **Qué es.** Framework de UE para deformación de tela de alta fidelidad en tiempo real aproximando una sim offline con una red ejecutada en runtime (NNE).
- **Cómo funciona.** (a) ML Deformer: Skeletal Mesh + Animation Sequence + Geometry Cache objetivo → red que predice el desplazamiento sobre el skin. (b) ML Cloth: datos con Chaos Cloth + Panel Cloth Node Graph → sim de tela neuronal en runtime con más fidelidad que Chaos clásico.
- **Precisión.** Media-alta. Secundario: simulado (según entrenamiento).
- **Límites.** ML Cloth experimental/beta, dependiente de versión UE; dataset grande; generaliza solo a lo entrenado; el setup vive en el engine.
- **Cuándo usarlo.** Juegos/tiempo real, cinemáticas in-engine con más fidelidad que la sim clásica sin pagar su coste por frame.
- **Encaje.** Exporta tus sims de Vellum/nCloth como Alembic/Geometry Cache como target de entrenamiento.

### ZivaRT (Ziva Real-Time) — **descontinuado**
- **Qué es.** Solución ML que reconstruye deformaciones no lineales (músculo/piel, correctivos de prenda ajustada) en runtime desde un set de shapes.
- **Estado (corrección grave).** **Unity descontinuó toda la línea Ziva (VFX, RT, Face Trainer) el 2 de abril de 2024**: cese de venta y soporte, portal cerrado; la IP pasó en licencia exclusiva a DNEG (uso interno). **No es adquirible.** Sirve solo como **referencia conceptual** del patrón sim→ML runtime.
- **Precisión.** Alta (soft-tissue). Secundario: aproximado.
- **Límites.** Enfocado a tejido/skin, no tela suelta; atado al ecosistema Unity; sin ruta de licenciamiento nueva.
- **Encaje.** Equivalente conceptual a comprimir tus setups AdonisFX a un runtime ligero; ya no como herramienta viva.

### Deformador correctivo neuronal propio (in-house) en Maya/Python
- **Qué es.** Tu red que predice desplazamientos correctivos de vértice desde la pose, como `MPxDeformerNode`.
- **Cómo funciona.** Dataset (poses ↔ geometría objetivo de tus sims/esculpidos) → MLP en PyTorch (features swing/twist) → delta en pose-space → pesos evaluados en el nodo. Es el hermano aprendido del PSD/RBF: generaliza entre shapes en vez de interpolar.
- **Precisión.** Alta. Secundario: aproximado (necesita inyectar velocidad/estado previo para dinámica).
- **Límites.** Mantienes toda la infraestructura; overfitting con pocos datos; coste de ingeniería alto frente a un PSD clásico.
- **Cuándo usarlo.** Control total, cero licencias, arrugas repetibles por pose en cadera/ingle/rodilla.
- **Encaje.** Encaje ideal con tu perfil; tus sims de Vellum son ground truth directo. Referencia práctica: *Fast and Deep Deformation Approximations* (Bailey et al., **SIGGRAPH 2018**) — el paper fundacional de esta rama.

### Subspace Neural Physics (Deep Cloth, Ubisoft)
- **Qué es.** Sim data-driven que avanza la dinámica de la tela en un subespacio PCA reducido, capturando inercia y ondeo.
- **Cómo funciona.** Reduce la geometría a PCA; una **red feed-forward autoregresiva** *(corrección: no es RNN)* recibe el estado reducido del frame previo + fuerzas externas y predice el siguiente estado, reproyectado a la malla. La dinámica viene del condicionamiento por estado previo. Aceleraciones reportadas 300–4000×.
- **Precisión.** Media-alta. Secundario: simulado.
- **Límites.** Drift en secuencias largas; PCA limita detalle fino y fija topología; hay que implementar el runtime; generaliza al dominio entrenado.
- **Cuándo usarlo.** Tela dinámica en tiempo real (juegos/VR) con ondeo e inercia reales.
- **Encaje.** Modelo mental clave para **reemplazar tu colisión por distancia por dinámica aprendida** de tus sims de Vellum.

### DeepWrinkles
- **Qué es.** (ECCV 2018) Deformación global desde subespacio aprendido de captura 3D real + arrugas de alta frecuencia por GAN condicional sobre normal maps.
- **Precisión.** Media. Secundario: ninguno (el detalle vive en el normal map, no cambia silueta).
- **Límites.** Necesita captura 4D registrada; específico de la prenda capturada.
- **Cuándo usarlo.** Arruga fina en normal map para render; base de baja frecuencia del rig/sim ligera.
- **Encaje.** Separa responsabilidades: rig/sim → baja frecuencia, red → arruga fina; datos 4D difíciles in-house.

### TailorNet
- **Qué es.** (CVPR 2020) Predice la geometría de la prenda como función de pose, forma corporal y estilo, separando baja/alta frecuencia (MLP + mixture-of-experts por pose).
- **Precisión.** Media. Secundario: ninguno (función de pose estática).
- **Límites.** Atado a cuerpos SMPL y a estilos entrenados; un modelo por tipo de prenda; no agnóstico a topología.
- **Cuándo usarlo.** Virtual try-on, avatares paramétricos.
- **Encaje.** Más valioso como **referencia conceptual** (descomposición baja/alta + mixture-of-experts) para tu correctivo propio que como herramienta para cine.

### Neural cloth auto-supervisado (PBNS / SNUG)
- **Qué es.** Redes que aprenden la deformación **sin dataset de sim**, minimizando la energía física (stretch/bend/colisión/gravedad/inercia) como loss. PBNS: cuasi-estático por pose; SNUG (CVPR 2022): reformula el integrador implícito → aprende dinámica auto-supervisada.
- **Precisión.** Media. Secundario: simulado (SNUG).
- **Límites.** Cuerpo/topología fijos por modelo; rango de materiales limitado; colisión aprendida falla en poses extremas; menos control fino.
- **Cuándo usarlo.** Cuando no puedes generar un dataset masivo: drapeado/dinámica con entrenamiento barato definiendo bien energías/material.
- **Encaje.** Filosóficamente afín a un creature TD (física como objetivo); inspira un correctivo físicamente plausible sin cachear miles de frames; código de referencia asume SMPL.

### HOOD (Graph Neural Networks)
- **Qué es.** (CVPR 2023) GNN con message passing jerárquico, entrenamiento no supervisado, que predice dinámica de tela para prendas/cuerpos/materiales/topologías arbitrarios **sin reentrenar por prenda**.
- **Cómo funciona.** Prenda como grafo; message passing multinivel propaga modos rígidos y preserva detalle local; loss física; admite cambios de topología/material en inferencia. Hereda de MeshGraphNets (DeepMind).
- **Precisión.** Alta. Secundario: simulado.
- **Límites.** Inferencia GNN más cara que un MLP; drift en secuencias largas; no-penetración no garantizada; integrar en Maya no es trivial.
- **Cuándo usarlo.** Tela suelta de vuelo libre (vestidos largos, capas) que generaliza entre prendas/personajes. La alternativa moderna más *sim-like* a los métodos LBS.
- **Encaje.** La vía más generalizable de la familia; código público para experimentar; encaja con vestidos tipo Anne/Freya.

### Deep Detail Enhancement / super-resolución neuronal de arrugas
- **Qué es.** (CGF 2021) Red que añade detalle de arruga plausible sobre una geometría grosera, como transferencia de estilo (Gram) sobre normal maps.
- **Precisión.** Media. Secundario: ninguno (detalle en normal map, no cambia silueta).
- **Realtime.** **No/near-interactive** en la variante original *(corrección: no es realtime garantizado)*; su evolución **Neural Garment Dynamic Super-Resolution (SIGGRAPH Asia 2024)** desplaza **geometría real** (más caro).
- **Límites.** Puede alucinar arrugas incoherentes con la física de la base.
- **Cuándo usarlo.** Base correcta en silueta pero sin micro-arruga: pipeline coarse-to-fine para primeros planos.
- **Encaje.** Capa final sobre tu rig/sim: tú aportas la forma global (ribbons/joints/Vellum low-res), la red la arruga fina.

*(Método que faltaba: **A Deep Emulator for Secondary Motion of 3D Characters** (Zhang et al., CVPR 2021) — aprende a añadir dinámica secundaria como post-proceso sobre una deformación primaria; relevante para el hueco de "secundario" que los métodos pose-space no cubren.)*

---

## Familia 8 — Flujos híbridos y estrategia de capas

Casi ningún plano de cine se resuelve con una sola técnica. Principio: **capa base (skin/wrap) para silueta y contacto** + **capas de secundario (sim, correctivos, jiggle)** para arrugas, inercia y descuelgue. La decisión de qué capa aporta precisión dónde depende de tres ejes: **ajuste** (ajustada → skin+PSD; suelta → sim o cadena mecánica con colisión), **medio** (cine tolera cachés/tech-anim por plano; juegos obliga a hornear en skin/PSD/ML) y **coste de plano** (hero vs. multitud). Patrón dominante: **riggear una base determinista, generar sim como REFERENCIA y luego "fijarla" en el rig** (correctivos, blend por regiones, o entrenando un deformador). Regla de oro: la sim manda en secundario y contacto; el rig manda en silueta, timing y dirección de arte; la capa de mezcla (máscaras, inputMeshAttract, blendshape por región) es donde se negocia el reparto.

### Base skin/wrap + capa de simulación viva (sim guiada por el skin)
- **Qué es.** Prenda skinneada/wrappeada como base determinista; encima una sim atraída hacia esa base que **solo añade el secundario**.
- **Cómo funciona.** Malla de sim desde la prenda skinneada; el skin como Input Mesh/goal: en **nCloth vía `inputMeshAttract`** (pintado por vértice). *(Corrección de herramientas: **Vellum es exclusivo de Houdini** —no existe en Maya—; **`nConstraint` pertenece a nCloth/Nucleus, no a Bifrost**; Bifrost es un sistema aparte (MPM) con su propio cloth. En un método Maya-only, el goal/attract se hace con nCloth `inputMeshAttract` o el cloth de Bifrost.)* Atractor alto = pegado (cinturilla/hombros); bajo = libre (bajos). El skin es la red de seguridad; la sim aporta arrugas y choque reales.
- **Precisión.** Alta. Secundario: simulado.
- **Límites.** Caché por plano; tuning de solver; no determinista si cambia el timing; pintado de inputMeshAttract artesanal.
- **Cuándo usarlo.** Precisión de arrugas/contacto sin renunciar a control de silueta; **reemplazo del push por distancia** en faldas offline.
- **Encaje.** Prenda skinneada + nucleus como capa; la máscara de atracción como control de rig.

### Sim de referencia → correctivos PSD/RBF disparados por el rig
- **Qué es.** Simular como referencia, capturar poses clave y convertirlas en correctivos que el rig dispara por ángulo/vector, sin sim en runtime.
- **Cómo funciona.** Snapshots de la sim → delta puro sobre el skin con **cvShapeInverter/SHAPES** → targets gobernados por PSD (1-2 joints) o RBF (multi-eje). En play, el rig reproduce el descuelgue de forma determinista, ligera y art-directable. Vía canónica para **fijar la sim en un rig entregable**.
- **Precisión.** Media. Secundario: aproximado.
- **Límites.** Solo lo dependiente de pose (no inercia/timing); explosión combinatoria; disciplina en poses y dobles transformaciones.
- **Cuándo usarlo.** Prendas ajustadas/descuelgue predecible; juego o coste bajo; rig sin sim viva.
- **Encaje.** Los drivers salen de tus joints; convierte tu push por distancia en algo determinista y reutilizable en personajes de misma topología.

### Cachear la sim y mezclarla por regiones (blend por máscara)
- **Qué es.** Cachear una sim completa y mezclarla con el skin por **máscaras de región**: cada zona toma sim o rig según convenga.
- **Cómo funciona.** Sim (Alembic) y skin como entradas a un blendShape; máscaras pintadas por región (bajos 100% sim, cinturilla 100% rig, transiciones suaves). Si una zona flamea, bajas su peso de sim sin re-simular.
- **Precisión.** Alta. Secundario: simulado.
- **Límites.** Offline (depende del caché); transiciones mal graduadas cosen mal (popping); no arregla un choque imposible, solo lo enmascara.
- **Cuándo usarlo.** Shot-cleanup de CFX en planos hero de vestidos largos.
- **Encaje.** Cacheas nCloth o importas Vellum como Alembic y montas el blend; las máscaras viven en el rig para tech-anim.

### Pase de tech-anim / CFX por plano sobre la anim cacheada
- **Qué es.** Tras aprobar la anim, un pase dedicado toma la caché como collider, simula la tela por plano, la limpia y la entrega. Es una capa de **proceso**, no una técnica de rig; el marco donde encajan los demás métodos.
- **Cómo funciona.** Anim aprobada como caché → cuerpo passive collider → sim (nCloth/Vellum) por plano (proxy, constraints, substeps/thickness) → tech-anim itera plano a plano.
- **Precisión.** Alta. Secundario: simulado.
- **Límites.** Caro, no reutilizable entre planos; no tiempo real; roles dedicados; sensible a cambios tardíos de anim.
- **Cuándo usarlo.** Cine/offline, planos hero, vestidos largos donde el contacto/descuelgue es no negociable.
- **Encaje.** Exprime tu doble stack Maya+Houdini: la anim sale del rig, se cachea, el garment se finaliza fuera del rig. **Aquí es donde tu colisión por distancia se jubila** a favor de colisión real por plano.

### Proxy de simulación de baja + wrap a la hero (capas por resolución)
- **Qué es.** Simular una proxy low-res estable y conducir la hero por wrap/proximity.
- **Cómo funciona.** Nucleus/Vellum sobre proxy ligera/limpia; hero atada por wrap (`proximityWrap` en Maya; **Point Deform** en Houdini) conservando UV/grosor/microdetalle. Física de la baja, detalle visual de la alta. Combina con inputMeshAttract y blend por regiones.
- **Precisión.** Alta. Secundario: simulado.
- **Límites.** El wrap pierde pliegues que no existan en la proxy; coste de correspondencia; sliding si la proxy es basta.
- **Cuándo usarlo.** Malla de render pesada/inestable; iterar dinámica en low-res. Base técnica recomendada para vestidos densos.
- **Encaje.** Modelas/decimas proxy, simulas, wrappeas la hero; reduce el coste de sim y estabiliza el solver.

### Biblioteca de poses/clips de sim mezclada por RBF (sim-in-a-can)
- **Qué es.** Pre-simular poses/ciclos, guardarlos como ejemplos y mezclarlos en runtime por RBF/nearest-pose, sin física viva.
- **Cómo funciona.** Diccionario de mallas simuladas por muestra; la pose del rig se proyecta contra el espacio de muestras y el RBF combina los ejemplos cercanos. A diferencia del PSD por delta, el target es la **malla simulada completa** (mejor descuelgue no local). Puede hornearse a VAT.
- **Precisión.** Media. Secundario: aproximado.
- **Límites.** No reacciona a colisiones/fuerzas fuera del set; coste de precómputo/memoria; poco art-directable; artefactos fuera del espacio muestreado.
- **Cuándo usarlo.** Tiempo real/juegos/multitudes con movimiento dependiente de pose/ciclo.
- **Encaje.** Entrenas la biblioteca con tu sim y la reproduces con un nodo RBF o exportas a motor. *(Base académica: **Near-exhaustive Precomputation of Secondary Cloth Effects**, Kim/Koh/Narain, SIGGRAPH 2013 — no confundir con "Example-Based Elastic Materials", que es otro paper, de Martin et al. 2011.)*

### Handoff Houdini Vellum → Maya con mezcla por regiones (cross-DCC)
- **Qué es.** Anim del rig de Maya → tela en Vellum → vuelta a Maya como caché, mezclada por regiones con el skin.
- **Cómo funciona.** Anim a Houdini (Alembic); cuerpo como collider; Vellum resuelve (control/estabilidad/self-collision); caché vuelve (packed → unpack/convert) y se conecta a un blendShape/mezcla por región. Un wrangle/blendshape arranca la sim desde reposo hacia la anim en los primeros frames.
- **Precisión.** Alta. Secundario: simulado.
- **Límites.** Complejidad de pipeline (versionado, correspondencia de topología, roundtrip lento); offline; disciplina de nomenclatura y puntos constantes.
- **Cuándo usarlo.** Solver de referencia Vellum + entregable/rig en Maya; planos hero con colisión/self-collision alta.
- **Encaje.** **Es tu pipeline real**: solo formaliza el ida y vuelta (cache sets, Alembic, blend por región). Vellum da mejor colisión/estabilidad que nCloth en vestidos largos.

### Capa de relajado/tensión (deltaMush o tension) + delta de sim
- **Qué es.** Sobre el skin base, un deltaMush que absorbe artefactos + un delta fino de la sim mapeado; deformación limpia con detalle de tela sin física viva.
- **Cómo funciona.** deltaMush relaja el skin hacia un rest suavizado (elimina colapsos en codos/rodillas/cadera) *(matiz: relaja, no es "preservación de volumen estricta")*. Encima, delta skin↔sim en poses clave como blendshape, o desplazamiento por mapa de tensión (compresión→arrugas). *(Corrección: Maya **no** trae un "tension deformer/tensionMap" de stock para esto; el mapa de tensión se monta a mano —colorSet del ratio de longitud de arista/área— o con plugins.)*
- **Precisión.** Media. Secundario: aproximado.
- **Límites.** No genera secundario real; deltaMush quita detalle si el radio es alto; el delta de tensión aproxima.
- **Cuándo usarlo.** **Mejora de línea base sobre el copy skin** en cualquier prenda; primer paso barato para tu queja de "poco preciso".
- **Encaje.** deltaMush nativo + máscara de tensión + ngSkin para el skin base; sirve offline y para juego.

### Estrategia multi-capa con colisión jerárquica
- **Qué es.** Con varias prendas superpuestas (enagua+falda+capa), decidir capa a capa qué se skinnea y qué se simula, y ordenar la prioridad de colisión.
- **Cómo funciona.** Interiores/ajustadas skinneadas o como colliders baratos; exteriores/sueltas simuladas usando como collider **la capa interior ya resuelta**; grosores escalonados; resolución en cascada (interior → exterior sobre su caché).
- **Precisión.** Alta. Secundario: simulado.
- **Límites.** El más caro de orquestar; dependencias de caché entre capas; errores de prioridad = crossovers difíciles; cambios en una interior obligan a re-resolver las exteriores.
- **Cuándo usarlo.** Vestuario de época/varias capas; planos hero de cine.
- **Encaje.** Enagua skinneada como collider, falda/capa en Vellum sobre ella; tu autorig da la base, el CFX resuelve la cascada.

### Deformador por ML entrenado con la sim (tech-anim aprendido)
- **Qué es.** Red entrenada con pares (pose → prenda simulada) que predice la deformación en runtime.
- **Correcciones de encaje.** El **ML Deformer nativo de Maya se introdujo en 2025.2** (no "Maya 2024") y **corre dentro de Maya para acelerar el playback**; Autodesk lo posiciona para casos "donde la precisión no es crítica" (fondo/crowds) y **no se exporta a Unreal/Unity**. Para ML de tela en runtime de motor se usa el ML Deformer de UE o custom; **Ziva RT está descontinuado (abril 2024, IP a DNEG)** y no es una opción viable hoy.
- **Precisión.** Media (dentro del dominio entrenado). Secundario: aproximado/ninguno según inputs.
- **Límites.** Fuera de distribución falla; no captura inercia/colisiones nuevas; dataset/entrenamiento caros; poco art-directable.
- **Cuándo usarlo.** Playback acelerado en Maya (nativo) o alta fidelidad en UE (framework de UE).
- **Encaje.** Generas el dataset con tu Vellum/AdonisFX y tu autorig; complementa con bone-chain para la parte inercial.

### Métodos que faltaban en esta familia
- **Sim horneada a una cadena de joints skinneada (sim-to-bone / bone-based cloth).** Capturar el movimiento simulado en un chain de huesos que luego se skinnea, para reproducir la tela en motor. **Distinto de VAT y del ML**: no interpola ejemplos ni infiere con red, **transfiere el sim a huesos**. Es el flujo estándar de faldas/capas en juegos y el que ya insinúa tu pipeline. Herramientas: SideFX Labs, bake de dynamic joints en Maya, SSDR.
- **Dinámica secundaria viva en el propio rig.** Cadenas dinámicas por nHair/nDynamics o solvers spring/aim (overlap/jiggle interactivos) que dan inercia y descuelgue **en tiempo de animación**, sin pase de CFX ni caché aparte. Cubre el hueco entre el PSD (sin inercia) y la sim offline: secundario real e interactivo dentro del rig entregable.

---

## Recomendación transversal para tu pipeline

El mayor salto de precisión sobre el copy skin viene de tres movimientos **combinables**, no de un solo método:

1. **Sube el escalón del binding y del refinado, ya.** Pasa de `closestPoint` a **geodesic voxel** (o `-uvSpace` + `-influenceAssociation label` en tu transferencia), organiza el afinado con **ngSkinTools**, añade **Delta Mush** como capa de acabado y decide DQ/weight-blended por zona. Es barato, en tiempo real, y elimina el cruce de influencias que hoy te molesta. Sobre esto, **correctivos PSD/RBF por ángulo de pierna** (con `combinationShape` para combos) meten el pliegue por compresión que la sim ganaba.
2. **Sustituye/complementa tu colisión por distancia con colisión real, al menos como referencia.** En **Vellum**, ajustar substeps y collision thickness sobre el collider Alembic del skin es exactamente el control que hoy te falta; **guía la sim** con el skin/ribbons como goal e `inputMeshAttract` para mezclar seguimiento (cintura) y vuelo libre (bajo). Para prendas holgadas, ese es el techo de realismo.
3. **Fija la precisión en un asset controlable según el medio.** Para cine: **blend por regiones** y **pase de tech-anim** con caché. Para juego/coste bajo: **sim → correctivos PSD/RBF**, **sim-to-bone (SSDR)**, **VAT** o **spring bones** (Kawaii Physics), reutilizando un único skeleton limpio de falda para cine y juego.

Mantén el **ancla de raíz por `proximityPin`/`uvPin`** (deslizamiento real de la piel en el arranque de la cadena) y reserva **Ziva/AdonisFX** para la piel/fascia, no para la tela suelta.

---

## Recursos

> **Antes de pasar un enlace al usuario, verifícalo** con `web_search`/`web_fetch`.
> Las URLs de abajo son de referencia; algunas están marcadas como *"buscar por título"*
> o *"verificar"* porque no había enlace fiable. No des por buena una URL sin comprobarla.

**Transferencia de pesos y skinning**
- Maya Help — `copySkinWeights` (flags `-surfaceAssociation`, `-uvSpace`, `-influenceAssociation`): buscar en help.autodesk.com por versión.
- ngSkinTools — User Guide: https://www.ngskintools.com/documentation/userguide/ · API: https://www.ngskintools.com/documentation/api/
- ngSkinTools Skinning Tips (Rigmarole Studio): https://rigmarolestudio.com/ngskintools-skinning-tips/
- Baran & Popović, *Automatic Rigging and Animation of 3D Characters* (SIGGRAPH 2007) — heat-diffusion binding: buscar por título.
- Dionne & de Lasa, *Geodesic Voxel Binding for Production Character Meshes* (SCA 2013): https://dl.acm.org/doi/10.1145/2485895.2485919 · Maya Help geodesic voxel: https://help.autodesk.com/cloudhelp/2018/ENU/Maya-CharacterAnimation/files/GUID-5EFDB81B-E332-4D6C-B1BB-0B989AD2F2C7.htm · Chris Evans: http://www.chrisevans3d.com/pub_blog/geodesic-voxel-binding-maya-2015/
- Jacobson, Baran, Popović, Sorkine, *Bounded Biharmonic Weights* (SIGGRAPH 2011) — buscar por título; implementación en **libigl**: https://github.com/libigl/libigl
- Mancewicz et al., *Delta Mush* (DigiPro 2014): https://www.researchgate.net/publication/266659626 · Maya Help deltaMush: https://help.autodesk.com/view/MAYAUL/2026/ENU/?guid=GUID-139B703C-28E7-4787-8FD4-C2991BD6C990
- Le & Lewis, *Direct Delta Mush* (SIGGRAPH 2019): https://dl.acm.org/doi/10.1145/3306346.3322982 · *Enhanced DDM* (arXiv 2101.02798): https://arxiv.org/abs/2101.02798 · plugin: https://github.com/2TallTim/direct-delta-mush · EA SEED: https://www.ea.com/seed/news/siggraph2019-direct-delta-mush
- Le & Deng, *Smooth Skinning Decomposition with Rigid Bones* (**SIGGRAPH Asia 2012**) — SSDR: buscar por título (UC Berkeley / autores).
- Chad Vernon — Maya API / skinCluster: https://www.chadvernon.com/ · Maya Help `bakeDeformer` y `tension`: buscar por nombre.

**Deformadores de envoltura (wrap)**
- Proximity Wrap — Maya Help: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-0D7E6B72-6021-4C66-9262-089D10246C3F · creación: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-83C9793D-54AB-4BA3-812B-005D8153A79C · Will Telford: https://www.youtube.com/watch?v=YE3KfGeSDxk
- Wrap highres sobre lowres (Maya Advanced Techniques): https://download.autodesk.com/us/maya/maya_2013_advanced_techniques/files/GUID-EFE22F39-CDF9-4CAD-BF42-10D3A8181EE0.htm *(verificar el enlace exacto antes de usar)*
- shrinkWrap — Maya Help: https://help.autodesk.com/view/MAYAUL/2022/ENU/?guid=GUID-2B3558DD-2EB2-4525-B716-885E859E27B8 *(la referencia de nodo real está bajo Maya-Tech-Docs/Nodes/shrinkWrap.html de la versión concreta)*
- cvWrap (Chad Vernon): https://github.com/chadmv/cvwrap · README: https://github.com/chadmv/cvwrap/blob/master/README.md
- Houdini **Point Deform SOP** y **Ray SOP** — SideFX Docs: buscar por nombre en https://www.sidefx.com/docs/houdini/
- Proximity Pin / UV Pin — Maya Help: buscar "Proximity Pin" / "UV Pin".
- cvShapeInverter (Chad Vernon): https://github.com/chadmv/cvShapeInverter
- Lewis, Cordner, Fong, *Pose Space Deformation* (SIGGRAPH 2000) — base del PSD/pose reader: buscar el PDF en scribblethink.org.

**Rigs por joints / mecánico**
- Maya Rigging Wiki — Clothing: https://sites.google.com/site/mayariggingwiki/rigging-notes/specialized/clothing · Ribbon: https://sites.google.com/site/mayariggingwiki/rigging-notes/rig-fundamentals/ribbon
- Ribbons in Maya (James Dunlop, incluye uvPin/matrix): https://jamesbdunlop.github.io/generalmaya/2021/06/27/ribbon.html
- mGear: https://github.com/mgear-dev/mgear4 · Ribbonizer (Gumroad): https://orkhan.gumroad.com/l/ribbonizer · mayaFollicleJoints: https://github.com/chisn8tech/mayaFollicleJoints
- Dynamic joint chains (nHair): https://lesterbanks.com/2014/02/building-dynamic-joint-chains-maya-hair/ · demo: https://www.youtube.com/watch?v=LElbJ_CqueU
- Kiel Figgins — nCloth/nDynamics for Animators: https://www.3dfiggins.com/writeups/ncloth/
- Automatic overlap chain (Barak Moshe): http://barakmoshe.blogspot.com/2013/09/tutorial-how-to-set-up-automatic.html · secondary-motion add-on (CG Channel 2025): https://www.cgchannel.com/2025/07/this-free-maya-add-on-adds-secondary-motion-to-3d-characters/ *(herramientas de overlap reconocidas: Overlappy de aTools/animBot)*
- Skirt rig con auto collision (Li Ling Liu): https://www.lilingliu.com/post/skirt-rig-with-auto-collision · Lesterbanks: https://lesterbanks.com/2020/05/how-to-create-a-joint-based-skirt-rig-with-auto-collisions-in-maya/ · Maya Help `keepout`: buscar "keepout".
- KawaiiPhysics: https://github.com/pafuhana1213/KawaiiPhysics · README: https://github.com/pafuhana1213/KawaiiPhysics/blob/master/README_en.md · UE AnimDynamics: buscar "AnimDynamics" en dev.epicgames.com.

**Correctivo y pose-space**
- Maya Help — Pose Space Deformations (overview): https://help.autodesk.com/view/MAYAUL/2022/ENU/?guid=GUID-45D389D6-B8E4-4225-B27B-9927BB61C28D · *Create pose space deformations*: https://knowledge.autodesk.com/support/maya/learn-explore/caas/CloudHelp/cloudhelp/2022/ENU/Maya-CharacterAnimation/files/GUID-00699C13-8CA1-450C-937D-57C7B3DFD8C6-htm.html
- SHAPES (brave rabbit): https://www.braverabbit.com/shapes/ · weightDriver (Gumroad): https://braverabbit.gumroad.com/l/weightDriverMaya · Wiki: https://github.com/IngoClemens/weightDriver/wiki · pose interpolation (Vimeo): https://vimeo.com/204003724
- mGear Rigbits RBF Manager: https://mgear4.readthedocs.io/en/latest/rigbitsUserDocumentation.html · `rbf_manager_ui.py`: https://github.com/mgear-dev/rigbits/blob/master/scripts/mgear/rigbits/rbf_manager_ui.py · mGear 5.1 RBF Manager 2.0: https://digitalproduction.com/2025/09/09/mgear-5-1-sharpens-rbf-manager-and-patches-shifter/
- Authoring RBF in Maya — MetaHuman (Epic): https://dev.epicgames.com/documentation/en-us/metahuman/authoring-rbf-in-maya *(el RBF de MetaHuman conduce joints, no morph targets)*
- Driving deformations by joint angle (Sol Brennan): https://sol-g-brennan.medium.com/rigging-tip-driving-your-deformations-primarily-for-games-9265a38492b5
- Mesh-Tension Driven Wrinkles (arXiv 2210.03529): https://arxiv.org/pdf/2210.03529 · tension/stress map en Maya (Autodesk Community): https://forums.autodesk.com/t5/maya-shading-lighting-and/how-to-create-tension-map-stress-map-in-maya/td-p/9954696 · wrinkle/tension maps (Polycount): https://polycount.com/discussion/108668/wrinkle-tension-maps-inside-maya
- WrinkleMatic (Gumroad): https://tikworks.gumroad.com/l/wrinklematic · Maya wrinkle deformer nativo: https://help.autodesk.com/view/MAYAUL/2026/ENU/?guid=GUID-69458E85-3291-428F-9732-55AB01E52AEE
- RBF math (Tech-Artists.Org): https://www.tech-artists.org/t/rbf-pose-interpolator-math-help/10490 · Chad Vernon deformers: https://www.chadvernon.com/tags/maya/

**Simulación física (offline)**
- Vellum — SideFX Docs: https://www.sidefx.com/docs/houdini/vellum/index.html · Advanced Vellum Workflows: https://tutorials.cgrecord.net/2019/06/advanced-houdini-vellum-workflows.html · Dynamic Cloth for Production (Gnomon/CG Channel): https://www.cgchannel.com/2025/03/tutorial-dynamic-cloth-simulation-for-production/
- nCloth — Kiel Figgins: https://www.3dfiggins.com/writeups/ncloth/ · Maya nCloth/Nucleus Help: buscar por versión.
- Qualoth (FXGear): https://qualoth.com/ · 80.lv: https://80.lv/articles/qualoth-tools-for-realistic-cloth-creation · Puppeteer Lounge: https://puppeteerlounge.com/2016/10/qualoth-for-maya-tutorial.html
- Syflex — solver clásico de tela (largometrajes): sitio del producto (buscar "Syflex cloth").
- Marvelous Designer: https://www.marvelousdesigner.com/
- Ziva VFX (legacy, línea discontinuada; IP en DNEG): docs históricos https://docs.zivadynamics.com/vfx/tutorial.html · contexto de sim de piel: https://www.williamgabriele.com/single-post/creatures-in-vfx-skin-binding-and-skin-simulation
- Houdini→Maya Alembic (Chaos/V-Ray): https://docs.chaos.com/display/VMAYA/Houdini+to+Maya+Alembic+Workflow · ROP Alembic: https://www.sidefx.com/docs/houdini/
- Sim Rig Build (Samuel Walsh): https://www.samuelwalsh.co.uk/tutorials/clothworkflow/simrigbuild · nCloth→FBX blendshapes: https://medium.com/fink-it/exporting-ncloth-animation-to-fbx-using-blend-shapes-in-maya3d-2f0dcf68e6bb · Houdini Cloth Capture (Artivoxa): https://www.artivoxa.com/houdini-cloth-capture-attaching-fabric-to-animated-characters/
- SideFX CFX Learning Path — Cloth: https://www.sidefx.com/learn/learning-paths/cfx/cloth/

**Tiempo real y juegos**
- ChaosCloth — UE Docs: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/ChaosCloth · Panel Cloth Editor: https://docs.unrealengine.com/5.3/en-US/panel-cloth-editor-overview/ · Chaos Cloth Demystified: https://dev.epicgames.com/community/learning/tutorials/MZeq/... · *The Gritty Reality of Real-Time Cloth* (Unreal Fest 2022): https://www.youtube.com/watch?v=4NkNBImONJU
- NvCloth (GameWorks): https://github.com/NVIDIAGameWorks/NvCloth · Havok Cloth: https://www.havok.com/havok-cloth/ · Cloth in Alan Wake: https://www.gamedeveloper.com/programming/the-secrets-of-cloth-simulation-in-i-alan-wake-i-
- Unity Manual — Cloth: https://docs.unity3d.com/6000.4/Documentation/Manual/class-Cloth.html · Skinned Mesh Renderer: https://docs.unity3d.com/6000.4/Documentation/Manual/class-SkinnedMeshRenderer.html · Maya→Unity cloth: https://medium.com/another-angle/unity-and-maya-character-cloth-workflows-e480e1f7afd
- SideFX Labs (VAT, export): https://github.com/sideeffects/SideFXLabs · VAT tutoriales: https://www.sidefx.com/tutorials/
- *Real-Time Transformations in The Order: 1886* (SIGGRAPH 2015): https://history.siggraph.org/learning/real-time-transformations-in-the-order-1886/ · PDF ACM: https://dl.acm.org/doi/pdf/10.1145/2775280.2793101 *(caso AAA de morph rig; NO es la fuente del tension/wrinkle blending)*
- UE5 Deformer Graph (Optimus): buscar "Deformer Graph" / "Optimus" en dev.epicgames.com.
- UE RBF Solver / Pose Driver en AnimGraph: buscar "RBF" / "Pose Driver" en dev.epicgames.com.

**Machine Learning / data-driven**
- ML Deformer — Maya Help (2025.2, backend PyTorch): https://help.autodesk.com/view/MAYAUL/2026/ENU/?guid=GUID-F386DC20-6C66-40D7-AD40-2C1B66937A71 · CG Channel: https://www.cgchannel.com/2024/07/maya-2025-2-adds-a-new-ml-deformer/ · Autodesk University: https://www.autodesk.com/autodesk-university/class/Rigging-Fast-Deformation-Estimation-with-Neural-Computation-in-Maya-2024
- ML Deformer Framework (UE): https://dev.epicgames.com/documentation/unreal-engine/ml-deformer-framework-in-unreal-engine · ML Cloth overview: https://dev.epicgames.com/documentation/unreal-engine/machine-learning-cloth-simulation-overview · tutorial: https://dev.epicgames.com/community/learning/tutorials/PdRX/... · sample (Fab): https://www.fab.com/listings/4c1f2eee-3004-4466-8c86-796e2e94d562
- ZivaRT — **descontinuado (Unity, abril 2024; IP a DNEG)**: contexto https://www.cgchannel.com/2023/07/unity-releases-ziva-real-time-2-0/ y "An update about Ziva" (Unity Blog).
- Bailey, Otte, DiLorenzo, O'Brien, *Fast and Deep Deformation Approximations* (SIGGRAPH 2018) — paper fundacional del ML deformer: UC Berkeley Graphics.
- Zhang et al., *A Deep Emulator for Secondary Motion of 3D Characters* (CVPR 2021).
- ML-Corrective-Deformer-Maya-Public: https://github.com/mayjackass/ML-Corrective-Deformer-Maya-Public · *Implementing an ML Deformer for CG Crowds* (arXiv 2406.09783): https://arxiv.org/pdf/2406.09783
- Holden et al., *Subspace Neural Physics* (SCA 2019, red feed-forward autoregresiva): https://daniel-holden.com/page/subspace-neural-physics-fast-data-driven-interactive-simulation · PDF Ubisoft: https://staticctf.ubisoft.com/.../DeepClothSCA.pdf
- DeepWrinkles (ECCV 2018): https://openaccess.thecvf.com/content_ECCV_2018/html/Zorah_Laehner_DeepWrinkles_Accurate_and_ECCV_2018_paper.html · arXiv 1808.03417
- TailorNet (CVPR 2020): https://virtualhumans.mpi-inf.mpg.de/tailornet/
- SNUG (CVPR 2022): https://mslab.es/projects/SNUG/ · CVF: https://openaccess.thecvf.com/content/CVPR2022/html/Santesteban_SNUG_... · PBNS (arXiv 2012.11310): https://arxiv.org/abs/2012.11310
- HOOD (CVPR 2023): https://dolorousrtur.github.io/hood/ · arXiv 2212.07242 · MeshGraphNets (arXiv 2010.03409): https://arxiv.org/abs/2010.03409
- Deep Detail Enhancement (CGF 2021): https://geometry.cs.ucl.ac.uk/projects/2021/DeepDetailEnhance/ · arXiv 2008.04367 · Neural Garment Dynamic Super-Resolution (SIGGRAPH Asia 2024): https://dl.acm.org/doi/10.1145/3680528.3687610

**Híbridos y estrategia de capas**
- Maya nCloth Advanced Techniques (PDF Autodesk): buscar en images.autodesk.com / download.autodesk.com (`nclothadvancedtechniques.pdf`) *(el enlace concreto varía; verificar)* · nCloth reference (mottosso): https://mottosso.com/ncloth-reference/
- Kim, Koh, Narain, *Near-exhaustive Precomputation of Secondary Cloth Effects* (SIGGRAPH 2013) — base de la biblioteca de sim por pose *(no confundir con "Example-Based Elastic Materials", Martin et al. 2011)*.
- Houdini import/cloth capture (Samuel Walsh): https://www.samuelwalsh.co.uk/tutorials/albertandvellum/houdiniimportandsetup · Vellum vs nCloth (SideFX Forum): https://www.sidefx.com/forum/topic/62242/ · HoudiniVellum (cgwiki): https://tokeru.com/cgwiki/HoudiniVellum.html
- SideFX CFX — layered garments/collision: https://www.sidefx.com/learn/learning-paths/cfx/cloth/ · Houdini cloth/muscle tips: https://yelzkizi.org/7-powerful-houdini-cloth-muscle-simulation-tips/ · Old nCloth notes: https://create3dcharacters.com/old-ncloth-notes/