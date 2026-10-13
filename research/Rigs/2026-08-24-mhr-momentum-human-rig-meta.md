---
source: https://github.com/facebookresearch/MHR
found: 2026-08-24
category: rig
priority: 3
tags: [maya, python, pytorch, human-rig, meta, parametric, blendshapes]
status: NEW
---

# MHR — Momentum Human Rig (Meta, facebookresearch, Nov 2025)

## Descripción
MHR (`facebookresearch/MHR`, 816 estrellas, Apache 2.0, actualizado noviembre 2025) es el modelo paramétrico full-body de Meta — la respuesta moderna a SMPL/SMPL-X. **Anatómicamente inspirado**, con esqueleto + blendshapes de identidad + blendshapes de pose (correctives) + rig facial FACS — todo diferenciable en PyTorch. Es el output representation de **SAM 3D Body** (foundation model de HMR desde imagen). Para un rigger, el interés no es que sea "otra SMPL" — es que trae un **sistema de correctives con sparse MLP** que es una implementación de referencia moderna para RBF/PSD, y separa cleanly identity / pose / facial / soft-tissue en cuatro capas de parámetros.

## Fundamento matemático / técnico

**Parametrización — cuatro capas ortogonales:**
- **Identity (β ∈ R^45):** 45 coeficientes controlando body shape / head shape / hand shape independientemente. Aplicados como blendshapes lineales sobre la mesh de referencia (rest pose).
- **Pose (θ ∈ R^204):** parámetros de articulación de joints. 204 params sugiere un esqueleto de ~50-60 joints con parametrización redundante (axis-angle o 6D por joint).
- **Facial (ψ ∈ R^72):** 72 weights FACS-style. Blendshapes lineales, no correctives.
- **Pose correctives:** el elemento clave — no son blendshapes lineales indexados por θ. Son un **sparse MLP** que produce Δvertex per pose.

**Pose corrective — sparse MLP (el detalle interesante):**
La arquitectura clásica de correctives PSD (Lewis 2000) usa RBF sobre pose space. MHR usa una MLP pero con activaciones esparcificadas: solo un pequeño subset de neurones activa por pose. Ventaja:
- **Memoria:** un MLP denso para 204→100k vertex offsets sería ~20M params. Sparse: ~1-2M efectivos.
- **Compute:** solo neuronas activas se propagan → 5-10× menos FLOPs por inference que dense MLP.
- **Interpretabilidad:** cada neurona activada corresponde a una "región anatómica sensible a esta pose" — más cerca de RBF que de MLP opaco.

Matemáticamente:
```
Δmesh(θ) = W₂ · TopK(σ(W₁ · θ + b₁), k) + b₂
TopK(z, k) = z con solo los k valores más grandes; el resto = 0
```
Con k << dim(z), es sparse activation. Backprop straight-through — diferenciable end-to-end.

**Hierarchical blendshapes:**
En vez de un solo array flat de 72 FACS blendshapes, MHR usa una jerarquía: blendshapes "primarias" (18-24 shapes) → combinaciones de segundo orden (interacciones entre pares). Reduce el número total de shapes necesarios y captura no-linearidad (una sonrisa + un guiño ≠ suma lineal).

**LOD (7 niveles):**
La mesh viene en LOD 0–6 (mismo esqueleto, distinta densidad). El rig es agnóstico a la LOD — mismos params β, θ, ψ generan la deformación consistente en todas las LODs. **Solución al problema de LOD-consistency que sufren rigs custom.**

**Diferenciabilidad end-to-end:**
Todo el pipeline (β → mesh, θ → pose, ψ → face) es PyTorch autograd-compatible. Esto habilita:
- Fitting inverso: dado un mesh target, resolver β, θ, ψ vía L-BFGS o Adam.
- Training de decoders que produzcan (β, θ, ψ) desde imagen (SAM 3D Body).
- Rigging retargeting como problema de optimización.

## Implementación en Maya

**MHR no es un plugin Maya.** Es PyTorch puro. Pero el flujo hacia Maya es directo:

**Ruta 1 — como target de fitting para el rig custom:**
```python
# Externo a Maya
import mhr, torch
model = mhr.load()
target_mesh = load_scan("actor_scan.obj")

# Fit MHR params al scan
beta, theta = model.fit(target_mesh, iterations=500)   # Adam, ~30s
mhr_pose_verts = model(beta, theta).cpu().numpy()      # (N, 3)

# Retarget a autorig_tools:
# - beta → shape blendshapes del rig autorig
# - theta → joint rotations del skeleton autorig (map de joint names)
export_to_alembic(mhr_pose_verts, "actor_fitted.abc")
```

**Ruta 2 — como reference rig para validar autorig_tools:**
- Correr autorig_tools sobre un asset.
- Correr MHR fit al mismo asset.
- Comparar deformación pose-by-pose. Si autorig_tools produce artefactos que MHR no, es un bug de tus correctives.

**Ruta 3 — replicar la arquitectura sparse MLP en autorig_tools:**
Este es el interés real. La RBF de mgear/autorig hoy es un solver por-pose que se evalúa en runtime. Un sparse MLP:
- Podría reemplazar el RBF con menor memoria y mejor generalización.
- Podría entrenarse offline (sculpts + PSD → training data) y desplegarse como un `MPxDeformerNode` que embeba un pequeño ONNX runtime.
- Trade-off: pierdes la editabilidad interactiva del RBF (artista añade un target y ve el cambio inmediato). Ganas performance y generalización.

**Dependencies para usar MHR:** Python 3.11+, PyTorch, `pymomentum ≥ 0.1.90`, `trimesh ≥ 4.8.3`. Instalación vía pixi, pip, o standalone TorchScript.

## Comparación con autorig_tools
`autorig_tools` es un auto-rigger clásico: skeleton + skinCluster + blendShapes + RBF PSD. MHR es una arquitectura *rig-as-differentiable-function* con separación clean de identity/pose/facial. Puntos donde MHR informa el diseño:

1. **Separación de identity vs pose:** en autorig_tools hoy, el shape del personaje está bakeado al mesh de rest. Cambiar la identity (build variant, LOD ropa distinta) requiere rebuild del rig. MHR muestra la vía "identity params → mesh, pose params → deform" como capas independientes.
2. **Sparse MLP correctives** — arquitectura de referencia para el próximo iteration del RBF PSD.
3. **Hierarchical FACS blendshapes** — el rig facial de autorig_tools tiene una lista flat de shapes. Jerarquizar (primary shapes → interaction shapes) reduce el trabajo de sculpt manual.
4. **LOD consistency:** MHR resuelve el problema con params compartidos. autorig_tools hoy hace LOD como meshes independientes con re-skinning — hay drift. MHR informa la solución "una identity, N meshes evaluadas del mismo param space".

MHR también sirve como **benchmark**: si autorig produce artefactos que MHR no, es una razón para revisar tu implementación.

## Aplicable directamente

**PARTIAL** — el modelo directo no encaja en el pipeline Maya-based, pero hay tres aplicaciones concretas:

1. **Reference para el nuevo sistema de correctives:** estudiar el sparse MLP implementation en `mhr/model/correctives.py` y considerar reemplazar el RBF actual con una versión entrenable. **Timeframe:** research (semana), prototype (mes), integración (2-3 meses).
2. **Fitting-to-scan tool:** wrapper que fittea MHR a un actor scan y genera los blendshapes de identidad para autorig_tools. Estimado: **1-2 días** para el wrapper + testing.
3. **Validación de rig:** batch job que corre autorig_tools + MHR fit sobre el mismo asset y produce un report side-by-side de deformation delta. Detecta artefactos automáticamente. Estimado: **2-3 días**.

**Riesgo:** MHR es research-grade code, no producción. La licencia Apache 2.0 permite uso comercial, pero el modelo tiene ~11 issues abiertos y 2 PRs — no maduro. Usar como referencia arquitectónica, no como dependencia crítica.

**Punto no negociable:** MHR requiere PyTorch fuera de mayapy. Toda integración pasa por un Python externo o un ONNX export.

## Fuente
- Repo: https://github.com/facebookresearch/MHR (816 estrellas, Apache 2.0)
- Paper (arxiv): https://arxiv.org/abs/2511.15586
- Project page: https://facebookresearch.github.io/MHR/
- Hugging Face: https://huggingface.co/papers/2511.15586
- Related — **SkinTokens** (2026-08-10 en Drive) — token-based rigging, arquitectura similar de autoregresive rig.
- Related — **UniRig SIGGRAPH 2025** (2026-08-10 en Drive) — one-model-rig-them-all, motivación similar.
- Related — **SMPL/SMPL-X** — predecessor conceptual; MHR es Meta's take con anatomia + soft tissue split.
