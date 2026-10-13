---
source: https://onlinelibrary.wiley.com/doi/10.1111/cgf.70388
found: 2026-08-24
category: math
priority: 1
tags: [maya, python, rigging, math, muscle, skin, fem, cgf2026, deformation-gradient]
status: NEW
---

# Skeletal-Driven Animation of Anatomical Humans via Neural Deformation Gradients (Nolte et al. 2026)

## Descripción
Nolte, Kemper, Schwanecke & Botsch (Computer Graphics Forum, abril 2026, TU Dortmund + RheinMain) atacan el problema de animar huesos + músculos + piel simultáneamente en tiempo interactivo. La aproximación clásica —simulación FEM completa— es correcta pero demasiado lenta; la aproximación de skinning geométrico —LBS/DQS— es rápida pero produce collapsing joints, volume loss y self-intersections en la anatomía interna. La propuesta: entrenar una red neuronal que predice **gradientes de deformación** (no desplazamientos de vértice) por tetraedro, entrenada con simulaciones FEM de alta calidad. Genera resultados anatómicamente plausibles a >30 fps.

## Fundamento matemático / técnico

**Deformation Gradient F — el objeto que predice la red:**
Para cada tetraedro con vértices `x₁,x₂,x₃,x₄` en pose de referencia y `x'₁,...,x'₄` en pose deformada:
```
F = D_x' · D_x⁻¹      ∈ R^{3×3}
D_x  = [x₂−x₁  x₃−x₁  x₄−x₁]     (matriz 3×3, "edge frame" reference)
D_x' = [x'₂−x'₁  x'₃−x'₁  x'₄−x'₁]  ("edge frame" deformed)
```
F es la Jacobiana local del mapa de deformación φ: R³ → R³. Es lo que mide FEM elasticidad: energía elástica ψ(F), stress = ∂ψ/∂F.

**Por qué predecir F y no desplazamientos:**
1. **Invariancia local** — F es intrínseco al tet, no depende de la traslación global. La red aprende física local, no correlaciones espaciales espurias.
2. **Regularización natural contra element inversion** — se puede añadir una pérdida `det(F) > 0` que rechaza tetraedros invertidos (colapso de joints). Con predicción de vertex displacements no hay una forma trivial de imponer det(F)>0.
3. **Volume deviation control** — pérdida `(det(F) − 1)²` mantiene volumen; imposible imponer directamente sobre desplazamientos sin regularización costosa.
4. **Robustez a mesh resolution** — F es un objeto por-tet, no por-vértice; la reconstrucción por integración de F es una vieja técnica (deformation-gradient reconstruction, Sumner & Popović 2004).

**Reconstrucción de vértices desde F predichos:**
Los `F_e` predichos por elemento no son un mapa consistente por sí solos (los elementos vecinos pueden dar Fs incompatibles). Se resuelve el sistema de Poisson:
```
argmin_{x'}  Σ_e V_e · ‖∇φ_e − F_e‖²    (φ_e = mapa lineal en el tet e)
```
que es un sistema lineal `L · x' = b` con `L` = Laplaciano cotangente de la malla volumétrica. Precomputable en tiempo de bind — inferencia = una sustitución hacia adelante de un factorizador Cholesky pre-armado.

**Training pipeline:**
- Simulaciones FEM ground-truth de alta calidad (StVK o Neo-Hookean, mallas anatómicas con huesos + músculos + piel).
- Input a la red: parámetros del esqueleto (204 model params en el estilo MHR/SMPL).
- Output: F_e para cada tetraedro (una tensor 3×3 por elemento).
- Pérdidas: `L_F = ‖F_pred − F_gt‖²` + `L_det = (det(F) − det(F_gt))²` + regularización de elemento invertido.

**Inference performance:**
- ONNX Runtime — modelo entrenado en PyTorch, exportado a ONNX, ejecutado con OpenMP.
- Poisson solve = pre-factorizado Cholesky sparse, `O(N log N)` sustitución.
- Reported: **interactive frame rates** (30+ fps) para meshes anatómicas de complejidad SMPL-X (~40k vertices piel + músculos internos).
- Bind time (Cholesky factorization) — one-time cost de segundos.

## Implementación en Maya
- **Standalone viewer:** el repo `fabiankemper/NeuralDeformationGradients` es C++ (GCC 12+), viewer independiente. **Sin plugin Maya oficial.**
- **Dependencies:** libzip, ONNX Runtime, OpenMP. Pre-trained models en HuggingFace.
- **Ruta de integración a Maya:**
  1. Escribir un `MPxDeformerNode` en C++ que embeba ONNX Runtime.
  2. Precomputar el Cholesky solve en `compute()` (o offline y almacenar el factor L en un `MDataHandle` estático).
  3. Inputs: `.jointArray` de matrices world del esqueleto (204 params). Outputs: `.outputGeometry` = mesh volumétrica o superficial deformada.
  4. Declaración `MPxNode::setSchedulingType(kParallel)` + `setMPSafe(true)` para no romper Parallel Evaluation.
- **Alternativa práctica sin C++:** ejecutar el viewer standalone como bake — precomputar la deformación para una ventana de tiempo, escribir a un Alembic, importar como `blendShape` targets. Pierdes interactividad pero es 100% Maya-nativo.
- **Consideración:** el paper trabaja con mallas volumétricas (tetrahedra). Un rig Maya típico es solo superficie. Para aplicar a superficie, cortar solo los tets frontera → predecir F solo para tets de piel → Poisson solve en la superficie.

## Comparación con autorig_tools
`autorig_tools` no modela músculos ni deformación anatómica interna; los correctives son PSD/RBF sobre pose del joint que empujan la piel superficial. El paper Nolte cubre un espacio distinto — **muscle + fat + skin coupled dynamics** — que hoy en autorig_tools requeriría:
- Muscle helpers (joints extra + smooth skin) — costoso, ~200-500 nodos extra, pesos manuales.
- BlendShape correctives sculpteados a mano — costo artístico.

Este método sería la vía "correcta" — inferir la deformación anatómica desde una simulación FEM entrenada offline. Complementa perfectamente el rig facial + spine actual: donde ahora hay un RBF de shoulder, podría haber un neural anatomical deformer.

**Encaje en el pipeline:**
- `build_anatomical_shoulder_deformer(mesh, skeleton)` como paso opcional post-`build_body_rig()`.
- Requiere un training set (FEM de músculos) — no algo trivial de producir sin un simulador anatómico (Ziva-like).

## Aplicable directamente
**NO — a corto plazo.** Requiere:
1. Un training set de simulaciones FEM anatómicas (no disponible en el paper; los autores entrenan con su propio dataset TU Dortmund).
2. Implementación C++ MPxDeformer para integración real en Maya.
3. Setup pipeline: exportar pose, inferir, importar.

**SÍ — a medio plazo, como referencia arquitectónica.** El insight de "predecir gradientes de deformación en vez de desplazamientos" es directamente aplicable a los correctives PSD/RBF actuales:
- En vez de aprender `Δvertex(pose)`, aprender `ΔF(pose)` local por triángulo, y reconstruir vía Poisson.
- Beneficio: correctives que preservan volumen automáticamente, no se rompen al escalar el personaje uniformemente, y admiten transfer entre personajes con topología parecida.

Recomendación: **guardar como referencia teórica** — probablemente hueco de 3-6 meses de trabajo antes de que sea prod-ready. Pero conceptualmente es el próximo paso natural del RBF corrective system.

## Fuente
- Paper (Wiley/CGF): https://onlinelibrary.wiley.com/doi/10.1111/cgf.70388
- Preprint: https://cg.cs.tu-dortmund.de/publications/2026-ndg.pdf
- Code (viewer): https://github.com/fabiankemper/NeuralDeformationGradients
- Related — **SSDR / DEM Bones** (2026-06-15 en Drive) — problema inverso: sim → LBS bones.
- Related — **Direct Delta Mush** (2026-06-08 en Drive) — Laplaciano precomputado, mismo espíritu de "O(1) inference con precomputación pesada".
- Prior art matemático — Sumner & Popović 2004, Deformation Transfer for Triangle Meshes.
