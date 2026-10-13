---
source: https://www.mdpi.com/2227-7390/11/5/1131 | https://arxiv.org/abs/2303.13395
found: 2026-07-27
category: math
priority: 1
tags: [maya, rigging, math, quaternion, interpolation, riemannian, so3, geodesic, frechet-mean, log-euclidean, blending, correctives, rbf]
status: NEW
---


# Interpolación Geodésica en SO(3): Media de Fréchet y Log-Euclidean Blending


## Descripción
SLERP interpola correctamente entre DOS quaterniones siguiendo el arco geodésico en S³. Pero cuando se necesita la media ponderada de N rotaciones (p.ej. para correctives RBF con múltiples poses-driver, o para interpolar en espacio de rotación con muchos targets), SLERP aplicado secuencialmente no da la media geométrica correcta — es dependiente del orden de aplicación. La media de Fréchet en SO(3) y la aproximación Log-Euclidean dan la media correcta e invariante al orden, y forman la base matemática para interpolación robusta de rotaciones en sistemas de correctives multi-driver.


## Fundamento matemático / técnico


### SO(3) como variedad Riemanniana


SO(3) — el grupo de rotaciones 3D — es una variedad diferenciable de dimensión 3. Tiene curvatura positiva (no es un espacio euclídeo plano). Esto implica que las operaciones estándar (suma, promedio aritmético) NO son válidas para rotaciones.


Representación como quaterniones unitarios: S³/Z₂ ≅ SO(3) (anti-podality: q y -q representan la misma rotación).


**Distancia geodésica** entre dos rotaciones R₁, R₂ ∈ SO(3):


```
d(R₁, R₂) = ||log(R₁^{-1} · R₂)||_F  =  2 · arccos(|q₁·q₂|)
```


Donde la última forma usa el producto escalar de quaterniones. Esa distancia es el ángulo del arco geodésico en S³.


---


### Mapa Logarítmico y Exponencial en SO(3)


**Mapa exponencial**: exp: T_I SO(3) → SO(3) (del espacio tangente a la variedad):


```
exp(v) = cos(||v||) + sin(||v||) · v/||v||   (como quaternión con w=cos, xyz=sin·n̂)
```


**Mapa logarítmico**: log: SO(3) → T_I SO(3) (de la variedad al espacio tangente):


```
Para q = (w, x, y, z) quaternión unitario:
θ = 2·arccos(|w|)
log(q) = θ/(2·sin(θ/2)) · (x, y, z)   si θ ≠ 0
log(q) = (0, 0, 0)                       si θ → 0
```


El resultado es un vector en ℝ³ (coordenadas del espacio tangente). Su norma es θ/2 (la mitad del ángulo de rotación).


---


### SLERP como caso especial (N=2)


SLERP entre q₁ y q₂ con parámetro t:


```
SLERP(q₁, q₂, t) = q₁ · exp(t · log(q₁^{-1} · q₂))
```


Interpretación geométrica: transportar desde q₁ en la dirección logarítmica hacia q₂ una fracción t del camino. Es el equivalente de la interpolación lineal en el espacio tangente, mapeada de vuelta a SO(3).


**Para N=2 con pesos iguales**: SLERP(q₁, q₂, 0.5) = media de Fréchet exacta.


---


### Media de Fréchet en SO(3) (media intrínseca)


La **media de Fréchet** μ es el minimizador de la suma ponderada de distancias geodésicas al cuadrado:


```
μ = argmin_{R ∈ SO(3)} Σ_i w_i · d²(R, R_i)
```


**Algoritmo iterativo de punto fijo** (Karcher 1977 / Moakher 2002):


```
1. Inicializar: μ₀ = q₁  (o media aritmética normalizada como aproximación inicial)
2. Repetir hasta convergencia:
   a. Calcular log tangentes: l_i = log(μ^{-1} · q_i)  para cada i
   b. Actualizar: Δ = Σ_i w_i · l_i   (media en espacio tangente)
   c. Actualizar: μ ← μ · exp(Δ)
   d. Renormalizar μ a quaternión unitario
3. Converge cuando ||Δ|| < ε (típico ε = 1e-6)
```


Convergencia garantizada si las rotaciones están dentro de un hemisferio (todas a distancia < π/2 de la media). Para rigs, esto se cumple prácticamente siempre en poses de producción (las poses extremas rara vez superan 90° de diferencia).


---


### Log-Euclidean Blending (aproximación más rápida)


Arsigny et al. 2006 proponen un marco que evita la iteración al operar en el espacio tangente en la identidad:


```
1. Calcular logaritmos individuales: l_i = log(q_i)  ∈ ℝ³ para cada quaternión
2. Mezcla lineal en ℝ³:             l_mean = Σ_i w_i · l_i
3. Mapear de vuelta:                 μ_LE = exp(l_mean)
```


- **Más rápido**: sin iteración, solo N evaluaciones de log + 1 exp.
- **Diferencia con Fréchet**: Log-Euclidean calcula la media en T_I SO(3) (tangente en la identidad), no en el tangente de la media actual. Para rotaciones cercanas entre sí, las diferencias son negligibles (O(θ³)).
- **Invariante al orden**: Σ_i w_i·l_i es conmutativa.


**Cuándo NO usar Log-Euclidean**: si las rotaciones a interpolar son antipodales (|q₁·q₂| ≈ 0), los logaritmos apuntan en direcciones opuestas y la media en ℝ³ puede dar resultados incorrectos. En ese caso, usar Fréchet iterativa con detección de antipodality.


---


### Diferencia con el promedio aritmético naive (quaterniones)


El promedio aritmético de quaterniones (q_avg = Σ w_i·q_i, normalizado) es una aproximación de primer orden al Log-Euclidean:


```
Error: O(θ²)  — aceptable para pequeñas rotaciones (< ~15°)
```


Para poses con rotaciones grandes (hombros, caderas — hasta 90-180°), el promedio aritmético puede dar hasta ~5-10° de error vs la media geodésica correcta. Para correctives de producción, esto es significativo.


---


### Aplicación a correctives RBF multi-driver


En un sistema RBF con K poses de entrenamiento (cada una con rotación de driver q_k) y pesos RBF w_k(q_current):


```
# Interpolación ingenua (incorrecta para grandes rotaciones):
q_out = normalize(Σ_k w_k · q_k)   ← error O(θ²)


# Interpolación Log-Euclidean (correcta):
l_k = log(q_k)   para cada k
l_out = Σ_k w_k · l_k
q_out = exp(l_out)   ← exacta para rotaciones en el mismo hemisferio
```


## Implementación en Maya


```python
import numpy as np
import maya.api.OpenMaya as om


def quaternion_log(q):
    """
    Mapa logarítmico: quaternión unitario → vector ℝ³ (espacio tangente en identidad)
    q: om.MQuaternion (x, y, z, w)
    """
    w = np.clip(q.w, -1.0, 1.0)
    theta = 2.0 * np.arccos(abs(w))
    if theta < 1e-8:
        return np.zeros(3)
    sin_half_theta = np.sin(theta / 2.0)
    return (theta / (2.0 * sin_half_theta)) * np.array([q.x, q.y, q.z])


def quaternion_exp(v):
    """
    Mapa exponencial: vector ℝ³ → quaternión unitario
    v: np.array shape (3,)
    """
    theta = np.linalg.norm(v)
    if theta < 1e-8:
        return om.MQuaternion(0, 0, 0, 1)
    n = v / theta
    s = np.sin(theta)
    c = np.cos(theta)
    return om.MQuaternion(s*n[0], s*n[1], s*n[2], c)


def log_euclidean_mean(quaternions, weights):
    """
    Media Log-Euclidean de N quaterniones con pesos arbitrarios.
    quaternions: lista de om.MQuaternion
    weights: lista de floats (deben sumar 1.0)
    """
    # Asegurar anti-podality: todos en el mismo hemisferio que el primero
    q_ref = quaternions[0]
    aligned = []
    for q in quaternions:
        if q_ref.x*q.x + q_ref.y*q.y + q_ref.z*q.z + q_ref.w*q.w < 0:
            aligned.append(om.MQuaternion(-q.x, -q.y, -q.z, -q.w))
        else:
            aligned.append(q)
    
    # Logaritmos individuales
    logs = np.array([quaternion_log(q) for q in aligned])
    
    # Media ponderada en espacio tangente
    mean_log = np.average(logs, weights=weights, axis=0)
    
    # Mapear de vuelta a SO(3)
    result = quaternion_exp(mean_log)
    return result.normal()


def frechet_mean_iterative(quaternions, weights, max_iter=20, tol=1e-8):
    """
    Media de Fréchet en SO(3) vía iteración Karcher (más precisa que Log-Euclidean).
    """
    # Inicializar con Log-Euclidean como aproximación
    mu = log_euclidean_mean(quaternions, weights)
    
    for _ in range(max_iter):
        # Calcular tangentes desde mu hacia cada q_i
        tangents = []
        for q in quaternions:
            q_rel = mu.inverse() * q
            if mu.x*q.x + mu.y*q.y + mu.z*q.z + mu.w*q.w < 0:
                q_rel = om.MQuaternion(-q_rel.x, -q_rel.y, -q_rel.z, -q_rel.w)
            tangents.append(quaternion_log(q_rel))
        
        tangents = np.array(tangents)
        delta = np.average(tangents, weights=weights, axis=0)
        
        if np.linalg.norm(delta) < tol:
            break
        
        mu = (mu * quaternion_exp(delta)).normal()
    
    return mu


# Uso en corrective RBF:
# driver_quats = [om.MQuaternion(...) for each pose]
# rbf_weights  = compute_rbf_weights(current_driver_pose, driver_poses)
# result_quat  = log_euclidean_mean(driver_quats, rbf_weights)
# cmds.setAttr(target_joint + '.rotate', *quat_to_euler(result_quat))
```


**Nodos Maya para casos simples (2 quaterniones):**
```
# SLERP entre dos rotaciones vía nodos nativos:
quatSlerp → animBlendNodeAdditiveRotation
# Para N rotaciones: no hay nodo nativo, requiere Python/C++ custom node
```


## Comparación con autorig_tools


El sistema RBF de autorig_tools usa mGear RBF Manager (que por defecto usa coordenadas de quaternión o Euler para drivers, y blendWeighted/interpolation nodes para los driven values). La interpolación interna de mGear para outputs de rotación usa blend lineal de quaterniones normalizado — una aproximación O(θ²).


Para la mayoría de correctives de producción (codo a 120°, hombro a 90°), el error del blend lineal vs Log-Euclidean es ~2-5° — potencialmente visible en lípido de personaje hero.


Lo que esta técnica añade: un `rbf_rotation_solver.py` que reemplaza el blend final de quaterniones de mGear con Log-Euclidean o Fréchet iterativa. No requiere tocar el pipeline de RBF — solo el nodo de evaluación final que mezcla los rotations outputs.


## Aplicable directamente


YES — Implementable en Python puro (numpy + maya.api.OpenMaya):
1. Escribir `autorig_tools/utils/quaternion_averaging.py` con `log_euclidean_mean()` y `frechet_mean_iterative()`.
2. En el evaluador de correctives RBF de autorig_tools, reemplazar el blend lineal final: en vez de `Σ w_i·q_i (normalizado)`, usar `log_euclidean_mean(quats, weights)`.
3. Impacto: ~0.1ms por corrective en Python, negligible.
4. Verificación: comparar pose en `shoulder.rotateX = 170°` (caso extremo) — diferencia debería ser visible sin lupa.


## Fuente
- Arsigny et al. 2006 "Log-Euclidean metrics": https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2275495/
- MDPI 2023 "Logarithm-Based Methods for Interpolating Quaternion Time Series": https://www.mdpi.com/2227-7390/11/5/1131
- Dual-Quaternion Interpolation review (Kenwright 2023): https://arxiv.org/abs/2303.13395
- Karcher 1977 (media de Fréchet en SO(3)): Riemannian Center of Mass and Mollifier Smoothing
- Moakher 2002 "Means and Averaging in the Group of Rotations": SIAM J. Matrix Anal. Appl.