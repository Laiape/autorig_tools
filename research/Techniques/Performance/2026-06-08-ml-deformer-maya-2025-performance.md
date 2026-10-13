---
source: https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-F386DC20-6C66-40D7-AD40-2C1B66937A71 | https://www.cgchannel.com/2024/07/maya-2025-2-adds-a-new-ml-deformer/ | https://arxiv.org/html/2406.09783v1
found: 2026-06-08
category: performance
priority: 2
tags: [maya, performance, ML-deformer, neural-network, PCA, deformation-approximation, machine-learning, 2025, interactive]
status: NEW
---

# Maya ML Deformer (2025.2) — Approximación Neural de Deformaciones Complejas

## Descripción
El ML Deformer, introducido en Maya 2025.2 (julio 2024), usa redes neuronales densas (DNN) con compresión PCA para aproximar el output de deformadores complejos en tiempo interactivo. El flujo productivo: entrenar offline el modelo con datos de animación → desplegar la aproximación en sesiones de animación (fast) → conmutar al deformador original para render final. Representa un cambio de paradigma en rendimiento de rig: en lugar de optimizar el deformer, se aprende una aproximación rápida de su output.

## Fundamento matemático / técnico

### Architecture: DNN + PCA Subspace Decomposition

The ML Deformer divides deformation into two components:

**1. Linear component**: handled by standard LBS/blendShape (fast, unchanged)

**2. Non-linear component** (the expensive residual): approximated by DNN

The deformation `d(v, pose)` of vertex v at pose p is split:
```
d(v, pose) = d_linear(v, pose) + d_nonlinear(v, pose)
```

The non-linear part uses **two-level approximation**:

#### Level 1: PCA subspace (global low-frequency deformations)
```
d_pca(pose) = PCA_basis · z(pose)
```
where:
- `PCA_basis` ∈ ℝ^{3V × k} = precomputed PCA eigenvectors of training deformations (k = 50 typical)
- `z(pose)` ∈ ℝ^k = latent code, predicted by the subspace mini-network

Subspace network architecture: small MLP, typically [input_dim → 128 → 64 → k]

#### Level 2: DNN in Cartesian coordinates (local high-frequency deformations)
```
d_highfreq(v, pose) = DNN(pose_encoding, v_neighborhood_features)
```
Architecture options:
- **Lightweight**: [input → 128 → 256 → 128 → 3V_out] with 50 PCA components
- **Deep residual**: 4 blocks with skip connections → [input → 512 → residual_blocks → 3V_out]

The final deformation:
```
d_total(v, pose) = LBS(v, pose) + PCA_basis · z(pose) + DNN_highfreq(v, pose)
```

### Pose Encoding (Input Features)

The pose is encoded as a vector of **Driver Control values** — whatever rig controls move the character. Typically:
- Joint rotations (as quaternions or euler angles)
- Custom attributes (IK blend, stretch values)
- Total: 100-500 dimensional input vector for a hero character

The network learns the mapping: `pose_controls → vertex displacements`.

### Training Workflow

```
1. TRAINING DATA GENERATION
   - Run Pose Generator (randomized control values) + existing keyframed animation
   - For each frame: capture (driver_control_values, target_mesh_vertex_positions)
   - Typically 1000-5000 training poses for a hero character

2. TRAINING
   - Loss: L2 on vertex positions + optional normal consistency term
   - Adam optimizer, ~100 epochs
   - Time: minutes to hours depending on complexity (GPU-accelerated)

3. DEPLOYMENT
   - Switch to ML Deformer during animation session (interactive frame rates)
   - Training Results window: compare accuracy between models
   - Toggle Target Morph to see deviation from source deformer

4. FINAL RENDER
   - Switch back to source deformer (full quality)
   - The ML Deformer is never used for final renders
```

### Performance Characteristics

Expected speedup (from production reports and documentation):
- Simple corrective blendshape stack: 2-5× speedup  
- Complex muscle simulation: 10-30× speedup  
- Full physics-based cloth: 20-50× speedup

ML Deformer runs in **Cached Playback**: after first-pass evaluation, subsequent plays are memory-bound (not compute-bound). So interactive session workflow:
```
Frame 1 (train pass): ML Deformer eval → ~5-10ms per frame
Cached Playback: memory read → <1ms per frame → 130fps+
```

### Known Limitations

1. **Control association**: with many controls (>200), the network may learn spurious correlations between unrelated controls and deformations in distant mesh regions
2. **Extrapolation**: degrades outside the training pose space coverage
3. **Topology**: cannot handle topology-changing deformations (cloth intersections, contact)
4. **Per-mesh**: a separate model is trained per mesh (not shared across a character)

### Related Open-Source Implementations

- **dgovil/MLDeform** (GitHub): earlier open-source Maya ML deformer, Maya 2018+, Python + TensorFlow. Conceptually similar but older architecture.
- **mayjackass/ML-Corrective-Deformer-Maya-Public**: predicts corrective vertex displacements directly from joint pose data. More targeted: joint pose → corrective only (not full deformation).
- **Implementing a Machine Learning Deformer for CG Crowds** (arxiv 2406.09783): production case study from a VFX crowd pipeline — trains per-character ML deformer from mocap, achieves 15× speedup for crowd deformation.

## Implementación en Maya

```python
# Maya ML Deformer - workflow via maya.cmds
import maya.cmds as cmds

# 1. Create ML Deformer node
deformer = cmds.deformer('body_mesh', type='mlDeformer')[0]

# 2. Set up driver controls (what feeds the neural network)
cmds.connectAttr('spine_IK.rx', deformer + '.inputValue[0]')
cmds.connectAttr('arm_L_IK.rx', deformer + '.inputValue[1]')
# ... all rig controls

# 3. Generate training poses using Pose Generator
cmds.mlDeformerPoseGenerator(deformer, 
    numPoses=2000, 
    randomSeed=42,
    useExistingAnimation=True)  # also sample from timeline

# 4. Train
cmds.mlDeformerTrain(deformer, 
    architecture='deep',    # 'lightweight' | 'deep'
    numPCAComponents=50,
    maxEpochs=100,
    learningRate=0.001)

# 5. Toggle evaluation
cmds.setAttr(deformer + '.enabled', True)   # use ML Deformer
cmds.setAttr(deformer + '.enabled', False)  # use source deformer

# 6. Check accuracy
cmds.mlDeformerEvaluateTraining(deformer)
# → prints per-vertex mean error in cm
```

**Maya 2026.1 update**: AI-powered ML Deformer improvements — better extrapolation, reduced control correlation artifacts, and improved convergence speed.

### GPU Evaluation
The ML Deformer runs DNN inference on CPU by default. Maya 2026+ adds GPU-accelerated inference (CUDA), further improving performance for large meshes.

## Comparación con autorig_tools

autorig_tools actualmente se centra en optimizar el rig en sí mismo (matrix nodes, parallel evaluation). ML Deformer es una estrategia complementaria y diferente: no optimiza el rig, sino que aprende una versión rápida de su output. Para Laia, el caso de uso más directo es: personajes con correctives complejos (deltaMush + RBF correctives + blendShapes) cuya simulación es lenta en sesiones de animación de layout. Entrenar un ML Deformer para esos personajes podría dar a los animadores un proxy rápido sin cambiar el rig publicado. La barrera de entrada es baja: es una feature nativa de Maya 2025.2, no requiere código adicional.

## Aplicable directamente

YES — Maya 2025.2+. Si Laia o su studio usa Maya 2025+:
1. Para personajes hero con stack de deformación pesada: entrenar ML Deformer como paso estándar de publicación del rig
2. Integrar `mlDeformerTrain()` en el post-build de autorig_tools como paso opcional
3. El Pose Generator automático + animation sampling elimina la necesidad de crear poses de entrenamiento manualmente
4. Tiempo estimado de setup: 1-2 horas para primer personaje (incluyendo entrenamiento)

## Fuente
- Maya 2025 docs: https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-F386DC20-6C66-40D7-AD40-2C1B66937A71
- CG Channel overview: https://www.cgchannel.com/2024/07/maya-2025-2-adds-a-new-ml-deformer/
- Crowd pipeline case study: https://arxiv.org/html/2406.09783v1
- Open source reference: https://github.com/dgovil/MLDeform
- ML corrective Maya: https://github.com/mayjackass/ML-Corrective-Deformer-Maya-Public
- Maya 2026.1 AI update: https://pixeldojo.ai/industry-news/autodesks-maya-20261-introduces-ai-powered-ml-deformer-to-revolutionize-animation-workflows
