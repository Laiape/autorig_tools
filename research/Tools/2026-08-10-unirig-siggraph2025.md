---
source: https://github.com/VAST-AI-Research/UniRig
found: 2026-08-10
category: tool
priority: 3
tags: [maya, rigging, autorig, machine-learning, siggraph, skeleton, skinning, transformer, python]
status: NEW
---

# UniRig — One Model to Rig Them All (SIGGRAPH 2025)

## Descripción
UniRig es un sistema de auto-rigging basado en Transformers presentado en SIGGRAPH 2025 por VAST-AI Research. A diferencia de sistemas anteriores que trabajan por categoría de asset (humanos, cuadrúpedos, objetos), UniRig usa un único modelo autoregresivo para generar esqueletos y pesos de skinning para cualquier tipo de malla 3D — humanos, animales y objetos inanimados. Es el primer sistema publicado que demuestra generalización cross-category a escala SIGGRAPH.

## Fundamento matemático / técnico

### Stage 1: Skeleton Prediction via Skeleton Tree Tokenization

The skeleton hierarchy is encoded as a sequence of tokens representing the tree structure. Each joint is tokenized as a tuple `(parent_idx, position_xyz, joint_name_embedding)`, serialized in BFS order. A GPT-style autoregressive transformer predicts the next joint token given all previous ones:

```
p(J₁, J₂, ..., Jₙ) = ∏ᵢ p(Jᵢ | J₁, ..., Jᵢ₋₁, M)
```

where M is the mesh embedding (point cloud processed via PointNet++ or similar). The tree topology is implicit in the parent index of each token — no separate graph decoder is needed.

**Skeleton Tree Tokenization** encodes:
- Joint positions in local coordinates (quantized to discrete vocabulary)
- Parent index as integer token
- Depth in tree for positional encoding

The autoregressive process enforces valid tree structure by masking invalid parent indices at each step.

### Stage 2: Skinning Prediction via Bone-Point Cross Attention

Given the predicted skeleton J = {j₁, ..., jₙ} and mesh vertices V = {v₁, ..., vₘ}, skinning weights W ∈ ℝᵐˣⁿ are predicted via cross-attention:

```
Attention(Q, K, V) where:
  Q = vertex features (from mesh encoder)
  K = bone features (from skeleton encoder)
  V = bone features
```

Output attention weights are interpreted directly as normalized skinning weights per vertex, with softmax ensuring partition-of-unity (∑ⱼ wᵢⱼ = 1 for each vertex i).

**Bone-Point Cross Attention** key insight: rather than computing per-bone radial basis functions (as in heat diffusion), the model learns arbitrary weight distributions conditioned on local geometry context — including topology, curvature, and semantic region.

### Quantitative Results

- **215% improvement** in rigging accuracy on challenging cross-category datasets
- **194% improvement** in motion accuracy vs prior SOTA
- Input formats: .obj, .fbx, .glb, .vrm
- Output: LBS skinning weights compatible with standard animation pipelines

## Implementación en Maya

UniRig outputs FBX with skeleton + skinning data. Integration in Maya pipeline:

```python
# Example pipeline: UniRig output → Maya skinCluster
# 1. Run UniRig inference (outside Maya, PyTorch required)
import subprocess
subprocess.run(['python', 'infer.py', '--input', 'char.obj', '--output', 'char_rigged.fbx'])

# 2. Import in Maya
import maya.cmds as cmds
cmds.file('char_rigged.fbx', i=True, type='FBX', ignoreVersion=True)

# 3. Transfer weights to original mesh if topology differs
cmds.copySkinWeights(
    sourceSkin='unirig_skinCluster',
    destinationSkin='original_skinCluster',
    noMirror=True,
    surfaceAssociation='closestPoint',
    influenceAssociation=['closestJoint', 'oneToOne']
)
```

**Requirements:** Python 3.11, PyTorch ≥ 2.3.1, CUDA GPU (8GB+ VRAM). Cannot run inside Maya's `mayapy` directly — external inference then import.

**Star count / activity:** 1,700+ stars, last updated June 2026.

## Comparación con autorig_tools

autorig_tools genera esqueletos y weights mediante lógica de rigging determinista (reglas de colocación de joints, heat diffusion via `bindSkin`). UniRig hace esto mediante un transformer autoregresivo: no hay reglas explícitas, sino un modelo entrenado en millones de assets. El resultado de UniRig es un punto de partida que requiere refinamiento manual — especialmente para personajes hero donde los pesos automáticos nunca son perfectos. La integración más valiosa sería usar UniRig como **paso de prototipado rápido** para nuevos personajes, luego refinar los weights con las herramientas de autorig_tools.

## Aplicable directamente

PARTIAL — UniRig requiere Python 3.11 + PyTorch fuera de Maya. No integrable en el pipeline Maya-nativo de forma directa, pero sí como paso previo offline. El workflow viable es: mesh → UniRig (FBX) → import Maya → `copySkinWeights` al mesh original → refinamiento con autorig_tools. Ahorra el paso de bind y weighted initial guess, que puede suponer 1-2h en personajes complejos.

## Fuente
- Repositorio principal: https://github.com/VAST-AI-Research/UniRig
- Paper SIGGRAPH 2025: buscar "UniRig: One Model to Rig Them All" en dl.acm.org
- Demo: https://vast-ai-research.github.io/UniRig/ (si disponible)
