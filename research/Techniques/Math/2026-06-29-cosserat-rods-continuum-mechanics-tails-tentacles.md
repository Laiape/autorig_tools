---
source: https://en.wikipedia.org/wiki/Cosserat_elasticity
found: 2026-06-29
category: math
priority: 1
tags: [maya, rigging, math, cosserat-rods, simulation, dynamics, tails, ropes, continuum-mechanics]
status: NEW
---

# Cosserat Rods — Mecánica de Continuo para Colas, Tentáculos y Cuerdas

## Descripción
Los Cosserat rods son el modelo matemático estándar en gráficos por computadora para simular elementos delgados y alargados (colas, tentáculos, cuerdas, cables, pelo grueso) con comportamiento físico realista: estiramiento, cizalla (shear), flexión (bending) y torsión (twist) como modos de deformación independientes y acoplados. A diferencia de una cadena de joints FK/IK pura (sin física) o un sistema de spline simple, un Cosserat rod resuelve ecuaciones de energía elástica para producir el comportamiento dinámico correcto bajo gravedad, inercia y colisión — relevante para cualquier apéndice secundario (cola, antena, oreja larga) que necesite simulación creíble en vez de animación manual o un solver de IK simple.

## Fundamento matemático / técnico

### Cinemática: la curva centroide + marco material
Un Cosserat rod se parametriza por:
- **r(s, t)**: curva centroide en 3D (posición a lo largo de la longitud de arco s, en el tiempo t)
- **Q(s, t)**: marco material (un quaternión o matriz de rotación por sección transversal) que codifica cómo está orientada/torsionada la sección en cada punto s

Esto es la diferencia clave frente a una simple curva: cada punto de la curva lleva consigo una orientación 3D completa, no solo una tangente. Esto permite representar torsión (twist) independientemente de la flexión — una cola puede doblarse en un plano Y torsionarse sobre su propio eje simultáneamente.

### Deformaciones (strains) — los 4 modos
Definiendo derivadas respecto a la longitud de arco s (denotado con prima):

```
Strain de stretch/shear:  v(s) = Q(s)ᵗ · r'(s) - v̄(s)     (v̄ = config. de reposo)
Strain de bend/twist:     u(s) = Q(s)ᵗ · Q'(s) - ū(s)     (vector de Darboux, ū = reposo)
```

`v(s)` tiene 3 componentes: una de stretch (a lo largo del eje del rod) y dos de shear (perpendiculares). `u(s)` tiene 3 componentes: dos de bending (curvatura en dos planos) y una de twist (torsión sobre el eje propio).

### Energía elástica
La energía de deformación por unidad de longitud (modelo lineal, válido para deformaciones moderadas):

```
W(s) = ½ · (v(s) - v̄)ᵗ · K_se · (v(s) - v̄)  +  ½ · (u(s) - ū)ᵗ · K_bt · (u(s) - ū)
```

donde:
- **K_se** = diag(GA, GA, EA) — rigidez de stretch/shear (E = módulo de Young, G = módulo de cizalla, A = área de la sección transversal)
- **K_bt** = diag(EI₁, EI₂, GJ) — rigidez de bending (EI, momento de inercia de área × Young) y twisting (GJ, momento polar × shear modulus)

Esto es exactamente análogo a la teoría de vigas de Euler-Bernoulli/Timoshenko, generalizada a 3D con orientación completa.

### Ecuaciones de movimiento (dinámica, forma fuerte)
Las ecuaciones de Cosserat completas (balance de fuerza lineal y de momento angular) son un sistema de PDEs:

```
ρA · r̈(s,t) = ∂/∂s [Q(s)·K_se·v(s)] + f_ext(s,t)
ρI · ω̇(s,t) = ∂/∂s [Q(s)·K_bt·u(s)] + (Q·K_se·v) × r' + τ_ext(s,t)
```

donde ρA es masa por unidad de longitud, ρI es el tensor de inercia rotacional por unidad de longitud, ω es la velocidad angular del marco material. Estas se resuelven numéricamente — en producción casi siempre con un esquema de **discretización discreta** (Discrete Elastic Rods, Bergou et al. 2008/2010) en vez de resolver el continuo: el rod se discretiza en N segmentos rígidos (como una cadena de joints), cada segmento lleva su propio marco material, y las strains se calculan como diferencias discretas entre segmentos consecutivos en vez de derivadas continuas.

### Discrete Elastic Rods (DER) — la forma práctica
```
Para cada par de segmentos consecutivos i, i+1:
  curvature_binormal_i = 2 * (e_i × e_{i+1}) / (|e_i||e_{i+1}| + e_i·e_{i+1})   # discrete curvature
  twist_i = ángulo de torsión relativo entre marcos materiales i, i+1

Energía total = Σᵢ [ ½ kbend · |κᵢ - κ̄ᵢ|²  +  ½ ktwist · (mᵢ - m̄ᵢ)²  +  ½ kstretch · (lᵢ - l̄ᵢ)²/l̄ᵢ ]

Fuerzas = -∇(Energía total) respecto a las posiciones de los vértices  (gradiente analítico o autodiff)
```
Esto convierte el problema en una optimización/integración estándar (similar a un solver de masas-resortes pero con términos de bending y twist físicamente correctos, no solo distancia).

## Implementación en Maya
Maya no tiene un solver Cosserat nativo. Las aproximaciones disponibles, de menor a mayor fidelidad:

1. **Spring/hairSystem nativo de Maya** — aproxima stretch/bend con masas-resortes, pero NO modela twist como grado de libertad independiente (el pelo de Maya no tiene "marco material" por segmento, solo posición). Sirve para colas simples sin torsión visible.
2. **nHair con stiffness/twist controles** — Maya nHair tiene algo de control de torsión pero es heurístico, no resuelve las ecuaciones de Cosserat reales.
3. **Bifrost Graph** — tiene primitivas de simulación de rods/strands (point/strand simulation) más cercanas a un solver Cosserat real vía su motor de física, corriendo en sus propios hilos (no bloquea el DG de Maya — ver documento de Bifrost si existe en Performance).
4. **Solver custom en C++ (MPxNode) o standalone (numpy/Eigen) + bake a curva/joints** — la opción de máxima fidelidad: implementar DER, simular offline o en tiempo real, y conducir una cadena de joints con los resultados (posición + frame material → orientación de joint).

```python
# Esqueleto conceptual de un paso de integración explícita para un Cosserat rod discretizado
def step_der(positions, frames, rest_lengths, rest_curvatures, dt, gravity):
    # 1. Calcular curvatura discreta y twist actuales entre segmentos consecutivos
    curvatures = compute_discrete_curvatures(positions, frames)
    twists = compute_discrete_twists(frames)
    # 2. Fuerzas elásticas = -gradiente de energía (bend + twist + stretch)
    forces = compute_elastic_forces(positions, curvatures, rest_curvatures, k_bend, k_twist, k_stretch)
    forces += gravity * mass_per_vertex
    # 3. Integrar (semi-implícito Euler o, mejor, position-based / implicit para estabilidad)
    velocities += forces / mass_per_vertex * dt
    positions += velocities * dt
    # 4. Actualizar marcos materiales por transporte paralelo + torsión integrada
    frames = update_material_frames(frames, positions, twists, dt)
    return positions, frames
```

Para conducir un rig de Maya: cada segmento del rod discretizado mapea a un joint; la posición da el `translate`, y el marco material (tras alinear el eje primario con la tangente del segmento) da el `rotate` vía `decomposeMatrix` de la matriz compuesta por (tangente, normal del marco, binormal).

## Comparación con autorig_tools
`autorig_tools` no tiene actualmente (según el contexto del pipeline) un solver de dinámica para apéndices secundarios — las colas/tentáculos se manejan probablemente con FK/IK estándar más quizá algún spring node nativo o nHair. Cosserat rods (vía Discrete Elastic Rods) serían la mejora de fidelidad física correcta si se necesita comportamiento de "cola pesada que se balancea con inercia y se retuerce" más allá de lo que da un spring simple. La complejidad de implementación es alta (requiere integración numérica, marcos materiales, transporte paralelo) — normalmente se justifica solo si el estudio/proyecto necesita ese nivel de fidelidad específicamente en apéndices tipo cola/tentáculo/cuerda, y si Bifrost (con su simulación de strands ya integrada en Maya) no es suficiente.

## Aplicable directamente
NO a corto plazo — es una pieza de alta complejidad de implementación que solo se justifica para un caso de uso específico:
1. Si surge un rig con cola/tentáculo/apéndice que necesite torsión + flexión físicamente correctas (no solo un FK/spring), evaluar primero si **Bifrost Graph** (nativo en Maya, sin necesidad de C++) ya resuelve el caso antes de implementar DER desde cero.
2. Si Bifrost no es suficiente o se necesita el control fino de un solver propio, DER es el algoritmo correcto a implementar (probablemente como herramienta standalone en Python/numpy que hornea resultados a curvas/joints, no como nodo en tiempo real).
3. Mantener como conocimiento de referencia — no es una prioridad inmediata de implementación.

## Fuente
- https://en.wikipedia.org/wiki/Cosserat_elasticity
- Bergou, Wardetzky, Robinson, Audoly, Grinspun — "Discrete Elastic Rods" (SIGGRAPH 2008) — paper fundacional del modelo DER usado en producción
- Bergou et al. — "Discrete Viscous Threads" (SIGGRAPH 2010) — extensión con viscosidad/disipación
- Relacionado: si existe, documento de Bifrost Graph en Performance (strand/rod simulation primitives)
