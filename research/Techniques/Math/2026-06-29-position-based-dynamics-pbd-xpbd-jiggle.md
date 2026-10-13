---
source: https://matthias-research.github.io/pages/publications/posBasedDyn.pdf
found: 2026-06-29
category: math
priority: 1
tags: [maya, rigging, math, PBD, XPBD, jiggle, secondary-motion, simulation, constraints]
status: NEW
---

# Position-Based Dynamics (PBD) y XPBD — Matemática para Jiggle y Correctivas de Movimiento Secundario

## Descripción
PBD (Müller et al. 2007) y su evolución XPBD (Macklin, Müller, Chentanez 2016) son la familia de solvers más usada en producción para simular movimiento secundario (jiggle de grasa/músculo, colgantes, cadenas, ropa simple) porque son incondicionalmente estables, rápidos, y fáciles de controlar artísticamente comparado con solvers basados en fuerzas (masas-resortes explícitas o FEM). Es directamente relevante para cualquier corrective de jiggle/secondary motion en `autorig_tools`, ya sea como sistema standalone en Python o como base conceptual para entender qué hace nHair/nCloth/Bifrost por debajo.

## Fundamento matemático / técnico

### El problema con masas-resortes + integración explícita
Un sistema masa-resorte clásico con integración explícita (Euler) es:
```
F = -k(|p1-p0| - l_rest) * dir - kd*v     (fuerza de resorte + damping)
v += (F/m) * dt
p += v * dt
```
Es inestable: si k es alto (resorte rígido) o dt es grande, el sistema explota numéricamente (oscilación divergente). Para estabilidad con masas-resortes hay que o reducir dt drásticamente (caro) o usar integración implícita (resolver un sistema lineal grande, caro y complejo).

### PBD: resolver en posiciones, no en fuerzas
PBD evita el problema reformulando las restricciones (springs, distancia, bending) como **proyecciones de posición** en vez de fuerzas. El loop básico:

```
1. Predecir posición:           p* = p + v*dt + (f_ext/m)*dt²      (gravedad, etc.)
2. Resolver restricciones:      para cada constraint C(p) = 0, proyectar p* directamente
                                  hacia la superficie donde C=0 (iterativo, Gauss-Seidel)
3. Actualizar velocidad:        v = (p* - p) / dt
4. Actualizar posición:         p = p*
```

**Proyección de una restricción de distancia** (el caso más simple — un "stick" entre dos partículas):
```
C(p1, p2) = |p1 - p2| - l_rest = 0

Δp1 = -(w1/(w1+w2)) * C * n
Δp2 = +(w2/(w1+w2)) * C * n
   donde n = (p1-p2)/|p1-p2|,  wᵢ = 1/mᵢ (inverse mass)
```
Esto mueve directamente las posiciones de las dos partículas para satisfacer exactamente la restricción de distancia, ponderado por masa inversa (partículas más "pesadas" —w pequeño— se mueven menos). Como es una corrección de posición directa, NUNCA puede explotar numéricamente — en el peor caso, converge lento, pero no diverge.

### XPBD: por qué PBD básico no es físicamente correcto, y cómo se arregla
El problema de PBD clásico: la rigidez efectiva de una restricción depende del número de iteraciones del solver Y del timestep — algo que no debería pasar en una simulación físicamente correcta (más iteraciones no debería cambiar qué tan "duro" es el material). XPBD resuelve esto introduciendo un multiplicador de Lagrange λ y una rigidez física real **compliance α = 1/k** (inverso de la rigidez):

```
Δλ = (-C(p) - α̃·λ) / (Σᵢ wᵢ|∇Cᵢ|² + α̃)         donde α̃ = α / dt²
Δpᵢ = wᵢ · ∇Cᵢ · Δλ
λ += Δλ
```//
Con α=0 (compliance cero = restricción rígida), XPBD se reduce a PBD clásico. Con α>0, la restricción se comporta como un resorte real con rigidez k=1/α, y el resultado converge a la solución física correcta independientemente del número de iteraciones o substeps — esto es lo que permite controlar el jiggle con un parámetro de "stiffness" que tiene significado físico estable, en vez de un parámetro mágico que cambia de comportamiento según la calidad del solver.

### Restricción de bending para jiggle de superficie
Para simular jiggle de una superficie (no solo una cadena de partículas), se añade una restricción de bending entre tríos/cuádruplos de partículas, basada en el ángulo diedro entre triángulos adyacentes:
```
C_bend(p1,p2,p3,p4) = acos( n1 · n2 ) - θ_rest
   donde n1, n2 son las normales de los dos triángulos que comparten la arista p1-p2
```
Esto es lo que da "memoria de forma" — sin esto, una malla de partículas conectada solo por distancias se pliega libremente, sin resistencia a doblarse (como tela sin rigidez, no como grasa/músculo).

### Por qué es ideal para jiggle de personaje (vs. nCloth genérico)
Un jiggle rig no necesita simular tela completa — necesita unas pocas partículas guía (1 por zona de jiggle: panza, pecho, papada) conectadas al esqueleto rígido mediante restricciones de distancia + bending con compliance ALTA en distancia (casi rígido, sigue el hueso) pero compliance ajustable en una restricción adicional de "objetivo" (attachment al hueso padre con un resorte blando), lo cual produce overshoot/settle creíble con un coste de cómputo trivial (unas pocas partículas, pocas iteraciones).

## Implementación en Maya
Maya nCloth/nucleus usa internamente un solver basado en posiciones similar en espíritu a PBD (no es XPBD exacto, pero comparte la filosofía de proyección iterativa de restricciones). Para un jiggle rig ligero hecho a medida, normalmente es más eficiente y controlable implementar XPBD directamente en Python/numpy (offline o per-frame) que configurar nCloth para un caso tan simple:

```python
import numpy as np

def xpbd_distance_constraint(p1, p2, w1, w2, rest_length, compliance, dt, lambda_acc):
    delta = p1 - p2
    length = np.linalg.norm(delta)
    if length < 1e-8:
        return p1, p2, lambda_acc
    n = delta / length
    C = length - rest_length
    alpha_tilde = compliance / (dt * dt)
    denom = (w1 + w2) + alpha_tilde
    if denom < 1e-8:
        return p1, p2, lambda_acc
    d_lambda = (-C - alpha_tilde * lambda_acc) / denom
    lambda_acc += d_lambda
    p1 = p1 + w1 * n * d_lambda
    p2 = p2 - w2 * n * d_lambda
    return p1, p2, lambda_acc

def jiggle_step(particle_pos, particle_prev, bone_target_pos, mass_inv,
                 compliance_attach, dt, gravity, substeps=4):
    sub_dt = dt / substeps
    vel = (particle_pos - particle_prev) / dt
    for _ in range(substeps):
        p_pred = particle_pos + vel * sub_dt + gravity * mass_inv * sub_dt * sub_dt
        lam = 0.0
        # restricción de "attachment" al joint padre (resorte blando = jiggle)
        p_pred, _, lam = xpbd_distance_constraint(
            p_pred, bone_target_pos, mass_inv, 0.0, 0.0, compliance_attach, sub_dt, lam)
        vel = (p_pred - particle_pos) / sub_dt
        particle_pos = p_pred
    return particle_pos, vel
```

El resultado (posición de la partícula relativa al joint padre) se conecta vía `decomposeMatrix`/`offsetParentMatrix` a un joint corrective o a un blendshape driver — exactamente el patrón que ya usa `autorig_tools` para correctivas RBF/SDK, pero conduciendo el driver con una simulación física en vez de una pose estática.

## Comparación con autorig_tools
Si el jiggle/secondary motion en `autorig_tools` se hace actualmente con expresiones, springs nativos de Maya, o RBF estático (que no tiene componente dinámico real — solo interpola entre poses), XPBD ofrece un upgrade de fidelidad con coste de implementación moderado: unas ~20-30 líneas de Python por zona de jiggle, sin dependencia de nCloth/nucleus (que añade overhead de simulación y arrastra el namespace de Maya dynamics), y con parámetros de compliance que tienen significado físico estable (no hay que reajustar "stiffness" cada vez que se cambia el frame rate o el número de substeps, a diferencia de spring nodes clásicos). Es compatible conceptualmente con el patrón `local_mmx`/matrix-based del pipeline: el resultado de la simulación se trata como una posición/matriz local más, igual que cualquier corrective.

## Aplicable directamente
PARTIAL — YES para zonas de jiggle nuevas o para reemplazar springs nativos problemáticos:
1. Implementar un módulo Python standalone de XPBD (distance + attachment constraint, ~50 líneas) ejecutado por-frame fuera del DG de Maya (en un callback de `scriptJob` o, mejor, vía un nodo C++/compute custom si se necesita en Parallel Evaluation — ver documento de custom MPxNode).
2. Empezar con 1-2 partículas de prueba en una zona de jiggle existente (panza/pecho) comparando contra el comportamiento actual (spring nativo o RBF estático).
3. Exponer `compliance` (no `stiffness` crudo) como atributo de control artístico — es más estable de tunear porque no depende del framerate/substeps.
4. Si la zona de jiggle ya funciona bien con el método actual, no hay urgencia de migrar — es una mejora de fidelidad, no un bug fix.

## Fuente
- https://matthias-research.github.io/pages/publications/posBasedDyn.pdf — Müller, Heidelberger, Hennix, Ratcliff, "Position Based Dynamics" (2007), paper fundacional
- Macklin, Müller, Chentanez — "XPBD: Position-Based Simulation of Compliant Constrained Dynamics" (MIG 2016) — la extensión con compliance física correcta
- Relacionado: archivos existentes sobre RBF/SDK correctivas, custom-mpxnode-parallel-evaluation.md
