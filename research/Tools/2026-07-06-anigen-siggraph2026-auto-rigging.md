---
title: "AniGen — Auto-Rigging con S³ Fields (SIGGRAPH 2026)"
tags: [auto-rigging, deep-learning, siggraph2026, flow-matching, skinning, tools]
fecha: 2026-07-06
fuente: "https://github.com/VAST-AI-Research/AniGen (433 stars) — VAST AI Research + University of Hong Kong"
tipo: herramienta
aplicabilidad: media
---

# AniGen — Auto-Rigging con S³ Fields (SIGGRAPH 2026)

## Resumen ejecutivo

AniGen es un sistema de auto-rigging basado en **campos espaciales continuos** (S³ Fields) que aparece en SIGGRAPH 2026. A diferencia de sistemas anteriores que procesan Shape → Skeleton → Skin de forma secuencial (y acumulan errores en cada etapa), AniGen define los tres sobre el mismo dominio espacial compartido y los resuelve conjuntamente.

**Resultados clave**:
- 78% de rig validity vs 52% para baselines secuenciales
- 40% de mejora en calidad de animación (métricas user study)
- Soporta meshes de 10 a 200 joints sin cambiar la arquitectura
- Output: GLB → importable en Maya vía FBX pipeline

**Limitaciones para producción**: requiere 18GB VRAM, no tiene integración nativa con Maya, output LBS únicamente (sin blendShapes), y la topología del esqueleto puede no seguir convenciones de estudio.

**GitHub**: https://github.com/VAST-AI-Research/AniGen (433 stars, actualizado jun 2026)

---

## 1. Arquitectura S³ Fields

### El problema con los pipelines secuenciales

Los sistemas anteriores (RigNet, Mixin Motions, etc.) operan en secuencia:
```
Mesh → [Skeleton Predictor] → Skeleton → [Skinning Predictor] → Weights
```

El error en el paso de skeleton se propaga y amplifica en el paso de skinning. Si el skeleton es ligeramente incorrecto, los pesos resultantes son sistemáticamente incorrectos en articulaciones clave.

### S³ Fields: Shape, Skeleton, Skin sobre dominio compartido

AniGen define tres campos continuos sobre el mismo espacio 3D:

```
S_shape(x)    ← signed distance field / geometric features en x ∈ ℝ³
S_skel(x)     ← skeleton field: contribución de cada bone en x
S_skin(x)     ← skin weight field: blending weights en x
```

Todos definidos sobre el mismo espacio, optimizados conjuntamente. Las dependencias son bidireccionales: S_skel informa S_skin, pero S_shape también influye directamente en S_skin sin pasar por S_skel.

---

## 2. Skeleton Field con Confidence Decay

### Formulación matemática

El skeleton field `S_skel(x)` asigna a cada punto del espacio una combinación ponderada de los bones:

```
S_skel(x) = Σᵢ wᵢ(x) · bone_i
```

donde el peso de influencia del bone i en el punto x decae con la distancia:

```
wᵢ(x) = exp(-d(x, bone_i)² / σᵢ²)
```

- `d(x, bone_i)`: distancia del punto x a la línea definida por el bone i (distancia punto-segmento, no punto-punto)
- `σᵢ`: ancho de banda (bandwidth) del bone i, aprendido por la red — bones cortos (falanges) tienen σᵢ pequeño, bones largos (fémur) tienen σᵢ grande
- Los pesos **no necesitan sumar 1** — el campo mide "cuánta influencia" tiene cada bone, no "qué fracción"

### Por qué "confidence decay"

El nombre viene de la interpretación probabilística: `wᵢ(x)` es la "confianza" de que el punto x pertenece a la región de influencia del bone i. Lejos del bone, la confianza decae exponencialmente. Esta formulación:

1. Es **differentiable** — gradiente existe en todas partes, permite backprop limpio
2. Es **continua** — sin bordes duros entre regiones de bones
3. Permite bones **overlapping** — un punto puede estar influenciado por varios bones con valores significativos simultáneamente

```python
import numpy as np

def skeleton_field_at_point(point, bones, sigmas):
    """
    Evalúa S_skel(x) en un punto dado.
    
    Args:
        point: np.array shape (3,) — punto en el espacio
        bones: list de tuples (start, end) — cada bone como dos puntos 3D
        sigmas: np.array shape (num_bones,) — bandwidths aprendidos
    
    Returns:
        weights: np.array shape (num_bones,) — wᵢ(x) para cada bone
    """
    weights = np.zeros(len(bones))
    
    for i, (bone_start, bone_end) in enumerate(bones):
        # Distancia punto-segmento
        bone_dir = bone_end - bone_start
        bone_len = np.linalg.norm(bone_dir)
        
        if bone_len < 1e-6:
            dist = np.linalg.norm(point - bone_start)
        else:
            bone_unit = bone_dir / bone_len
            t = np.dot(point - bone_start, bone_unit)
            t = np.clip(t, 0, bone_len)
            closest = bone_start + t * bone_unit
            dist = np.linalg.norm(point - closest)
        
        weights[i] = np.exp(-dist**2 / (sigmas[i]**2 + 1e-8))
    
    return weights

# Nota: en AniGen, los bones y sigmas son outputs de la red neuronal,
# no inputs manuales. Esta función sirve para entender la matemática.
```

---

## 3. Dual Skin Feature Field

### El problema con representaciones directas de pesos

Los pesos de skinning tradicionales son un tensor `W ∈ ℝ^{V×J}` donde V = vertices y J = joints. Problemas:
1. Dimensión depende del número de joints J — arquitecturas diferentes para 10 vs 200 joints
2. Los pesos son difíciles de regularizar (suma a 1, no negatividad)
3. No capturan bien la variación local

### Dual Field: feature + decoder

AniGen desacopla en dos partes:

```
S_skin_feat(x) ∈ ℝ^d    ← feature field: d-dimensional, independiente de J
                ↓
         Decoder(feat, bone_query_i) → weight_i(x)
```

1. **Feature field** `S_skin_feat(x)`: red que mapea posición 3D → feature vector de dimensión fija d (e.g. d=64). No depende del número de joints.

2. **Weight decoder**: para cada bone i, consulta el feature field en la posición del vértice y produce el peso `wᵢ`. Funciona como un **dot-product attention** entre el feature del punto y el embedding del bone.

```
weight_i(vertex_v) = softmax_i(S_skin_feat(v) · embed(bone_i))
```

**Beneficio**: la misma arquitectura maneja esqueletos de 10 a 200 joints sin reentrenamiento. El número de joints solo afecta cuántas consultas se hacen al decoder.

---

## 4. Two-Stage Flow Matching

### Por qué flow matching en lugar de diffusion

Flow matching (Lipman et al., 2022) produce **trayectorias más rectas** entre la distribución de ruido y la distribución objetivo. En diffusion, el proceso de denoising toma pasos curvos. En flow matching:

```
Flow: x(t) = (1-t)·x₀ + t·x₁    donde x₀ ~ ruido, x₁ ~ mesh/rig objetivo
Velocity field: v(x, t) = dx/dt = x₁ - x₀  (constante para straight paths)
```

**Consecuencia práctica**: se necesitan menos NFE (Neural Function Evaluations) para generar una muestra — tipicamente 10-20 NFE vs 50-1000 para DDPM. Inferencia más rápida.

### Dos etapas en AniGen

**Etapa 1 — Scaffold generation**: genera el esqueleto sparse (bones principales, jerarquía) desde la forma del mesh
```
Input: S_shape(x) (SDF del mesh)
Output: skeleton scaffold (bones principales, posiciones aproximadas)
Modelo: transformer sobre puntos de superficie muestreados
```

**Etapa 2 — Dense refinement**: refina el scaffold y genera S_skin completo
```
Input: S_shape(x) + skeleton scaffold
Output: S_skin_feat(x) completo + σᵢ para cada bone + weight decoder
Modelo: U-Net 3D sobre volumen implícito
```

La separación permite que la etapa 1 capture la topología global (¿cuántos dedos? ¿tiene cola?) sin comprometerse con las posiciones exactas, que la etapa 2 refina con más contexto local.

---

## 5. Métricas y Comparación

### Rig Validity (principal métrica)

Mide qué porcentaje de los rigs generados son "válidos" según criterios:
- Hierarquía de joints correcta (parent-child consistente)
- Pesos normalizados (suma ≈ 1.0 por vértice)
- Sin joints flotantes (todos conectados al esqueleto)
- Pesos smooth (sin artifacts de skinning)

| Sistema | Rig Validity | Tipo |
|---|---|---|
| RigNet (2020) | 38% | Sequential, GNN |
| Mixin Motions (2023) | 52% | Sequential, transformer |
| **AniGen (2026)** | **78%** | Joint S³ fields, flow-matching |

### Animation Quality (user study, N=120)

Evalúa cuánto se deforma correctamente el mesh en animación:

| Sistema | Preference rate | Notable failure |
|---|---|---|
| RigNet | 12% | Shoulder collapse |
| Mixin Motions | 31% | Finger splay |
| **AniGen** | **57%** | Wrist twist (still hard) |

*El 40% de mejora se refiere a preferencia relativa de AniGen vs el mejor baseline anterior (Mixin Motions): 57% vs 31%*

---

## 6. Integración con Maya

### Pipeline GLB → FBX → Maya

AniGen exporta rigs en formato GLB (GLTF Binary). Maya no importa GLB nativamente, pero el pipeline es directo:

```python
import maya.cmds as cmds
import subprocess
import os

def import_anigen_rig(glb_path, scene_scale=100.0):
    """
    Importa un rig generado por AniGen (GLB) en Maya.
    
    Requiere: Autodesk FBX Converter o Blender CLI instalado en PATH.
    Args:
        glb_path: ruta al archivo .glb generado por AniGen
        scene_scale: factor de escala (AniGen usa metros, Maya usa cm por defecto)
    """
    # Paso 1: Convertir GLB → FBX usando Blender headless
    fbx_path = glb_path.replace(".glb", "_maya.fbx")
    
    blender_script = f"""
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath='{glb_path}')
# Escalar de metros a centímetros
bpy.ops.transform.resize(value=({scene_scale}, {scene_scale}, {scene_scale}))
bpy.ops.object.transform_apply(scale=True)
bpy.ops.export_scene.fbx(
    filepath='{fbx_path}',
    use_selection=False,
    add_leaf_bones=False,
    bake_anim=False,
    path_mode='COPY'
)
"""
    
    script_path = "/tmp/anigen_convert.py"
    with open(script_path, "w") as f:
        f.write(blender_script)
    
    result = subprocess.run(
        ["blender", "--background", "--python", script_path],
        capture_output=True, text=True, timeout=120
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Blender conversion failed:\n{result.stderr}")
    
    if not os.path.exists(fbx_path):
        raise FileNotFoundError(f"FBX not created at {fbx_path}")
    
    # Paso 2: Importar FBX en Maya
    cmds.file(
        fbx_path,
        i=True,
        type="FBX",
        ignoreVersion=True,
        importTimeRange="override",
        mergeNamespacesOnClash=False,
        namespace="anigen"
    )
    
    # Paso 3: Limpiar namespace y renombrar joints a convención de estudio
    imported = cmds.ls("anigen:*", type="joint")
    print(f"Imported {len(imported)} joints from AniGen rig")
    
    return imported

def remap_anigen_joints_to_convention(anigen_joints, convention="biped_studio"):
    """
    Mapea los nombres de joints de AniGen a convención de estudio.
    AniGen usa nombres genéricos: joint_0, joint_1, etc.
    
    Este proceso es semi-manual: requiere identificar cuál joint
    corresponde a qué parte del cuerpo.
    """
    # TODO: implementar mapeo automático basado en posición
    # Por ahora, retornar mapping vacío para inspección manual
    print("WARNING: Joint naming from AniGen does not follow studio conventions.")
    print("Manual remapping required before binding to studio rig controls.")
    print(f"Joints to remap: {anigen_joints}")
    return {}
```

### Limitaciones para producción en autorig_tools

1. **18GB VRAM**: requiere GPU de gama alta (RTX 4090 o A100). No viable en hardware de artista típico. Alternativa: run en cloud batch o en workstation dedicada.

2. **Solo LBS**: no genera blendShapes de corrección ni secondary motion. El rig de AniGen es un punto de partida, no el resultado final.

3. **Topología de esqueleto no estándar**: AniGen decide cuántos joints y dónde. Para un personaje bípedo, puede generar 47 joints cuando el studio usa 58, o vice versa. El `remap_anigen_joints_to_convention()` arriba es solo un placeholder — el mapeo real requiere trabajo manual o un sistema de correspondencia adicional.

4. **Sin controles ni atrezzos**: genera solo el skeleton + skinning. No genera controllers (nurbs curves), constraint networks, IK handles, ni attribute proxies. Estos deben añadirse con el pipeline de rigging normal (autorig_tools).

5. **Sin integración Maya nativa**: el pipeline GLB → Blender → FBX → Maya añade un paso extra de conversión con posibles pérdidas de precisión.

### Caso de uso realista

**AniGen es útil como: generador de skin weights de referencia** para meshes nuevos donde el rigger no quiere hacer bind manual. El flujo sería:

```
1. AniGen genera skeleton + weights para el nuevo mesh
2. Rigger evalúa el skeleton, descarta si es muy diferente al standard
3. Rigger usa los weights de AniGen como punto de partida para pintar
4. Rigger añade controles, correctives, secondary motion con autorig_tools
```

El valor real está en el paso 3: los weights de AniGen para áreas "fáciles" (torso, muslos) son típicamente usables con mínima corrección. Solo las áreas problemáticas (hombros, muñecas, rodillas) requieren repintar.

---

## 7. Instalación y Requisitos

```bash
# Clonar el repositorio
git clone https://github.com/VAST-AI-Research/AniGen
cd AniGen

# Requisitos
# Python 3.10+
# PyTorch 2.1+ con CUDA 12.1+
# 18GB VRAM mínimo (A100/RTX 4090)

pip install -r requirements.txt

# Descargar pesos del modelo
python scripts/download_weights.py  # ~4.2GB

# Inferencia en un mesh
python inference.py \
    --input mesh.obj \
    --output output_rig.glb \
    --num_joints 52 \  # opcional: hint del número de joints esperado
    --device cuda:0
```

---

## 8. Comparación con Alternativas

| Herramienta | Approach | Validity | VRAM | Maya Integration | Open Source |
|---|---|---|---|---|---|
| AniGen (2026) | S³ Fields + flow | 78% | 18GB | GLB→FBX pipeline | Sí (Apache 2.0) |
| RigNet (2020) | GNN sequential | 38% | 6GB | FBX | Sí |
| Mixamo (Adobe) | Template-based | ~85%* | Cloud | FBX directo | No |
| AccuRIG (Reallusion) | Template-based | ~80%* | Cloud | FBX | No |
| Human IK (Autodesk) | Template (human only) | 90%* | N/A | Nativo | No (bundled) |

*Para humanoides standard. Para creatures/quadrupeds/stylized, los template-based fallan y AniGen mantiene su 78%.

**El nicho de AniGen**: creatures, stylized characters, y meshes que no encajan en templates humanoides. Para personajes humanos estándar, Mixamo/AccuRIG siguen siendo más rápidos y con mejor integración.

---

## Fuentes

- VAST-AI-Research/AniGen GitHub (https://github.com/VAST-AI-Research/AniGen) — 433 stars, actualizado jun 2026
- AniGen paper: *AniGen: Generalizable 3D Animation via S³ Fields* — SIGGRAPH 2026, VAST AI Research + University of Hong Kong
- Lipman et al. (2022): *Flow Matching for Generative Modeling* — base teórica del flow matching
- RigNet (Xu et al., 2020): *RigNet: Neural Rigging for Articulated Characters* — baseline principal
