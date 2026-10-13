---
source: https://github.com/VAST-AI-Research/SkinTokens
found: 2026-08-10
category: tool
priority: 3
tags: [maya, rigging, skinning, machine-learning, autoregressive, transformer, LBS, discrete-tokens, vae]
status: NEW
---

# SkinTokens — Learned Compact Representation for Unified Autoregressive Rigging (2026)

## Descripción
SkinTokens es el sucesor de UniRig (SIGGRAPH 2025), publicado por VAST-AI Research en febrero de 2026. Resuelve el problema fundamental de UniRig: los pesos de skinning son valores continuos por vértice difíciles de predecir autorregressivamente. SkinTokens convierte los pesos de skinning en tokens discretos aprendidos via FSQ-CVAE (Finite Scalar Quantized Conditional VAE), unificando la predicción de esqueleto Y pesos en una única secuencia autoregresiva. Mejora un 98-133% la precisión de skinning vs SOTA y un 17-22% la predicción de huesos.

## Fundamento matemático / técnico

### El problema: skinning weights como secuencia discreta

Linear Blend Skinning weights W ∈ ℝᵐˣⁿ are sparse (typically k ≤ 8 influences per vertex) and continuous — values in [0,1] with partition-of-unity. A naive autoregressive model cannot predict real-valued vectors one token at a time without quantization.

**FSQ-CVAE (Finite Scalar Quantized Conditional VAE):**

1. **Encoder:** Given vertex vi and its local geometry context Gᵢ (neighborhood mesh features), encode the skinning weight vector wᵢ ∈ ℝⁿ (n = number of bones) into a latent z ∈ ℝᵈ:
   ```
   z = Enc(wᵢ | Gᵢ)
   ```

2. **Finite Scalar Quantization (FSQ):** Instead of VQ-VAE's codebook lookup (argmin distance to learned centroids), FSQ quantizes each dimension independently to a finite set of integers:
   ```
   zq[k] = round(tanh(z[k]) × L) / L,   L = codebook levels per dim
   ```
   Result: a discrete token tᵢ ∈ {-L,...,L}ᵈ per vertex. No codebook collapse, no EMA updates needed.

3. **Decoder:** Reconstruct skinning weights from quantized token:
   ```
   ŵᵢ = softmax(Dec(tᵢ | Gᵢ))   (enforces partition-of-unity)
   ```

4. **Conditioning on geometry:** The VAE is conditioned on local mesh geometry Gᵢ = {position, normal, local curvature, distance to bones}, so the token encodes not just the weight distribution but also its geometric context.

### Unified Autoregressive Token Sequence

The full rig is predicted as a single token sequence:
```
[BOS] | J₁ J₂ ... Jₙ | [SEP] | t₁ t₂ ... tₘ | [EOS]
```

Where:
- Jᵢ = joint token (position + parent index, as in UniRig)
- tᵢ = skin token for vertex i (FSQ discrete code)
- [SEP] separates skeleton phase from skinning phase

The autoregressive transformer processes this entire sequence causally. The skinning tokens attend to both previous skin tokens AND the full skeleton, enabling skinning to be informed by the complete predicted skeleton structure.

**Why this outperforms UniRig's two-stage approach:** In UniRig, skeleton errors propagate to the skinning stage independently. In TokenRig (SkinTokens framework), the joint-skinning attention in the unified sequence allows the model to jointly reason about topology and deformation.

### Quantitative gains over state-of-the-art
- +98% to +133% skinning accuracy
- +17% to +22% bone prediction accuracy
- 288 GitHub stars as of Aug 2026

## Implementación en Maya

Same external inference pattern as UniRig — run outside Maya via PyTorch, import result as FBX:

```python
# SkinTokens inference (outside Maya)
# python infer.py --input mesh.obj --output rigged.fbx

# In Maya: import and transfer
import maya.cmds as cmds
import maya.api.OpenMaya as om

def import_skintokens_result(fbx_path, target_mesh):
    """Import SkinTokens FBX result and transfer weights to target mesh."""
    # Import FBX
    cmds.file(fbx_path, i=True, type='FBX')
    
    # Find imported skinCluster
    imported_sc = cmds.ls(type='skinCluster')[0]
    
    # Get or create skinCluster on target
    joints = cmds.skinCluster(imported_sc, q=True, influence=True)
    if not cmds.ls(cmds.listHistory(target_mesh), type='skinCluster'):
        target_sc = cmds.skinCluster(joints, target_mesh, tsb=True)[0]
    else:
        target_sc = cmds.ls(cmds.listHistory(target_mesh), type='skinCluster')[0]
    
    # Transfer weights
    cmds.copySkinWeights(
        ss=imported_sc, ds=target_sc,
        noMirror=True,
        surfaceAssociation='closestPoint',
        influenceAssociation=['closestJoint', 'oneToOne']
    )
    return target_sc
```

**HuggingFace model:** VAST-AI/SkinTokens on HuggingFace Hub — model weights downloadable via `huggingface_hub`.

## Comparación con autorig_tools

El sistema de skinning de autorig_tools usa `cmds.skinCluster` con `bindMethod=3` (Geodesic Voxel) + refinamiento manual. SkinTokens proporciona un punto de partida inicial potencialmente superior al heat diffusion automático de Maya, especialmente en zonas difíciles (axilas, ingle, ropa compleja). La combinación óptima: SkinTokens para los pesos iniciales → herramientas de autorig_tools para el refinamiento fino y la exportación. El FSQ-CVAE es conceptualmente similar al sistema de RBF de autorig_tools pero en el espacio de aprendizaje profundo — ambos buscan representaciones compactas de los pesos.

## Aplicable directamente

PARTIAL — Requiere Python 3.11 + PyTorch fuera de Maya y GPU con suficiente VRAM. El overhead de instalación es de 1-2h. Una vez configurado, el flujo (mesh → SkinTokens → FBX → Maya transfer) puede ahorrar 2-4h por personaje en la fase de skinning inicial. Prioridad alta para probar en el próximo personaje hero nuevo.

## Fuente
- GitHub: https://github.com/VAST-AI-Research/SkinTokens
- HuggingFace: https://huggingface.co/VAST-AI/SkinTokens
- Paper: https://arxiv.org/abs/2602.04805
- Project page: https://zjp-shadow.github.io/works/SkinTokens/
