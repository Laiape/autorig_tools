---
source: https://www.ngskintools.com/releases/v2/ | https://www.ngskintools.com/v2/changelog/ | https://www.cgchannel.com/2026/03/autodesk-releases-maya-2027-and-maya-creative-2027/
found: 2026-07-13
category: tool
priority: 3
tags: [maya, python, rigging, skinning, ngskintools, layer-based, mirroring, masking, maya-2027, built-in]
status: NEW
---

# ngSkinTools 2 -- Layer-Based Skinning, Ahora Free y Bundled en Maya 2027

## Descripcion
ngSkinTools 2 es el estandar de la industria para pintado de skin weights con capas (layer-based) en Maya. En mayo 2025 paso a ser gratuito para uso comercial (v2.4.0 elimino el sistema de licencias). En Maya 2027, ngSkinTools esta incluido como plugin nativo en la instalacion base de Maya, introduciendo un workflow de skinning no-destructivo completamente nuevo con masking, mirroring por capa, y controles de brush compatibles con las herramientas de sculpting de Maya. Relevante para autorig_tools: el sistema de capas de ngSkinTools es el mejor complemento disponible para el skin data export/import pipeline.

## Fundamento matematico / tecnico

### Layer-Based Skinning Architecture

Standard Maya skinCluster stores a single flat array of weights per vertex:
```
vertex[i].weights = [w0, w1, w2, ..., wN]  (one weight per influence, all layers merged)
```

ngSkinTools introduces a **layer stack** where each layer stores:
```
Layer structure:
  - influence_weights: dict {joint_name: [w_per_vertex]}
  - opacity: float [0-1] (overall layer blend)
  - mask: [float_per_vertex] (per-vertex layer activation)
  - enabled: bool

Final weight at vertex v for influence j:
  w_final(v, j) = sum over layers L:
    L.mask[v] * L.opacity * L.influence_weights[j][v]
  Normalized to sum=1 across all influences
```

This is analogous to Photoshop layers: each layer adds a deformation contribution, the mask controls WHERE the layer applies, and opacity controls HOW MUCH.

### Why Layer-Based Beats Flat Skinning for Production

**Problem with flat skinCluster:**
- Editing shoulder weights affects everything connected through shoulder influence
- Cannot isolate "base bind skin" vs "muscle bulge correction" vs "cloth wrinkle fix"
- Mirroring requires freezing and rebuilding weights

**With ngSkinTools layers:**
```
Layer 0 (Base):   overall bind skin (most vertices, base deformation)
Layer 1 (Muscle): shoulder/bicep bulge correction (masked to upper arm area)
Layer 2 (Fix):    specific problem vertex region fix (masked to elbow only)

Workflow: edit Layer 1 without touching Layer 0
          disable Layer 2 to see Layer 1 in isolation
          mirror Layer 1 independently from Layers 0 and 2
```

### Mirroring Mathematics

ngSkinTools mirrors weights by:
1. For each vertex v on one side of the rig (e.g., left side):
   - Find corresponding vertex v' on the opposite side (via X-axis reflection or custom mirror mapping)
   - Copy weights from v to v', remapping influence indices: `left_shoulder -> right_shoulder`
2. This can be done per-layer, so only the affected layer is mirrored

**Layer-level mirroring formula:**
```
For each vertex v in LEFT half:
  Find mirror vertex v' (X-mirrored position lookup)
  For each influence j:
    mirror_j = get_mirror_influence(j)  // e.g., l_shoulder -> r_shoulder
    layer[v', mirror_j] = layer[v, j]
```

The mask of each layer is also mirrored independently.

### New Maya 2027 Features (Bundled Plugin)

From CG Channel coverage of Maya 2027 release (March 2026):
- ngSkinTools is bundled as a **native Maya plugin** (no separate install needed)
- Introduces **non-destructive layer-based skinning** as a first-class Maya workflow
- **Masking** per layer: paint areas where each layer is active
- **Per-layer mirroring**: mirror specific correction layers without affecting base skin
- **MMB brush controls**: Middle-mouse drag left/right for brush SIZE, up/down for INTENSITY (matches Maya sculpting tools behavior -- no keyboard modifier needed)
- **Lock influences per layer**: Prevent specific joints from being modified in a layer

### ngSkinTools 2.4.0 (May 2025) -- Free Commercial License

Version 2.4.0 made ngSkinTools completely free for commercial use:
- Removed license key management system
- No activation required, no trial limits
- Compatible with Maya 2025 (and now bundled in Maya 2027)

Previous pricing was ~$50-150/seat -- now $0.

## Implementacion en Maya

**Installation (Maya 2022-2026, before 2027 bundling):**
```
Download from ngskintools.com
Module file: add to Maya modules directory (Documents/maya/modules/)
Or: pip install ngskintools (newer versions support pip)
```

**Maya 2027:** Automatically available as a plugin (load via Plugin Manager if not auto-loaded).

**Basic workflow:**
```python
# The main API is UI-driven, but layers can be accessed via API:
import ngSkinTools2.api as ngst

# Initialize ngSkinTools on a mesh
skin_cluster = 'pSphere1_skinCluster'
layers = ngst.Layers(skin_cluster)

# Create a new layer
base_layer = layers.add(name='Base Skin')
correction_layer = layers.add(name='Elbow Correction')

# Set layer opacity
correction_layer.opacity = 0.8

# Paint is done via Maya paint tool (not API)
# But mask can be set programmatically:
correction_layer.mask.set(values=[0.0, 0.0, 1.0, 1.0, 0.5, ...])  # per-vertex

# Merge all layers to flat skinCluster (for export/delivery)
layers.bake_to_skin_cluster()
```

**Mirror per layer:**
```python
import ngSkinTools2.api as ngst

layers = ngst.Layers('pSphere1_skinCluster')
correction_layer = layers.get('Elbow Correction')

# Mirror this layer only (left -> right)
correction_layer.mirror(axis='x', influences_mirror_mode='name_based')
# name_based: matches l_ prefix to r_ prefix automatically
```

**Export ngSkinTools layer data:**
ngSkinTools stores layer data as custom node attributes on the mesh -- it persists in the Maya scene file. For pipeline transfer, ngSkinTools supports exporting to JSON:
```python
import ngSkinTools2.api as ngst
ngst.export_layers('pSphere1', filepath='skin_layers_export.json')
ngst.import_layers('pSphere2', filepath='skin_layers_export.json')
```

**Integration with autorig_tools post-build:**
```python
def save_ngskin_layers(mesh, filepath):
    """Save ngSkinTools layer data alongside standard skin export."""
    try:
        import ngSkinTools2.api as ngst
        ngst.export_layers(mesh, filepath=filepath)
        print(f"ngSkinTools layers saved: {filepath}")
    except ImportError:
        print("ngSkinTools not installed -- skipping layer export")

def load_ngskin_layers(mesh, filepath):
    """Restore ngSkinTools layer data after rig rebuild."""
    import os
    try:
        import ngSkinTools2.api as ngst
        if os.path.exists(filepath):
            ngst.import_layers(mesh, filepath=filepath)
            print(f"ngSkinTools layers restored: {filepath}")
        else:
            print(f"No layer data found at {filepath}")
    except ImportError:
        print("ngSkinTools not installed -- flat skin weights only")
```

## Comparacion con autorig_tools

`autorig_tools` tiene su propio sistema de skinning tools y skin data export/import. ngSkinTools 2 es complementario, no sustitutivo: el pipeline de build del rig puede seguir usando el sistema propio para el bind y la distribucion de pesos base, pero el skinning artist puede usar ngSkinTools para el refinamiento artistico en capas. El punto de mayor impacto es el **per-layer mirroring**: si el artista trabaja correctives de musculos solo en el lado izquierdo, un mirror por capa los propaga al lado derecho sin perder el trabajo de la capa base. Con Maya 2027 bundling, ngSkinTools pasa a ser un estandar de facto que todos los artistas en el studio ya tendran disponible.

## Aplicable directamente

YES:
1. **Descarga inmediata (free):** Instalar ngSkinTools 2.4.0 en Maya 2022-2026. Es gratis, sin activacion, Maya 2025 compatible.
2. **Anadir layer export al pipeline (2-3h):** Implementar `save_ngskin_layers()` / `load_ngskin_layers()` en el post-build de autorig_tools para que los layers del skinning artist se preserven entre rebuilds del rig.
3. **Prepararse para Maya 2027:** Con el bundling como plugin nativo, los futuros proyectos asumiran que ngSkinTools esta disponible. Documentar en el pipeline que las capas de ngSkinTools son soportadas por autorig_tools.

## Fuente
- https://www.ngskintools.com/releases/v2/ -- release notes ngSkinTools 2
- https://www.ngskintools.com/v2/changelog/ -- changelog completo
- https://apps.autodesk.com/MAYA/en/Detail/Index?id=7170586444225134622 -- Autodesk App Store
- https://www.cgchannel.com/2026/03/autodesk-releases-maya-2027-and-maya-creative-2027/ -- Maya 2027 features
