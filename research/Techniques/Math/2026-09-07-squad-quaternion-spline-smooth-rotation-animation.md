---
source: https://dl.acm.org/doi/10.1145/325165.325242
found: 2026-09-07
category: math
priority: 1
tags: [maya, python, rigging, math, quaternion, interpolation, slerp, squad, animation-curves, spline]
status: NEW
---

# SQUAD — Spherical Quadrangle Interpolation para Rotaciones Suaves (Shoemake 1985/1987)

## Descripción
SQUAD (Spherical QUADrangle interpolation) es la extensión cúbica de SLERP propuesta por Ken Shoemake en SIGGRAPH 1985 y refinada en 1987. Mientras SLERP interpola linealmente entre dos quaterniones (velocidad constante pero discontinuidad de derivada en los keyframes), SQUAD genera curvas C¹ continuas en la 3-esfera S³ — el equivalente a una curva Bézier cúbica sobre el espacio de quaterniones. Es el fundamento matemático de la interpolación suave de rotación en motores de animación modernos. Relevante para cualquier sistema procedural que interpole poses de joints en autorig_tools: spines, ribbons, IK/FK blending.

## Fundamento matemático / técnico

### SLERP — base

SLERP interpola entre dos quaterniones q₀ y q₁:

```
SLERP(q₀, q₁, t) = q₀ · (q₀⁻¹ · q₁)ᵗ
                  = (sin((1-t)Ω) / sinΩ) · q₀  +  (sin(tΩ) / sinΩ) · q₁
```

donde Ω = arccos(q₀ · q₁). Velocidad constante en S³, pero la segunda derivada es discontinua en los keyframes → "popeo" de velocidad angular en animación si hay muchos keys consecutivos.

### SQUAD — cubic Bézier en S³

Shoemake define los puntos de control intermedios (tangentes de Bézier en S³):

```
sᵢ = qᵢ · exp( −( log(qᵢ⁻¹ · qᵢ₋₁) + log(qᵢ⁻¹ · qᵢ₊₁) ) / 4 )
```

donde:
- log(q): si q = [cos θ, n̂ sin θ], entonces  log(q) = [0, n̂ θ]  (quaternión puro)
- exp(p): si p = [0, v],             entonces  exp(p) = [cos|v|, v̂ sin|v|]

Con sᵢ calculado una vez por keyframe, SQUAD evalúa el segmento entre qᵢ y qᵢ₊₁:

```
SQUAD(qᵢ, qᵢ₊₁, sᵢ, sᵢ₊₁, t) = SLERP(
    SLERP(qᵢ, qᵢ₊₁, t),
    SLERP(sᵢ, sᵢ₊₁, t),
    2t(1−t)
)
```

Coste: **3 SLERP** (vs 7 para De Casteljau cúbico completo). Resultado: C¹ continua en los keyframes → sin popeo de velocidad angular.

### Log-quaternion blending para N pesos (caso RBF)

Para blending de N quaterniones con pesos wᵢ (como en un RBF de correctives):

```
q_blend = exp( Σᵢ wᵢ · log(qᵢ) )
```

Válido sólo cuando todos los qᵢ están en el mismo hemisferio (dot(qᵢ, q_ref) > 0 para todo i). Error vs Fréchet mean: <0.5° para separaciones < 90° entre poses. El archivo riemannian-so3-frechet (2026-07-27) cubre el caso general con exactitud geodésica total.

### Nearest quaternion flip (gotcha clásico)

Antes de cualquier SLERP o SQUAD, verificar que q₀ · q₁ > 0; si no, negar q₁ (ambos representan la misma rotación pero SLERP tomaría el camino largo de 360°):

```python
if np.dot(q0, q1) < 0:
    q1 = -q1
```

## Implementación en Maya

### Python: SQUAD completo con OpenMaya 2

```python
import math
import maya.api.OpenMaya as om

def _quat_dot(a, b):
    return a.x*b.x + a.y*b.y + a.z*b.z + a.w*b.w

def slerp_quat(q0, q1, t):
    """SLERP entre dos om.MQuaternion."""
    dot = _quat_dot(q0, q1)
    if dot < 0.0:
        q1 = om.MQuaternion(-q1.x, -q1.y, -q1.z, -q1.w)
        dot = -dot
    dot = min(dot, 1.0)
    theta = math.acos(dot)
    if abs(theta) < 1e-10:
        result = om.MQuaternion(
            q0.x*(1-t) + q1.x*t,
            q0.y*(1-t) + q1.y*t,
            q0.z*(1-t) + q1.z*t,
            q0.w*(1-t) + q1.w*t
        )
        return result.normalizeIt()
    sin_theta = math.sin(theta)
    s0 = math.sin((1-t)*theta) / sin_theta
    s1 = math.sin(t*theta) / sin_theta
    return om.MQuaternion(
        s0*q0.x + s1*q1.x,
        s0*q0.y + s1*q1.y,
        s0*q0.z + s1*q1.z,
        s0*q0.w + s1*q1.w
    )

def squad_control_point(q_prev, q_curr, q_next):
    """Calcula el punto de control SQUAD sᵢ para el keyframe q_curr."""
    inv_curr = q_curr.conjugate()
    qa = inv_curr * q_prev
    log_a_angle = 2.0 * math.acos(max(-1.0, min(1.0, qa.w)))
    sa = math.sin(log_a_angle/2 + 1e-10)
    log_ax = qa.x * (log_a_angle / (2.0 * sa)) if log_a_angle > 1e-10 else 0.0
    log_ay = qa.y * (log_a_angle / (2.0 * sa)) if log_a_angle > 1e-10 else 0.0
    log_az = qa.z * (log_a_angle / (2.0 * sa)) if log_a_angle > 1e-10 else 0.0
    qb = inv_curr * q_next
    log_b_angle = 2.0 * math.acos(max(-1.0, min(1.0, qb.w)))
    sb = math.sin(log_b_angle/2 + 1e-10)
    log_bx = qb.x * (log_b_angle / (2.0 * sb)) if log_b_angle > 1e-10 else 0.0
    log_by = qb.y * (log_b_angle / (2.0 * sb)) if log_b_angle > 1e-10 else 0.0
    log_bz = qb.z * (log_b_angle / (2.0 * sb)) if log_b_angle > 1e-10 else 0.0
    avg_x = -(log_ax + log_bx) / 4.0
    avg_y = -(log_ay + log_by) / 4.0
    avg_z = -(log_az + log_bz) / 4.0
    avg_angle = math.sqrt(avg_x**2 + avg_y**2 + avg_z**2)
    if avg_angle > 1e-10:
        s = math.sin(avg_angle) / avg_angle
        exp_q = om.MQuaternion(avg_x*s, avg_y*s, avg_z*s, math.cos(avg_angle))
    else:
        exp_q = om.MQuaternion(0, 0, 0, 1)
    return q_curr * exp_q

def squad(q0, q1, s0, s1, t):
    """SQUAD entre q0 y q1 con puntos de control s0, s1."""
    inner0 = slerp_quat(q0, q1, t)
    inner1 = slerp_quat(s0, s1, t)
    return slerp_quat(inner0, inner1, 2.0*t*(1.0-t))
```

### Uso en spine procedural (FK override con tangentes suaves)

```python
def build_spine_squad_evaluator(ctrl_joints):
    """
    ctrl_joints: lista de joint names (de cadera a hombro)
    Retorna una función evaluate(t) -> om.MQuaternion
    """
    import maya.cmds as cmds
    keys = []
    for jnt in ctrl_joints:
        rot = cmds.getAttr(f'{jnt}.rotate')[0]
        q = om.MEulerRotation(*[math.radians(r) for r in rot]).asQuaternion()
        keys.append(q)
    
    controls = [None]
    for i in range(1, len(keys)-1):
        s = squad_control_point(keys[i-1], keys[i], keys[i+1])
        controls.append(s)
    controls.append(None)
    
    def evaluate(t):
        n_segs = len(keys) - 1
        seg = min(int(t * n_segs), n_segs - 1)
        local_t = t * n_segs - seg
        s0 = controls[seg] if controls[seg] is not None else keys[seg]
        s1 = controls[seg+1] if controls[seg+1] is not None else keys[seg+1]
        return squad(keys[seg], keys[seg+1], s0, s1, local_t)
    
    return evaluate
```

## Comparación con autorig_tools

El ribbon spine de autorig_tools usa de Boor para interpolación posicional, pero la orientación de los frames a lo largo del ribbon probablemente usa SLERP simple o Euler lineal entre joints de control — lo que causa discontinuidades de velocidad angular en spines con keyframes muy próximos. Sustituir por SQUAD en el evaluate_ribbon_frame() daría continuidad C¹ de la velocidad angular. También relevante para el IK/FK matching: cuando la función de match calcula las poses intermedias del FK spine para igualar la pose IK, SQUAD da una interpolación más natural que SLERP directo.

## Aplicable directamente

PARTIAL — La implementación Python completa está lista. El uso más inmediato es en `evaluate_at_t` de ribbons procedurales y en el FK spine override. No requiere cambios en el rig compilado, sólo en el código Python de build y de IK/FK matching. Estimado: 2-4h de integración + tests visuales.

## Fuente
https://dl.acm.org/doi/10.1145/325165.325242
https://splines.readthedocs.io/en/latest/rotation/squad.html
https://history.siggraph.org/learning/animating-rotation-with-quaternion-curves-by-shoemake/
https://liorsinai.github.io/mathematics/2021/12/06/quaternion-4-interpolation.html
