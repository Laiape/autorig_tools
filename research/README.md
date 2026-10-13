# Rigging Research — Archivo completo

Toda la información recogida por las investigaciones semanales automáticas sobre rigging, descargada de Google Drive (`Obsidian/Research/`) y organizada en una sola carpeta. Va del 2026-05-05 al 2026-10-12.

## Origen

| Rutina | Frecuencia | Qué produce | Carpetas |
|---|---|---|---|
| **Rigging Research — Weekly** | Semanal (lunes) | Técnicas matemáticas y de rendimiento, herramientas y rigs de referencia, más una entrada en el Research Log | `Techniques/`, `Techniques/Math/`, `Techniques/Performance/`, `Tools/`, `Rigs/`, `Logs/` |
| **Portfolio Research — Weekly** | Semanal (miércoles) | Análisis de portfolios de riggers/TDs y el documento de insights acumulados | `Portfolios/` |

## Por dónde empezar

- [`Logs/00-Research-Log.md`](Logs/00-Research-Log.md): resumen semanal de cada ronda, con lo más destacado en matemáticas y rendimiento, y lo aplicable de inmediato a autorig_tools. Tiene 21 entradas.
- [`Portfolios/00-Portfolio-Insights-latest-2026-10-07.md`](Portfolios/00-Portfolio-Insights-latest-2026-10-07.md): conclusiones acumuladas de los portfolios analizados.
- [`Portfolios/00-Portfolio-Insights-archivo-hasta-2026-08-26.md`](Portfolios/00-Portfolio-Insights-archivo-hasta-2026-08-26.md): versión archivada de los insights hasta el 26 de agosto.

## Recuento

| Carpeta | Archivos |
|---|---|
| `Techniques/Math/` | 58 |
| `Techniques/Performance/` | 36 |
| `Techniques/` | 6 |
| `Tools/` | 38 |
| `Rigs/` | 5 |
| `Portfolios/` | 80 |
| `Logs/` | 1 |
| **Total** | **224** |

## Técnicas — Matemáticas / avanzado

`Techniques/Math/` — 58 archivos


**2026-10-12**

- [Pose Space Deformation (PSD): Unified Math for RBF Corrective Shapes](Techniques/Math/2026-10-12-psd-pose-space-deformation-rbf-correctives-math.md)
- [Exponential Maps & Rotation Representations: Euler, Quaternion, Axis-Angle, Exp Map](Techniques/Math/2026-10-12-exponential-maps-rotation-representation-gimbal.md)

**2026-09-14**

- [RigPAPR: LBS Aplicado a Nubes de Puntos Neuronales (arXiv:2606.06685, SIGGRAPH 2026)](Techniques/Math/2026-09-14-rigpapr-lbs-neural-point-clouds-siggraph2026.md)
- [A Geodesic Cut-Cell Prior for Neural Skinning](Techniques/Math/2026-09-14-geodesic-cut-cell-prior-neural-skinning.md)

**2026-09-07**

- [SQUAD — Spherical Quadrangle Interpolation para Rotaciones Suaves (Shoemake 1985/1987)](Techniques/Math/2026-09-07-squad-quaternion-spline-smooth-rotation-animation.md)
- [OmniFaceRig — Pipeline Automático de FACS Facial Rigging con Inner Mouth (arXiv:2606.08043, Jun 2026)](Techniques/Math/2026-09-07-omniface-rig-facs-automatic-facial-rigging-2026.md)

**2026-08-31**

- [ViPS: Video-Informed Pose Spaces for Auto-Rigged Meshes (arXiv Apr 2026)](Techniques/Math/2026-08-31-vips-video-informed-pose-spaces-autorig-correctives.md)
- [POE Splines on Lie Groups: SO(3) and SE(3) — Müller 2025/2026](Techniques/Math/2026-08-31-poe-splines-lie-groups-SO3-SE3-ribbon-spine.md)

**2026-08-24**

- [SkinCells — Sparse Skinning using Voronoi Cells (Eurographics/CGF 2026)](Techniques/Math/2026-08-24-skincells-voronoi-sparse-skinning-eurographics2026.md)
- [PhysSkin — Real-Time Generalizable Physics-Based Animation via Self-Supervised Neural Skinning (CVPR 2026 Highlight)](Techniques/Math/2026-08-24-physskin-neural-skinning-fields-cvpr2026.md)
- [Skeletal-Driven Animation of Anatomical Humans via Neural Deformation Gradients (Nolte et al. 2026)](Techniques/Math/2026-08-24-neural-deformation-gradients-anatomical-humans-nolte.md)

**2026-08-17**

- [Matrix Twist Extraction en Maya — Swing-Twist Decomposition sin Gimbal Lock](Techniques/Math/2026-08-17-matrix-twist-extraction-maya-nodes-swing-twist.md)
- [FABRIK vs CCD IK Solvers — Convergencia, Matemática e Implementación](Techniques/Math/2026-08-17-fabrik-ccd-ik-solvers-comparison-convergence.md)
- [Dual Quaternion Skinning (DQS) vs Linear Blend Skinning — Matemática y Artefactos](Techniques/Math/2026-08-17-dual-quaternion-skinning-dqs-lbs-math.md)
- [B-Spline y Algoritmo de de Boor — Ribbon Spine sin NURBS ni Rivets](Techniques/Math/2026-08-17-bspline-deboor-algorithm-ribbon-spine-rigging.md)

**2026-08-10**

- [ViPS — Video-Informed Pose Spaces for Auto-Rigged Meshes (Apr 2026)](Techniques/Math/2026-08-10-vips-video-informed-pose-spaces.md)
- [6D Continuous Rotation Representations — Matemática para Pipelines Diferenciables de Rigging](Techniques/Math/2026-08-10-6d-continuous-rotation-representations.md)

**2026-08-03**

- [IK Singularity Avoidance — Unified Treatment: DLS, SDLS, Riemannian Manipulability (Apr 2026)](Techniques/Math/2026-08-03-ik-singularity-unified-treatment-dls-sdls-2026.md)
- [Corrective Blendshape Delta Extraction — Tangent Space Math](Techniques/Math/2026-08-03-corrective-blendshape-delta-extraction-tangent-space.md)
- [Automatic Skinning Weight Computation — Heat Diffusion vs Geodesic Voxel](Techniques/Math/2026-08-03-automatic-skinning-heat-diffusion-voxel-geodesic.md)

**2026-07-27**

- [Interpolación Geodésica en SO(3): Media de Fréchet y Log-Euclidean Blending](Techniques/Math/2026-07-27-riemannian-so3-geodesic-interpolation-frechet-mean.md)
- [Jacobian Null Space IK: Secondary Objectives y Resolución de Redundancia](Techniques/Math/2026-07-27-jacobian-nullspace-secondary-objectives-redundancy-resolution.md)
- [Cage-Based Deformation: Harmonic, Mean Value & Green Coordinates](Techniques/Math/2026-07-27-cage-based-deformation-harmonic-green-mean-value-coordinates.md)

**2026-07-20**

- [HJCD-IK — GPU-Accelerated IK via Batched Hybrid Jacobian Coordinate Descent](Techniques/Math/2026-07-20-hjcd-ik-gpu-accelerated-ik-solver.md)

**2026-07-13**

- [Volume Preservation en Squash/Stretch -- Matematicas e Implementacion en Maya](Techniques/Math/2026-07-13-volume-preservation-squash-stretch-math.md)
- [Rotation Representations — Euler, Quaternion, Axis-Angle, Exponential Map y Gimbal Lock](Techniques/Math/2026-07-13-rotation-representations-exponential-maps-gimbal-lock.md)
- [Polar Decomposition y Deformation Gradient para Correctives](Techniques/Math/2026-07-13-polar-decomposition-deformation-gradient-correctives.md)

**2026-07-06**

- [ML/DNN para Inverse Kinematics en Tiempo Real — Más Allá de FABRIK y CCD](Techniques/Math/2026-07-06-ml-neural-ik-solvers-realtime.md)
- [Conformal Geometric Algebra (CGA) para Character Skinning](Techniques/Math/2026-07-06-conformal-geometric-algebra-cga-skinning.md)

**2026-06-29**

- [ScLERP (Screw Linear Interpolation) — Interpolación de Transformaciones Rígidas en SE(3)](Techniques/Math/2026-06-29-sclerp-screw-linear-interpolation-dual-quaternions.md)
- [Position-Based Dynamics (PBD) y XPBD — Matemática para Jiggle y Correctivas de Movimiento Secundario](Techniques/Math/2026-06-29-position-based-dynamics-pbd-xpbd-jiggle.md)
- [Cosserat Rods — Mecánica de Continuo para Colas, Tentáculos y Cuerdas](Techniques/Math/2026-06-29-cosserat-rods-continuum-mechanics-tails-tentacles.md)
- [Curvas de Bézier y el Algoritmo de De Casteljau](Techniques/Math/2026-06-29-bezier-curves-de-casteljau-algorithm.md)

**2026-06-22**

- [Spherical Blend Skinning (SBS)](Techniques/Math/2026-06-22-spherical-blend-skinning-sbs.md)
- [Bounded Biharmonic Weights (BBW) — Automatic Skinning Weights](Techniques/Math/2026-06-22-bounded-biharmonic-weights-bbw.md)
- [As-Rigid-As-Possible (ARAP) Surface Modeling](Techniques/Math/2026-06-22-arap-as-rigid-as-possible-surface-modeling.md)

**2026-06-15**

- [SSDR — Smooth Skinning Decomposition with Rigid Bones (Le & Deng, SIGGRAPH Asia 2012)](Techniques/Math/2026-06-15-ssdr-smooth-skinning-decomposition-rigid-bones.md)
- [FABRIK & CCD — Solvers Iterativos de IK para Cadenas N-Joint](Techniques/Math/2026-06-15-fabrik-ccd-ik-solvers-iterative.md)
- [CoR — Real-Time Skeletal Skinning with Optimized Centers of Rotation (Le & Hodgins, SIGGRAPH 2016)](Techniques/Math/2026-06-15-cor-center-of-rotation-skinning-le-hodgins-2016.md)

**2026-06-08**

- [Velocity Skinning — Deformación Estilizada en Tiempo Real desde Velocidades Óseas](Techniques/Math/2026-06-08-velocity-skinning-stylized-real-time.md)
- [Laplacian Surface Editing — Deformación que Preserva Detalle Superficial](Techniques/Math/2026-06-08-laplacian-surface-editing-sorkine-2004.md)
- [Direct Delta Mush (DDM) — Laplacian Skinning sin Iteración](Techniques/Math/2026-06-08-direct-delta-mush-ddm-siggraph2019.md)

**2026-06-01**

- [Pose Space Deformation — Fundamento Matemático Tensor y RBF (Lewis et al. 2000)](Techniques/Math/2026-06-01-tensor-psd-pose-space-deformation-math.md)
- [Swing-Twist Quaternion Decomposition — Math y Nodos Maya](Techniques/Math/2026-06-01-swing-twist-quaternion-decomposition.md)
- [RBF Kernel Functions — Matemáticas para Correctives y Mesh Retargeting](Techniques/Math/2026-06-01-rbf-kernel-functions-mathematical-basis.md)

**2026-05-25**

- [Stretch IK with Pure Matrix Math — No distanceBetween Node](Techniques/Math/2026-05-25-stretch-ik-pure-matrix-maya.md)
- [Rotation Representations: Euler vs Quaternion vs Axis-Angle vs Exponential Map — Gimbal Lock & Maya Implications](Techniques/Math/2026-05-25-rotation-representations-gimbal-lock.md)
- [Aim Constraint Replacement with Matrix Nodes — worldUpMatrix Patterns & aimMatrix Node](Techniques/Math/2026-05-25-aim-constraint-worldUpMatrix-matrix-nodes.md)

**2026-05-18**

- [Polar Decomposition, SVD y Deformation Gradients para Rigging](Techniques/Math/2026-05-18-polar-decomposition-svd-deformation-gradients.md)
- [B-Splines, Algoritmo de de Boor y NURBS para Ribbon Spine](Techniques/Math/2026-05-18-bspline-deboor-nurbs-ribbon-math.md)
- [Analytic Two-Bone IK — Ley de Cosenos, Pole Vector y Implementación Maya](Techniques/Math/2026-05-18-analytic-twobone-ik-law-cosines.md)

**2026-05-11**

- [Volume Preservation in Stretch/Squash Rigs — Matemática y Nodo Graph Maya](Techniques/Math/2026-05-11-volume-preservation-stretch-squash-math.md)
- [Skinning Algorithms Beyond LBS — CoR, SSDR, SBS](Techniques/Math/2026-05-11-skinning-beyond-lbs-cor-ssdr.md)
- [Quaternion Interpolation — SLERP, SQUAD y Log-Quaternion Blending](Techniques/Math/2026-05-11-quaternion-interpolation-slerp-squad-log.md)
- [Matrix Twist Extraction in Maya — Pure Quaternion/Matrix Solution, No Trigonometry](Techniques/Math/2026-05-11-matrix-twist-extraction-maya.md)
- [IK Solvers — FABRIK, CCD y Jacobian Pseudoinversa: Matemática y Comparativa](Techniques/Math/2026-05-11-ik-solvers-fabrik-ccd-jacobian.md)
- [Dual Quaternion Skinning (DQS) — Math, Artifacts & LBS Comparison](Techniques/Math/2026-05-11-dual-quaternion-skinning-math.md)
- [Delta Mush y Deformación Laplaciana — Matemática e Implementación](Techniques/Math/2026-05-11-delta-mush-laplacian-deformation-math.md)

## Técnicas — Rendimiento (Maya evaluation, GPU, caché)

`Techniques/Performance/` — 36 archivos


**2026-10-12**

- [Maya Profiler & Evaluation Toolkit: Complete Benchmarking Workflow](Techniques/Performance/2026-10-12-maya-profiler-evaluation-toolkit-workflow.md)
- [Deformer Stack Ordering for GPU Performance in Maya](Techniques/Performance/2026-10-12-deformer-stack-ordering-gpu-performance.md)

**2026-09-14**

- [mGear Evaluation Partition: Mesh Splitting for Parallel Deformer Evaluation](Techniques/Performance/2026-09-14-mgear-evaluation-partition-polygon-groups-parallel.md)

**2026-09-07**

- [Maya Scheduling Mode — Optimización Dinámica de Visibilidad sin Repartición (Maya 2023+/2026)](Techniques/Performance/2026-09-07-maya-scheduling-mode-invisibility-evaluator-visibility-opt.md)
- [aimMatrix Node — Aim Nativo sin aimConstraint (Maya 2020+)](Techniques/Performance/2026-09-07-aimMatrix-node-native-aim-offsetParentMatrix-performance.md)

**2026-08-31**

- [Maya Cached Playback White Paper 2025 — Arquitectura Completa](Techniques/Performance/2026-08-31-maya-cached-playback-whitepaper-2025-architecture.md)
- [Highly Accurate GPU-Accelerated Animation Rigs for Toothless — Framestore / SIGGRAPH 2025](Techniques/Performance/2026-08-31-framestore-toothless-gpu-opencl-deformers-siggraph2025.md)

**2026-08-24**

- [Maya 2026 — Serial Evaluation Mode & the "No Dirty Propagation" EG Architecture](Techniques/Performance/2026-08-24-maya-2026-serial-evaluation-dirty-propagation-architecture.md)
- [Maya 2026.3 — Dynamic Geometry Attributes (dgaTension / dgaDelta / dgaVisualizer / dgaToArray)](Techniques/Performance/2026-08-24-maya-2026-3-dga-tension-delta-procedural-wrinkles.md)

**2026-08-17**

- [MPxNode::schedulingType — Custom Nodes en Parallel Evaluation](Techniques/Performance/2026-08-17-mpxnode-schedulingtype-parallel-evaluation-custom-nodes.md)
- [Deformer Stack Ordering y GPU Cluster — Guía de Performance para Production Rigs](Techniques/Performance/2026-08-17-deformer-stack-ordering-gpu-cluster-skinning-performance.md)

**2026-08-03**

- [SPECapc for Maya 2024 — Benchmark & Production Rig Performance Data](Techniques/Performance/2026-08-03-specapc-maya-2024-benchmark-deformer-rig-metrics.md)
- [Animated BlendShape Targets — CPU Constraint That Breaks GPU Clusters](Techniques/Performance/2026-08-03-animated-blendshape-targets-cpu-constraint-gpu-cluster-break.md)

**2026-07-27**

- [Topología del Cluster Graph en Parallel Evaluation: Minimizando Re-evaluación](Techniques/Performance/2026-07-27-parallel-evaluation-cluster-graph-topology-dirty-minimization.md)
- [Expression Nodes y Dirty Propagation: Por Qué Serializan la Evaluación](Techniques/Performance/2026-07-27-expression-nodes-dirty-propagation-evaluation-serialization.md)

**2026-07-20**

- [Maya 2026 Cached Playback -- Topology Tracking y Tres Modos de Cache](Techniques/Performance/2026-07-20-maya-cache-playback-2026-rig-topology.md)

**2026-07-13**

- [GPU Override -- Vertex Count Thresholds y Benchmarks de Deformacion](Techniques/Performance/2026-07-13-gpu-override-vertex-thresholds-benchmarks.md)
- [Deformer Stack Ordering para GPU Override y Parallel Evaluation](Techniques/Performance/2026-07-13-deformer-stack-ordering-gpu-compatibility.md)

**2026-07-06**

- [MPxGPUDeformer — Deformadores Custom en GPU OpenCL (C++ API)](Techniques/Performance/2026-07-06-mpxgpudeformer-opencl-custom-gpu-deformers.md)
- [Maya 2024 Deformer Evaluator — Granular Scheduling & GPU Read-Back](Techniques/Performance/2026-07-06-maya-2024-deformer-evaluator-granular-scheduling.md)

**2026-06-29**

- [Threading Interno de Maya — Intel TBB vs OpenMP y MThreadPool](Techniques/Performance/2026-06-29-maya-threading-internals-tbb-vs-openmp.md)
- [Locators vs Transforms — Coste Oculto de Nodos DAG en Rigs Grandes](Techniques/Performance/2026-06-29-locators-vs-transforms-hidden-performance-cost.md)
- [Bifrost Graph — Características de Rendimiento para Rigging](Techniques/Performance/2026-06-29-bifrost-graph-performance-rigging.md)

**2026-06-22**

- [unitConversion Nodes — Cuándo Aparecen y Cuándo Eliminarlos](Techniques/Performance/2026-06-22-unitconversion-nodes-when-to-avoid.md)
- [Influences por Vértice — Coste Computacional vs Calidad de Deformación](Techniques/Performance/2026-06-22-skinning-influence-count-performance-tradeoff.md)
- [Deformer Stack Ordering — blendShape vs skinCluster y el coste de GPU](Techniques/Performance/2026-06-22-deformer-stack-ordering-performance.md)

**2026-06-15**

- [Deformation Layering in Maya's Parallel GPU World (Charles Wardlaw)](Techniques/Performance/2026-06-15-deformation-layering-parallel-gpu-world.md)

**2026-06-08**

- [Maya ML Deformer (2025.2) — Approximación Neural de Deformaciones Complejas](Techniques/Performance/2026-06-08-ml-deformer-maya-2025-performance.md)

**2026-06-01**

- [Maya 2026 — Dynamic GPU Node Evaluation y Mejoras de Repartitioning](Techniques/Performance/2026-06-01-maya-2026-dynamic-gpu-evaluation.md)

**2026-05-25**

- [Custom MPxNode Design for Parallel Evaluation — Scheduling Declarations & Python vs C++](Techniques/Performance/2026-05-25-custom-mpxnode-parallel-evaluation.md)

**2026-05-18**

- [Maya Evaluation Toolkit — Profiling de Rigs, Diagnosis de Serialización y Benchmarks](Techniques/Performance/2026-05-18-maya-evaluation-toolkit-rig-profiling.md)
- [Maya Cached Playback — Arquitectura, Caching Points y Topología de Rig](Techniques/Performance/2026-05-18-maya-cached-playback-caching-points.md)

**2026-05-11**

- [Rig Optimization Patterns in Maya — Matrix vs Constraints, Deformer Stack, Node Topology](Techniques/Performance/2026-05-11-rig-optimization-patterns-maya.md)
- [Maya Parallel Evaluation Architecture — Scheduling, Dirty Propagation & Rig Compatibility](Techniques/Performance/2026-05-11-maya-parallel-evaluation-architecture.md)
- [Maya GPU Override — Deformadores Soportados, Bloqueantes y Maya 2024 Improvements](Techniques/Performance/2026-05-11-gpu-override-deformers-maya.md)
- [Disney Animation: Optimizing Rig Manipulation with GPU + Parallel Evaluation (Frozen 2 / SIGGRAPH 2019)](Techniques/Performance/2026-05-11-disney-frozen2-gpu-rig-manipulation.md)

## Técnicas — Generales (primera ronda)

`Techniques/` — 6 archivos


**2026-05-05**

- [Ribbon Spine Rigging — Setup Matrix-Based sin Follicles](Techniques/2026-05-05-ribbon-spine-matrix.md)
- [Quadruped Rigging para Producción en Maya — Técnicas Avanzadas](Techniques/2026-05-05-quadruped-rigging-production.md)
- [RBF / PSD Correctives en Maya — mGear RBF Manager + Epic PoseWrangler](Techniques/2026-05-05-mgear-rbf-manager-psd.md)
- [Matrix Rigging con offsetParentMatrix — Space Switch sin Constraints](Techniques/2026-05-05-matrix-rigging-offsetParentMatrix.md)
- [IK/FK Matching — Teoría y Algoritmo de Implementación](Techniques/2026-05-05-ikfk-matching-theory.md)
- [Facial Rigging de Producción en Maya — Jaw, Eyes, Eyelids, Lips](Techniques/2026-05-05-facial-rigging-production.md)

## Herramientas

`Tools/` — 38 archivos


**2026-10-12**

- [MayaBridge — MCP/TCP Bridge for AI Agent Automation of Maya](Tools/2026-10-12-asukacodes-mayabridge-mcp-tcp-ai-automation.md)

**2026-09-14**

- [mGear 5.3 — Autorig Framework for Maya 2022–2027](Tools/2026-09-14-mgear-5-3-autorig-framework-maya2027.md)
- [Ji Hun Park — Maya Production Python Toolkit (elom1213/Maya_Python)](Tools/2026-09-14-elom1213-jh-park-maya-production-toolkit.md)

**2026-09-07**

- [Hyperdrive — Pose-Based Rig Caching Plugin para Maya (timlehr, ~58 estrellas)](Tools/2026-09-07-hyperdrive-pose-based-rig-caching-timlehr.md)

**2026-08-31**

- [AKEric/skinner — Maya Skin Weight Export/Import (AAA Production)](Tools/2026-08-31-akeric-skinner-skin-weight-pipeline-tool.md)

**2026-08-24**

- [Skinner (AKEric) — Skin Weight Export/Import Tool for Maya](Tools/2026-08-24-akeric-skinner-skin-export-import-maya-tool.md)

**2026-08-17**

- [GT Tools — Free Maya Python Scripts Collection (TrevisanGMW)](Tools/2026-08-17-gt-tools-trevisangmw-maya-python-scripts.md)

**2026-08-10**

- [UniRig — One Model to Rig Them All (SIGGRAPH 2025)](Tools/2026-08-10-unirig-siggraph2025.md)
- [SPRig — Self-Supervised Pose-Invariant Rigging from Dynamic Mesh Sequences (Feb 2026)](Tools/2026-08-10-sprig-pose-invariant-rigging.md)
- [SkinTokens — Learned Compact Representation for Unified Autoregressive Rigging (2026)](Tools/2026-08-10-skintokens-learned-compact-representation.md)

**2026-08-03**

- [Hive Auto-Rigger (Zoo Tools 2.12.4) — Joint-Based Facial Rigs for Game Engines (Feb 2026)](Tools/2026-08-03-hive-autorig-zoo-tools-joint-facial-2026.md)

**2026-07-13**

- [skinner (AKEric) -- Skin Weight Export/Import para Maya](Tools/2026-07-13-skinner-akeric-skin-export-import.md)
- [ngSkinTools 2 -- Layer-Based Skinning, Ahora Free y Bundled en Maya 2027](Tools/2026-07-13-ngskintools2-maya2027-bundled.md)

**2026-07-06**

- [AniGen — Auto-Rigging con S³ Fields (SIGGRAPH 2026)](Tools/2026-07-06-anigen-siggraph2026-auto-rigging.md)

**2026-06-29**

- [autoRigger (leixingyu) — Herramienta Modular de Auto-Rigging en Python](Tools/2026-06-29-leixingyu-autorigger-modular-rigging-tool.md)
- [DQS Maya Plugin (Guido de Haan) — Nodo skinClusterDq de Producción](Tools/2026-06-29-guidodehaan-dqs-maya-plugin.md)

**2026-06-22**

- [nl_rigging_tools (nickyliux)](Tools/2026-06-22-nl-rigging-tools-nickyliux.md)
- [maya-matrix-autorig (MarcadrienLePape)](Tools/2026-06-22-maya-matrix-autorig-marcadrienlepape.md)
- [Mansur-Rig 3.0 — De licencia cerrada a distribución abierta en GitHub](Tools/2026-06-22-mansur-rig-3.0-open-source.md)

**2026-06-15**

- [Skinner (AKEric) — Skin Export / Import Tools para Maya (Production-grade)](Tools/2026-06-15-skinner-akeric-skin-export-import.md)
- [DEM Bones (Electronic Arts) — SSDR Production Implementation](Tools/2026-06-15-dem-bones-electronicarts-ssdr-production.md)

**2026-06-08**

- [MayaMeshRetarget (yamahigashi) — Retargeting de Deformaciones entre Meshes via RBF](Tools/2026-06-08-yamahigashi-meshretarget-rbf.md)
- [maya-math-nodes (serguei-k) — Librería C++ de Nodos Matemáticos para Maya](Tools/2026-06-08-maya-math-nodes-serguei-k.md)

**2026-06-01**

- [MayaMeshRetarget (yamahigashi) — Retargeting de Mesh con RBF](Tools/2026-06-01-yamahigashi-MayaMeshRetarget-RBF.md)
- [dm2skin — Convertir Delta Mush a Skin Weights (duncanskertchly)](Tools/2026-06-01-dm2skin-delta-mush-to-skin-weights.md)
- [CMT — Chad Vernon Maya Toolkit (chadmv/cmt)](Tools/2026-06-01-cmt-chad-vernon-toolkit.md)

**2026-05-25**

- [maya-skinning-tools (robertjoosten) — Herramientas Interactivas de Skinning Paint](Tools/2026-05-25-robertjoosten-maya-skinning-tools.md)
- [GT Tools (TrevisanGMW) — Colección Completa de Scripts Python para Maya](Tools/2026-05-25-gt-tools-trevisangmw.md)
- [Dual-Quaternion-Skinning-Sample-Codes (brainexcerpts) — Tutorial C++ de DQS](Tools/2026-05-25-brainexcerpts-dqs-sample-codes.md)

**2026-05-18**

- [Skinner (AKEric) — Skin Weight Export/Import para Producción AAA](Tools/2026-05-18-skinner-akeric-skin-weight-tool.md)
- [Maya Math Nodes (Serguei Kalentchouk) — Nodos Matemáticos C++ para Reemplazar Expressions](Tools/2026-05-18-maya-math-nodes-kalentchouk.md)

**2026-05-11**

- [SSDR Maya Python — Smooth Skinning Decomposition with Rigid Bones (dalton-omens)](Tools/2026-05-11-ssdr-maya-python-repo.md)

**2026-05-05**

- [Rigamajig2 — Data-Centric Modular Rigging System](Tools/2026-05-05-rigamajig2.md)
- [ML-Corrective-Deformer-Maya — Deformador Correctivo via Machine Learning](Tools/2026-05-05-ml-corrective-deformer.md)
- [mGear 5.3 — Open-Source Modular Rigging Framework for Maya](Tools/2026-05-05-mgear.md)
- [Mansur-Rig 3.0 — Modular Rig Builder con C++ Node Library](Tools/2026-05-05-mansur-rig.md)
- [FreeformTools (V1Interactive) — Rigging Modular con Reestructuración en Animación](Tools/2026-05-05-freeformtools.md)
- [dpAutoRigSystem — Sistema de Auto-Rigging Modular Open-Source](Tools/2026-05-05-dpAutoRigSystem.md)

## Rigs de referencia

`Rigs/` — 5 archivos


**2026-08-24**

- [MHR — Momentum Human Rig (Meta, facebookresearch, Nov 2025)](Rigs/2026-08-24-mhr-momentum-human-rig-meta.md)

**2026-07-27**

- [SPRig: Self-Supervised Pose-Invariant Auto-Rigging desde Secuencias de Malla](Rigs/2026-07-27-sprig-self-supervised-pose-invariant-rigging-mesh-sequences.md)

**2026-06-22**

- [Ray — Rig de Animation Mentor (Victor Vinyals / DreamWorks)](Rigs/2026-06-22-ray-rig-animation-mentor.md)

**2026-05-05**

- [Noa — ASWF Production Character Rig (AWS / Spanner)](Rigs/2026-05-05-noa-aswf-rig.md)
- [Malcolm 2.0 — AnimSchool Free Maya Rig](Rigs/2026-05-05-animschool-malcolm-rig.md)

## Portfolios de riggers / TDs

`Portfolios/` — 80 archivos


**2026-10-07**

- [Tomás Poveda — Senior Animation TD / Pipeline TD](Portfolios/2026-10-07-tomas-poveda-senior-animation-td-thats-no-moon-ubisoft.md)
- [Nazmi Yazici — Senior Rigging TD (Cinesite / MPC)](Portfolios/2026-10-07-nazmi-yazici-senior-rigging-td-cinesite-mpc-snow-white.md)
- [Mathieu Schmit / CG-WESK — Senior Maya Rigger & Rigging TD](Portfolios/2026-10-07-mathieu-schmit-cgwesk-senior-rigger-tat-productions.md)
- [Martin L'Anton — Senior Rigging TD / Rigging Pipeline TD](Portfolios/2026-10-07-martin-lanton-rigging-pipeline-td-animal-logic-ea.md)

**2026-09-16**

- [Tim Petre — Lead Creature TD (timpetrecg.com)](Portfolios/2026-09-16-tim-petre-creature-td-ilm-method-digital-domain.md)
- [Morgan Loomis — Animation \| Rigging \| Pipeline (morganloomis.com)](Portfolios/2026-09-16-morgan-loomis-rigger-animator-pipeline-mltTools.md)
- [CreatureFX — Lead Creature FX & Rigging Artist (creature-fx.com)](Portfolios/2026-09-16-creaturefx-lead-cfx-td-image-engine-mpc.md)
- [Cole O'Brien — Technical Animator / Rigger (coleobrienart.com)](Portfolios/2026-09-16-cole-obrien-technical-animator-just-cause-rigloo.md)

**2026-09-09**

- [Richard Stubbs — Technical Rigger (Muscle Tools + Modular Python Autorig)](Portfolios/2026-09-09-richard-stubbs-technical-rigger-muscle-autorig.md)
- [Noreen Qureshi — Character TD / Creature FX / UX Designer](Portfolios/2026-09-09-noreen-qureshi-character-td-creature-fx.md)
- [Mr. Paween — Character TD / Rigger (Thailand)](Portfolios/2026-09-09-mrpaween-character-td-rigger-thailand.md)
- [Jordan Dion-Duval — Rigger & Technical Animator](Portfolios/2026-09-09-jordan-dion-duval-rigger-ubisoft.md)

**2026-09-02**

- [Robbie Reid — Senior Rigging TD / Freelance (robbiereid.artstation.com)](Portfolios/2026-09-02-robbie-reid-rigging-td-method-studios.md)
- [Colin Kennedy — Lead Pipeline Engineer (colinkennedy.github.io)](Portfolios/2026-09-02-colin-kennedy-pipeline-td-the-mill.md)
- [Bjørn Blaabjerg Sørensen — CG Generalist / Creature TD (blaabjergb.com)](Portfolios/2026-09-02-bjorn-blaabjerg-creature-td-ilm.md)

**2026-08-26**

- [Scott Woodhams — Senior Technical Artist at EA / Temperance Technical Art](Portfolios/2026-08-26-scott-woodhams-ea-ta-temperancetechart.md)
- [Maurofreecg — Sr Rigger Artist / Mid Technical Animator](Portfolios/2026-08-26-maurofreecg-sr-rigger-battlefield6.md)
- [Kiel Figgins — Animator / Setup Artist at ILM (3dfiggins.com)](Portfolios/2026-08-26-kiel-figgins-3dfiggins-ilm.md)
- [Jairo Alzate — Character Rigger / Technical Artist](Portfolios/2026-08-26-jairo-alzate-character-rigger.md)

**2026-08-19**

- [Nick Van Diem — Zerply + ILM Creature Supervisor](Portfolios/2026-08-19-nick-van-diem-ilm-creature-supervisor.md)
- [Lukas Bilek — Zerply + Blog — Pipeline & Rigging TD](Portfolios/2026-08-19-lukas-bilek-pipeline-td-dreamworks.md)
- [Iker J. de los Mozos — ArtStation Portfolio](Portfolios/2026-08-19-iker-de-los-mozos-wdas-google-xr.md)
- [David Lantos — Zerply + Vimeo — Creature Technical Supervisor DNEG](Portfolios/2026-08-19-david-lantos-dneg-creature-supervisor.md)

**2026-08-12**

- [2026-08-12-valentin-procida-rigger-cfx.md](Portfolios/2026-08-12-valentin-procida-rigger-cfx.md)
- [Sebastián Cisneros — Freelance Rigger & TD (Rigs by Cisneros)](Portfolios/2026-08-12-sebastian-cisneros-rigsbycisneros.md)
- [Nims Bun — Rigging Supervisor at Framestore](Portfolios/2026-08-12-nims-bun-framestore-rigging-supervisor.md)
- [2026-08-12-ian-woskey-ai-facial-rigging-td.md](Portfolios/2026-08-12-ian-woskey-ai-facial-rigging-td.md)

**2026-08-05**

- [Sean Teo — Character TD at PlayStation](Portfolios/2026-08-05-sean-teo-character-td-playstation.md)
- [Drago Avdalovic — CreativeRigs](Portfolios/2026-08-05-drago-avdalovic-creativerigs.md)
- [Benoit Gielly — CTO Stim Studio / bgdev](Portfolios/2026-08-05-benoit-gielly-stim-studio-bgdev.md)
- [Areeba Rikhan — Senior Character TD](Portfolios/2026-08-05-areeba-rikhan-character-td.md)

**2026-07-29**

- [Martin Gunnarsson (Deer Stranger) — Freelance Character Rigger](Portfolios/2026-07-29-martin-gunnarsson-deer-stranger-freelance-rigger.md)
- [J Reinhart — Rigging TD (Framestore)](Portfolios/2026-07-29-j-reinhart-framestore-rigging-td.md)
- [Ernesto Ruiz Velasco — Character TD / Rigging Supervisor (Buck Design)](Portfolios/2026-07-29-ernesto-ruiz-velasco-rigging-supervisor.md)

**2026-07-22**

- [Walt Hyneman — Sr. Creature Technical Director (ILM)](Portfolios/2026-07-22-walt-hyneman-ilm-creature-td.md)
- [Jose Antonio Martin Martin — Character TD / Rigger + Online Educator](Portfolios/2026-07-22-jose-antonio-martin-martin-td-educator.md)
- [Henry Foster (Toadstorm) — Technical Artist / Pipeline TD](Portfolios/2026-07-22-henry-foster-toadstorm-technical-artist.md)
- [Brittany McGrath — Character Technical Director](Portfolios/2026-07-22-brittany-mcgrath-character-td.md)

**2026-07-15**

- [Navin Pinto — Senior Rigging & Simulation TD at Blizzard](Portfolios/2026-07-15-navin-pinto-blizzard-sim-td.md)
- [Nathaniel Scheurer — Technical Art (TGA Graduate)](Portfolios/2026-07-15-nathaniel-scheurer-technical-art.md)
- [François Chancrin — Rigging Supervisor at DNEG](Portfolios/2026-07-15-francois-chancrin-dneg-rigging-supervisor.md)
- [Adien Dendra — Creature TD at ILM Sydney](Portfolios/2026-07-15-adien-dendra-ilm-creature-td.md)

**2026-07-08**

- [Sebastien Camrrubi — Senior CG Character TD (Animal Logic / Netflix)](Portfolios/2026-07-08-sebastien-camrrubi-artstation.md)
- [Marin Petrov — Sr. Character TD Blue Sky Studios / SaaS Co-founder](Portfolios/2026-07-08-marin-petrov-blue-sky-character-td.md)
- [Dorota Sikorska — Sr. Rigging TD / Software Developer (MPC / ML)](Portfolios/2026-07-08-dorota-sikorska-fairydora.md)
- [Ariel Podreider Lenzi — CG Supervisor (Creature) / CFX/Groom Sup TD](Portfolios/2026-07-08-ariel-podreider-lenzi-creature-supervisor.md)

**2026-07-01**

- [Tim Coleman — Lead Character TD / VP Digital Human Studio (zerply.com/tccoleman)](Portfolios/2026-07-01-tim-coleman-zerply-tccoleman.md)
- [Robert Joosten — Pipeline Rigging Supervisor (robertjoosten.github.io)](Portfolios/2026-07-01-robert-joosten-robertjoosten-github-io.md)
- [Michele Trabona — Rigger & Development TD (micheletrabona.com)](Portfolios/2026-07-01-michele-trabona-micheletrabona-com.md)
- [Bram Van Rompuy — Developer / Rigger (zerply.com/bram-van-rompuy + bramvanrompuy.be + gimbalgoats.com)](Portfolios/2026-07-01-bram-van-rompuy-zerply-bramvanrompuy-be.md)

**2026-06-24**

- [Pradeep Kumar Katta](Portfolios/2026-06-24-pradeep-kumar-katta-pcgart.md)
- [Mason Smigel](Portfolios/2026-06-24-mason-smigel-rigamajig.md)
- [Jose Lozano ("Peperig")](Portfolios/2026-06-24-jose-peperig-lozano-cinesite.md)
- [Christopher McCabe](Portfolios/2026-06-24-christopher-mccabe-dreamworks.md)

**2026-06-10**

- [Vittorio Leone — Character Rigger, Feature Animation](Portfolios/2026-06-10-vittorio-leone-feature-animation-rigger.md)
- [Subbu Addanki — Boom Rigs / Hyper Skinning System](Portfolios/2026-06-10-subbu-addanki-boomrigs-hyper-skinning.md)
- [Matthew R. Tucker — Technical Artist Portfolio](Portfolios/2026-06-10-matthew-tucker-tuckertd.md)
- [Assaf Ben Zur — Mansur-Rig (MPC Lead Rigging TD)](Portfolios/2026-06-10-assaf-ben-zur-mansur-rig-mpc.md)

**2026-06-03**

- [Shervin Shahidi — Head of Production Technology, Cinesite (zerply.com/shervin)](Portfolios/2026-06-03-shervin-shahidi-cinesite-td.md)
- [Niels Kleinheinz — Character Rigging / Scripting (kleinhei.nz)](Portfolios/2026-06-03-niels-kleinheinz-character-td.md)
- [Jakub Krompolc — RIG-IT.net (Character Rigs for Games, Animation and VFX)](Portfolios/2026-06-03-jakub-krompolc-rig-it.md)
- [Grant Laker — Lead Rigger / Rigging Supervisor (zerply.com/grant_laker)](Portfolios/2026-06-03-grant-laker-laika-method-studios.md)

**2026-05-27**

- [Ozgur Aydogdu — Character TD, Pixar Animation Studios](Portfolios/2026-05-27-ozgur-aydogdu-pixar-td.md)
- [Markus Daum — Rigging Pipeline TD, Digital Domain](Portfolios/2026-05-27-markus-daum-digital-domain.md)
- [Justin Phillips — Character TD](Portfolios/2026-05-27-justin-phillips-character-td.md)

**2026-05-20**

- [Saurabh Kapoor — saurabhrigtd.com](Portfolios/2026-05-20-saurabh-kapoor-saurabhrigtd.md)
- [Nicky Liu — nickyliu.com ("# Rigging TD")](Portfolios/2026-05-20-nicky-liu-nickyliu.md)
- [Jeremy Ernst — jeremyernst.com (Riot Games / Epic Games / ART Toolkit)](Portfolios/2026-05-20-jeremy-ernst-riot-games-td.md)
- [Chris Lesage — Rigmarole Blog (chrislesage.com / rigmarolestudio.com)](Portfolios/2026-05-20-chris-lesage-rigmarole-blog.md)

**2026-05-13**

- [Joy Johnson — Disney Character Rigging TD / CG Supervisor](Portfolios/2026-05-13-joy-johnson-disney-character-td.md)
- [Hector Abraham Torres — HAT Rigs (Disney/Sony)](Portfolios/2026-05-13-hector-abraham-torres-hat-rigs.md)
- [Bernat Mas — Technical Director, Skydance Animation](Portfolios/2026-05-13-bernat-mas-skydance-td.md)
- [Alexander Richter — TD Academy (Weta FX / Oscar)](Portfolios/2026-05-13-alexander-richter-weta-td.md)

**2026-05-06**

- [Sergi Caballer — Disney Character TD & Rigger](Portfolios/2026-05-06-sergi-caballer.md)
- [Josh Carey — CGJosh](Portfolios/2026-05-06-josh-carey-cgjosh.md)
- [James Dunlop — Animal Logic (GitHub Portfolio)](Portfolios/2026-05-06-james-dunlop-animal-logic.md)
- [Ericka Go — Creature TD (ILM)](Portfolios/2026-05-06-ericka-go-creature-td.md)
- [Carlos Contreras — Mothman TD](Portfolios/2026-05-06-carlos-contreras-mothman-td.md)

**Resúmenes**

- [Portfolio Insights — Laia Peris Research](Portfolios/00-Portfolio-Insights-latest-2026-10-07.md)
- [Portfolio Insights — Laia Peris Research](Portfolios/00-Portfolio-Insights-archivo-hasta-2026-08-26.md)
