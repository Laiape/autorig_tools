---
source: https://arxiv.org/abs/2506.14714
found: 2026-08-24
category: math
priority: 1
tags: [maya, python, rigging, math, skinning, voronoi, sparse, eurographics2026]
status: NEW
---

# SkinCells — Sparse Skinning using Voronoi Cells (Eurographics/CGF 2026)

## Descripción
Larionov, Santesteban, Chen, Lin, Herholz, Goldade, Kavan, Roble, Stuyck (2026, Weta/Meta/Utah) proponen un método automático para generar pesos de skinning **con control directo de sparsity** — es decir, especificar de antemano el número máximo de huesos que pueden influenciar cada vértice — sin sacrificar calidad. La motivación: mobile / streaming / crowd, donde `maxInfluences=4` o menos es hard requirement. La idea central: una función implícita de campo de pesos inspirada en diagramas de Voronoi genera regiones "de influencia" limpias por hueso, con transiciones suaves solo en las fronteras.

## Fundamento matemático / técnico

**Setup del problema:**
Dado un mesh de referencia M (A-pose o T-pose) con N vértices y un esqueleto con B huesos, encontrar pesos `wᵢⱼ ∈ [0,1]` tales que:
- Partition of unity: `Σⱼ wᵢⱼ = 1` para todo vértice i.
- Sparsity: `|{j : wᵢⱼ > 0}| ≤ K` (con K típicamente 4 u 8).
- Deformación resultante bajo LBS = plausible bajo poses de test (`x' = Σⱼ wⱼ · Tⱼ · x̄`).
- No self-intersections en la mesh deformada.

Los métodos previos (BBW, heat map, geodesic voxel) o (a) no controlan sparsity directamente y necesitan post-hoc pruning, o (b) producen pesos negativos/ruidosos cerca de axilas/ingle/codos.

**La idea Voronoi — implicit weight field:**
Definir una función de distancia `dⱼ(p)` para cada hueso j (Euclidea, geodesic, o power-diagram con weight per bone) y construir el peso como:
```
wⱼ(p) = softmin(dⱼ(p), τ) / Σₖ softmin(dₖ(p), τ)
softmin(d, τ) = exp(−d/τ)          (partition analógica de Voronoi suavizada)
```
Con τ → 0, `wⱼ(p)` es la función indicatriz de la celda de Voronoi del hueso j (un-hot, hard boundary). Con τ finito, transiciones suaves solo en la vecindad de las fronteras de Voronoi. La sparsity emerge naturalmente: fuera de un radio de influencia, `exp(−d/τ)` es numéricamente cero, así que el vértice solo tiene peso no-cero de huesos "cercanos".

**Control de sparsity K:**
El algoritmo mantiene solo los K menores `dⱼ(p)` para cada vértice — top-K selection — y renormaliza. Como `softmin` decae exponencialmente, esto es un truncamiento con error acotado ≤ `exp(−(d_{K+1} − d_K)/τ)`.

**Distancia — clave del método:**
La distancia debe respetar la geometría del mesh (no Euclidea directa que atraviesa el volumen). SkinCells usa **distancia geodésica sobre el mesh** (heat method o fast marching) modulada por un weight per bone (power diagram), donde los weights se ajustan iterativamente para minimizar deformación anisotrópica bajo poses de test.

**Optimización:**
Los weights `αⱼ` del power diagram se optimizan alternando:
1. Fijar `αⱼ`, calcular pesos LBS `wᵢⱼ` implícitamente.
2. Simular deformación bajo un banco de poses (típicamente 20-50 poses sintéticas del esqueleto).
3. Medir residual: energía elástica local, o distancia al ground-truth (si hay).
4. Actualizar `αⱼ` con L-BFGS o gradient descent.

**Comparativas del paper (mesh humanoide típico):**
- SkinCells con K=4: calidad ≈ BBW con K=∞. BBW pruned a K=4 pierde partition of unity y produce popping.
- SkinCells maxInf=8: mejora sobre heat map/geodesic voxel en axilas y ingle sin post-processing.
- Tiempo de bind: seconds a minutes (offline, no runtime).

## Implementación en Maya

**Ruta directa (Python offline):**
Requiere una library externa que compute geodesic distances y power diagrams. Opciones:
- `libigl` (Python bindings, `igl.heat_geodesic_distances`, `igl.exact_geodesic`).
- `pygeodesic` (fast marching).

**Snippet conceptual:**
```python
import igl, numpy as np, maya.cmds as cmds, maya.api.OpenMaya as om, maya.api.OpenMayaAnim as oma

def skincells_bind(mesh_name, joints, K=4, tau=0.05):
    V, F = mesh_to_arrays(mesh_name)              # V=(N,3), F=(M,3)
    joint_pos = np.array([cmds.xform(j, q=True, ws=True, t=True) for j in joints])

    # Heat geodesic from each joint's closest surface point
    d = np.zeros((len(V), len(joints)))
    for j, jp in enumerate(joint_pos):
        seed = closest_vertex(V, jp)
        d[:, j] = igl.heat_geodesic(V, F, np.array([seed]))

    # Optional: optimize per-bone weights alpha for power diagram
    alpha = optimize_alphas(V, F, joints, poses_test_bank)      # L-BFGS

    # Compute softmin weights with sparsity K
    d_mod = d - alpha[None, :]                    # power-diagram distance
    W = np.exp(-d_mod / tau)
    # top-K selection per vertex
    topK_idx = np.argsort(W, axis=1)[:, -K:]
    W_sparse = np.zeros_like(W)
    np.put_along_axis(W_sparse, topK_idx, np.take_along_axis(W, topK_idx, axis=1), axis=1)
    W_sparse /= W_sparse.sum(axis=1, keepdims=True)

    # Import to Maya skinCluster
    skin = cmds.skinCluster(joints, mesh_name, tsb=True, mi=K)[0]
    write_weights_api(skin, W_sparse)             # via MFnSkinCluster.setWeights
```

**Ruta de integración con Maya existente:**
- Ejecutar el bind offline (Python 3 con libigl fuera de mayapy, o mayapy 2024+ con pip install).
- Escribir pesos vía `MFnSkinCluster.setWeights` — el mismo API que ya usa `skin_data` en autorig_tools.
- El `skinCluster(mi=K)` respetará el max influences declarado.

## Comparación con autorig_tools
`autorig_tools` usa hoy `bindMethod=3` (Geodesic Voxel) o heat map, con `maximumInfluences=8` y luego `prune_and_cap_skin_weights()` para reducir a 4 en LODs. Este flujo tiene dos problemas:
1. **Prune post-hoc rompe partition of unity** — hay que renormalizar y perdemos garantía de deformación matemáticamente consistente.
2. **Axilas/ingle/codos** requieren fix manual en cada personaje nuevo — el voxel bind produce pesos ruidosos con soporte demasiado ancho.

SkinCells sustituye directamente el bind inicial:
- Sparsity **built-in** al método — no hay prune destructivo.
- Voronoi diagram = fronteras limpias entre huesos vecinos — resuelve el ruido en zonas problemáticas.
- Compatible con el `skin_data` export/import existente sin cambios.

## Aplicable directamente
**YES** — es el método más directamente aplicable de esta semana. Plan de implementación:

1. **Hora 0–2:** instalar `libigl` en el Python externo del pipeline (`pip install libigl`). Testear `igl.heat_geodesic()` sobre un mesh de personaje.
2. **Hora 2–6:** portar el pseudocódigo a `autorig_tools/skinning/skincells.py`, con:
   - Función `skincells_bind(mesh, joints, K=4)` — devuelve `(N, B)` array de pesos.
   - Wrapper `apply_skincells_to_skin_cluster(skin_cluster, W)` que usa `MFnSkinCluster.setWeights`.
3. **Hora 6–10:** ajuste de `tau` sobre 2-3 personajes de test — un solo hyperparámetro global, muy manejable.
4. **Hora 10–14:** benchmark side-by-side vs geodesic voxel + prune. Elegir por LOD:
   - LOD 0 (hero): geodesic voxel + BBW post + manual brush.
   - LOD 1-3: SkinCells K=4.
   - LOD 4+: SkinCells K=2.

**Impacto esperado:**
- Reducción del ~50% del tiempo de fix manual en axilas/ingle para nuevos personajes.
- Pesos LOD generados automáticamente — reemplaza el paso "manual redistribution" de LODs bajos.
- Compatible con `skinningMethod=2` (blended DQS/LBS) sin cambios.

**Riesgo:** la performance del bind es "seconds to minutes" por mesh — no es interactivo. Encaja bien como paso batch de post-build.

## Fuente
- Paper (Wiley/CGF): https://onlinelibrary.wiley.com/doi/10.1111/cgf.70381
- Preprint (arxiv): https://arxiv.org/abs/2506.14714 · https://arxiv.org/html/2506.14714
- Video demo: https://www.youtube.com/watch?v=cLnU9qbnSyY
- ResearchGate: https://www.researchgate.net/publication/392766492
- Related — **BBW** (2026-06-22 en Drive) — convex optimization sin sparsity control directo.
- Related — **PhysSkin** (2026-08-24 en Drive) — neural counterpart sin sparsity explícita.
- Related — **SkinTokens** (2026-08-10 en Drive) — token discreto vs field continuo.
