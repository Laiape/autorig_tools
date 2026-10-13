---
source: https://arxiv.org/abs/2606.08043
found: 2026-09-07
category: math
priority: 1
tags: [maya, rigging, facial, facs, blendshapes, auto-rigging, inner-mouth, topology, neural, production, tps]
status: NEW
---

# OmniFaceRig — Pipeline Automático de FACS Facial Rigging con Inner Mouth (arXiv:2606.08043, Jun 2026)

## Descripción
OmniFaceRig (Wang, Ma, Doublestein et al., Jun 2026) es un pipeline end-to-end que convierte una malla 3D estática de superficie pura — sin cavidad oral modelada — en un rig facial FACS completo con hasta 155 blendshapes, dientes/encías/lengua procedurales, y UV/textura re-empaquetada. Soporta humanos, humanoides, y cuadrúpedos (perros/lobos/zorros; gatos/osos/conejos/tigres) sin parámetros manuales, sin templates por-asset y sin setup previo. Tiempo total: 20-30 segundos por asset en una GPU A100. Publica Omni-Bench: 1,000 personajes con GT FACS + inner mouth geometry.

## Fundamento matemático / técnico

### Pipeline: 5 etapas

**Etapa 1 — Riggability Check (VLM+CV hybrid)**
Un VLM (Vision-Language Model) combinado con detector de cara CV vota si el mesh tiene cara riggable y clasifica: human / humanoid / long_muzzle / short_muzzle / not_riggable. Recall ~98% en Omni-Bench.

**Etapa 2 — Face Parsing (segmentation ensemble)**
Ensemble de 3-4 modelos de segmentación facial que votan por región per-vértice (frente, ojos, nariz, boca, mentón, mejillas). La mayoría-de-votos produce una máscara facial robusta incluso con topologías no-humanas.

**Etapa 3 — Dense Keypoint-Driven Template Registration (TPS)**
Un detector de ~200 keypoints faciales empareja el input mesh con el template FACS mediante una Thin-Plate Spline (TPS):

```
T(x) = a + Ax  +  Σᵢ wᵢ · φ(||x − pᵢ||)
```

donde:
- φ(r) = r² log(r)  (función de base radial de TPS)
- pᵢ = keypoints detectados en el input mesh
- wᵢ, a, A = coeficientes que minimizan la energía de doblado (bending energy):

```
E_bend = ∫∫ (∂²T/∂x²)² + 2(∂²T/∂x∂y)² + (∂²T/∂y²)² dx dy
```

Esto da la deformación de mínima curvatura que mapea keypoints del template al input.

**Etapa 4 — Procedural Inner Mouth Construction**
Construcción procedural de cavidad oral:
1. Curva de labios superior/inferior → extrude interior (2-3 rows)
2. Template de dientes/encías/lengua → ajuste al tamaño de boca detectado
3. Collision-aware fitting de dientes con solver contact-point:

```
minimize over pos_teeth:
    E = Σ_v max(0, −sdf(v))²  +  λ · ||pos − nominal_pos||²
```

donde sdf(v) = signed distance field de la malla de cara. Resuelto con L-BFGS, ~50 iteraciones.

**Etapa 5 — Collision-Aware Blendshape Transfer**
155 blendshapes FACS del template transferidos a la topología del input:

1. Para cada vértice v del input: coordenadas baricéntricas (u, v, w) del triángulo más cercano en el template
2. Transfer de deltas:
```
Δ_input(v) = R_local(v) · Δ_template(P(v))
```
donde R_local(v) = rotación del frame tangente local (preserva la dirección del delta relativo a la superficie).

3. Post-corrección de colisiones dientes-cara en blendshapes extremos: mismo solver L-BFGS.

### Dataset Omni-Bench
- 1,000 personajes 3D con GT blendshapes FACS + inner mouth geometry
- Distribución: ~500 human/humanoid, ~250 long-muzzle, ~250 short-muzzle
- Métricas: face detection recall, penetration depth (cm), blendshape transfer error (cm RMS)
- Disponible: https://omnifacerig.github.io/

### Los 155 FACS shapes vs ARKit (52 shapes)
El superset de 155 incluye los 52 ARKit más:
- 40 shapes de micro-expresión (wrinkle zones: nasolabial, crow's feet, forehead)
- 25 shapes de interacción no-lineal (smile+squint ≠ suma lineal)
- 38 shapes de inner mouth (tongue positions, gum exposure, throat)

## Implementación en Maya

El paper no publica código abierto (sólo website y dataset). El output es un blendShape node estándar de Maya con hasta 155 targets:

```python
import maya.cmds as cmds

def export_mesh_for_omniface(mesh_name, output_path):
    """Exporta la malla desde Maya al formato OBJ para OmniFaceRig."""
    cmds.select(mesh_name)
    cmds.file(output_path, force=True, type='OBJexport',
              options='groups=0;ptgroups=0;materials=0;smoothing=1;normals=1',
              exportSelected=True)

def connect_facs_to_rig_controls(bs_node, control_mapping):
    """
    Conecta los 155 FACS shapes a los controles del rig de autorig_tools.
    control_mapping: dict {facs_name: (ctrl, attr)}
    Los 52 ARKit shapes mapean directamente a los controles estándar:
    """
    ARKIT_TO_AUTORIG = {
        'jawOpen':        ('ctrl_jaw',          'translateY'),
        'eyeBlinkLeft':   ('ctrl_eyelid_L',     'rotateX'),
        'eyeBlinkRight':  ('ctrl_eyelid_R',     'rotateX'),
        'mouthSmileLeft': ('ctrl_lip_corner_L', 'translateX'),
        'mouthSmileRight':('ctrl_lip_corner_R', 'translateX'),
        'browInnerUp':    ('ctrl_brow_inner',   'translateY'),
        # ... etc (52 shapes ARKit cubiertos por los controles existentes)
    }
    for facs_name, (ctrl, attr) in ARKIT_TO_AUTORIG.items():
        if cmds.objExists(f'{bs_node}.{facs_name}'):
            cmds.connectAttr(f'{ctrl}.{attr}', f'{bs_node}.{facs_name}')
```

### Integración con el sistema facial de autorig_tools

El pipeline facial de autorig_tools (jaw, eyes, eyelids, brows, teeth, tongue, lips) cubre ~30-40 controles equivalentes a ~40-52 FACS shapes. OmniFaceRig ofrece 155, de los cuales ~100 son relevantes para producción AAA. La integración más directa: usar OmniFaceRig como generador de la **base de blendshapes** y autorig_tools como constructor del **sistema de control** (SDK/RBF, picker, space switching).

## Comparación con autorig_tools

El rig facial de autorig_tools requiere geometría con cavidad oral ya modelada y rigging manual/semi-asistido de cada región. OmniFaceRig resuelve los tres cuellos de botella principales: (1) inner mouth construction procedural desde malla de superficie pura, (2) blendshape basis automático de 155 shapes sin sculpting por artista, y (3) transfer entre topologías distintas. Si el código se publica (esperado Q4 2026 según el patrón de releases de este grupo), podría integrarse como pre-pass de autorig_tools para generar la base de blendshapes faciales, reduciendo el trabajo de sculpting de ~40-80h a ~1-2h de review y corrección por asset.

## Aplicable directamente

PARTIAL — No hay código público aún. Lo aplicable hoy: descargar el dataset Omni-Bench (1,000 personajes con GT FACS + inner mouth) como benchmark para validar la calidad del facial rig de autorig_tools, especialmente en topologías de cuadrúpedos donde la generación manual de rigs faciales es el mayor cuello de botella. Cuando el código esté disponible, la integración más directa es como generador de blendshape basis.

## Fuente
https://arxiv.org/abs/2606.08043
https://arxiv.org/pdf/2606.08043
https://omnifacerig.github.io/
