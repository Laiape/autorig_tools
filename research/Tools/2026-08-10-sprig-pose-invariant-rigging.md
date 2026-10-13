---
source: https://arxiv.org/abs/2602.12740
found: 2026-08-10
category: tool
priority: 3
tags: [maya, rigging, machine-learning, skinning, self-supervised, temporal-consistency, pose-invariant, mesh-sequence]
status: NEW
---

# SPRig — Self-Supervised Pose-Invariant Rigging from Dynamic Mesh Sequences (Feb 2026)

## Descripción
SPRig (arxiv 2602.12740) resuelve un problema crítico en auto-rigging: los sistemas existentes (incluido UniRig) asumen una T-pose canónica, pero secuencias de mallas dinámicas (DyMesh, DT4D, simulaciones nCloth capturadas) no tienen pose canónica disponible. Aplicar auto-rigging frame-by-frame produce topologías de esqueleto inconsistentes entre frames. SPRig es un framework de fine-tuning self-supervisado que impone consistencia temporal usando la propia secuencia como señal de supervisión.

## Fundamento matemático / técnico

### El problema: topological inconsistency in per-frame rigging

Given a mesh sequence M = {M₁, M₂, ..., Mₜ} representing the same character in different poses, a per-frame rigger R produces:

```
Rᵢ = R(Mᵢ)  →  (skeleton Sᵢ, weights Wᵢ)
```

The problem: S₁, S₂, ..., Sₜ may have different joint counts, different hierarchy topologies, or same topology but inconsistent joint ordering. This breaks any animation retargeting, blend shape transfer, or temporal interpolation.

### Self-supervised consistency signal

Key insight: **a single animated character has a single canonical rig.** The sequence itself encodes this constraint without any ground-truth rig annotation.

**SPRig framework:**

1. **Anchor frame selection:** Select the frame Mₐ that is "most canonical" (e.g., closest to neutral pose, or user-specified). Run the base rigger to get anchor rig Rₐ = R(Mₐ).

2. **Cross-frame consistency loss:** For each frame Mᵢ, compute a fine-tuned prediction Rᵢ* and enforce:
   ```
   L_consistency = Σᵢ d(Sᵢ*, Sₐ) + λ · ||Wᵢ* - Wₐ||_F
   ```
   where d(S, Sₐ) is a topology-preserving skeleton distance (graph edit distance with structural constraint) and ||·||_F is Frobenius norm on weight matrices (after joint correspondence alignment).

3. **Reconstruction loss:** Each Rᵢ* must still explain the geometry of Mᵢ:
   ```
   L_reconstruct = ||LBS(Sᵢ*, Wᵢ*, Bᵢ) - Vᵢ||²
   ```
   where Bᵢ are the bone transformations from Sᵢ* relative to Sₐ, and Vᵢ are the vertices of Mᵢ.

4. **Fine-tuning:** The pre-trained base model (e.g., UniRig) is fine-tuned on the specific sequence using this combined loss — no extra labeled data needed.

**Joint correspondence alignment:** Before computing the consistency loss, joints from Rᵢ* are matched to joints in Rₐ using bipartite matching (Hungarian algorithm) on joint position distances. This handles cases where the per-frame model finds joints in different orders.

### Why this is novel vs. alternative approaches

- **Not a smoothing post-process:** SPRig modifies the model predictions, not just filters them in output space. This preserves geometric accuracy per-frame while enforcing structural consistency.
- **Not sequence-specific training from scratch:** It fine-tunes an existing model, so it benefits from large-scale pretraining while adapting to the specific sequence.
- **Self-supervised:** No artist-annotated rigs from the sequence needed — the consistency is derived from the assumption that it's the same character.

### Results
- Superior temporal coherence vs. per-frame UniRig/RigNet
- Often improves per-frame static quality as well (the consistency signal acts as regularization)
- Works on DyMesh and DT4D datasets (captured clothing simulations, articulated dynamic objects)

## Implementación en Maya

SPRig is most relevant for workflows where the input is a mesh sequence (Alembic cache) rather than a static T-pose mesh:

```python
# Workflow: Alembic sequence → SPRig → consistent rig → Maya
# Step 1: Export Alembic cache from Maya simulation
import maya.cmds as cmds
cmds.AbcExport(j='-frameRange 1 100 -dataFormat ogawa -file /tmp/sim_sequence.abc')

# Step 2: Run SPRig outside Maya (Python 3.11 + PyTorch)
# python sprig_infer.py --input sim_sequence.abc --anchor_frame 1 --output rigged.fbx

# Step 3: Import result into Maya
cmds.file('rigged.fbx', i=True, type='FBX')

# Step 4: Validate temporal consistency
joints = cmds.ls(type='joint')
print(f"Consistent skeleton: {len(joints)} joints across all frames")
```

**Key use case for production:** nCloth/Marvelous Designer simulations exported as Alembic that need to be converted to LBS skinClusters (e.g., for DEM Bones workflow). SPRig can generate the initial rig consistently across all frames before DEM Bones SSDR extraction.

**GitHub:** https://github.com/WANG-Ruipeng/SPRig

## Comparación con autorig_tools

autorig_tools genera rigs desde poses T estáticas — el caso estándar de producción. SPRig aborda el caso específico de secuencias dinámicas sin T-pose, que aparece en producción cuando: (1) se recibe una simulación de ropa/pelo capturada, (2) se trabaja con mallas escaneadas en diferentes poses, (3) se quiere extraer un rig de una simulación de física para convertirla en skinning GPU-compatible. Complementa el flujo sim→DEM Bones→skinCluster que ya está documentado, añadiendo un paso de rigging consistente previo a DEM Bones.

## Aplicable directamente

PARTIAL — El caso de uso principal es específico: secuencias de mallas dinámicas sin T-pose. Para personajes de producción estándar con T-pose, UniRig o el pipeline actual de autorig_tools son mejores opciones. SPRig es el tool correcto cuando se recibe una simulación nCloth/Qualoth/Marvelous y se necesita un skinCluster GPU-compatible final. Estimar 2-4h de setup para integrar en el pipeline.

## Fuente
- arXiv: https://arxiv.org/abs/2602.12740
- GitHub: https://github.com/WANG-Ruipeng/SPRig
- Relacionado: DEM Bones (EA) para la conversión SSDR posterior
