---
source: https://pomax.github.io/bezierinfo/
found: 2026-06-29
category: math
priority: 1
tags: [maya, rigging, math, bezier, curves, deCasteljau, interpolation, splines]
status: NEW
---

# Curvas de Bézier y el Algoritmo de De Casteljau

## Descripción
Las curvas de Bézier son la base matemática de los controles de animación (graph editor), de las curvas NURBS/Bezier usadas para spines tipo ribbon, y de muchos sistemas de motion paths. El algoritmo de De Casteljau es el método numéricamente estable para evaluar estas curvas mediante interpolación lineal recursiva, evitando evaluar directamente el polinomio de Bernstein (que pierde precisión en grados altos). Entender este algoritmo es relevante porque subyace a cualquier sistema de curvas (incluyendo B-splines/de Boor, que ya está documentado, pero que es una generalización de Bézier por tramos).

## Fundamento matemático / técnico

### Definición de Bézier vía polinomios de Bernstein
Una curva de Bézier de grado n con puntos de control P₀...Pₙ se define como:

```
B(t) = Σᵢ₌₀ⁿ  C(n,i) · (1-t)^(n-i) · t^i · Pᵢ,   t ∈ [0,1]
```

donde `C(n,i) · (1-t)^(n-i) · t^i` es el i-ésimo polinomio base de Bernstein de grado n. Para el caso cúbico (n=3, el más usado en rigging):

```
B(t) = (1-t)³P₀ + 3(1-t)²t·P₁ + 3(1-t)t²·P₂ + t³·P₃
```

Evaluar esta forma directamente es numéricamente inestable para n grande (cancelación catastrófica en (1-t)^(n-i)·t^i cuando t→0 o t→1) y computacionalmente cara para evaluar en muchos puntos.

### Algoritmo de De Casteljau
En vez de expandir el polinomio, De Casteljau interpola linealmente de forma recursiva entre los puntos de control:

```
Pᵢ⁽⁰⁾ = Pᵢ                                  (puntos de control originales)
Pᵢ⁽ʳ⁾ = (1-t)·Pᵢ⁽ʳ⁻¹⁾ + t·Pᵢ₊₁⁽ʳ⁻¹⁾           r = 1..n,  i = 0..n-r

B(t) = P₀⁽ⁿ⁾
```

Es decir: en cada iteración, cada par de puntos consecutivos se reemplaza por su lerp con parámetro t. Después de n iteraciones queda un único punto: ese es B(t).

Pseudocódigo:
```python
def de_casteljau(points, t):
    pts = list(points)
    while len(pts) > 1:
        pts = [lerp(pts[i], pts[i+1], t) for i in range(len(pts)-1)]
    return pts[0]
```

**Complejidad**: O(n²) por evaluación (triángulo de De Casteljau con n(n+1)/2 lerps), frente a O(n) de evaluar el polinomio de Bernstein con el esquema de Horner — pero a cambio de estabilidad numérica perfecta, porque cada paso es solo una interpolación lineal entre valores ya acotados por el casco convexo de los puntos de control (convex hull property). Nunca hay términos grandes que se cancelen.

**Propiedad geométrica clave**: el triángulo de De Casteljau también da, gratis, las tangentes en los extremos: la tangente en t=0 es `P₁⁽⁰⁾ - P₀⁽⁰⁾` (dirección P0→P1), y la subdivisión en t (cortar la curva en dos Béziers) se obtiene directamente de las columnas del triángulo — el lado izquierdo del triángulo es la primera mitad, el lado derecho es la segunda mitad. Esto es exactamente cómo se subdivide una curva Bezier para refinamiento adaptativo (p.ej. para igualar la densidad de un ribbon).

### Derivada e hodógrafa
La derivada de una Bézier de grado n es otra Bézier de grado n-1 cuyos puntos de control son las diferencias escaladas:

```
B'(t) = n · Σᵢ₌₀ⁿ⁻¹ (Pᵢ₊₁ - Pᵢ) · Bernstein_{n-1,i}(t)
```

Esto permite calcular tangentes/normales analíticamente sin diferenciación numérica — útil para sistemas de aim/twist a lo largo de una curva.

## Implementación en Maya
Las curvas NURBS de Maya (`curve`, `bezierCurve`) usan internamente representación B-spline (de Boor), pero los segmentos Bezier individuales (como en el Graph Editor de animación, o un `bezierCurve` legacy) se evalúan con De Casteljau o equivalente. En `autorig_tools`, donde ya se usa de Boor/NURBS para las ribbon spines, el algoritmo de De Casteljau es relevante para:

```python
def de_casteljau_point(control_points, t):
    """control_points: list of (x,y,z) tuples or om2.MVector"""
    pts = list(control_points)
    while len(pts) > 1:
        pts = [p0 * (1.0 - t) + p1 * t for p0, p1 in zip(pts[:-1], pts[1:])]
    return pts[0]

def de_casteljau_tangent(control_points, t):
    # tangente = derivada de la curva, otra Bezier de grado n-1
    n = len(control_points) - 1
    deriv_pts = [(control_points[i+1] - control_points[i]) * n
                 for i in range(n)]
    return de_casteljau_point(deriv_pts, t)
```

Casos de uso directos: evaluar posición/tangente a lo largo de una curva motion-path sin depender de `nearestPointOnCurve` (que es caro), subdividir adaptativamente una curva ribbon para añadir más joints sin recalcular toda la curva, y construir sistemas de "stretchy" a lo largo de curvas que necesiten la longitud de arco aproximada (se puede aproximar integrando |B'(t)| con muestreo de De Casteljau, más preciso que un polígono de cuerdas simple).

## Comparación con autorig_tools
El spine ribbon de `autorig_tools` ya usa B-splines con de Boor (documentado en `bspline-deboor-nurbs-ribbon-math.md`), que es la generalización por tramos de Bézier y matemáticamente superior para curvas largas con muchos puntos de control (continuidad C² automática, soporte local). De Casteljau es más relevante para Bézier individuales: si en el pipeline hay algún sistema de motion-path o de control de tangentes manual (p.ej. un FK spline simple con 4 puntos), evaluarlo con De Casteljau en vez de expandir el polinomio da estabilidad numérica gratis y permite subdivisión adaptativa sin coste extra. No es un cambio urgente, pero es la herramienta correcta si se necesita evaluar/subdividir un segmento Bezier individual en Python sin pasar por nodos `curveInfo`/`pointOnCurveInfo` de Maya (que tienen coste de evaluación DG no trivial si se llaman en bucle).

## Aplicable directamente
PARTIAL — útil como utilidad matemática interna (no requiere cambios estructurales en autorig_tools):
1. Implementar `de_casteljau_point()`/`de_casteljau_tangent()` como utilidades puras de Python (sin nodos Maya) para precálculo de poses, preview en herramientas de UI (PySide2), o para sistemas de motion-path ligeros que no necesiten un nodo `motionPath` real.
2. Si se añade algún sistema de control de tangentes manual a la ribbon spine (edición de tangentes tipo Bezier sobre los joints), usar subdivisión De Casteljau para refinar la curva sin recomputar de Boor completo.
3. No sustituye al sistema de Boor existente — es complementario para casos de Bezier puro/segmentos individuales.

## Fuente
- https://pomax.github.io/bezierinfo/ — "A Primer on Bézier Curves" (Pomax), referencia completa e interactiva
- https://en.wikipedia.org/wiki/De_Casteljau%27s_algorithm
- Relacionado: archivo existente `bspline-deboor-nurbs-ribbon-math.md` (generalización por tramos)
