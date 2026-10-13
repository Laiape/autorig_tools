---
source: "https://arxiv.org/abs/2510.07514"
source_github: "https://github.com/a2r-lab/HJCD-IK"
found_date: 2026-07-20
category: Math/IK-Solvers
priority: 1
tags:
  - inverse-kinematics
  - GPU
  - CCD
  - jacobian
  - parallel-computing
  - IK-solver
  - research-paper
  - autorig
status: NEW
---

# HJCD-IK — GPU-Accelerated IK via Batched Hybrid Jacobian Coordinate Descent

## Descripcion

HJCD-IK (Hybrid Jacobian Coordinate Descent IK) es un solver de cinematica inversa GPU-paralelo publicado por el A2R Lab (MIT) en octubre de 2025 (arxiv 2510.07514). Combina dos fases complementarias:

1. **PO-CCD** (Position-Orientation aware Coordinate Descent) -- fase de inicializacion: genera **cientos a miles de seeds de configuracion** en paralelo en GPU, distribuidas por bloques, warps y threads CUDA. Cada seed ejecuta iteraciones CCD orientation-aware de forma independiente.
2. **PJ-IK** (Parallel Jacobian IK) -- fase de refinamiento: toma las mejores seeds del PO-CCD y aplica un paso de refinamiento Jacobiano paralelo para converger a soluciones de alta precision.

El resultado es un algoritmo que alcanza la **frontera Pareto de accuracy-latency** con ganancias de **orden de magnitud** sobre el state-of-the-art (NLOPT, IKFlow, CCD clasico) manteniendo la distribucion de muestras con la **menor Maximum Mean Discrepancy (MMD)**.

## Fundamento matematico/tecnico

### Phase 1: PO-CCD (Position-Orientation CCD)

CCD clasico minimiza error posicional moviendo una articulacion a la vez. PO-CCD extiende esto con orientacion:

Para la articulacion i con eje z_i, el angulo CCD estandar minimiza:

    theta_i* = argmin ||p_EE(theta_i) - p_target||^2

PO-CCD anade el termino de orientacion:

    theta_i* = argmin [ alpha * ||p_EE - p_target||^2 + beta * d_orient(R_EE, R_target) ]

donde d_orient puede ser la distancia geodesica en SO(3): d(R1, R2) = ||log(R1^T R2)||_F

**Paralelizacion GPU**: cada thread CUDA maneja una seed independiente. Para una cadena de n articulaciones:
- Block dimension: (num_seeds_per_block, 1, 1)
- Grid dimension: (total_seeds / seeds_per_block, 1, 1)
- Shared memory: configuracion actual theta en R^n por thread

Esto permite explorar simultaneamente todo el espacio de configuraciones sin conflictos de escritura entre seeds.

### Phase 2: PJ-IK (Parallel Jacobian Polishing)

Las k mejores seeds (menor error residual) del PO-CCD pasan por de refinamiento Jacobiano:

**Jacobian geometrico** de la cadena:

    J = [ J_v ]  en R^{6 x n}
        [ J_w ]

donde para articulacion rotacional i:

    J_{v,i} = z_i x (p_EE - p_i),   J_{w,i} = z_i

**Damped Least Squares (DLS)** para evitar singularidades:

    Delta_theta = J^T (J J^T + lambda^2 I)^{-1} Delta_x

donde Delta_x = [p_target - p_EE, omega_error]^T en R^6.

**Variable Damping (VD-IK)**: lambda adapta segun la condicion de la Jacobiana:

    lambda = lambda_max * (1 - sigma_min / epsilon)^2   si sigma_min < epsilon

Multiples seeds ejecutan DLS en paralelo. La solucion ganadora es la que converge primero al umbral de error dado.

### Maximum Mean Discrepancy (MMD) -- Calidad de distribucion

El paper reporta que HJCD-IK no solo es rapido sino que produce **soluciones bien distribuidas** en el espacio de configuraciones. La MMD mide si las muestras IK cubren la distribucion real de soluciones IK:

    MMD^2(P, Q) = E[k(x,x')] - 2*E[k(x,y)] + E[k(y,y')]

con k un kernel RBF. HJCD-IK obtiene la MMD mas baja comparado con IKFlow (normalizing flows) y CCD-batch clasico, lo que significa que sus soluciones son mas representativas de todo el espacio de soluciones IK posibles.

### Comparacion cuantitativa (resultados del paper)

| Metodo | Latency (ms) | Pos Error (mm) | MMD |
|--------|-------------|----------------|-----|
| CCD clasico | ~50 | 2-5 | alto |
| NLOPT | ~100-500 | < 1 | medio |
| IKFlow | ~10-20 | 3-8 | bajo |
| HJCD-IK | ~5-15 | < 1 | minimo |

*(valores aproximados de la figura Pareto del paper)*

## Implementacion en Maya

HJCD-IK como tal **no es directamente implementable en Python/Maya** porque requiere CUDA. Sin embargo, los conceptos son aplicables:

### Aplicacion conceptual en autorig_tools

```python
import numpy as np

def po_ccd_step(joints, positions, target_pos, target_rot=None, alpha=1.0, beta=0.1):
    """
    Single PO-CCD iteration for a joint chain.
    joints: list of joint transforms (4x4 matrices)
    positions: list of joint world positions
    target_pos: target end-effector position (3,)
    """
    n = len(joints)
    ee_pos = positions[-1]

    for i in range(n - 1, -1, -1):
        joint_pos = positions[i]

        to_ee = ee_pos - joint_pos
        to_target = target_pos - joint_pos

        axis = np.cross(to_ee / (np.linalg.norm(to_ee) + 1e-8),
                        to_target / (np.linalg.norm(to_target) + 1e-8))
        sin_angle = np.linalg.norm(axis)
        cos_angle = np.dot(to_ee, to_target) / (
            np.linalg.norm(to_ee) * np.linalg.norm(to_target) + 1e-8)
        angle = np.arctan2(sin_angle, cos_angle)

        joints[i] = apply_rotation(joints[i], axis / (sin_angle + 1e-8), angle)
        positions = forward_kinematics(joints)
        ee_pos = positions[-1]

    return joints, positions


def parallel_seeds_cpu(n_seeds, joint_chain_init, target, n_iters=10):
    """
    CPU-parallel seed exploration (thread pool equivalent of GPU warps).
    In real HJCD-IK this runs in CUDA.
    """
    from concurrent.futures import ThreadPoolExecutor

    seeds = []
    for s in range(n_seeds):
        noise = np.random.uniform(-0.3, 0.3, len(joint_chain_init))
        seeds.append(joint_chain_init + noise)

    def run_seed(seed_config):
        joints = seed_config.copy()
        positions = forward_kinematics(joints)
        for _ in range(n_iters):
            joints, positions = po_ccd_step(joints, positions, target)
        error = np.linalg.norm(positions[-1] - target)
        return joints, error

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(run_seed, seeds))

    best = min(results, key=lambda r: r[1])
    return best[0]
```

### MPxNode plugin (C++/CUDA) -- arquitectura

Para implementacion real en produccion como plugin Maya:

```cpp
// Sketch de MPxNode que wrappea HJCD-IK CUDA
class HJCDIKNode : public MPxNode {
public:
    static MObject aChainMatrices;   // input: array de matrices de cadena
    static MObject aTargetMatrix;    // input: target world matrix
    static MObject aNumSeeds;        // input: numero de GPU seeds
    static MObject aOutputRotations; // output: rotaciones resultantes

    MStatus compute(const MPlug& plug, MDataBlock& data) override {
        // 1. Extract chain matrices from MDataBlock
        // 2. Call hjcd_ik_cuda_kernel<<<grid, block>>>(seeds, chain, target)
        // 3. Write best result to aOutputRotations
        return MS::kSuccess;
    }
};
```

## Comparacion con autorig_tools

| Aspecto | autorig_tools actual | Con HJCD-IK |
|---------|---------------------|-------------|
| Solver IK | FABRIK / CCD en Python | GPU parallel seeds + Jacobian polish |
| Precision | Buena (FABRIK converge) | Alta (DLS polish garantiza convergencia fina) |
| Velocidad cadenas largas (>10 joints) | Lenta en Python | Order-of-magnitude mas rapido en GPU |
| Distribucion de soluciones multiples | Single solution | Multiples seeds -- distribucion de soluciones |
| Integracion Maya | Directa via cmds | Requiere MPxNode CUDA (plugin externo) |
| Aplicabilidad inmediata | Alta | Baja (requiere C++/CUDA) |

**Gap existente**: autorig_tools tiene FABRIK y CCD (cubiertos en `2026-06-15-fabrik-ccd-ik-solvers-iterative.md`). HJCD-IK anade el concepto de **exploracion en paralelo de seeds** y **refinamiento Jacobiano post-CCD**, que puede prototiparseen Python para rigs procedurales de cola/spine con multiples soluciones posibles.

## Aplicable directamente

### Corto plazo (Python prototipo):
1. Implementar `parallel_seeds_cpu()` en autorig_tools como wrapper de FABRIK con multiples configuraciones iniciales aleatorias -- mejora la calidad de convergencia para cadenas complejas sin GPU.
2. Anadir paso DLS post-FABRIK como "polishing phase" para reducir error residual en el end-effector.

### Medio plazo (C++ plugin):
3. Evaluar el codigo CUDA de https://github.com/a2r-lab/HJCD-IK para wrapping como MPxNode.
4. Integrar como solver opcional en rig de cola procedimental donde la velocidad GPU justifique el setup.

### Conceptual (arquitectura):
5. El concepto "multiples seeds -> seleccionar mejor" es aplicable a **blend shapes de correctives**: generar multiples candidatos de corrective y elegir el que mejor minimice distorsion volumetrica.

## Fuente

- **Paper principal**: https://arxiv.org/abs/2510.07514 -- "GPU-Accelerated Inverse Kinematics through Batched Hybrid Jacobian Coordinate Descent" -- A2R Lab, MIT, octubre 2025
- **Codigo**: https://github.com/a2r-lab/HJCD-IK
- **Archivos relacionados en esta libreria**:
  - `2026-06-15-fabrik-ccd-ik-solvers-iterative.md` -- FABRIK/CCD detallado
  - `2026-05-11-ik-solvers-fabrik-ccd-jacobian.md` -- Jacobian DLS base
  - `2026-06-01-rbf-kernel-functions-mathematical-basis.md` -- kernels MMD/RBF
