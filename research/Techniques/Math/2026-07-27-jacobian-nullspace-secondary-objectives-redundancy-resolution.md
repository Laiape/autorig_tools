---
source: https://www.sciencedirect.com/science/article/pii/S2667379726000677 | https://arxiv.org/abs/2605.31436 | https://doi.org/10.3390/biomimetics11060408
found: 2026-07-27
category: math
priority: 1
tags: [maya, rigging, math, ik, inverse-kinematics, jacobian, null-space, redundancy, secondary-objectives, full-body-ik]
status: NEW
---


# Jacobian Null Space IK: Secondary Objectives y Resolución de Redundancia


## Descripción
En una cadena cinemática redundante (más grados de libertad que la tarea requiere, p.ej. 7 joints para posicionar un end-effector en 6DOF), el Jacobiano tiene un espacio nulo no trivial: existen movimientos de joint que no mueven el end-effector. Esto permite añadir objetivos secundarios — límites de joint, singularidades, pose natural — sin interferir con el objetivo primario de IK. Es la base matemática de Full-Body IK, IK con restricciones de pose natural, y cualquier sistema IK con más de una prioridad de tarea.


## Fundamento matemático / técnico


### El Jacobiano y su solución de mínima norma


El Jacobiano **J** (m×n) mapea velocidades de joint q̇ (n-dim) a velocidades del end-effector ṡ (m-dim):


```
ṡ = J · q̇
```


Para n > m (cadena redundante), el sistema está subdeterminado. La solución de **mínima norma** es:


```
q̇_min = J† · ṡ


donde J† = J^T · (J·J^T)^{-1}   (Moore-Penrose pseudoinversa, válida si J tiene rango completo de filas)
```


### El espacio nulo y la solución general


El proyector al espacio nulo N de J:


```
N = I - J†·J    (n×n)
```


Propiedad: J · N·z = 0 para cualquier vector z ∈ ℝⁿ — los movimientos en el espacio nulo no mueven el end-effector.


**Solución general completa** (Lie & Walker 1988; estándar en robótica):


```
q̇ = J†·ṡ  +  (I - J†·J)·z
       ↑              ↑
  objetivo primario   objetivo secundario
  (mínima norma)      (proyectado al null space)
```


El término (I - J†·J)·z "inyecta" la dirección z al movimiento de joint SIN afectar al end-effector.


### Objetivos secundarios comunes


**1. Evitar límites de joint** (Liegeois 1977):


```
H_limits = Σ_i  [(q_i - q_mid_i) / (q_max_i - q_min_i)]²
z = -∂H_limits/∂q  (gradiente negativo → minimiza alejarse del centro del rango)
```


**2. Maximizar manipulabilidad** (Yoshikawa 1985) — alejar de singularidades:


```
w = sqrt(det(J·J^T))   (índice de manipulabilidad)
z = +∂w/∂q             (gradiente → aumenta w)
```


**3. Pose natural / posición de descanso**:


```
z = k · (q_rest - q)   (fuerza al joint hacia su ángulo de reposo)
```


**4. Límites "duros" via saturación en el null space** (Antonelli 2009):


```
# Cuando q_i alcanza límite:
z_i = 0   (ignorar el componente de ese joint en la proyección)
# Evita que la solución viole límites físicos a costa de afectar ligeramente el primario
```


### Damped Least Squares (DLS) — robustez near singularidades


Cuando J pierde rango, J†J^T → singular. DLS regulariza:


```
q̇_DLS = J^T · (J·J^T + λ²·I)^{-1} · ṡ


λ = damping factor  (típico: 0.05-0.3)
```


Cerca de singularidades: λ grande → solución estable pero con error en end-effector.
Lejos de singularidades: λ pequeño → solución casi óptima.


**Variable damping** (Sugihara 2011): λ = λ_max · (1 - w/w_threshold) para transición suave.


### Prioridades múltiples de tarea (Siciliano & Slotine 1991)


Para dos tareas con prioridad 1 > 2:


```
q̇_1 = J_1† · ṡ_1
N_1  = I - J_1†·J_1


ṡ_2_aug = ṡ_2 - J_2·q̇_1        (residual de tarea 2 dado tarea 1 ya satisfecha)
q̇_2     = N_1 · J_2† · ṡ_2_aug  (proyectado al null space de tarea 1)


q̇_total = q̇_1 + q̇_2
```


Ejemplo práctico: tarea 1 = IK de mano (6DOF), tarea 2 = pose natural de codo (1DOF). La pose de codo se optimiza dentro del espacio nulo del IK de mano.


### Hybrid framework para 7-DoF (Biomimetics 2026)


El paper "A Hybrid Inverse Kinematics Framework for Biomimetic Redundancy Resolution in 7-DoF Humanoid Arms" (2026) combina:
- Analytical null-space parameterization (para el shoulder swivel angle)
- Null-space gradient projection para objetivos secundarios continuos
- Joint-limit admissibility como constraint hard (NNLS en cada paso)


Resultado: convergencia más rápida que iteración pura con menor violación de límites.


## Implementación en Maya


```python
import numpy as np
import maya.api.OpenMaya as om


def jacobian_ik_with_nullspace(
    joint_chain,      # lista de nombres de joints
    target_pos,       # MVector: posición target del end-effector
    target_rot,       # MQuaternion: rotación target (opcional)
    iterations=50,
    dt=0.1,           # paso de integración
    damping=0.1,      # λ para DLS
    secondary_weight=0.3,
    q_rest=None       # ángulos de reposo para objetivo secundario
):
    n = len(joint_chain)
    q_rest = q_rest or np.zeros(n)
    
    for _ in range(iterations):
        # 1. Calcular Jacobiano numérico (3×n para posición, 6×n para pos+rot)
        J = compute_numerical_jacobian(joint_chain, target_pos)  # 3×n
        
        # 2. Error del end-effector
        ee_pos = get_world_position(joint_chain[-1])
        error = np.array([target_pos.x - ee_pos.x,
                          target_pos.y - ee_pos.y,
                          target_pos.z - ee_pos.z])
        
        if np.linalg.norm(error) < 1e-4:
            break
        
        # 3. DLS pseudoinversa
        JJT = J @ J.T
        J_dls = J.T @ np.linalg.inv(JJT + damping**2 * np.eye(3))
        
        # 4. Solución primaria (IK)
        q_dot_primary = J_dls @ error
        
        # 5. Proyector al null space
        N = np.eye(n) - J_dls @ J
        
        # 6. Objetivo secundario: pose natural
        q_current = get_joint_angles(joint_chain)
        z_secondary = secondary_weight * (q_rest - q_current)
        q_dot_secondary = N @ z_secondary
        
        # 7. Paso total
        q_new = q_current + dt * (q_dot_primary + q_dot_secondary)
        
        # 8. Clamp a límites de joint
        q_new = np.clip(q_new, joint_lower_limits, joint_upper_limits)
        
        set_joint_angles(joint_chain, q_new)
    
    return get_joint_angles(joint_chain)


def compute_numerical_jacobian(joints, target, eps=0.001):
    """Jacobian numérico por diferencias finitas"""
    n = len(joints)
    J = np.zeros((3, n))
    q_base = get_joint_angles(joints)
    ee_base = get_world_position(joints[-1])
    
    for i in range(n):
        q_perturb = q_base.copy()
        q_perturb[i] += eps
        set_joint_angles(joints, q_perturb)
        ee_perturb = get_world_position(joints[-1])
        J[:, i] = (np.array(ee_perturb) - np.array(ee_base)) / eps
        set_joint_angles(joints, q_base)
    
    return J
```


## Comparación con autorig_tools


autorig_tools usa IK handles nativos de Maya (RP Solver 2-bone, SC Solver), que no exponen acceso al null space. Los IK handles de Maya no son extensibles para secondary objectives.


Lo que esta técnica añade:
- **Full-Body IK** con prioridades: pelvis primero → torso segundo → extremidades terceras
- **Spine procedural IK**: la columna tiene 5+ joints (redundante) — el null space puede usarse para mantener una pose "natural" de columna mientras el torso y la pelvis se posicionan
- **Tail/tentacle IK**: cadenas largas (8-12 joints) donde FABRIK no permite secondary objectives; con Jacobian null-space projection se puede mantener twist, curvatura natural, o evitar auto-colisiones


Implementable como `utils/ik_solvers.py` con numpy. Coste: ~2-5ms por cadena en Python, aceptable para uso offline o en playblast.


## Aplicable directamente


YES (offline) / PARTIAL (runtime) — En Python, para:
1. **Procedural spine posing** en un tool de posado (no en tiempo real en la escena): la columna de 5 joints da 5DOF → null space de 5-6=−1, espera, para 3DOF de tarea (posición torso) hay 2DOF de null space para curvatura de spine.
2. **IK de cola/tentáculo offline**: calcular pose IK con secondary joint-limit avoidance fuera de Maya y setear las rotaciones finales.
3. **Investigación de Full-Body IK** como sistema separado (Python puro, numpy), integrable en autorig_tools/utils/fk_ik_fullbody.py.


Para runtime en escena: requeriría C++ MPxNode o usar los built-in FBIK nodes de Maya (menos control pero nativo).


## Fuente
- Review 2026: https://www.sciencedirect.com/science/article/pii/S2667379726000677
- Hybrid 7-DoF 2026: https://doi.org/10.3390/biomimetics11060408
- Actuator-Aware IK 2026: https://arxiv.org/abs/2605.31436
- Saeed Ghorbani blog (CCD, FABRIK, Jacobian comparison): https://saeed1262.github.io/blog/2025/inverse-kinematics-models/
- Liegeois 1977 (original null-space method): classical robotics reference