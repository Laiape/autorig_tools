---
source: https://arxiv.org/abs/2602.12740
found: 2026-07-27
category: rig
priority: 3
tags: [maya, rigging, auto-rigging, neural, machine-learning, pose-invariant, mesh-sequences, skinning, self-supervised, research]
status: NEW
---


# SPRig: Self-Supervised Pose-Invariant Auto-Rigging desde Secuencias de Malla


## Descripción
SPRig (Arxiv 2602.12740, Febrero 2026) propone un sistema de auto-rigging completamente auto-supervisado que aprende a extraer esqueletos y pesos de skinning directamente desde secuencias de mallas animadas (sin ground truth de esqueleto). A diferencia de sistemas anteriores (RigNet, AnyRig, ANIGEN) que requieren mallas en pose neutra o templates predefinidos, SPRig es pose-invariante: puede inferir el esqueleto incluso si la malla de entrada está en pose arbitraria. El resultado es un skinCluster-compatible con el pipeline estándar de Maya.


## Fundamento matemático / técnico


### El problema: pose-dependency en auto-rigging


Los sistemas previos de auto-rigging basados en learning (RigNet 2020, AnyRig 2023) asumen que la malla de entrada está en una pose neutra o A-pose. Esto se debe a que extraen features geométricas (curvatura, distancias geodésicas, volumen local) que cambian con la pose:


```
Problema: feature(mesh_in_pose_A) ≠ feature(mesh_in_rest)
→ El clasificador entrenado en rest-pose falla al ver mallas en pose animada
```


SPRig resuelve esto con **pose normalization vía deformation-aware features**.


### Arquitectura SPRig


```
Input: secuencia de mallas M = {M_t : t=0..T}   (mismo personaje, T frames)
       (no se necesita ground truth de skeleton ni pesos de skinning)


Paso 1: Pose Normalization Network (PNN)
  - Encoder GNN (Graph Neural Network sobre la malla)
  - Extrae features invariantes a la pose de cada vértice
  - Entrenado con self-supervision: predice la transformación que lleva M_t a una pose canónica
  - Output: canonical_feature(v_i) ∈ ℝ^d para cada vértice i


Paso 2: Skeleton Extraction Network (SEN)
  - Opera sobre los canonical features
  - Predice N "joint candidates" (posiciones 3D + jerarquía)
  - Usa attention mechanism para agrupar vértices en segmentos de bone
  - Pérdida de entrenamiento: self-supervised vía skinning reconstruction


Paso 3: Skinning Weight Prediction (SWP)
  - Para cada (vértice, joint) pair: peso de skinning w_ij ∈ [0,1]
  - Restricciones: Σ_j w_ij = 1 (partición de unidad)
  - Sparseidad: K influencias máximas por vértice (K=4 por defecto)
  - Pérdida: minimizar error de reconstrucción de la secuencia completa dada el skeleton


Objetivo de entrenamiento (self-supervised):
  L = Σ_t Σ_i ||M_t[i] - LBS(M_0[i], {T_j(t)}, {w_ij})||²
  
  donde T_j(t) son las transformaciones de joint j en frame t (también predichas)
```


### Diferencia clave con métodos anteriores


| Método | Requiere rest pose | Requiere GT skeleton | Pose-invariant |
|---|---|---|---|
| RigNet (2020) | Sí | No (unsupervised) | No |
| AnyRig (2023) | Sí | No | Parcial |
| ANIGEN (SIGGRAPH 2026) | Sí | No | No |
| SPRig (2026) | **No** | **No** | **Sí** |


### Resultados cuantitativos


Del paper (evaluado en CAPE, AMASS, Mixamo datasets):
- Skeleton topology accuracy: 87.3% joint correctness (vs 79.1% AnyRig)
- Skinning quality (Vertex Error): 4.2mm median error (vs 5.8mm AnyRig)
- Pose-invariant test (mallas en poses extremas): SPRig mantiene accuracy; AnyRig degrada ~30%
- Runtime: ~2s por malla en GPU (inference + skinning prediction)


### Limitaciones


- Entrenado principalmente en humanoides. Para cuadrúpedos/criaturas: requiere fine-tuning.
- El número de joints predichos es limitado por la arquitectura (típicamente 20-35 joints).
- No infiere nombres de joints ni jerarquía semántica (no sabe qué es "hombro" vs "codo").
- Salida es compatible con LBS estándar, no con DQS o técnicas avanzadas.


## Implementación en Maya


El paper no incluye release público de código (a diferencia de ANIGEN). Sin embargo, el pipeline de uso sería:


```python
# Workflow conceptual de integración en autorig_tools (cuando el código esté disponible):
import subprocess
import numpy as np
import maya.cmds as cmds
import maya.api.OpenMaya as om


def sprig_auto_rig(mesh_sequence_paths, output_skeleton_name='sprig_skeleton'):
    """
    Ejecuta SPRig sobre una secuencia de mallas exportadas como OBJ/ABC
    y crea el skinCluster resultante en Maya.
    
    mesh_sequence_paths: lista de paths a OBJ (un por frame)
    """
    # 1. Exportar secuencia de mallas desde Maya a formato SPRig
    # (asumiendo que la red puede procesar OBJ directamente)
    
    # 2. Llamar al modelo SPRig (inference Python/PyTorch):
    result = subprocess.run([
        'python', 'sprig_inference.py',
        '--input', ' '.join(mesh_sequence_paths),
        '--output_json', '/tmp/sprig_result.json'
    ], capture_output=True)
    
    # 3. Parsear resultado
    import json
    with open('/tmp/sprig_result.json') as f:
        rig_data = json.load(f)
    
    # 4. Crear joints en Maya
    joints = []
    for joint_info in rig_data['joints']:
        pos = joint_info['position']
        parent = joint_info['parent']  # -1 = root
        
        if parent == -1:
            j = cmds.joint(position=pos, name=f"{output_skeleton_name}_root")
        else:
            cmds.select(joints[parent])
            j = cmds.joint(position=pos, name=f"{output_skeleton_name}_{joint_info['id']}")
        joints.append(j)
    
    # 5. Aplicar skinning weights
    mesh_name = cmds.ls(sl=True, type='mesh')[0]  # la malla principal
    skin_cluster = cmds.skinCluster(joints, mesh_name, toSelectedBones=True, 
                                     bindMethod=0, skinMethod=0)[0]
    
    # Importar los pesos desde sprig
    weights = np.array(rig_data['weights'])  # shape: (n_verts, n_joints)
    fn_skin = om.MFnSkinCluster(...)  # API para setWeights
    
    return skin_cluster, joints


# Uso alternativo inmediato: 
# SPRig como referencia de pesos para mejorar el heat-diffusion inicial:
# 1. Exportar ABC de simulación o mocap retargeted
# 2. Correr SPRig para obtener pesos de referencia
# 3. Importar pesos como punto de partida y refinar manualmente
```


### Aplicación práctica sin el código de SPRig


Incluso sin el código public del paper, el **concepto** de SPRig es inmediatamente útil para autorig_tools:


1. **Input de referencia**: usar secuencias de ABC (nCloth, Qualoth sim) como "secuencia de entrenamiento" para SSDR/DEM Bones (que ya está en Drive). Filosofía similar a SPRig pero con algoritmos existentes.


2. **Workflow alternativo** (disponible ahora):
   - nCloth sim → ABC sequence → DEM Bones → skinCluster
   - Este pipeline ya está documentado en `2026-06-15-dem-bones-electronicarts-ssdr-production.md` y produce resultados equivalentes para personajes humanoides.


## Comparación con autorig_tools


autorig_tools hace rigging manual: el Technical Director construye el esqueleto manualmente y pinta pesos. SPRig es auto-rigging end-to-end. No reemplaza autorig_tools para producción de calidad AAA, sino que podría complementarlo como:


1. **Generación de pesos de referencia** para acelerar el painting inicial (igual que DEM Bones o dm2skin).
2. **Rigging rápido de assets secundarios** (props, ropa, pelo) que no justifican rig manual.
3. **Auto-rigging de crowd characters** donde los pesos auto-generados son suficientemente buenos.


La limitación clave vs autorig_tools: SPRig no puede capturar la intención artística de un rigger (correctives, extreme pose fidelity, animability). Es una baseline automatizada, no un sustituto.


## Aplicable directamente


NO (código no público aún) / PARTIAL (concepto) — SPRig no tiene repositorio público en Jul 2026. Monitorear https://arxiv.org/abs/2602.12740 para code release. Mientras tanto:
- Usar DEM Bones como alternativa funcional para el mismo workflow.
- El concepto "pose-invariant feature extraction" es útil para mejorar el propio sistema de skin transfer de autorig_tools (usar features invariantes a la pose en lugar de distancias euclidianas en rest-pose).


## Fuente
- Paper: https://arxiv.org/abs/2602.12740
- Paper title: "SPRig: Self-Supervised Pose-Invariant Rigging from Mesh Sequences"
- Comparación ANIGEN (SIGGRAPH 2026): https://arxiv.org/pdf/2602.12740
- DEM Bones (alternativa funcional): https://github.com/electronicarts/dem-bones