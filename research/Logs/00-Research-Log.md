# 00 - Research Log

### 2026-10-12 — Weekly Research Run
- Math/Advanced: 2 archivos
- Performance: 2 archivos
- Tools/Rigs: 1 archivo
- Total: 5 archivos
- Destacado matemático: **Exponential Maps / Grassia 1998** — La representación correcta de rotaciones para RBF e IK: `v = θ·n̂ ∈ ℝ³` mapea eje-ángulo a un vector 3D sin singularidades excepto en θ=±π, corregible con reparameterización dinámica. La distancia geodésica en SO(3) como kernel RBF (vs. Euclidiana en Euler, con error O(θ²) hasta 5-10° en hombros a 90°+). Complementado con PSD math completo (Lewis 2000): RBF correctives como interpolación multidimensional en pose space, con combination shapes via producto de pesos.
- Destacado performance: **Deformer Stack Ordering & GPU Break Rules** — Reglas concretas que determinan si el stack corre en GPU o cae a CPU: (1) live animated mesh target en blendShape rompe GPU upstream; (2) outMesh→inMesh entre meshes fuerza CPU en toda la cadena; (3) deltaMush soporta GPU desde Maya 2024. `audit_deformer_stack_gpu(mesh)` lista todos los problemas. Complementado con workflow completo de benchmarking: `full_rig_benchmark()` + `rig_cache_health_report()` listos para integrar como post-build validator.
- Aplicable inmediatamente: **`audit_deformer_stack_gpu()` + `full_rig_benchmark()`** en `autorig_tools/utils/performance.py` (1-2h). **MayaBridge** (Asukacodes) — bridge TCP para controlar Maya desde Claude Code directamente, setup en 30-60 min para debugging interactivo de builds. **Exponential map distance** como kernel en el sistema RBF de correctives para hombros/caderas con rango > 60°.

---

### 2026-09-14 — Weekly Research Run
- Math/Advanced: 2 archivos
- Performance: 1 archivo
- Tools/Rigs: 2 archivos
- Total: 5 archivos
- Destacado matemático: **Geodesic Cut-Cell Prior** (arXiv:2608.11272, Aug 2026) — Prior geométrico que aproxima distancias geodésicas volumétricas via grafo cut-cell (Dijkstra O(V log V)) para regularizar métodos neuronales de cálculo de pesos de skinning. Órdenes de magnitud más rápido que BBW O(V³), robusto a artefactos topológicos. Se integra como término de loss en cualquier pipeline neural: L_total = L_data + α·||W_pred - W_cutcell||_F². Potencial para implementar `build_geodesic_weights()` en autorig_tools con scipy.sparse (~200-300 líneas).
- Destacado performance: **mGear 5.3 Evaluation Partition + Wire to Skinning** — Divide meshes en N grupos de polígonos independientes que se evalúan en N threads en paralelo. T_parallel ≈ T_seq/N + T_merge. Para mesh de 12ms con N=4: ~4.2ms (2.86×). Wire to Skinning convierte wireDeformers (kGloballySerialize) a skinClusters (kParallel), eliminando bloqueadores de GPU Override. .evp config exportable para reutilización cross-rig.
- Aplicable inmediatamente: **Wire to Skinning audit** — ejecutar `mc.ls(type='wireDeformer')` en rigs de autorig_tools; si hay wire deformers, convertirlos con mGear 5.3 elimina globally_serialize blockers del EG. 30-60 min, ROI alto. También: **mGear SDK Creator** — el patrón de "leer timeline → generar SDKs" es directamente extractable como `build_sdk_from_pose()` para autorig_tools (3-4h). **Ji Hun Park toolkit** (elom1213/Maya_Python, actualizado 2026-09-08): Constraint→Matrix converter elimina kLocallySerialize del EG; geodesic binder (cotangent Laplacian + heat method) es la base para `build_geodesic_weights()`; RBF solver con JSON persistence ~150 líneas portables a autorig_tools.

---

### 2026-09-07 — Weekly Research Run
- Math/Advanced: 2 archivos
- Performance: 2 archivos
- Tools/Rigs: 1 archivo
- Total: 5 archivos
- Destacado matemático: **OmniFaceRig** (arXiv:2606.08043, Jun 2026) — Pipeline end-to-end que convierte una malla 3D de superficie pura en un rig facial FACS completo con 155 blendshapes + inner mouth procedural en 20-30s/asset. 5 etapas: VLM riggability check → segmentation ensemble → TPS registration (φ(r)=r²log(r), mínima energía de doblado) → L-BFGS collision-aware inner mouth fitting (E=Σmax(0,−sdf(v))² + λ||pos−nominal||²) → blendshape transfer (Δ_input = R_local · Δ_template). Dataset Omni-Bench: 1,000 personajes con GT FACS. Potencial para reducir el trabajo de sculpting facial de 40-80h a 1-2h de review. SQUAD (Shoemake 1987) también archivado: interpolación C¹ cúbica en S³ vía SLERP anidados — sᵢ = qᵢ·exp(−(log(qᵢ⁻¹·qᵢ₋₁)+log(qᵢ⁻¹·qᵢ₊₁))/4), coste 3 SLERP, sin popeo de velocidad angular.
- Destacado performance: **Scheduling Mode / Invisibility Evaluator** (Maya 2023+/2026) — Pre-pasada O(|EG|) por frame que marca nodos INVISIBLE_SUSPENDED para objetos ocultos/fuera de cámara sin reconstruir el Evaluation Graph. Reducción de 15-40% del tiempo de evaluación en escenas multi-personaje. Blockers principales: expression-driven .visibility, animated .visibility (keyed), nodos globally_serialized. audit_scheduling_mode_blockers(rig_root) identifica los blockers. **aimMatrix node** también archivado: DG puro paralelo, ~0.02ms vs ~0.05-0.15ms de aimConstraint, conecta a offsetParentMatrix. 20 nodos de aim en un biped = ~1.6ms/frame recuperados.
- Aplicable inmediatamente: **aimMatrix node** — audit_aim_constraints_in_rig(rig_root) sobre biped de autorig_tools; reemplazar pole vector aims (brazo/pierna), eye aims (facial), ribbon frame aims. Workaround worldUpType=objectRotationUp via pickMatrix+pointMatrixMult documentado en el archivo. 2-4h. **Hyperdrive** (timlehr): pose-based caching para crowd/ciclos — compute_pose_id() hash MD5 de joint worldMatrices + PoseCacheLRU — ortogonal al Cached Playback de Maya, excelente para NPCs con ciclos repetidos (hit rate >70%).

---

### 2026-08-31 — Weekly Research Run
- Math/Advanced: 2 archivos
- Performance: 2 archivos
- Tools/Rigs: 1 archivo
- Total: 5 archivos
- Destacado matemático: **POE Splines on Lie Groups — SO(3) y SE(3)** (Müller, arXiv:2508.10513, Aug 2026). Splines de orden k en grupos de Lie como producto de exponenciales: γ(t) = g₀·exp(a₁(t)·X₁)·exp(a₂(t)·X₂)·...·exp(aₖ(t)·Xₖ). Elimina la limitación fundamental de De Casteljau en Lie groups (los segmentos locales estaban forzados a arrancar en la identidad del grupo). Para el ribbon spine de autorig_tools: interpolación en SE(3) = posición + frame del joint simultáneamente, con twist geométricamente consistente incluso bajo curvas extremas en S. El algoritmo de orden 3 resuelve coeficientes Hermite cúbicos en el álgebra de Lie y sube al grupo via exp map — aplicable offline en Python/numpy al build-time del ribbon.
- Destacado performance: **Framestore Toothless — GPU OpenCL MPxDeformer** (SIGGRAPH 2025, Framestore, How to Train Your Dragon). Patrón producción: MPxDeformerNode CPU (referencia exacta) + mirror MPxGPUDeformer OpenCL (mismo algoritmo, kernel GPU). BVH de colisión portado a GPU vía radix sort + prefix scan paralelo. Resultado: 13 FPS → 19 FPS en rig de 200K vértices — cerca del máximo teórico (passthrough FPS). Testing automatizado: modo test crea contexto OpenCL desde CPU, ejecuta el mismo kernel, compara resultados (tolerancia 1e-4) — integrable en CI sin GUI de Maya. Aplicable para portar deformadores custom (bulge, colisión, wrinkle) de autorig_tools a GPU sin perder precisión.
- Aplicable inmediatamente: **`audit_cache_blockers(rig_root)`** — del White Paper de Cached Playback 2025 de Autodesk. Función Python que detecta: (1) expression nodes con conteo de downstream afectados, (2) deformadores sin soporte GPU en la cadena, (3) conexiones outMesh→inMesh que rompen el cluster GPU. Implementable en 30 minutos, ejecutable hoy sobre cualquier rig de producción de autorig_tools para cuantificar el impacto de cada bloqueador de caché. Combinar con `audit_expression_nodes()` (log 2026-07-27) para auditoría completa.

---

### 2026-08-24 — Weekly Research Run
- Math/Advanced: 3 archivos (PhysSkin CVPR 2026, Neural Deformation Gradients CGF 2026, SkinCells Eurographics 2026)
- Performance: 2 archivos (Maya 2026 Serial Evaluation + Dirty Propagation architecture, Maya 2026.3 DGA nodes)
- Tools/Rigs: 2 archivos (MHR Meta parametric human rig, AKEric/skinner Maya tool)
- Total: 7 archivos

- Destacado matemático: **SkinCells — Sparse Skinning using Voronoi Cells (Larionov et al., Eurographics/CGF 2026)** — Método automático de bind con **control directo de sparsity** (max K influences per vertex) sin sacrificar calidad. Idea central: campo implícito de pesos `wⱼ(p) = softmin(dⱼ(p), τ) / Σₖ softmin(dₖ(p), τ)` inspirado en diagramas de Voronoi. Con τ→0, cada vértice cae en una celda hard; con τ finito, transiciones suaves solo en fronteras de Voronoi. Sparsity emerge naturalmente porque `exp(−d/τ)` decae exponencialmente. Distancia = geodesic sobre mesh (heat method) modulada por weight-per-bone (power diagram) optimizado con L-BFGS sobre un banco de poses de test. **Ventaja crítica sobre BBW/heat/geodesic voxel:** partition of unity garantizada a K influences, no requiere prune post-hoc que rompe la garantía. Directamente sustituible por `voxel_skin_init()` en autorig_tools para bind inicial de LODs y mobile assets.

- Destacado performance: **Maya 2026 — Serial Evaluation Mode + EG estática sin dirty propagation** — Cambio arquitectónico fundamental: una vez construido el Evaluation Graph, Maya NO propaga dirty flags en cada frame; los reusa hasta invalidation. Ganancia típica: 4-8ms/frame que antes se comía el dirty propagation. **Serial Evaluation mode** = EG-sin-dirty pero single-thread — el nuevo modo por defecto durante DESARROLLO de rigs, no DG legacy: expone bugs de dependencia undeclared vía `dbtrace(keyword='eval')` que en Parallel serían race conditions intermitentes. Función `audit_eg_health()` detecta 4 blockers (expressions, Python MPxNode, animated visibility, cycles) en una pasada. También destacable: **Maya 2026.3 introduce nodos DGA (Dynamic Geometry Attributes) — dgaTension/dgaDelta/dgaVisualizer/dgaToArray** — computan strain per-vertex nativamente, kParallel, GPU-friendly, reemplazando 20-50 expression nodes de wrinkle systems clásicos. Un solo `dgaTension` puede driver un wrinkle blendShape sin sculpting per-pose.

- Aplicable inmediatamente: **SkinCells como bind inicial + `audit_eg_health()` en post-build** — (1) SkinCells: instalar `libigl` en Python externo (`pip install libigl`), portar el pseudocódigo del archivo `2026-08-24-skincells-voronoi-sparse-skinning-eurographics2026.md` a `autorig_tools/skinning/skincells.py`, aplicar como bind inicial en LODs 1+ (K=4). Estimado 6-10h de integración + 4h de tuning τ sobre 2-3 personajes. Beneficio: reducción ~50% del fix manual en axilas/ingle. (2) `audit_eg_health()` del archivo `2026-08-24-maya-2026-serial-evaluation-dirty-propagation-architecture.md` en el health check de post-build (2h). Añadir modo "diagnostic build" que auto-cambia a Serial + `dbtrace` 30 frames (3h). Detecta expressions residuales + Python MPxNode + animated visibility en una llamada — riesgo que puede costar 10-30ms/frame invisiblemente.

---

### 2026-08-17 — Weekly Research Run
- Math/Advanced: 4 archivos (2 genuinamente nuevos: FABRIK vs CCD; 2 suplementos con nuevo código y tablas sobre temas ya cubiertos: DQS + B-spline)
- Performance: 2 archivos (1 genuinamente nuevo: deformer stack ordering + GPU influence count table; 1 suplemento con audit function sobre MPxNode scheduling ya cubierto en mayo)
- Tools/Rigs: 1 archivo (GT Tools — TrevisanGMW, 174★, Maya 2025/2026/2027)
- Total: 7 archivos

- Destacado matemático: **FABRIK vs CCD — Benchmarks cuantitativos de convergencia** — FABRIK: media de 15.4 iteraciones / 13.2ms para targets alcanzables. CCD: 26 iteraciones / 123ms alcanzable, 400 iteraciones / 4000ms NO alcanzable. Jacobiano pseudoinverso: 28 iteraciones / 13,100ms. FABRIK ~10× menos iteraciones que CCD por su operación O(1) por joint (proyección sobre línea) vs CCD que requiere recomputar la rotación completa para cada joint y propagarla downstream. Implementación Python om2 lista para `autorig_tools/utils/ik_solvers.py`. Variante FABRIK+SQP (2023) para convergencia de alta precisión (ε<10⁻⁶) bajo restricciones angulares estrictas.

- Destacado performance: **Deformer Stack Ordering + GPU influence count table** — El orden relativo de skinCluster / blendShape_correctives / deltaMush determina si hay 1 o 3 clusters GPU. Nuevo dato: la tabla de GPU speedup por influencias muestra que 8 influencias es el sweet spot (GPU advantage 25×) vs 4 influencias (GPU advantage 16×) — más influencias = más ventaja GPU relativa sobre CPU. Pruning agresivo a 4 influencias pierde más speedup GPU del que gana en compute reducido. GPU readback cost: 0.5-4ms por mesh por frame; un stack mal ordenado en un personaje de 4 meshes consume 2-16ms = 25-40% del presupuesto de frame a 25fps.

- Aplicable inmediatamente: **`audit_deformer_stack(mesh)` + FABRIK Python** — (1) La función `audit_deformer_stack()` del archivo de deformer ordering es integrable directamente en el post-build health check de autorig_tools en <1h: detecta GPU cluster breaks, animated weightFunction, y muestra el número de readbacks por mesh. (2) La implementación FABRIK Python completa está lista para `autorig_tools/utils/ik_solvers.py` para tail rigs y spine procedural de >3 joints (2-3h de integración + tests).

---

### 2026-08-10 — Weekly Research Run
- Math/Advanced: 2 archivos
- Performance: 0 archivos
- Tools/Rigs: 3 archivos
- Total: 5 archivos
- Destacado matemático: **6D Continuous Rotation Representations para pipelines diferenciables** — Zhou et al. 2019 demostró que no existe surjección continua ℝⁿ → SO(3) para n < 5, lo que invalida Euler (n=3), axis-angle (n=3) y quaterniones (n=4) como input features para sistemas con gradiente. La representación 6D (dos primeras columnas de la matriz de rotación + Gram-Schmidt) es la mínima continua. Complementa el archivo de Riemannian SO(3) Fréchet del 27/07: aquél cubre la interpolación geodésica correcta entre N rotaciones; éste cubre por qué las representaciones sub-5D no funcionan para backprop. Aplicación: cambiar el input del optimizador de RBF kernel widths de Euler a 6D para correctives en hombros/caderas > 90°.
- Destacado performance: (sin archivo nuevo esta semana — el exhaustivo archivo 2026-08-03 cubre SpecAPC benchmarks y animated blendshape GPU constraint, que es lo más reciente publicado. El whitepaper de Maya 2026 estuvo bloqueado por proxy. Se recomienda intentar acceder en próxima sesión.)
- Aplicable inmediatamente: **wrapper `rotation_to_6d()` (3 líneas)** para el optimizador RBF de correctives de autorig_tools. `col0 = wm[0:3]; col1 = wm[4:7]; features_6d = col0 + col1` (donde wm = getAttr(joint + '.worldMatrix[0]')). Reemplazar los 3 Euler angles actuales como input features del RBF fitter por estos 6 valores elimina las discontinuidades de gradiente en poses extremas. Impacto: convergencia más rápida y estable del fitting para correctives de hombro y cadera. Estimado: 30 minutos de implementación, sin cambios en el rig.

---

### 2026-08-03 — Weekly Research Run
- Math/Advanced: 3 archivos
- Performance: 2 archivos
- Tools/Rigs: 1 archivo
- Total: 6 archivos
- Destacado matemático: **IK Singularity Avoidance — Unified Treatment (arxiv 2604.13405, Apr 2026)** — Taxonomía de 12 solvers IK: pseudoinversa, DLS (Δθ = Jᵀ(JJᵀ + λ²I)⁻¹Δx), SDLS (amortiguación por valor singular), variable-λ(w) basado en manipulabilidad w = sqrt(det(JJᵀ)), e IK por aprendizaje (IKFlow, HJCD-IK). SDLS produce ~2% error de tarea vs ~5% del DLS fijo en singularidades. Directly upgrades the FABRIK solver for chains > 6 joints (tail, redundant spine).
- Destacado performance: **Animated BlendShape Targets — CPU Constraint** — Un blendShape con target mesh animado fuerza CPU en toda la cadena GPU upstream. La regla de oro: todos los targets deben ser sculpts estáticos; los pesos se drivean con SDK/RBF. Maya 2024 partial GPU download reduce el impacto a 0.5-2ms overhead. `deformerEvaluator(mesh, query=True, verbose=True)` + `full_gpu_audit()` identifican los offenders.
- Aplicable inmediatamente: **`tangentSpace=True` en corrective blendShapes de autorig_tools** — Los correctives de hombro/cadera probablemente usan object space (default Maya). Añadir `tangentSpace=True` al comando de creación evita que se vean incorrectos al rotar el personaje. Cambio de 1 línea. También: usar `bindMethod=3` (Geodesic Voxel) para personajes con geometría compleja — mejora pesos automáticos en axilas/ropa sin coste de runtime.

---

### 2026-07-27 — Weekly Research Run
- Math/Advanced: 3 archivos
- Performance: 2 archivos
- Tools/Rigs: 1 archivo
- Total: 6 archivos
- Destacado matemático: **Riemannian SO(3) Fréchet Mean & Log-Euclidean Blending** — La media geodésica correcta de N quaterniones: μ = argmin Σ w_i·d²(R, R_i) via iteración Karcher. El blend lineal naive de quaterniones (Σw_i·q_i normalizado) tiene error O(θ²) — hasta 5-10° de error en hombros/caderas a 90°+. Log-Euclidean (log → mezcla lineal en ℝ³ → exp) es orden de magnitud más rápido que Fréchet iterativa con error negligible para poses de producción. Directamente aplicable al sistema RBF de correctives para obtener interpolación de rotación geodésicamente correcta.
- Destacado performance: **Expression Nodes & Dirty Propagation** — Los expression nodes reciben scheduling globally_serialize porque sus dependencias (getAttr arbitrario en MEL) no pueden analizarse estáticamente. Esto crea una barrera total: nada puede evaluarse en paralelo mientras el expression corre. Overhead: ~0.5-2ms por expression + pérdida de slots paralelos para todos los nodos downstream. En Cached Playback: always_dirty → el cache nunca persiste downstream del expression. 30-50 expressions en rig facial legacy = 15-100ms acumulados de overhead puro.
- Aplicable inmediatamente: **`audit_expression_nodes()` en el rig facial de autorig_tools** — La función detecta expressions por severidad (HIGH = getAttr implícito, >10 nodos downstream). La tabla de sustitución cubre el 90% de los casos: SDK/animCurve para correctives driven de rotación, multiplyDivide para escalas, condition para condicionales, aimMatrix para direcciones. Eliminar 5-10 expressions del facial puede recuperar 10-30ms por frame y desbloquear el Cached Playback para toda la cadena facial.

---

### 2026-07-20 — Weekly Research Run
- Math/Advanced: 1 archivo
- Performance: 1 archivo
- Tools/Rigs: 0 archivos
- Total: 2 archivos
- Destacado matemático: **HJCD-IK — GPU-Accelerated IK via Batched Hybrid Jacobian Coordinate Descent** (A2R Lab, arxiv 2510.07514, Oct 2025). Combina PO-CCD initialization (CCD orientation-aware con cientos de seeds en paralelo en GPU — cada thread CUDA explora una seed independiente) + PJ-IK polishing (refinamiento Jacobiano DLS paralelo sobre las mejores seeds). Logra gains de orden de magnitud sobre state-of-the-art (NLOPT, IKFlow, CCD clásico) en la frontera accuracy-latency Pareto, con la distribución de muestras de menor MMD (Maximum Mean Discrepancy). Nuevo marco conceptual post-FABRIK/CCD/DLS para cadenas largas y multi-chain en GPU.
- Destacado performance: **Maya 2026 Cached Playback — Topology tracking y tres modos de cache** — El Caching Point invalida solo cuando cambia la topología de dependencia (no por valores). Tres modos: Evaluation Cache (RAM, más compatible), VP2 Hardware Cache (VRAM, zero CPU overhead, más rápido — bloqueado por Visibility animada), GPU Cache (VRAM post-deformación GPU). GPU Override + VP2 Hardware Cache activos simultáneamente = máximo speedup. Dynamic GPU Node Reclamation en 2026 reclasifica nodos previously `globally_serialize`. El rig matrix-based de autorig_tools (multMatrix, decomposeMatrix) es cache-friendly by design.
- Aplicable inmediatamente: (1) Ejecutar `audit_rig_for_cache_compatibility(rig_root)` para detectar blockers de VP2 Hardware Cache — el sospechoso principal es `.visibility` keyed en algún módulo de autorig_tools. (2) Activar Evaluation Cache desde el icono de reloj en el Time Slider sin cambiar el rig. (3) Concepto "multiple seeds → select best" de HJCD-IK aplicable como parallel_seeds_cpu() wrapper sobre FABRIK para cadenas de cola/spine con múltiples soluciones posibles.

---

### 2026-07-13 — Weekly Research Run
- Math/Advanced: 3 archivos
- Performance: 2 archivos
- Tools/Rigs: 2 archivos
- Total: 7 archivos
- Destacado matemático: **Polar Decomposition F=R·S + Exponential Maps para RBF drivers** — La descomposición polar F=R·S via SVD extrae la rotación geométrica por vértice (no el Euler del joint), y los exponential maps son drivers 3DOF libres de singularidades para optimizadores IK (Grassia 1998). Juntos permiten drivers pose-space geodésicamente correctos: polar decomposition mide la deformación local real, el exponential map codifica la pose de entrada sin gimbal lock ni discontinuidades, y el RBF interpola en el espacio tangente de SO(3).
- Destacado performance: **GPU Override vertex thresholds (AMD >500, NVIDIA >2000)** — Por debajo de estos umbrales la deformación GPU es más lenta que CPU por el overhead del driver (~0.3ms base cost fijo). deltaMush ya soporta GPU en Maya 2024. La ratio de speedup por influencia aumenta con GPU (más influencias = más ventaja GPU sobre CPU). La función `audit_gpu_suitability()` del archivo clasifica cada mesh automáticamente.
- Aplicable inmediatamente: **Volume preservation fix: `s^(-0.5)` not `s^(0.5)` + `build_volume_preserve_ik()` GPU-compatible** — La función reemplaza cualquier `distanceBetween` en cadenas IK con `decomposeMatrix.outputTranslateX` y conecta `power(-0.5)` a las escalas laterales. Directamente aplicable en `build_arm_rig()` y `build_leg_rig()`.

---

### 2026-07-06 — Weekly Research Run
- Math/Advanced: 2 archivos
- Performance: 2 archivos
- Tools/Rigs: 1 archivo
- Total: 5 archivos
- Destacado matemático: **CGA (Conformal Geometric Algebra) para Skinning** — CGA motors en 5D subsumen quaterniones, dual quaterniones y matrices. Los dilators de CGA soportan escala uniforme algebraicamente (algo que DQS no puede): `D = cosh(γ) + sinh(γ)·e∞`. Esto significa que squash/stretch está encodado nativamente en el motor sin necesidad de nodos de compensación `multiplyDivide`. GPU skinning (OpenCL) con los mismo perfil de rendimiento que DQS (~3× sobre CPU LBS). También se añade la formalización matemática completa de DNN IK solvers (arxiv Jul 2025): 1000× más rápido que CD (~0.1ms GPU vs ~123ms), con >95% de éxito bajo restricciones angulares realistas.
- Destacado performance: **MPxGPUDeformer — Deformadores Custom en GPU OpenCL** — La API C++ que permite escribir deformadores que corren en OpenCL, manteniéndose dentro del GPU Deformer Cluster sin readback CPU. Un único deformador sin GPUDeformer registration añade +4-10ms de overhead por frame (round-trip GPU→CPU→GPU). La función `audit_gpu_blockers()` en Python detecta qué nodos rompen el cluster GPU en el stack de deformación. Nuevo también: **Maya 2024 Granular Deformer Scheduling** — follicles y uvPin ya no rompen todo el cluster GPU upstream, solo hacen readback local. Rigs con 1-3 follicles ganan ~30% velocidad interactiva con solo actualizar a Maya 2024, sin tocar el rig.
- Aplicable inmediatamente: **`fabrik_solver()` Python + `audit_gpu_blockers()`** — La implementación completa de FABRIK en `maya.api.OpenMaya` está lista para copiar en `autorig_tools/utils/ik_solvers.py` para tail rigs, procedural spine pose, y cadenas >3 bones (1-2h). La función `audit_gpu_blockers()` es accionable inmediatamente en cualquier rig de producción para identificar dónde se rompen los clusters GPU.

---

### 2026-06-29 — Weekly Research Run
- Math/Advanced: 4 archivos
- Performance: 3 archivos
- Tools/Rigs: 2 archivos
- Total: 9 archivos
- Destacado matemático: **Position-Based Dynamics (PBD) y XPBD** — La reformulación de simulación física como proyección directa de posiciones (en vez de integración de fuerzas) explica por qué nCloth y todos los solvers modernos de jiggle son incondicionalmente estables frente a masas-resortes clásicas. XPBD añade un parámetro de compliance (α=1/k) que hace que el resultado converja a la física correcta independientemente del número de iteraciones/substeps — a diferencia de PBD básico, donde la rigidez efectiva depende del solver. Para una zona de jiggle (panza, papada) bastan 1-2 partículas con restricción de distancia + attachment, ~50 líneas de Python/numpy, sin pasar por nCloth. Complementa el research de esta semana sobre ScLERP (interpolación exacta de poses rígidas en SE(3)) y Cosserat rods (física de colas/tentáculos vía Discrete Elastic Rods) — los tres llenan el hueco de "dinámica/interpolación geométrica avanzada" que no estaba cubierto en semanas anteriores.
- Destacado performance: **TBB vs OpenMP — thread oversubscription con plugins de terceros** — Maya migró su threading interno a Intel TBB (work-stealing scheduler, pool de hilos único y compartido por proceso). Un plugin de terceros compilado con OpenMP (p.ej. un solver custom) crea SU PROPIO pool de hilos independiente — con N cores físicos y dos sistemas reclamando N hilos cada uno, el resultado es oversubscription: activar Parallel Evaluation puede volverse MÁS LENTO que DG serial si hay un plugin OpenMP en la escena. Es un gotcha real e invisible si no se sabe qué librería de threading usa cada plugin instalado.
- Aplicable inmediatamente: **Auditoría de locators auxiliares (`audit_auxiliary_locators()`)** — Cada locator usado solo para "transportar" una matriz (en vez de ser un control real manipulable por el animador) añade una cadena completa de `worldMatrix` recursiva (DAG) en vez del coste mínimo de un `multMatrix`/`pickMatrix` puro (DG). En un rig de cuerpo completo, 30-60 locators auxiliares "por comodidad" en espacios de aim/pole vector/twist son habituales y reemplazables 1:1 por nodos de matrix directos sin cambiar el comportamiento del rig — acción de bajo riesgo y alto retorno, lista para ejecutar esta semana sobre un rig de producción de autorig_tools.

---

### 2026-06-22 — Weekly Research Run
- Math/Advanced: 3 archivos
- Performance: 3 archivos
- Tools/Rigs: 4 archivos
- Total: 10 archivos
- Destacado matemático: **Bounded Biharmonic Weights (BBW)** — Jacobson, Baran, Popović & Sorkine (SIGGRAPH 2011) formalizan el pintado automático de pesos de skinning como un problema de optimización convexo: minimizar la energía biarmónica (Laplaciano al cuadrado) sujeta a partición de unidad y pesos acotados en [0,1]. La restricción de acotamiento es la clave — elimina los pesos negativos que producen heat-diffusion o biharmonic sin cotas cerca de axilas/ingle/codos. Computable offline con `libigl` (`igl.bbw`) y cargable directo a un `skinCluster` vía `MFnSkinCluster.setWeights`. Completa el research de la familia CoR/SSDR/SBS ya cubierta en semanas anteriores, y se acompaña esta semana de ARAP (Sorkine & Alexa 2007) para limpieza de correctives vía SVD por celda, y Spherical Blend Skinning (Kavan & Žára 2005) como eslabón histórico entre LBS y DQS.
- Destacado performance: **unitConversion nodes en SDK/RBF facial** — Un facial rig de producción real midió 760ms acumulados en nodos `unitConversion`+`blendWeighted` por las conexiones float→doubleAngle que Maya inserta automáticamente en cada SDK. El stack matrix-based de Laia (local_mmx, offsetParentMatrix) ya evita esto en las cadenas de transform, pero las zonas de riesgo real son el rig facial y los correctivos RBF/SDK donde sí conecta atributos escalares directamente.
- Aplicable inmediatamente: **`audit_unit_conversion_nodes()` + `prune_and_cap_skin_weights()`** — Dos funciones de diagnóstico/limpieza de bajo esfuerzo (1-2h cada una, sin dependencias externas): la primera detecta nodos unitConversion costosos en cadenas SDK/facial; la segunda aplica `skinPercent(pruneWeights=...)` + `skinCluster(maximumInfluences=8)` al final del pipeline de skinning para eliminar el coste de influencias residuales de valor casi nulo sin perder calidad de deformación. Ambas se integran directamente en el post-build health check existente de autorig_tools.

---

### 2026-06-15 — Weekly Research Run
- Math/Advanced: 3 archivos
- Performance: 1 archivo
- Tools/Rigs: 2 archivos
- Total: 6 archivos
- Destacado matemático: **SSDR / DEM Bones** — El algoritmo Smooth Skinning Decomposition with Rigid Bones (Le & Deng, SIGGRAPH Asia 2012) invierte el problema de skinning: dada una secuencia de animación de malla, calcula automáticamente joints virtuales y pesos LBS óptimos via Block Coordinate Descent alternando SVD (para transforms de bone, O(B·T)) y NNLS (para pesos por vértice, con sparsity k≤4). EA Open Source implementa esto como DEM Bones (C++, BSD-3, plugin Maya incluido). Workflow: simulación → Alembic → DEM Bones → skinCluster estándar. Complementa CoR skinning (Le & Hodgins 2016, SIGGRAPH): CoR resuelve candy-wrapper+bulging precomputando centros de rotación por vértice con polar decomposition SVD en runtime — sin nodo Maya nativo, pero elimina la necesidad de correctivos en zonas problemáticas.
- Destacado performance: **Deformation Layering — outMesh→inMesh rompe GPU** — Conectar `outMesh` de un mesh con skinCluster al `inMesh` de otro mesh fuerza CPU para toda la cadena upstream (regla de Using Parallel Maya). La solución: usar blendShape como "pasarela" entre capas de deformación. La función `audit_deformation_architecture()` del archivo detecta estos patrones automáticamente. Este es uno de los principales causantes silenciosos de pérdida de GPU Override en rigs complejos que combinan múltiples meshes.
- Aplicable inmediatamente: **DEM Bones para simulaciones a LBS** — Workflow directo: nCloth/Qualoth sim → exportar ABC → DEM Bones (`--nBones 20-30 --nnz 4`) → importar FBX en Maya → transferir pesos al mesh original con `copySkinWeights`. Convierte simulaciones CPU-only en skinClusters GPU-compatibles. La función `ssdr_preskin()` del archivo `2026-06-15-dem-bones-electronicarts-ssdr-production.md` está lista para integrar en el pipeline de autorig_tools como paso de pre-skinning para assets con simulación.

---

### 2026-06-08 — Weekly Research Run
- Math/Advanced: 3 archivos
- Performance: 1 archivo
- Tools/Rigs: 2 archivos
- Total: 6 archivos
- Destacado matemático: **Direct Delta Mush (DDM)** — Le & Lewis (EA SEED, SIGGRAPH 2019) precomputa el operador Laplaciano iterativo L^n en matrices estáticas por hueso en tiempo de bind, convirtiendo el deltaMush iterativo en una operación O(1) por vértice idéntica en coste a LBS. Las matrices M_{b,i} son simétricas (10 floats, no 16), calculables offline con scipy.sparse. Resuelve el problema crítico: el `deltaMush` nativo de Maya es CPU-only y rompe GPU Override. DDM implementado como C++ MPxDeformerNode sería GPU-compatible y kParallel. Enhanced DDM (Apple 2021, arxiv 2101.02798) añade términos de corrección por pose.
- Destacado performance: **Maya ML Deformer (2025.2)** — DNN + PCA en dos niveles: subspace mini-network para deformaciones globales (50 PCA components) + red residual para alta frecuencia. Training en horas offline (Pose Generator automático) deployment interactivo. Speedup típico: 5-50× sobre deformadores complejos durante sesión de animación. GPU inference en Maya 2026+. Integrable en post-build de autorig_tools como `mlDeformerTrain()` para personajes hero con stack pesado.
- Aplicable inmediatamente: **MayaMeshRetarget (yamahigashi)** — Python puro (scipy + scikit-learn), Maya 2022+. `ymt_mesh_retarget.retarget(source, target, kernel='gaussian', apply_rigid_transform=True)` transfiere skin weights entre topologías distintas en una línea, preservando rigidez articular via bone-cluster RBF. Directo para variantes de personaje y LODs. Instalación: `mayapy -m pip install scipy scikit-learn embreex` + clone del repo. Setup en 1-2 horas.

---

### 2026-06-01 — Weekly Research Run
- Math/Advanced: 3 archivos
- Performance: 1 archivo
- Tools/Rigs: 3 archivos
- Total: 7 archivos
- Destacado matemático: **Swing-Twist Quaternion Decomposition** — La separación matemática de una rotación en componente de twist (alrededor del eje longitudinal del hueso) y swing (rotación restante) via `quatNormalize` con ceros en los ejes no-twist. El insight clave: `swing = inverse(twist) * full_rotation`. Permite propagar pesos de twist independientes por joint (0.33, 0.66, 1.00) sin flipping. Implementable como `build_swing_twist_extractor(driver, joints, axis, weights)` en autorig_tools — reemplaza el forearm/shin twist actual con un resultado matemáticamente correcto.
- Destacado performance: **Maya 2026 Dynamic GPU Node Evaluation** — El evaluador ahora reclama nodos especulativamente para GPU y hace switching dinámico CPU/GPU frame-a-frame sin repartitioning. Los follicles y uvPin nodes ya no bloquean toda la cadena de deformación. Impacto: hasta 30% mejora interactiva en rigs con 1-3 follicles. Los rigs con matrix rivets siguen siendo óptimos, pero ya no es urgente migrar follicles existentes en pipelines Maya 2026+.
- Aplicable inmediatamente: **dm2skin** — Convertir resultados de delta-mush a skin weights óptimos via optimización NNLS (scipy). El flujo: bind single-influence → delta-mush → keyframe 10+ poses → dm2skin genera pesos ponderados. Requiere fork y actualización a Python 3 para Maya 2022+, pero es una aceleradora directa para el skinning inicial de nuevos personajes en autorig_tools (3-4h de adaptación).

---

### 2026-05-25 — Weekly Research Run
- Math/Advanced: 3 archivos
- Performance: 1 archivo
- Tools/Rigs: 3 archivos
- Total: 7 archivos
- Destacado matemático: **Stretch IK con matriz pura** — Reemplazar `distanceBetween` (CPU-only) con `multMatrix + decomposeMatrix + vectorProduct` para stretch IK sin nodos CPU en la cadena de evaluación. La versión X-axis optimizada usa solo 4 nodos vs los 6 clásicos, eliminando el sqrt del hot path. Aplicable directamente en `build_arm_rig()` y `build_leg_rig()`.
- Destacado performance: **Custom MPxNode y GIL de Python** — Los MPxNode en Python no pueden ser `kParallel` por el GIL: fuerzan serialización incluso en ramas DG completamente independientes. Solución: nodos nativos → maya-math-nodes (C++) → C++ propio con `kParallel` + `setMPSafe(true)`. La función `audit_node_scheduling()` del archivo detecta los offenders inmediatamente.
- Aplicable inmediatamente: **aimMatrix para ojos y helpers** — Reemplazar `aimConstraint` en el rig facial (ojos, eyelids) y shoulder helpers con `aimMatrix + multMatrix + decomposeMatrix` (Maya 2020+). Elimina nodos `locally_serialized` del grafo de evaluación. El `build_aim_matrix()` incluido en el archivo Math es drop-in replacement del constraint existente.

---

### 2026-05-18 — Weekly Research Run
- Math/Advanced: 3 archivos
- Performance: 2 archivos
- Tools/Rigs: 2 archivos
- Total: 7 archivos
- Destacado matemático: **B-spline / Algoritmo de de Boor** — La matemática detrás del ribbon spine de Laia: fórmula Cox-de Boor recursiva, knot vector clamped, por qué los joints del ribbon no son equidistantes con parámetros uniformes.
- Destacado performance: **Cached Playback Caching Points** — Qué estructura de rig invalida el caché de 130fps: expression nodes (always dirty), topology changes, deep chains vs wide branches. La check function `rig_health_report()` es aplicable inmediatamente.
- Aplicable inmediatamente: **`rig_health_report()`** (Evaluation Toolkit file) — función Python que detecta nodos serializadores + expresiones + benchmarks DG vs Parallel en una sola llamada. Integrar en el post-build de autorig_tools.

---

### 2026-05-11 — Weekly Research Run
- Math/Advanced: 7 archivos
- Performance: 4 archivos
- Tools/Rigs: 1 archivo
- Total: 12 archivos
- Destacado matemático: **Dual Quaternion Skinning (DQS)** — La matemática del candy-wrapper de LBS (rank-deficient matrix average a 180°) vs el bulging de DQS (SLERP arc path) queda completamente formalizada. Anti-podality check es el detalle crítico que rompe implementaciones naive. `skinningMethod=2` (blended) en Maya permite usar LBS y DQS por zona en el mismo skinCluster. Implementable en 2-3 horas.
- Destacado performance: **Disney Frozen 2 SIGGRAPH 2019** — Benchmarks reales de producción: DG mode 3-5fps → Parallel+GPU 20-30fps → Cached Playback 130fps+. El bloqueante principal fueron custom C++ deformers sin declaración de parallel scheduling y follicles en cadenas GPU. La eliminación de expression nodes es el primer paso (fuerzan serialización de todo lo downstream).
- Aplicable inmediatamente: **Matrix Twist Extraction** (`decomposeMatrix → quatNormalize (zero Y/Z) → quatToEuler`) — reemplaza aimConstraints y ikHandle tricks para forearm/shin twist. 3 nodos nativos, 100% GPU-compatible, sin trig, sin flipping. Implementar como `build_twist_extractor(source, axis)` en autorig_tools (1-2 horas).

---

### 2026-05-05 — Weekly Research Run
*(archivos de referencia — ver Techniques/, Tools/, Rigs/ para contenido completo)*
- Técnicas: 6 archivos (ribbon-spine-matrix, matrix-offsetParentMatrix, ikfk-matching, mgear-rbf-psd, facial-production, quadruped-production)
- Tools: 6 archivos (mgear 5.3, rigamajig2, dpAutoRigSystem, mansur-rig, freeformtools, ml-corrective-deformer)
- Rigs: 2 archivos (noa-aswf, animschool-malcolm)
- Total: 14 archivos
