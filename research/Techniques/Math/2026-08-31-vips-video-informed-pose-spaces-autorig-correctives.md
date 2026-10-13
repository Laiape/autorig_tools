---
source: https://arxiv.org/abs/2604.17623
found: 2026-08-31
category: math
priority: 1
tags: [maya, rigging, math, PSD, pose-space, RBF, correctives, ML, VAE, auto-rig, video-diffusion]
status: NEW
---

# ViPS: Video-Informed Pose Spaces for Auto-Rigged Meshes (arXiv Apr 2026)

## Descripción
ViPS (Video-informed Pose Spaces) es un framework feedforward publicado en arXiv:2604.17623 (Apr 2026, v3 May 2026) que aprende automáticamente el espacio de poses válidas de un rig articulado destilando priors de movimiento de un modelo de difusión de vídeo preentrenado — sin necesidad de datasets 4D creados por artistas. El problema que resuelve: dado un rig automático (auto-rigged mesh), el espacio de parámetros del rig (ángulos de joint) es enorme y la mayoría de combinaciones produce poses inválidas (hiperextensión, auto-intersección). ViPS aprendte un espacio latente compacto y suave donde todas las muestras son anatómicamente plausibles. Comparable en calidad a métodos entrenados en datos 4D de artistas, pero usa solo priors de vídeo.

## Fundamento matemático / técnico

**Architecture overview:**

```
θ ∈ ℝ^n  (rig joint angles, n=DOF of rig)
    ↓
Encoder E: θ → μ, σ ∈ ℝ^d     (VAE-style, d << n)
    ↓
z ~ N(μ, σ²)  (latent pose code)
    ↓
Decoder D: z → θ̂ ∈ ℝ^n
```

**Training loss:**

```
L = λ_video · L_video(θ̂) + λ_geo · L_geo(θ̂) + λ_KL · D_KL(q(z|θ) || p(z))
```

Where:
- **L_video**: Differentiable rendering loss computed by rendering the skinned mesh S(θ̂) and comparing to frames from video diffusion model V. The video model provides a distribution over plausible motion sequences — no explicit 3D supervision required.
  ```
  L_video = E_{v~V}[||render(S(θ̂)) - v||²]
  ```
- **L_geo**: Differentiable geometric validators applied directly to the skinned mesh:
  - Self-intersection penalty: volume overlap between mesh parts
  - Hyperextension penalty: joint angle limits derived from anatomy priors
  ```
  L_geo = Σ_i max(0, θ_i - θ_max_i)² + Σ_{(j,k)} max(0, -SDF_{jk})²
  ```
- **D_KL**: Kullback-Leibler divergence for smooth latent space (standard VAE term)

**Pose space applications:**

1. **Diverse pose sampling**: Sample z ~ N(0, I), decode to θ̂ → all anatomically valid
2. **IK manifold projection**: Given target end-effector position p*, find:
   ```
   z* = argmin_{z} ||FK(D(z)) - p*||² + ||z||²
   ```
   solved by gradient descent in latent space — much lower dimensional than raw joint space
3. **Temporal coherence for keyframing**: Smooth path in latent space z(t) → smooth pose sequence θ̂(t) free of anatomical violations

**Relationship to PSD/RBF correctives:**
In traditional PSD (Pose Space Deformation), the corrective shapes are centered at manually-placed example poses in the joint angle space ℝ^n. The RBF kernel distances are computed in this raw space. ViPS provides a learned smooth manifold in ℝ^d (d=32-64 in the paper) where:
- Distances between poses are geometrically meaningful (respect anatomy)
- The manifold is smooth → RBF interpolation is better conditioned
- New corrective centers can be placed in latent space z instead of raw angle space

## Implementación en Maya

**Current PSD/RBF workflow in autorig_tools:**
- Artist defines pose examples (θ_1, ..., θ_N) manually
- RBF centers = raw joint angle vectors in ℝ^n
- Corrective weights: w_i(θ) = φ(||θ - θ_i||) / Σ φ(||θ - θ_j||)

**ViPS-informed approach (offline, Python):**
```python
import numpy as np
from scipy.optimize import minimize

# Assume ViPS encoder/decoder available as ONNX models
# (paper does not provide Maya plugin, but models are in PyTorch/ONNX)
import onnxruntime as ort

encoder = ort.InferenceSession("vips_encoder.onnx")
decoder = ort.InferenceSession("vips_decoder.onnx")

def encode_pose(joint_angles: np.ndarray) -> np.ndarray:
    """θ ∈ ℝ^n → z ∈ ℝ^d"""
    mu, log_sigma = encoder.run(None, {"theta": joint_angles[None]})[0:2]
    return mu[0]

def decode_pose(z: np.ndarray) -> np.ndarray:
    """z ∈ ℝ^d → θ ∈ ℝ^n"""
    return decoder.run(None, {"z": z[None]})[0][0]

def ik_latent_projection(target_pos, fk_func, z_init=None):
    """
    Find valid pose (via latent space) that places end-effector near target.
    fk_func: callable(theta) -> end_effector_position
    """
    if z_init is None:
        z_init = np.zeros(64)
    def objective(z):
        theta = decode_pose(z)
        ee_pos = fk_func(theta)
        return np.sum((ee_pos - target_pos)**2) + 0.01 * np.sum(z**2)
    result = minimize(objective, z_init, method='L-BFGS-B')
    return decode_pose(result.x)

# Use encoded pose centers for RBF correctives:
# Instead of manual (θ_i) centers, place centers in latent space
def rbf_weights_latent(z_current, z_centers, kernel='gaussian', width=1.0):
    """Compute RBF weights in latent space instead of joint angle space"""
    dists = np.array([np.linalg.norm(z_current - c) for c in z_centers])
    w = np.exp(-(dists / width)**2)
    return w / w.sum()
```

**Maya integration concept:**
- Run ViPS encoder on current pose every frame (Python node or expression-free C++ MPxNode)
- Use encoded z vector (32-64 floats) as RBF driver instead of raw joint angles
- RBF centers defined in latent space → smaller, better-conditioned RBF matrix

## Comparación con autorig_tools

Laia ya tiene un sistema RBF en autorig_tools (basado en mGear RBF Manager, cubierto en 2026-05-05). El pain point actual: definir manualmente los centros de poses en el espacio de ángulos raw es costoso y el RBF puede volverse inestable cuando dos centros son anatómicamente similares pero numéricamente distantes en ℝ^n. ViPS ofrece: (1) sampling automático de poses válidas para pre-poblar centros de correctives sin que el artista tenga que posar manualmente, y (2) un espacio latente mejor condicionado para la interpolación RBF. El paper es de Apr 2026, el modelo público no está disponible aún como plugin Maya, pero el framework conceptual es directamente adaptable.

## Aplicable directamente

PARTIAL — No hay plugin Maya disponible. La integración práctica requiere: (1) entrenar o usar el encoder ViPS preentrenado con el rig de production específico (~4-8h de entrenamiento GPU), (2) exportar como ONNX, (3) llamar desde un MPxNode C++ o desde Python offline. El concepto más inmediatamente aplicable sin ViPS: usar el espacio latente de un PCA simple sobre las poses de ejemplo existentes como espacio de driver para RBF — reducción de dimensión clásica que mejora la estabilidad ya en 1-2h de implementación.

## Fuente

- arXiv paper: https://arxiv.org/abs/2604.17623
- HTML version (figures, diagrams): https://arxiv.org/html/2604.17623v2
- Project page: https://honglin-c.github.io/vips/
- PDF: https://arxiv.org/pdf/2604.17623
