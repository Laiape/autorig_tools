---
source: https://dl.acm.org/doi/10.1145/1276377.1276432 | https://dl.acm.org/doi/10.1145/1360612.1360647 | https://arxiv.org/abs/2501.15279
found: 2026-07-27
category: math
priority: 1
tags: [maya, rigging, math, deformation, cage, barycentric, harmonic-coordinates, green-coordinates, mean-value-coordinates, skinning]
status: NEW
---


# Cage-Based Deformation: Harmonic, Mean Value & Green Coordinates


## Descripción
Las deformaciones basadas en jaula (cage-based) usan una malla de control grosera (cage) para deformar una malla detallada interior. Cada vértice interior se expresa como combinación ponderada de los vértices de la jaula mediante coordenadas generalizadas bariocéntricas. Son una alternativa al skinning esqueletal para deformaciones orgánicas y soft-body. El resultado depende críticamente del tipo de coordenadas usado — cada familia tiene propiedades matemáticas distintas que impactan la calidad de deformación.


## Fundamento matemático / técnico


### Coordenadas bariocéntricas generalizadas
Para un punto interior **p** con jaula de vértices {**v**_j}, las coordenadas φ_j(p) satisfacen:


```
p = Σ_j φ_j(p) · v_j    (reproducción de puntos)
Σ_j φ_j(p) = 1            (partición de unidad)
```


Desiderata para coordenadas de calidad: suavidad (C∞ interior), positividad (φ_j ≥ 0), localidad, y computabilidad eficiente.


---


### 1. Harmonic Coordinates (Joshi et al., SIGGRAPH 2007)
Cada función de peso φ_j satisface la **ecuación de Laplace** dentro de la jaula:


```
∇²φ_j(p) = 0   para todo p interior a la jaula
φ_j(v_k) = δ_jk   (condición de contorno: 1 en vértice j, 0 en el resto)
```


- **Propiedades**: Siempre positivas (máximo en el contorno), C∞ en el interior, no negativas — eliminan el artifact de "pull-through" de MVC.
- **Limitación**: No tienen forma cerrada → requieren resolución numérica de la ecuación de Laplace (FEM, diferencias finitas). Coste O(V log V) con factorización sparse de Cholesky.
- **Discretización**: Se construye la matriz Laplaciana de cotangentes L y se resuelve L·φ = 0 con condiciones de contorno φ|_{cage} = δ_j usando scipy.sparse o libigl.


```python
# Esquema de discretización con scipy
import scipy.sparse as sp
import scipy.sparse.linalg as spla


def solve_harmonic_coords(L_interior, L_boundary, boundary_values):
    """
    L_interior: Laplacian sub-matrix for interior vertices
    L_boundary: Laplacian coupling interior to boundary
    boundary_values: cage vertex values for one cage vertex j
    Returns: φ_j values for all interior vertices
    """
    rhs = -L_boundary @ boundary_values
    phi_interior = spla.spsolve(L_interior, rhs)
    return phi_interior
```


---


### 2. Mean Value Coordinates (Floater, CAGD 2003 — 3D: Ju et al. 2005)
Forma cerrada basada en el **teorema del valor medio de las funciones armónicas**:


Para un punto **p** y un triángulo de jaula con ángulo α_ij subtendido:


```
φ_j(p) = w_j / Σ_k w_k


donde w_j = (tan(α_{j-1}/2) + tan(α_j/2)) / |v_j - p|
```


- `α_j` es el ángulo en **p** del triángulo formado con la arista (v_j, v_{j+1}) de la jaula.
- **Forma vectorial 3D** (Ju et al.): usa ángulos sólidos y normales de cara.
- **Propiedades**: C∞ donde la jaula no tiene aristas, **pueden ser negativas** cerca de concavidades → artefactos de "pull" inverso en jaulas cóncavas o con triángulos de alto cociente de aspecto.
- **Ventaja**: O(V·F_cage) — forma completamente cerrada, sin resolución de sistema lineal. Ideal para evaluación en runtime.


---


### 3. Green Coordinates (Lipman et al., SIGGRAPH 2008)
Extienden la representación para incluir pesos de **cara**, no solo de vértice. Definen dos familias de coordenadas:


```
p' = Σ_j φ_j(p) · v'_j  +  Σ_k ψ_k(p) · s_k · n'_k
```


Donde:
- φ_j: coordenadas de vértice (como antes)
- ψ_k: coordenadas de cara (nuevas)
- s_k: escalar de "escala de cara" en el estado deformado
- n'_k: normal de la cara k deformada


**Propiedad clave**: Las Green Coordinates son **quasi-conformes** — minimizan la distorsión angular (preservan formas locales). Si la deformación de la jaula es conforme, la deformación interior también lo es.


Fórmulas explícitas para triángulos de jaula (Lipman 2008):


```
φ_j(p) = -1/(2π) · Σ_k ∮_{e_k adjacent to j} G_k(p, e_k) ds
ψ_k(p) = 1/(2π) · área del ángulo sólido subtenido por la cara k desde p
```


Donde G_k es la función de Green del triángulo k.


---


### 4. Polynomial 2D Biharmonic Coordinates (Michel et al., arxiv 2501.15279, 2025)
Extensión reciente que usa la **ecuación biharmónica** (∇⁴φ = 0) con jaulas de orden superior:


```
∇⁴φ_j(p) = 0   interior
Condiciones de contorno: valor φ y gradiente ∂φ/∂n en aristas de la jaula
```


- El grado polinomial más alto permite deformaciones más suaves con menos vértices de jaula.
- Relevante para jaulas de alta precisión donde MVC tiene artefactos negativos.


## Implementación en Maya


Maya no tiene soporte nativo para cage-based deformation. Opciones:


**Opción 1 — Python MPxDeformerNode con scipy:**
```python
import maya.api.OpenMaya as om
import numpy as np
from scipy.sparse import linalg


class CageHarmonicDeformer(om.MPxDeformerNode):
    def deform(self, dataBlock, geoIter, matrix, multiIndex):
        # 1. Obtener posiciones de la cage (cage_verts)
        # 2. Resolver coordenadas harmónicas φ (precalculadas en bind time)
        # 3. Por cada vértice interior: nueva_pos = Σ φ_j · cage_verts[j]
        while not geoIter.isDone():
            idx = geoIter.index()
            new_pos = sum(self.phi[idx, j] * cage_verts[j] for j in range(n_cage))
            geoIter.setPosition(om.MPoint(new_pos))
            geoIter.next()
```


**Opción 2 — Usando libigl desde mayapy:**
```python
# Offline: calcular coordenadas y guardar como array
import igl
V_cage, F_cage = load_cage_mesh()
V_detail, F_detail = load_detail_mesh()
# Harmonic coords (libigl)
W = igl.harmonic(V_cage, F_cage, V_detail, 1)  # 1 = Laplacian order
# Guardar W a un archivo numpy para cargarlo en el deformer
np.save('harmonic_weights.npy', W)
```


**Opción 3 — wrapDeformer de Maya (aproximación):**
El `wrapDeformer` nativo usa una aproximación a MVC con K-nearest cage vertices. No es geometricamente correcto pero no requiere scipy.


## Comparación con autorig_tools


El skinning esqueletal de autorig_tools (LBS/DQS vía skinCluster) asume deformaciones rígidas por hueso. Las cage-based deformations son complementarias: permiten deformaciones de cuerpo blando no-skeletal, útiles para elementos como trajes, pelo, bolsas de grasa, y correctives de volumen que no tienen un "joint driver" claro. En el pipeline de Laia, una aplicación directa sería usar una cage Harmonic para corregir el volumen de la barriga/pecho en compresión extrema, donde los correctives RBF tienen discontinuidades.


La limitación práctica es que Maya no los soporta nativamente: requieren o un MPxDeformerNode custom o un paso offline con libigl/scipy. No son GPU-compatibles sin un MPxGPUDeformer C++ adicional.


## Aplicable directamente


PARTIAL — La matemática es directamente implementable en Python como MPxDeformerNode con scipy. El flujo:
1. En bind time: resolver coordenadas harmónicas offline con libigl.igl.harmonic() → guardar array (V_interior × V_cage).
2. En runtime: new_pos = phi_matrix @ cage_positions (operación matricial numpy, ~1ms para mallas medianas).
3. Para runtime GPU-compatible: requeriría portar el paso 2 a C++ MPxGPUDeformer con OpenCL.


El caso de uso MÁS inmediato: usar MVC (forma cerrada, Python puro) como deformer de volumen en zonas de jiggle (papada, barriga) en lugar de simular con nCloth.


## Fuente
- Joshi et al. 2007 "Harmonic coordinates for character articulation": https://dl.acm.org/doi/10.1145/1276377.1276432
- Lipman et al. 2008 "Green Coordinates": https://dl.acm.org/doi/10.1145/1360612.1360647
- Floater 2003 "Mean value coordinates": https://www.sciencedirect.com/science/article/pii/S0167839603000032
- Survey: https://link.springer.com/content/pdf/10.1007/978-94-007-5446-1_3.pdf
- Biharmonic 2025: https://arxiv.org/abs/2501.15279