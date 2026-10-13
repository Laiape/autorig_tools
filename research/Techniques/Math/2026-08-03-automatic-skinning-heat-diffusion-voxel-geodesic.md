---
source: https://people.csail.mit.edu/ibaran/papers/2007-SIGGRAPH-Pinocchio.pdf
found: 2026-08-03
category: math
priority: 1
tags: [maya, rigging, math, skinning, heat-diffusion, geodesic, automatic-weights, bind]
status: NEW
---


# Automatic Skinning Weight Computation — Heat Diffusion vs Geodesic Voxel


## Descripción
La matemática de cómo Maya calcula los pesos automáticos de skinning al hacer "Bind Skin" (método Heat Map), y por qué falla en geometrías con topología compleja (cuencas de ojo profundas, axilas, ropa). El método alternativo de Geodesic Voxel (disponible como método de bind en Maya 2017+) resuelve estos casos. Complementa los archivos BBW (2026-06-22) y CoR (2026-06-15) con la comprensión de cómo se generan los pesos iniciales antes de cualquier post-proceso.


## Fundamento matemático / técnico


### Heat Diffusion Method — Baran & Popovic 2007 (Maya default "Heat Map")


**Core idea**: Use heat diffusion physics to propagate bone influence from bones outward through the mesh.


For each bone b, compute a scalar heat field h_b(v) at every vertex v by solving the heat equation:


    (L + c·M) · h_b = c·M · H_b


Where:
- L: cotangent Laplacian matrix of the mesh (sparse, n×n for n vertices)
  - L_ij = -½(cot α_ij + cot β_ij)  for adjacent vertices i,j
  - L_ii = -Σⱼ L_ij
- M: diagonal mass matrix, M_ii = Voronoi area of vertex i
- c: falloff constant (user-controllable as "bind distance")
- H_b: initial heat vector — 1.0 for vertices near bone b, 0 elsewhere


**Physics intuition**: bone b is a "heat source". Heat diffuses through the mesh surface. Vertices close to (or on the same side as) bone b get high heat values.


**Normalization** (to enforce partition-of-unity Σ_b w_b(v) = 1):


    w_b(v) = h_b(v) / Σ_b' h_b'(v)


**Cotangent Laplacian computation:**
```python
# For edge (i,j), α and β are the angles opposite to that edge
# in the two triangles sharing the edge
import numpy as np
from scipy.sparse import lil_matrix


def build_cotangent_laplacian(vertices, faces):
    n = len(vertices)
    L = lil_matrix((n, n))
    for face in faces:
        i, j, k = face
        # Compute cotangents for all 3 angles
        for (a, b, c) in [(i,j,k),(j,k,i),(k,i,j)]:
            va = vertices[b] - vertices[a]
            vb = vertices[c] - vertices[a]
            cos_angle = np.dot(va, vb)
            sin_angle = np.linalg.norm(np.cross(va, vb))
            cot = cos_angle / (sin_angle + 1e-10)
            L[b,c] -= cot/2
            L[c,b] -= cot/2
            L[b,b] += cot/2
            L[c,c] += cot/2
    return L.tocsr()
```


**Heat map failure modes:**
- **Thin geometry** (eyelids, fingers): heat "leaks" through the thin mesh surface — vertex on front of eyelid gets heat from both top and bottom bones
- **Concavities** (armpits, groin): heat from bone on one side reaches vertices on the other side via short diffusion paths through concave space
- **Geodesic vs Euclidean distances**: heat diffusion follows mesh topology (geodesic), but the default falloff uses bone-vertex distance in 3D space (Euclidean) → mismatch in complex shapes


### Geodesic Voxel Binding — Maya 2017+


**Core idea**: Voxelize the character volume, then compute geodesic distances INSIDE the volume (not on surface) from each bone to each vertex.


**Algorithm:**
1. Voxelize the mesh at resolution N³ (e.g., 256³)
2. For each bone, mark voxels containing the bone as seeds
3. Run a 3D BFS/Dijkstra from seeds through the INTERIOR voxels (not surface)
4. The geodesic distance d_b(v) for each vertex v = distance to nearest bone b voxel, measured through interior
5. Convert distances to weights: w_b(v) = f(d_b(v)) / Σ_b' f(d_b'(v))
   where f is typically f(d) = exp(-σ·d) or f(d) = max(0, 1 - d/R)


**Key advantage over Heat Map**: Interior geodesic distances cannot "leak" through thin surfaces because the path stays inside the volume. An armpit vertex has a long interior path to the chest bone, even if the Euclidean distance is small.


**Maya implementation:**
In Maya's Bind Skin dialog:
- `Bind Method: Geodesic Voxel` (since 2017)
- `Resolution`: voxel grid size (higher = more accurate but slower)
- `Falloff Rate`: controls how sharply influence decreases with distance


```python
# Maya Python: bind with Geodesic Voxel
cmds.skinCluster(
    joints, mesh,
    bindMethod=3,        # 3 = Geodesic Voxel (0=closest, 1=heat, 2=distance)
    resolution=1024,     # voxel resolution
    falloff=0.2,         # falloff rate
    toSelectedBones=True,
    maximumInfluences=4,
    normalizeWeights=1
)
```


### Comparison: Heat Map vs Geodesic Voxel vs BBW


| Method | Geodesic? | Volume-aware | Bounded ≥0? | Speed | Best for |
|--------|-----------|--------------|-------------|-------|----------|
| Heat Map | Surface | No | Yes | Fast | Simple topology |
| Geodesic Voxel | Volume | Yes | Yes | Medium | Complex topology |
| BBW (Jacobson 2011) | Surface | Partial | Yes (convex) | Slow | Offline, best quality |
| Manual painting | - | Manual | Manual | - | Hero assets |


### Laplacian Smoothing as Post-Process


After any automatic binding, a Laplacian smoothing pass reduces weight noise:


    w_i^{k+1} = (1-α)·w_i^k + α · (1/|N_i|) Σ_{j ∈ N_i} w_j^k


where N_i is the 1-ring neighborhood of vertex i, and α ∈ [0,1] controls smoothing strength.


Maya's "Smooth Skin Weights" operation applies this iteratively. The same operation underlies Delta Mush.


```python
def laplacian_smooth_weights(weights, adjacency, iterations=3, alpha=0.5):
    """
    weights: (n_vertices, n_joints) array
    adjacency: list of neighbor lists per vertex
    """
    w = weights.copy().astype(float)
    for _ in range(iterations):
        w_new = w.copy()
        for i, neighbors in enumerate(adjacency):
            if neighbors:
                avg = w[neighbors].mean(axis=0)
                w_new[i] = (1-alpha)*w[i] + alpha*avg
        # Renormalize
        row_sums = w_new.sum(axis=1, keepdims=True)
        w_new /= np.maximum(row_sums, 1e-10)
        w = w_new
    return w
```


## Implementación en Maya


### Querying which method was used:
```python
skin = cmds.ls(type='skinCluster')[0]
# bindMethod: 0=closest, 1=heat, 2=distance, 3=geodesicVoxel
bind_method = cmds.getAttr(f'{skin}.bindMethod')
print({0:'closest', 1:'heat', 2:'distance', 3:'geodesicVoxel'}[bind_method])
```


### Inspecting and fixing problematic weight regions:
```python
from maya.api import OpenMaya as om


def find_weight_leakage(skin_cluster, threshold=0.05):
    """Find vertices with unexpected influence from distant bones."""
    sel = om.MSelectionList()
    sel.add(skin_cluster)
    fn_skin = om.MFnSkinCluster(sel.getDependNode(0))
    # ... iterate influences and flag unexpected non-zero weights
```


## Comparación con autorig_tools


autorig_tools probablemente usa Heat Map por defecto (el método histórico de Maya). Para personajes con geometría compleja (ropa superpuesta, axilas profundas, dedos de pie), cambiar a Geodesic Voxel en la función `bind_skin()` de autorig_tools mejoraría significativamente los pesos iniciales. El coste computacional es mayor (~5-10× más lento en el bind inicial) pero se paga una sola vez y reduce el tiempo manual de peso-painting posterior. El entendimiento de la fórmula cotangente del Laplaciano también es útil para entender por qué `deltaMush` produce los resultados que produce (misma base matemática).


## Aplicable directamente


**YES** — Cambiar el `bindMethod=3` (Geodesic Voxel) en la función de skinning de autorig_tools para personajes hero con geometría compleja. Para personajes simples, Heat Map sigue siendo suficiente. Implementar como parámetro: `bind_skin(mesh, joints, method='geodesic_voxel', resolution=512)`. Tiempo: 1 hora para añadir el parámetro y documentarlo.


## Fuente
- Baran & Popovic 2007 (Pinocchio/heat diffusion): https://people.csail.mit.edu/ibaran/papers/2007-SIGGRAPH-Pinocchio.pdf
- Jacobson et al. 2011 (BBW, ya cubierto): https://igl.ethz.ch/projects/bbw/
- Maya Geodesic Voxel docs: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-7665A291-FAA7-44C0-BDEB-A6C83482116C
- Cotangent Laplacian reference: Sorkine et al. 2004 (Laplacian Surface Editing, ya cubierto 2026-06-08)