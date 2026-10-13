---
source: https://github.com/AKEric/skinner
found: 2026-08-24
category: tool
priority: 3
tags: [maya, python, skinning, tool, aaa, production, weights]
status: NEW
---

# Skinner (AKEric) — Skin Weight Export/Import Tool for Maya

## Descripción
`skinner` de Eric Pavey (AKEric, Volition/DeepSilver) es una herramienta de **export/import de skin weights** para Maya, open-source desde febrero 2023, en uso en producción AAA de videojuegos. Cubre lo mismo que `ngSkinTools` cubre para paint pero para la parte de I/O (persistir/restaurar pesos entre versiones del mesh, entre personajes distintos, o entre sesiones): storage estable, mapping robusto entre topologías distintas, y una API con ambos frontend GUI y scripting. Su modelo de datos internos — `SkinChunk` — es más rápido que JSON tradicional para import (por buffers NumPy en vez de parseo).

## Fundamento matemático / técnico

**SkinChunk data model:**
En vez de exportar pesos como JSON (`{vertex_id: {joint_name: weight, ...}, ...}`), skinner exporta como una tupla:
```
SkinChunk = (
    mesh_uv_coords,        # (N, 2) — UV-space signature del mesh
    mesh_world_coords,     # (N, 3) — posición world del vértice en A-pose
    joint_names,           # (B,) lista de nombres
    weights,               # (N, B) numpy array — sparse-compatible
    normalize_method,      # int
    max_influences,        # int
    dual_quaternion_flag,  # bool
    prebind_matrices       # (B, 4, 4) — matriz de bind por joint
)
```

**Ventajas de SkinChunk sobre JSON:**
1. **Import 10-100× más rápido** — `np.load()` de arrays binarios vs `json.loads()` parsing por-vértice.
2. **Mesh matching robusto** — el mapping vértice → weights no depende del índice de vértice (que rota con cada re-mesh), sino de una combinación de UV coords + world coords + normal orientation. Si Laia rehace la topología pero mantiene forma, skinner re-encuentra el mapping.
3. **Cross-mesh transfer:** SkinChunk es transferable a un mesh distinto si sus signatures UV/world son parecidas (basado en closest-point con umbral). Es esencialmente un `copySkinWeights` que persiste y no depende de tener el mesh original en escena.

**Algoritmo de mapping cross-topology:**
Dado source mesh (con SkinChunk) y target mesh (necesita weights):
1. Para cada vértice `t` del target: buscar los K vecinos más cercanos en el source (K-D tree sobre world coords).
2. Barycentric interpolation de weights: `w_t = Σ_k α_k · w_s[k]` con `α_k` = barycentric coords en el triángulo formado por los k vecinos.
3. Renormalize a partition of unity, cap a `max_influences` si es necesario.

**Numpy 1.x / 2.x support (v1.5.1+):**
Maya 2026 ships con NumPy 1.26.4. Otras herramientas requieren NumPy 2.x. Skinner v1.5.1 tiene un shim de compatibility que permite ambos en el mismo pipeline sin conflicts — esto no lo tienen la mayoría de herramientas Maya open-source.

## Implementación en Maya

**Uso básico via CLI (dentro de mayapy o Maya standalone):**

```python
import skinner

# Export
skinner.export_skin('C:/rigs/hero_body.chunk',
                    mesh='hero_body_geo',
                    include_shapes=False,
                    compress=True)

# Import (mismo mesh, mismos joints — restaura exacto)
skinner.import_skin('C:/rigs/hero_body.chunk',
                    mesh='hero_body_geo')

# Import cross-topology (target mesh distinto, mapping por closest-point)
skinner.import_skin('C:/rigs/hero_body.chunk',
                    mesh='hero_body_lod2_geo',
                    method='closest_point',
                    max_distance=0.05)      # 5cm threshold

# Batch mode
for mesh in cmds.ls(type='mesh'):
    if cmds.skinCluster(mesh, query=True):
        skinner.export_skin(f'./chunks/{mesh}.chunk', mesh=mesh)
```

**UI:** el tool trae una GUI PySide2 accesible via `skinner.show_ui()`. Panel con:
- Selector de mesh + export path.
- Modo de import: `exact` / `closest_point` / `closest_vertex` / `uv_space`.
- Cap de max influences opcional.
- Prune de pesos < threshold antes de export.

**Comparado con `deformerWeights` nativo de Maya:**
El comando `deformerWeights` es el estándar Maya para I/O de pesos, pero:
- Solo maneja mesh idéntica (no cross-topology).
- Formato XML (lento en meshes grandes).
- No pre-serializa a numpy.
- No maneja bien joints renombrados.

Skinner supera a `deformerWeights` en los tres puntos.

## Comparación con autorig_tools

`autorig_tools` ya tiene su propio `skin_data` para I/O de pesos. Ventajas de skinner que podrían adoptarse:

1. **Cross-topology mapping** — si `skin_data` hoy asume el mismo mesh, adoptar el approach de skinner (K-NN + barycentric) resuelve LOD retarget sin necesidad de `copySkinWeights` de Maya.
2. **NumPy 1.x/2.x compat shim** — vale la pena adoptar directamente para pipelines mixed (fuente disponible bajo license permissive).
3. **UV+world+normal signature** para mesh matching — más robusto que solo world coords.

Alternativa: mantener `skin_data` como el módulo interno y añadir un adapter `skin_data.import_from_skinner()` que lea `.chunk` files como formato de intercambio con estudios que usen skinner. Best of both worlds.

## Aplicable directamente

**PARTIAL** — dos vías:

1. **Adoptar como reference implementation:** portar la lógica de mapping cross-topology + numpy shim al `skin_data` interno. Estimado: **1-2 días** (leer código, adaptar).
2. **Instalarlo como tool complementario** para el team, sin integrar al core: `pip install skinner` en el mayapy environment, usarlo como export/import general del pipeline. Estimado: **1h** setup + **1-2h** training del equipo.

**Consideración:** el repo es de un solo autor (Eric Pavey), pero está probado en AAA production. Mantenimiento activo (v1.5.1 nov 2025 = Maya 2026 support). License permissive (revisar exacta en LICENSE.md).

**Impacto esperado:**
- Reducción del tiempo de LOD retarget: hoy autorig_tools requiere `copySkinWeights` con el LOD 0 en escena. Con skinner, un `.chunk` persistente permite bind directo a LOD N sin dependencia de LOD 0.
- Compat con NumPy 2.x sin romper Maya 2026 (NumPy 1.26.4 por default).

## Fuente
- Repo: https://github.com/AKEric/skinner
- Releases: https://github.com/AKEric/skinner/releases
- README: https://github.com/AKEric/skinner/blob/main/README.md
- Autodesk community thread: https://forums.autodesk.com/t5/maya-animation-and-rigging-forum/new-skin-weight-import-export-tool-available/td-p/10792517
- Python Inside Maya group: https://groups.google.com/g/python_inside_maya/c/K_ATtyvFrCg
- Related — **MayaMeshRetarget (yamahigashi)** (2026-06-08 en Drive) — cross-topology skin transfer con scipy/RBF. Complementary tool.
- Related — **DEM Bones (EA)** (2026-06-15 en Drive) — para simulación → LBS. Ortogonal al problema de skinner.
