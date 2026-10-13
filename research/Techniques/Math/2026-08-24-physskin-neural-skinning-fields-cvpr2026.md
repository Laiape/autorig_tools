---
source: https://arxiv.org/abs/2603.23194
found: 2026-08-24
category: math
priority: 1
tags: [maya, python, rigging, math, skinning, neural, cvpr2026, physics]
status: NEW
---

# PhysSkin — Real-Time Generalizable Physics-Based Animation via Self-Supervised Neural Skinning (CVPR 2026 Highlight)

## Descripción
PhysSkin (Lei, Cheng, Li et al., ZJU3DV, CVPR 2026 Highlight) aprende **campos de skinning continuos** — no pesos discretos por vértice — usando un autoencoder neuronal entrenado únicamente con geometrías estáticas y objetivos físicos auto-supervisados. El resultado: un feed-forward que produce deformación físicamente consistente en tiempo real para *cualquier* malla o discretización (tet mesh, superficie, point cloud), sin datos anotados ni bind pose fija. Es el paso lógico después de SkinTokens: en vez de tokens discretos, un campo continuo aprendido con FEM-loss.

## Fundamento matemático / técnico

**Setup — LBS reinterpretado como campos:**
Clásico LBS con B huesos:
```
x'(p) = Σᵢ wᵢ(p) · Tᵢ · p̄     con Σᵢ wᵢ(p) = 1,  wᵢ ≥ 0
```
donde `wᵢ: R³ → R` son los pesos por vértice/punto. PhysSkin trata `wᵢ` como un **campo escalar continuo** aprendido — no un valor discreto por vértice — parametrizado por una red neuronal:
```
w(p; z_shape) : R³ × R^{256×768} → R^B
```
donde `z_shape` es el latente que codifica la geometría (encoder transformer, 256 tokens × 768 dim). Esto lo hace **discretization-agnostic**: la misma red evalúa pesos en cualquier resolución de malla o point cloud sin reentrenar.

**Arquitectura:**
- **Shape Encoder (Transformer):** malla estática → latente 256×768. Aprende una descripción geométrica global.
- **Cross-Attention Field Decoder:** `(punto p, latente z) → w(p) ∈ R^B`. El decoder consulta el latente vía cross-attention por cada punto de query.
- **Handle-driven subspace:** el subespacio de movimiento se define por las transformaciones de los handles (huesos), como en LBS clásico. La novedad no está en el subespacio, sino en cómo se generan los pesos que lo lift a full-space.

**Pérdidas físicas auto-supervisadas (sin datos anotados):**
Tres objetivos que operan directamente sobre el campo aprendido:

1. **Energy minimization (elasticidad):** L_elastic = Σ_p ψ(F(p)), donde F es el gradiente de deformación local y ψ es una densidad de energía tipo Neo-Hookean o ARAP. Se calcula on-the-fly sobre poses sintéticas de los handles.
2. **Spatial smoothness:** L_smooth = ‖∇w(p)‖² integrado sobre el shape — pesos suaves espacialmente para evitar rebanadas.
3. **Orthogonality / partition of unity:** L_pou = (Σᵢ wᵢ(p) − 1)² + ReLU(−wᵢ(p))² — restricciones de LBS válido incrustadas como pérdida.

**Novedades clave del training:**
- **On-the-fly skinning-field normalization:** durante training, cada batch normaliza el campo predicho antes de calcular energías (previene el colapso a wᵢ = 1/B constante).
- **Conflict-aware gradient correction (ConFIG):** cuando los gradientes de L_elastic, L_smooth y L_pou entran en conflicto (producto interno negativo), se proyectan a una dirección común que reduce todas las pérdidas. Es un método formal de gradient surgery, no un ad-hoc λ-tuning.

**Inference:**
Feed-forward puro. Una vez entrenado (150 epochs con el checkpoint publicado, `physskin_rignet_epoch150.pt`), la red aplica `w(p)` a cualquier point cloud N×3 normalizado a [−1,1] en una sola pasada — sin bind pose, sin optimización por-shape.

## Implementación en Maya
- **Dependencies:** PyTorch 2.7.1 (CUDA 11.8), PyTorch Lightning 1.6.4, NumPy 1.26.4, `conflictfree` 0.1.8. Python 3.11.
- **Integración pipeline:** el modelo produce `w(p) ∈ R^B` para cualquier point cloud. Workflow para Maya:
  1. Exportar mesh estática + skeleton canónico (A-pose).
  2. Muestrear vértices del mesh como puntos de query.
  3. Ejecutar PhysSkin inference offline (mayapy no soporta PyTorch nativo — usar Python externo o USD passthrough).
  4. Escribir los pesos resultantes al `skinCluster` vía `MFnSkinCluster.setWeights()` estándar.
- **No hay integración Maya oficial** — es un modelo de investigación. Pero el output es un array de pesos LBS estándar, compatible con `skinCluster` de Maya sin cambios.
- **GPU inference cost:** el paper indica "real-time" — para meshes de personaje típicos (~50k vertices) esperar <100ms por inference en una RTX 4090.

**Snippet conceptual (offline pre-skinning):**
```python
# fuera de Maya
import torch, physskin
model = physskin.load("physskin_rignet_epoch150.pt")
mesh_pts = torch.from_numpy(verts).float().cuda()      # (N, 3), normalizado
z_shape  = model.encoder(mesh_pts.unsqueeze(0))         # (1, 256, 768)
weights  = model.decoder(mesh_pts, z_shape).cpu().numpy()  # (N, B)

# dentro de Maya
skin = cmds.skinCluster(joints, mesh, tsb=True)[0]
mObj = om.MSelectionList(); mObj.add(skin)
sk   = oma.MFnSkinCluster(mObj.getDependNode(0))
sk.setWeights(dagPath, comp, infl_ids, om.MDoubleArray(weights.flatten()), False)
```

## Comparación con autorig_tools
`autorig_tools` tiene un pipeline de skinning basado en heat map / geodesic voxel (bindMethod=3) + refinamiento manual con brushes, con export/import via `skin_data`. PhysSkin llena tres huecos:

1. **Skinning inicial "físicamente correcto"** sin depender del voxelizer de Maya. El heat/voxel actual da resultados razonables en cuerpo pero flojos en axilas/ingle/codos donde la energía elástica es lo que realmente importa.
2. **Bind-pose-agnostic:** SkinTokens y BBW asumen A/T-pose. PhysSkin genera pesos válidos para cualquier pose canónica ya que la red aprende sobre poses sintéticas de handles, no sobre una bind pose específica.
3. **LOD / topology retarget "gratis":** el campo continuo w(p; z_shape) es evaluable en cualquier resolución sin repintar. Ideal para variantes LOD 0→6 (mismo esqueleto, meshes de distinta densidad).

No sustituye el brush workflow — sustituye el paso "smoothBind + fix axila". Encaja como `physskin_preskin()` en el bloque de skinning inicial (equivalente al `voxel_skin_init()` actual).

## Aplicable directamente
**PARTIAL** — la parte de *pesos iniciales físicamente consistentes* es aplicable pero requiere:
- Instalar PyTorch fuera de mayapy (Python 3.11 environment externo).
- Escribir un wrapper `physskin_preskin(mesh, skeleton) → weights_array` que llame al modelo desde CLI o socket.
- Función de import a Maya vía `setWeights` de la API C++ — Laia ya tiene esto en `skin_data`.

Estimación de integración: **4–6h** para el wrapper + testing en un personaje real de autorig_tools. Beneficio esperado: eliminación del ~70% del tiempo de fix manual en axilas/ingle/codos para nuevos personajes, especialmente en variantes LOD.

**Riesgo:** el paper no publica benchmarks side-by-side contra BBW/heat en malla de producción. Es novedoso — validar sobre uno o dos personajes antes de sustituir el bind actual.

## Fuente
- Paper (arxiv): https://arxiv.org/abs/2603.23194
- Project page: https://zju3dv.github.io/PhysSkin/
- Code (GitHub): https://github.com/zju3dv/PhysSkin
- CVPR poster: https://cvpr.thecvf.com/virtual/2026/poster/39227
- Related — **SkinTokens** (2026-08-10 en Drive) — token-based en vez de continuous field.
- Related — **BBW** (2026-06-22 en Drive) — solución offline convex; PhysSkin es la neural counterpart.
