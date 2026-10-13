---
source: https://arxiv.org/abs/2604.17623
found: 2026-08-10
category: math
priority: 1
tags: [maya, rigging, math, pose-space, video-diffusion, machine-learning, pose-manifold, correctives, interpolation, auto-rigging]
status: NEW
---

# ViPS — Video-Informed Pose Spaces for Auto-Rigged Meshes (Apr 2026)

## Descripción
ViPS (Video-informed Pose Spaces, arxiv 2604.17623) es un framework que descubre la distribución latente de articulaciones válidas para mallas auto-rigeadas, destilando priors de movimiento de un modelo de difusión de video preentrenado. El resultado es un "espacio de pose" — un manifold navegable de formas deformadas que representa el rango de poses plausibles para un personaje. Publicado en abril 2026 por Columbia University, U. Toronto, Adobe Research y Cambridge. Altamente relevante conceptualmente para sistemas de correctives y PSD avanzados.

## Fundamento matemático / técnico

### The pose manifold problem

An auto-rigged character has joint angles θ ∈ ℝʲ (j joints × degrees of freedom). Not all θ are "valid" poses — the feasible set is constrained by:
- Joint limits (anatomical constraints)
- Self-intersection avoidance
- Physical plausibility (humans don't do impossible stretches)

These constraints define a **pose manifold M ⊂ ℝʲ**: a lower-dimensional submanifold of plausible poses embedded in the full joint angle space.

**Traditional PSD / Pose Space Deformation** samples this manifold manually (artists sculpt corrective shapes at specific poses). **ViPS learns M automatically from video data.**

### Video Diffusion Prior Distillation

Video diffusion models (trained on internet video) implicitly encode p(motion | character) — they've learned what kinds of deformations look natural for articulated characters. ViPS distills this prior into the pose space.

**Key mathematical machinery — Score Distillation Sampling (SDS):**

Given a video diffusion model with score function ∇ₓ log p(x), SDS computes a gradient that pushes rendered images of the character toward the natural image manifold:

```
∇_θ L_SDS = E_t[w(t)(ε̂_φ(xₜ; y, t) - ε)] · ∂render(θ)/∂θ
```

Where:
- θ = pose parameters (joint angles)
- x = rendered image of character in pose θ
- ε̂_φ = noise prediction from video diffusion model
- y = conditioning (e.g., "a character walking")
- ε = added noise
- render(θ) = differentiable renderer (NVDiffrast or similar)

The gradient flows: video diffusion model → rendered image → differentiable renderer → joint angles θ. This creates a supervision signal for "what joint angle distributions look natural" without any motion capture data.

### Pose Space as Learned Manifold

ViPS parameterizes the pose manifold as a latent space of a variational autoencoder:

```
Encoder: θ → z ∈ ℝᵈ  (d << j, typically d = 8-16)
Decoder: z → θ̂ ∈ ℝʲ

Training: L = ||θ - θ̂||² + β · KL(q(z|θ) || N(0,I)) + λ · L_SDS
```

The SDS loss forces the latent space to correspond to plausible video-like motions. The KL term ensures the latent space is smooth and interpolatable.

**Applications enabled by the pose manifold:**

1. **Manifold-constrained editing:** Move a character along M → always looks natural. Constrain animator's pose exploration to plausible region.

2. **Smooth pose-space interpolation:** Interpolate between poses A and B along the geodesic in the learned manifold, not a straight line in joint angle space. Avoids unnatural intermediate poses.

3. **Corrective shape generation:** For PSD, the manifold defines which poses need correctives — the boundary of the manifold corresponds to extreme (correctable) poses. Auto-generate corrective shapes at manifold boundaries.

4. **Pose-guided video synthesis:** Given a target pose, synthesize a video of the character reaching that pose via the manifold-constrained path.

### Connection to existing PSD math

The ViPS manifold is conceptually related to the pose space in traditional PSD:
- Traditional PSD: manual artist-defined samples in ℝʲ → RBF interpolation
- ViPS: learned manifold M ⊂ ℝʲ → smooth VAE interpolation
- The RBF kernel functions (Gaussian, multiquadric) can be interpreted as local approximations to the manifold metric
- The bandwidth parameter σ in RBF corresponds to the "width" of the manifold in pose space

## Implementación en Maya

ViPS is not directly deployable in Maya today — it requires video diffusion model inference (multi-GPU) and a differentiable renderer. However, the conceptual outputs are Maya-compatible:

```python
# Conceptual: ViPS outputs a set of N pose samples on the manifold
# These can be directly used as PSD pose samples in Maya

def load_vips_pose_samples(vips_output_json, rig_namespace=''):
    """Load ViPS-generated pose samples as Maya animation keys."""
    import json, maya.cmds as cmds
    
    with open(vips_output_json) as f:
        poses = json.load(f)  # List of {joint_name: [rx, ry, rz]} dicts
    
    for frame, pose in enumerate(poses, start=1):
        cmds.currentTime(frame)
        for joint, rotation in pose.items():
            full_name = f'{rig_namespace}:{joint}' if rig_namespace else joint
            if cmds.objExists(full_name):
                cmds.setAttr(f'{full_name}.rotate', *rotation)
    
    print(f"Loaded {len(poses)} pose samples as keyframes 1-{len(poses)}")
    # Artist can then sculpt correctives at extreme frames
```

**Integration pathway:** ViPS poses → Maya keyframes → artist selects extreme poses → sculpt correctives → RBF/SDK setup. Replaces the "manual pose exploration" step in corrective setup.

**Related paper:** ViP-Rig (arxiv 2607.27982, July 2026) extends this to visual-prompted controllable rigging — the user provides a reference image and the system generates a consistent rig.

## Comparación con autorig_tools

El sistema de correctives de autorig_tools usa RBF/SDK con poses definidas manualmente por el artista. ViPS cambia fundamentalmente de dónde vienen esas poses: en lugar de que el artista pruebe poses hasta encontrar las problemáticas, el manifold de poses de ViPS identifica automáticamente las zonas extremas que necesitan correctives. La fórmula de SDS aplicada a rigs es análoga matemáticamente al sistema de Riemannian geodesics que ya está en el archivo de agosto — ambos buscan el camino "más natural" entre poses en un espacio de rotaciones con métrica no-Euclidiana.

## Aplicable directamente

NO — ViPS requiere video diffusion models (multi-GPU, horas de inferencia) no disponibles en un pipeline Maya estándar. Sin embargo, el **concepto de manifold de poses** es inmediatamente aplicable como framework mental: cuando se definen poses para correctives RBF, en lugar de escoger poses arbitrarias, escoger poses en la "frontera" del rango de movimiento real del personaje (los extremos que el animador usará en producción). Formaliza el proceso intuitivo ya existente en autorig_tools. Seguir el paper para entender en qué zonas del espacio de poses se concentra la mayor parte del movimiento natural.

## Fuente
- arXiv: https://arxiv.org/abs/2604.17623
- Project page: https://honglin-c.github.io/vips/
- Relacionado: ViP-Rig https://arxiv.org/abs/2607.27982 (julio 2026)
- Relacionado: SPRig https://arxiv.org/abs/2602.12740 (temporal consistency)
