---
source: https://en.wikipedia.org/wiki/Dual_quaternion#ScLERP
found: 2026-06-29
category: math
priority: 1
tags: [maya, rigging, math, quaternion, dual-quaternion, interpolation, SE3, screw-theory]
status: NEW
---

# ScLERP (Screw Linear Interpolation) — Interpolación de Transformaciones Rígidas en SE(3)

## Descripción
ScLERP es el equivalente, para transformaciones rígidas completas (rotación + traslación), de lo que SLERP es para rotaciones puras. Mientras SLERP interpola sobre la esfera unitaria de cuaterniones (SO(3)/S³), ScLERP interpola sobre la variedad de cuaterniones duales unitarios, que representa el grupo de Lie SE(3) (rotaciones + traslaciones). Es relevante para cualquier sistema que necesite "blendear" dos poses rígidas completas de forma geométricamente correcta — IK/FK matching, blending de poses de matrices, o transiciones entre dos transforms de joint — en vez de interpolar posición y rotación por separado (que ya está cubierto por el documento existente de DQS, pero ScLERP es el operador de interpolación específico entre DOS transforms, no el blending ponderado de N huesos).

## Fundamento matemático / técnico

### SE(3) como grupo de Lie y por qué la interpolación separada falla
Una transformación rígida (R, t) vive en SE(3) = SO(3) ⋉ ℝ³. Interpolar t linealmente y R con SLERP por separado (el método más común en producción) NO sigue la geodésica de SE(3): produce una trayectoria donde el centro de rotación efectivo se desplaza de forma no física cuando rotación y traslación están acopladas (p.ej. un objeto que rota alrededor de un punto lejano — la interpolación separada hace que el objeto "se acerque y se aleje" del eje en vez de seguir un arco helicoidal limpio).

ScLERP en cambio interpola directamente en el espacio de cuaterniones duales unitarios, que es isomorfo a SE(3), siguiendo la geodésica real del grupo: un movimiento de tornillo (screw motion) — rotación constante alrededor de un eje fijo combinada con traslación constante a lo largo de ese mismo eje (teorema de Chasles: todo desplazamiento rígido es un movimiento de tornillo).

### Fórmula
Dados dos cuaterniones duales unitarios q̂₁, q̂₂ representando las poses inicial y final:

```
q̂(t) = q̂₁ · (q̂₁⁻¹ · q̂₂)^t,    t ∈ [0,1]
```

donde el exponente fraccionario `(·)^t` se calcula vía logaritmo/exponencial de cuaterniones duales (igual que SLERP usa `(q1⁻¹q2)^t` para cuaterniones simples):

```
Δq̂ = q̂₁⁻¹ · q̂₂                         (transformación relativa)
log(Δq̂) = (θ/2 + ε·d/2) · (l̂)           extracción eje de tornillo l̂, ángulo θ, traslación d a lo largo del eje, y el offset de momento (pitch)
q̂(t) = q̂₁ · exp(t · log(Δq̂))
```

El logaritmo de un cuaternión dual unitario se descompone en:
- **θ** — ángulo de rotación alrededor del eje de tornillo
- **d** — distancia de traslación a lo largo de ese mismo eje
- **l̂ = l + ε·m** — la línea de Plücker del eje (l = dirección, m = momento, codificando el offset del eje respecto al origen)

Esto da el **pitch** del movimiento de tornillo: `h = d/θ` (cuánto se traslada por radián rotado) — el invariante físico que ScLERP preserva, y que SLERP+LERP separados destruyen.

### Por qué importa la velocidad constante
ScLERP produce velocidad angular Y lineal constante a lo largo de la trayectoria (verdadera interpolación geodésica). DLB (Dual quaternion Linear Blending, usada en DQS para blending de N huesos) es una aproximación que normaliza una suma ponderada — más barata computacionalmente pero NO sigue la geodésica exacta entre solo dos poses. Para N>2 con pesos, DLB es la elección correcta (es lo que ya usa DQS). Para interpolar exactamente ENTRE DOS poses (t de 0 a 1, p.ej. un blend de IK/FK, o un slider de "blend pose A → pose B"), ScLERP es la solución matemáticamente exacta.

| Operación | Método correcto | Por qué |
|---|---|---|
| Blending ponderado de N huesos (skinning) | DLB / DQS | Barato, suficientemente preciso con normalización |
| Interpolación exacta entre 2 poses (t∈[0,1]) | ScLERP | Geodésica real en SE(3), velocidad constante |
| Rotación pura entre 2 orientaciones | SLERP | Caso particular de ScLERP sin componente de traslación |

## Implementación en Maya
Maya no tiene un nodo nativo de ScLERP. Las opciones disponibles en la escena son: `LERP` (interpolar translate) + `SLERP` vía `quatSlerp`/`MQuaternion::slerp` (interpolar rotate) por separado — que es la aproximación estándar y suficiente en la mayoría de blends de animación cortos, pero introduce el artefacto descrito arriba cuando el blend es largo (>~45°) y el pivote está lejos del objeto.

```python
import maya.api.OpenMaya as om2

def dual_quat_from_matrix(m):
    """m: om2.MMatrix -> (real_quat, dual_quat) as om2.MQuaternion"""
    t = om2.MTransformationMatrix(m)
    q = t.rotation(asQuaternion=True)
    pos = t.translation(om2.MSpace.kWorld)
    t_quat = om2.MQuaternion(pos.x, pos.y, pos.z, 0)
    dual = (t_quat * q) * 0.5
    return q, dual

def dual_quat_log(real, dual):
    """Extract screw axis, angle, pitch (translation along axis) from unit dual quaternion."""
    # theta from real part (standard quaternion log)
    theta = 2.0 * math.acos(max(-1.0, min(1.0, real.w)))
    if abs(theta) < 1e-8:
        axis = om2.MVector(0, 0, 0)
    else:
        s = math.sin(theta * 0.5)
        axis = om2.MVector(real.x, real.y, real.z) / s
    # translation distance along axis from dual part (pitch term)
    d = -2.0 * dual.w / (math.sin(theta * 0.5) if abs(theta) > 1e-8 else 1.0)
    return theta, axis, d

def sclerp(q1_real, q1_dual, q2_real, q2_dual, t):
    """ScLERP between two rigid poses given as unit dual quaternions."""
    # delta = q1^-1 * q2  (relative screw transform)
    r1_conj = q1_real.conjugate()
    delta_real = r1_conj * q2_real
    delta_dual = r1_conj * q2_dual + q1_dual.conjugate() * q2_real  # simplified composition
    # log -> scale by t -> exp, then compose with q1 (full impl needs dual-quaternion pow)
    # In production, use a vetted dual-quaternion library (e.g. numpy-quaternion + custom dual layer,
    # or Eigen's Eigen::DualQuaternion in C++) rather than hand-rolling the log/exp.
    ...
```

En la práctica, para producción se recomienda usar una librería ya probada (Eigen en C++ para un nodo custom, o `numpy-quaternion`/`dual-quaternions` en Python para herramientas offline) en vez de reimplementar el log/exp de cuaterniones duales a mano — es fácil introducir errores de signo en la extracción del pitch.

## Comparación con autorig_tools
`autorig_tools` ya cubre SLERP/SQUAD para interpolación de rotaciones (documentado en `quaternion-interpolation-slerp-squad-log.md`) y DQS para skinning. ScLERP llenaría el hueco específico de blends de pose completa (rotación+traslación) en sistemas como IK/FK matching o "pose blender" sliders, donde actualmente lo más probable es que se esté usando lerp+slerp por separado (el patrón estándar de la industria, y válido para la mayoría de blends cortos). Si el pipeline tiene algún blend de pose donde el pivote está lejos del objeto (p.ej. blendear entre una pose de FK con el codo muy flexionado y otra recta, sobre un hueso largo), vale la pena evaluar si el artefacto de "acercarse/alejarse" del eje es visible — si lo es, ScLERP es la solución matemática exacta.

## Aplicable directamente
PARTIAL — no es un cambio urgente, es una mejora de precisión para un caso específico:
1. Identificar si algún slider de blending de poses en autorig_tools (IK/FK match, blend de espacios) usa lerp+slerp por separado y muestra artefactos visibles de "encogimiento" en blends grandes.
2. Si existe ese caso, prototipar ScLERP con una librería de cuaterniones duales en Python (offline, no en tiempo real de DG) para validar si la diferencia visual justifica la complejidad añadida.
3. Para blending de N huesos en skinning, NO usar ScLERP — DLB/DQS (ya implementado) es la herramienta correcta ahí.

## Fuente
- https://en.wikipedia.org/wiki/Dual_quaternion#Screw_linear_interpolation_(ScLERP)
- Kavan, Collins, Žára, O'Sullivan — "Skinning with Dual Quaternions" (ya referenciado en dual-quaternion-skinning-math.md, sección de interpolación)
- Relacionado: archivo existente `quaternion-interpolation-slerp-squad-log.md`, `dual-quaternion-skinning-math.md`
