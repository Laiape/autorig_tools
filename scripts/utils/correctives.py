"""
Joints correctivas (muscle pushers) reutilizables, 100% automáticas y driven por
matrices/nodos. Dos primitivas:

  - corrective_push : 1 joint que se EMPUJA (translate) a lo largo de un eje local
                      cuando un driver entra en un rango. Para biceps/triceps/etc.
  - corrective_ring : ANILLO de N joints alrededor de un joint base (sección
                      transversal) que inflan radialmente hacia fuera, automático.
                      El "círculo" = la disposición en anillo.

Driver = cualquier atributo (p.ej. la rotación del codo). El rango (in_min, in_max)
del remapValue se auto-clampa: por debajo de in_min no hace nada, en in_max llega al
máximo. La cantidad se pasa como PLUG (atributo) para que el rigger la ajuste en vivo.
"""

import math
import maya.cmds as cmds
import maya.api.OpenMaya as om


def _set_or_connect(plug, value):
    """setAttr si value es número, connectAttr si es un plug (string)."""
    if isinstance(value, str):
        cmds.connectAttr(value, plug)
    else:
        cmds.setAttr(plug, value)


def _remap01(name, driver, in_min, in_max):
    """remapValue 0..1 (auto-clamp) desde driver en [in_min, in_max].
    in_min/in_max pueden ser número o un plug (atributo) para hacerlos tunables."""
    rmv = cmds.createNode("remapValue", name=f"{name}_RMV", ss=True)
    cmds.connectAttr(driver, f"{rmv}.inputValue")
    _set_or_connect(f"{rmv}.inputMin", in_min)
    _set_or_connect(f"{rmv}.inputMax", in_max)
    cmds.setAttr(f"{rmv}.outputMin", 0)
    cmds.setAttr(f"{rmv}.outputMax", 1)
    return f"{rmv}.outValue"


def corrective_push(name, base_joint, driver, in_min, in_max, axis, amount_attr, enable_attr=None):

    """
    Crea una joint correctiva hija de `base_joint` que se empuja a lo largo de
    `axis` (vector local) cuando `driver` va de in_min a in_max.

    Args:
        name (str): prefijo de los nodos/joint (se crea `{name}_JNT`).
        base_joint (str): joint padre (sigue al miembro; la correctiva nace en su origen).
        driver (str): plug del driver (p.ej. "L_elbowFk_CTL.rotateZ").
        in_min, in_max (float): rango del driver -> 0..1 (auto-clamp).
        axis (tuple): dirección local del empuje (se normaliza).
        amount_attr (str): plug con la distancia máxima de empuje (tunable en vivo).
        enable_attr (str|None): plug 0-1 para activar/desactivar.
    Returns:
        str: la joint correctiva.
    """
    jnt = cmds.createNode("joint", name=f"{name}_JNT", ss=True, parent=base_joint)
    cmds.setAttr(f"{jnt}.translate", 0, 0, 0)
    cmds.setAttr(f"{jnt}.jointOrient", 0, 0, 0)

    drv = _remap01(name, driver, in_min, in_max)
    ax = om.MVector(*axis)
    if ax.length() > 1e-9:
        ax.normalize()

    for i, comp in enumerate("XYZ"):
        if abs(ax[i]) < 1e-6:
            continue
        mul = cmds.createNode("multiply", name=f"{name}T{comp}_MUL", ss=True)
        cmds.connectAttr(drv, f"{mul}.input[0]")          # 0..1
        _set_or_connect(f"{mul}.input[1]", amount_attr)  # distancia máx (vivo)
        cmds.setAttr(f"{mul}.input[2]", float(ax[i]))     # componente del eje
        if enable_attr is not None:
            _set_or_connect(f"{mul}.input[3]", enable_attr)
        cmds.connectAttr(f"{mul}.output", f"{jnt}.translate{comp}")

    return jnt


def corrective_extra(joint, name, driver, in_min, in_max, axis, amount_attr, enable_attr=None):

    """
    Añade un empuje EXTRA (otro rango/eje) sobre una joint correctiva YA creada.
    Para una segunda fase: p.ej. que el bíceps además SUBA (+Y) cerca de la flexión
    máxima del codo, encima del empuje principal hacia delante.

    IMPORTANTE: usar canales de translate NO usados por el push principal (si el
    push principal ya escribe translateZ, aquí usa translateY/X).
    """
    drv = _remap01(name, driver, in_min, in_max)
    ax = om.MVector(*axis)
    if ax.length() > 1e-9:
        ax.normalize()

    for i, comp in enumerate("XYZ"):
        if abs(ax[i]) < 1e-6:
            continue
        mul = cmds.createNode("multiply", name=f"{name}T{comp}_MUL", ss=True)
        cmds.connectAttr(drv, f"{mul}.input[0]")
        _set_or_connect(f"{mul}.input[1]", amount_attr)
        cmds.setAttr(f"{mul}.input[2]", float(ax[i]))
        if enable_attr is not None:
            _set_or_connect(f"{mul}.input[3]", enable_attr)
        cmds.connectAttr(f"{mul}.output", f"{joint}.translate{comp}")

    return joint


def corrective_ring(name, base_joint, count, radius, driver, in_min, in_max, amount_attr, normal_axis="X", enable_attr=None):

    """
    Anillo de `count` joints correctivas alrededor de `base_joint`, en el plano
    perpendicular a `normal_axis` (= eje del hueso), que inflan RADIALMENTE hacia
    fuera de forma automática según `driver`.

    Cada joint nace en su posición del círculo (radius) y su translate radial se
    incrementa (posición_base + empuje) con el driver.

    Returns:
        list: las joints del anillo.
    """
    drv = _remap01(name, driver, in_min, in_max)
    ring = []
    for k in range(count):
        ang = 2.0 * math.pi * k / count
        c, s = math.cos(ang), math.sin(ang)
        if normal_axis == "X":
            direction = (0.0, c, s)
        elif normal_axis == "Y":
            direction = (c, 0.0, s)
        else:  # Z
            direction = (c, s, 0.0)

        jnt = cmds.createNode("joint", name=f"{name}{k:02d}_JNT", ss=True, parent=base_joint)
        cmds.setAttr(f"{jnt}.jointOrient", 0, 0, 0)
        cmds.setAttr(f"{jnt}.translate", direction[0] * radius, direction[1] * radius, direction[2] * radius)

        for i, comp in enumerate("XYZ"):
            if abs(direction[i]) < 1e-6:
                continue
            mul = cmds.createNode("multiply", name=f"{name}{k:02d}T{comp}_MUL", ss=True)
            cmds.connectAttr(drv, f"{mul}.input[0]")
            _set_or_connect(f"{mul}.input[1]", amount_attr)
            cmds.setAttr(f"{mul}.input[2]", float(direction[i]))
            if enable_attr:
                cmds.connectAttr(enable_attr, f"{mul}.input[3]")
            # translate = posicion_base_en_el_anillo + empuje_radial
            add = cmds.createNode("sum", name=f"{name}{k:02d}T{comp}_SUM", ss=True)
            cmds.setAttr(f"{add}.input[0]", direction[i] * radius)
            cmds.connectAttr(f"{mul}.output", f"{add}.input[1]")
            cmds.connectAttr(f"{add}.output", f"{jnt}.translate{comp}")

        ring.append(jnt)

    return ring


def bend_driver(name, upper_joint, lower_joint, axis, sign=1.0):

    """
    Ángulo de flexión de `lower_joint` respecto a `upper_joint` calculado desde sus
    matrices MUNDO -> FUNCIONA IGUAL EN FK Y EN IK (solo depende de la pose final, no
    de qué control la genera). Sustituye a leer la rotación de un FK_CTL (que solo
    existe en FK) o la de un joint del esqueleto (que en este rig va por matriz y su
    rotate local es 0).

    relativeMatrix = lower.worldMatrix x upper.worldInverseMatrix -> decompose -> euler.
    Se devuelve el plug del eje pedido, con el REST (pose de bind) llevado a 0 y
    multiplicado por `sign` (para igualar el comportamiento L/R, ya que en R el miembro
    está espejado y el ángulo sale con signo contrario).

    Args:
        name (str): prefijo de nodos.
        upper_joint (str): hueso superior (p.ej. armUpper00 / legUpper00).
        lower_joint (str): hueso inferior = la articulación (armLower00 / legLower00).
        axis (str): "X"/"Y"/"Z" (codo = "Y", rodilla = "Z").
        sign (float): +1 en L, -1 en R.
    Returns:
        str: plug con el ángulo de flexión (grados), rest a 0.
    """
    mm = cmds.createNode("multMatrix", name=f"{name}_MM", ss=True)
    cmds.connectAttr(f"{lower_joint}.worldMatrix[0]", f"{mm}.matrixIn[0]")
    cmds.connectAttr(f"{upper_joint}.worldInverseMatrix[0]", f"{mm}.matrixIn[1]")
    dec = cmds.createNode("decomposeMatrix", name=f"{name}_DEC", ss=True)
    cmds.connectAttr(f"{mm}.matrixSum", f"{dec}.inputMatrix")
    # rotateOrder con el EJE DE LA BISAGRA primero -> ese ángulo tiene rango completo
    # (±180) y NO se flippea al pasar de 90° (con XYZ, el eje del medio salta de signo).
    # X->xyz(0), Y->yzx(1), Z->zxy(2)
    cmds.setAttr(f"{dec}.inputRotateOrder", {"X": 0, "Y": 1, "Z": 2}[axis])
    raw = f"{dec}.outputRotate{axis}"

    # rest (bind) -> 0
    rest = cmds.getAttr(raw)
    sub = cmds.createNode("subtract", name=f"{name}Rest_SUB", ss=True)
    cmds.connectAttr(raw, f"{sub}.input1")
    cmds.setAttr(f"{sub}.input2", rest)
    drv = f"{sub}.output"

    if abs(sign - 1.0) > 1e-9:
        mul = cmds.createNode("multiply", name=f"{name}Sign_MUL", ss=True)
        cmds.connectAttr(drv, f"{mul}.input[0]")
        cmds.setAttr(f"{mul}.input[1]", float(sign))
        drv = f"{mul}.output"

    return drv


def corrective_offset_push(name, base_joint, driver, in_min, in_max, rest_offset, push_axis, amount, enable_attr=None):

    """
    Como corrective_push pero la joint NACE con un OFFSET de reposo (`rest_offset`,
    vector local) y ADEMÁS se empuja a lo largo de `push_axis` cuando el driver va de
    in_min a in_max. translate = rest_offset + empuje.

    Útil p.ej. para el trasero del muslo: parte ya desplazado DETRÁS (rest_offset) y al
    flexionar la rodilla se CONTRAE (push_axis hacia el hueso/arriba).
    """
    jnt = cmds.createNode("joint", name=f"{name}_JNT", ss=True, parent=base_joint)
    cmds.setAttr(f"{jnt}.jointOrient", 0, 0, 0)
    cmds.setAttr(f"{jnt}.translate", float(rest_offset[0]), float(rest_offset[1]), float(rest_offset[2]))

    drv = _remap01(name, driver, in_min, in_max)
    ax = om.MVector(*push_axis)
    if ax.length() > 1e-9:
        ax.normalize()

    for i, comp in enumerate("XYZ"):
        base_val = float(rest_offset[i])
        if abs(ax[i]) < 1e-6:
            continue  # ese canal se queda en su rest (ya seteado arriba)
        mul = cmds.createNode("multiply", name=f"{name}T{comp}_MUL", ss=True)
        cmds.connectAttr(drv, f"{mul}.input[0]")
        _set_or_connect(f"{mul}.input[1]", amount)
        cmds.setAttr(f"{mul}.input[2]", float(ax[i]))
        if enable_attr is not None:
            _set_or_connect(f"{mul}.input[3]", enable_attr)
        add = cmds.createNode("sum", name=f"{name}T{comp}_SUM", ss=True)
        cmds.setAttr(f"{add}.input[0]", base_val)
        cmds.connectAttr(f"{mul}.output", f"{add}.input[1]")
        cmds.connectAttr(f"{add}.output", f"{jnt}.translate{comp}")

    return jnt


def corrective_arc(name, base_joint, driver, in_min, in_max,
                   forward_axis, up_axis, forward_limit, up_limit,
                   enable_attr=None, rest_offset=(0.0, 0.0, 0.0), up_power=2.0):

    """
    Joint correctiva con trayectoria en ARCO. Cuando el driver va de in_min a in_max:
      - se EMPUJA a lo largo de `forward_axis` de forma lineal con el progreso, y
      - A LA VEZ SUBE a lo largo de `up_axis` siguiendo progreso^up_power (sube tarde),
    de modo que describe una CURVA: primero sale, y cuanto más avanza más sube.

    `forward_limit` / `up_limit` son LÍMITES (hasta dónde llega como máximo, en unidades),
    NO activación -> se pasan como plug (atributo) para tunearlos en vivo.
    `enable_attr` (0/1) activa/desactiva TODA la función. `rest_offset` = offset de reposo
    (vector local). `up_power` = curvatura del arco (2 = sube tarde; mayor = más tarde).

    Returns: la joint.
    """
    jnt = cmds.createNode("joint", name=f"{name}_JNT", ss=True, parent=base_joint)
    cmds.setAttr(f"{jnt}.jointOrient", 0, 0, 0)
    cmds.setAttr(f"{jnt}.translate", float(rest_offset[0]), float(rest_offset[1]), float(rest_offset[2]))

    prog = _remap01(name, driver, in_min, in_max)            # 0..1 (avance del push)
    pown = cmds.createNode("power", name=f"{name}UpProg_POW", ss=True)
    cmds.connectAttr(prog, f"{pown}.input")
    cmds.setAttr(f"{pown}.exponent", float(up_power))
    prog_up = f"{pown}.output"                                # progreso de subida (arco)

    fA = om.MVector(*forward_axis)
    if fA.length() > 1e-9:
        fA.normalize()
    uA = om.MVector(*up_axis)
    if uA.length() > 1e-9:
        uA.normalize()

    for i, comp in enumerate("XYZ"):
        terms = []
        if abs(fA[i]) > 1e-6:
            m = cmds.createNode("multiply", name=f"{name}Fwd{comp}_MUL", ss=True)
            cmds.connectAttr(prog, f"{m}.input[0]")
            _set_or_connect(f"{m}.input[1]", forward_limit)
            cmds.setAttr(f"{m}.input[2]", float(fA[i]))
            if enable_attr is not None:
                _set_or_connect(f"{m}.input[3]", enable_attr)
            terms.append(f"{m}.output")
        if abs(uA[i]) > 1e-6:
            m = cmds.createNode("multiply", name=f"{name}Up{comp}_MUL", ss=True)
            cmds.connectAttr(prog_up, f"{m}.input[0]")
            _set_or_connect(f"{m}.input[1]", up_limit)
            cmds.setAttr(f"{m}.input[2]", float(uA[i]))
            if enable_attr is not None:
                _set_or_connect(f"{m}.input[3]", enable_attr)
            terms.append(f"{m}.output")
        if not terms:
            continue
        s = cmds.createNode("sum", name=f"{name}T{comp}_SUM", ss=True)
        cmds.setAttr(f"{s}.input[0]", float(rest_offset[i]))
        for k, t in enumerate(terms):
            cmds.connectAttr(t, f"{s}.input[{k + 1}]")
        cmds.connectAttr(f"{s}.output", f"{jnt}.translate{comp}")

    return jnt


def world_to_local_dir(parent, world_dir):
    """Dirección MUNDO -> espacio local de `parent` (normalizada). Para definir
    ejes de empuje en mundo (personaje mira +Z, L en +X) y convertirlos al frame
    real del padre en build -> funciona con joints de cualquier orientación y con
    el mirror-behavior de R sin reglas de signos a mano."""
    mi = om.MMatrix(cmds.getAttr(f"{parent}.worldInverseMatrix[0]"))
    v = om.MVector(*world_dir) * mi
    if v.length() > 1e-9:
        v.normalize()
    return (v.x, v.y, v.z)


def world_to_local_point(parent, world_point):
    """Punto MUNDO -> translate local bajo `parent` (para rest_offset)."""
    mi = om.MMatrix(cmds.getAttr(f"{parent}.worldInverseMatrix[0]"))
    p = om.MPoint(world_point[0], world_point[1], world_point[2]) * mi
    return (p.x, p.y, p.z)


def mirror_axis(v, side):
    """Vector de empuje LOCAL L -> R: negar el vector COMPLETO (las guías se
    espejan con mirrorBehavior; regla verificada en arm/leg)."""
    return v if side == "L" else (-v[0], -v[1], -v[2])


def matrix_source(node):
    """Plug de matriz mundo de `node`: worldMatrix para DAG, outputMatrix/matrixSum
    para nodos de matriz (aimMatrix, blendMatrix, multMatrix...). Permite usar como
    fuente de un pose reader un frame rígido tipo {side}_armNonRollAim_AMX en vez
    de un joint de ribbon (cuyo aim contaminan los bendys)."""
    for attr, plug in (("worldMatrix", f"{node}.worldMatrix[0]"),
                       ("outputMatrix", f"{node}.outputMatrix"),
                       ("matrixSum", f"{node}.matrixSum")):
        if cmds.attributeQuery(attr, node=node, exists=True):
            return plug
    return None


def target_frame_dir(world_dir, rest_bone_world, target_world):
    """Pre-rota una dirección de empuje autorada EN LA POSE OBJETIVO al frame de
    BIND. La correctiva vive en el frame del hueso, que rota rest->target cuando
    el cono se activa: sin esta pre-rotación, a plena activación el push mundial
    llega girado hasta 90° (p.ej. un deltoides autorado "arriba" acabaría
    empujando hacia el cuello con el brazo elevado). En rest el push vale ~0
    (driver 0), así que la dirección solo importa cerca del target.

    dir_bind = dir_pose.rotateBy(swing(rest->target)^-1)
    """
    a = om.MVector(rest_bone_world[0], rest_bone_world[1], rest_bone_world[2])
    b = om.MVector(target_world[0], target_world[1], target_world[2])
    if a.length() < 1e-9 or b.length() < 1e-9:
        return om.MVector(world_dir[0], world_dir[1], world_dir[2])
    a.normalize()
    b.normalize()
    q = om.MQuaternion(a, b)
    return om.MVector(world_dir[0], world_dir[1], world_dir[2]).rotateBy(q.inverse())


def cone_driver(name, joint, ref_parent, target_world, bone_axis="X", axis_sign=1.0, margin=0.02, half_angle=None):
    """
    Pose reader MULTI-EJE (cono auto-calibrado) para hombro/cadera, donde un
    euler de un eje (bend_driver) no vale. Devuelve un plug 0..1: 0 en la pose
    de BUILD (rest, sea T-pose o A-pose) y 1 cuando el eje `bone_axis` del
    `joint` apunta a `target_world` (dirección MUNDO en bind).

    - La dirección del hueso se mide EN ESPACIO de `ref_parent` (chest, pelvis,
      clavícula): acompaña al torso y es inmune a masterwalk/escala.
    - `target_world` se convierte a espacio del padre EN BUILD y queda estático.
    - Auto-calibración: inputMin del remap = dot(eje en rest, target) + margin ->
      el driver vale 0 exacto en bind y rampa suave (smooth) hasta 1 en la pose.
    - `axis_sign`: +1/-1 según el eje local apunte A FAVOR o EN CONTRA del hueso
      (en R el ribbon puede aimear -X); medirlo con la dirección real
      upper->lower y pasarlo aquí.
    - `half_angle` (grados): SEMIÁNGULO del cono. Sin él, la activación cubre
      TODO el arco desde bind (con target ⟂ al rest son ~90°: una rampa de
      hemiesfera que se cuela en poses cotidianas). Con half_angle, el driver
      arranca a ese ángulo del target: inputMin = max(rest_dot+margin,
      cos(half_angle)). Valores razonables: 55-65.
    - `joint` puede ser un joint (worldMatrix) o un nodo de matriz con
      outputMatrix/matrixSum — p.ej. el {side}_armNonRollAim_AMX: un frame
      RÍGIDO de la articulación que los bendys del ribbon no contaminan.
    - El TWIST es invisible al cono (girar el hueso sobre su eje no cambia su
      dirección): para poses con twist combinar con matrix_manager.extract_twist.

    Returns:
        str|None: plug 0..1, o None si el target está demasiado cerca del rest
        (cono degenerado: no habría rango útil).
    """
    axis_idx = {"X": 0, "Y": 1, "Z": 2}[bone_axis]

    src = matrix_source(joint)
    if src is None:
        return None

    # target (y rest) en espacio del padre, estáticos de bind
    pim = om.MMatrix(cmds.getAttr(f"{ref_parent}.worldInverseMatrix[0]"))
    tv = om.MVector(*target_world) * pim
    if tv.length() < 1e-9:
        return None
    tv.normalize()
    tv *= float(axis_sign)

    jm = om.MMatrix(cmds.getAttr(src)) * pim
    rest_axis = om.MVector(jm[axis_idx * 4], jm[axis_idx * 4 + 1], jm[axis_idx * 4 + 2])
    if rest_axis.length() < 1e-9:
        return None
    rest_axis.normalize()
    rest_dot = rest_axis * tv
    if rest_dot > 1.0 - 2.0 * margin:
        return None  # el rest ya está "en la pose": el cono no discrimina

    # dirección del hueso en espacio del padre, EN VIVO
    mm = cmds.createNode("multMatrix", name=f"{name}_MM", ss=True)
    cmds.connectAttr(src, f"{mm}.matrixIn[0]")
    cmds.connectAttr(f"{ref_parent}.worldInverseMatrix[0]", f"{mm}.matrixIn[1]")
    rfm = cmds.createNode("rowFromMatrix", name=f"{name}Axis_RFM", ss=True)
    cmds.setAttr(f"{rfm}.input", axis_idx)
    cmds.connectAttr(f"{mm}.matrixSum", f"{rfm}.matrix")

    dot = cmds.createNode("vectorProduct", name=f"{name}_DOT", ss=True)
    cmds.setAttr(f"{dot}.operation", 1)  # dot product
    cmds.setAttr(f"{dot}.normalizeOutput", 1)  # cos limpio aunque haya escala
    for ax in "XYZ":
        cmds.connectAttr(f"{rfm}.output{ax}", f"{dot}.input1{ax}")
    cmds.setAttr(f"{dot}.input2", tv.x, tv.y, tv.z, type="double3")

    input_min = rest_dot + margin
    if half_angle is not None:
        input_min = max(input_min, math.cos(math.radians(float(half_angle))))
    rmv = cmds.createNode("remapValue", name=f"{name}_RMV", ss=True)
    cmds.connectAttr(f"{dot}.outputX", f"{rmv}.inputValue")
    cmds.setAttr(f"{rmv}.inputMin", min(input_min, 0.98))
    cmds.setAttr(f"{rmv}.inputMax", 1.0)
    cmds.setAttr(f"{rmv}.outputMin", 0.0)
    cmds.setAttr(f"{rmv}.outputMax", 1.0)
    for i in (0, 1):  # rampa smooth (entrada/salida suaves del cono)
        cmds.setAttr(f"{rmv}.value[{i}].value_Interp", 2)
    return f"{rmv}.outValue"


def corrective_curve(name, base_curve, targets, num_joints=5, parent_joint=None, enable_attr=None):
    """
    Sistema POSE -> CURVA -> JOINTS (estilo "curve based joint drivers" de Matt
    Le-Fevre): en vez de tunear N pushes sueltos, el rigger esculpe EL PERFIL de
    la zona como curva por pose, y una batería de joints monta la curva y lo
    reproduce en el skinning. Ideal para siluetas continuas: línea de nudillos,
    pliegue de la muñeca, perfil del antebrazo, nasolabial.

    Montaje:
      1. blendShape FRONT OF CHAIN sobre `base_curve` con una target por pose;
         el peso de cada target = remapValue(driver, in_min..in_max) [x enable].
         Los targets se esculpen en ESPACIO DE REPOSO (duplicado de la curva
         base): como el skin de la curva evalúa después, se ve el resultado en
         vivo con el rig posado mientras mueves CVs del target.
      2. `num_joints` joints `{name}CurveCorrective{NN}_JNT` montadas sobre la
         curva (pointOnCurveInfo por porcentaje -> fourByFourMatrix -> multMatrix
         x parent.worldInverseMatrix -> offsetParentMatrix): siguen la curva
         deformada Y al rig, sin doble transformación. El naming con "corrective"
         hace que skeleton_hierarchy las cuelgue del _ENV de `parent_joint`.

    IMPORTANTE: la curva base debe SEGUIR AL RIG — skinnéala a las joints de
    deformación de la zona (cmds.skinCluster sobre la curva) o cuélgala de un
    módulo. Si la curva se queda estática en mundo, las joints no acompañarán al
    personaje. Después, pinta las joints nuevas en el skinCluster de correctivas
    (`C_corrective_SKC`) como cualquier otra.

    Re-ejecutable: si el blendShape `{name}CurveCorrective_BLS` ya existe sobre
    la curva, las targets nuevas se AÑADEN a él (para ir sumando poses) y no se
    recrean las joints existentes.

    Args:
        name (str): prefijo `{L|R|C}_zona` (p.ej. "L_knuckles").
        base_curve (str): transform de la curva NURBS de reposo (skinneada al rig).
        targets (list): tuplas (target_curve, driver, in_min, in_max) — una por
            pose; driver es un plug (bend_driver, cone_driver, peso de BLS, ctl…)
            e in_min/in_max aceptan número o plug (auto-clamp del remap).
        num_joints (int): joints a montar sobre la curva.
        parent_joint (str|None): joint de deformación del que cuelgan las joints
            (necesario para el export _ENV). Sin él, se parentan al mundo y NO
            entran en el esqueleto de export (warning).
        enable_attr (str|None): plug 0-1 que multiplica TODOS los pesos.

    Returns:
        dict: {"joints": [...], "blendshape": str, "curve": base_curve}
    """
    shapes = cmds.listRelatives(base_curve, shapes=True, noIntermediate=True, fullPath=True) or []
    shape = shapes[0] if shapes else None
    if not shape or cmds.nodeType(shape) != "nurbsCurve":
        cmds.error(f"corrective_curve: '{base_curve}' no tiene shape de curva NURBS no-intermediate")

    bls_name = f"{name}CurveCorrective_BLS"

    # --- blendShape front of chain (reutilizable entre llamadas para sumar poses)
    if cmds.objExists(bls_name):
        bls = bls_name
        # índice libre REAL (weightCount miente si se borró un target intermedio)
        ids = cmds.getAttr(f"{bls}.weight", multiIndices=True) or []
        next_idx = (max(ids) + 1) if ids else 0
        existing_targets = set(cmds.blendShape(bls, q=True, target=True) or [])
    else:
        bls = cmds.blendShape(base_curve, name=bls_name, frontOfChain=True)[0]
        next_idx = 0
        existing_targets = set()

    idx = next_idx
    for target_curve, driver, in_min, in_max in targets:
        t_short = _short(target_curve)
        if t_short in existing_targets:
            om.MGlobal.displayWarning(
                f"corrective_curve {name}: '{t_short}' ya es target del BLS — se salta (no duplicar poses)")
            continue
        cmds.blendShape(bls, edit=True, target=(base_curve, idx, target_curve, 1.0))
        drv = _remap01(f"{name}Crv{t_short}", driver, in_min, in_max)
        if enable_attr is not None:
            mul = cmds.createNode("multiply", name=f"{name}Crv{t_short}En_MUL", ss=True)
            cmds.connectAttr(drv, f"{mul}.input[0]")
            _set_or_connect(f"{mul}.input[1]", enable_attr)
            drv = f"{mul}.output"
        cmds.connectAttr(drv, f"{bls}.weight[{idx}]", force=True)
        idx += 1

    # --- joints montadas sobre la curva (porcentaje de longitud)
    if parent_joint is not None and not cmds.objExists(parent_joint):
        parent_joint = None
    if parent_joint is None:
        om.MGlobal.displayWarning(
            f"corrective_curve {name}: sin parent_joint — las joints NO entrarán en el esqueleto de export")

    stale = cmds.ls(f"{name}CurveCorrective??_JNT", type="joint") or []
    if stale and len(stale) > num_joints:
        om.MGlobal.displayWarning(
            f"corrective_curve {name}: hay {len(stale)} joints y pides {num_joints} — "
            f"las sobrantes conservan su parámetro antiguo (bórralas si cambias la densidad)")

    joints = []
    for i in range(num_joints):
        # fracción de PARÁMETRO (0-1 del dominio de knots), no de longitud de arco
        param = i / max(num_joints - 1, 1)
        jnt_name = f"{name}CurveCorrective{i:02d}_JNT"
        poc_name = f"{name}Crv{i:02d}_POC"
        if cmds.objExists(jnt_name):
            # re-ejecución: se conserva la joint pero se re-reparte el parámetro
            # para que la distribución sea coherente con num_joints actual
            if cmds.objExists(poc_name):
                cmds.setAttr(f"{poc_name}.parameter", param)
            joints.append(jnt_name)
            continue
        poc = cmds.createNode("pointOnCurveInfo", name=poc_name, ss=True)
        cmds.connectAttr(f"{shape}.worldSpace[0]", f"{poc}.inputCurve")
        cmds.setAttr(f"{poc}.turnOnPercentage", 1)
        cmds.setAttr(f"{poc}.parameter", param)
        fbf = cmds.createNode("fourByFourMatrix", name=f"{name}Crv{i:02d}_FBF", ss=True)
        for ax, slot in (("X", "in30"), ("Y", "in31"), ("Z", "in32")):
            cmds.connectAttr(f"{poc}.position{ax}", f"{fbf}.{slot}")

        kw = {"name": jnt_name, "ss": True}
        if parent_joint:
            kw["parent"] = parent_joint
        jnt = cmds.createNode("joint", **kw)
        cmds.setAttr(f"{jnt}.jointOrient", 0, 0, 0)
        if parent_joint:
            mm = cmds.createNode("multMatrix", name=f"{name}Crv{i:02d}_MM", ss=True)
            cmds.connectAttr(f"{fbf}.output", f"{mm}.matrixIn[0]")
            cmds.connectAttr(f"{parent_joint}.worldInverseMatrix[0]", f"{mm}.matrixIn[1]")
            cmds.connectAttr(f"{mm}.matrixSum", f"{jnt}.offsetParentMatrix")
        else:
            cmds.connectAttr(f"{fbf}.output", f"{jnt}.offsetParentMatrix")
        joints.append(jnt)

    return {"joints": joints, "blendshape": bls, "curve": base_curve}


def _inf_index(skin_cluster, inf):
    """Índice lógico de la influencia `inf` en el array .matrix del skinCluster."""
    conns = cmds.listConnections(f"{inf}.worldMatrix[0]", source=False, destination=True, plugs=True) or []
    for c in conns:
        if c.startswith(f"{skin_cluster}.matrix["):
            return int(c.split("[", 1)[1].split("]", 1)[0])
    return None


def localize_corrective_skin(skin_cluster):

    """
    Hace LOCAL un skinCluster de correctivas para que NO se rompa al mover el rig
    (masterwalk u otra transform global). Soluciona la DOBLE TRANSFORMACIÓN que ocurre
    al apilar dos skinClusters sobre la misma malla (body + correctivas): el segundo
    re-aplicaba el movimiento global porque su bindPreMatrix era estático.

    Para cada influencia conecta su `bindPreMatrix` a la worldInverseMatrix de su JOINT
    PADRE (el hueso del que cuelga la correctiva), de modo que:
        contribución = bindPreMatrix * worldMatrix = identidad cuando el push = 0,
    para CUALQUIER pose/posición global -> solo se aplica el DELTA local del empuje.
    No hay pop: en la pose actual el valor coincide con el bindPreMatrix original.

    Llamar UNA VEZ después de pintar/bindear el skinCluster de correctivas, con el rig
    en la pose neutra (correctivas a 0). Idempotente por influencia (reescribe la conexión).

    Args:
        skin_cluster (str): el skinCluster de correctivas (p.ej. "C_corrective_SKC").
    Returns:
        list: influencias localizadas.
    """
    infs = cmds.skinCluster(skin_cluster, query=True, influence=True) or []
    done = []
    for inf in infs:
        parent = (cmds.listRelatives(inf, parent=True, fullPath=True) or [None])[0]
        if not parent:
            continue  # influencia raíz: nada que cancelar
        idx = _inf_index(skin_cluster, inf)
        if idx is None:
            continue
        bpm = om.MMatrix(cmds.getAttr(f"{skin_cluster}.bindPreMatrix[{idx}]"))
        pw = om.MMatrix(cmds.getAttr(f"{parent}.worldMatrix[0]"))
        # restLocal^-1 (constante) = parentWorld_bind * bindPreMatrix_estatico
        const = pw * bpm
        mm = cmds.createNode("multMatrix", name=f"{_short(inf)}_localBPM_MM", ss=True)
        cmds.connectAttr(f"{parent}.worldInverseMatrix[0]", f"{mm}.matrixIn[0]")
        cmds.setAttr(f"{mm}.matrixIn[1]", list(const), type="matrix")
        cmds.connectAttr(f"{mm}.matrixSum", f"{skin_cluster}.bindPreMatrix[{idx}]", force=True)
        done.append(inf)
    return done


def _short(n):
    return n.rsplit("|", 1)[-1].split(":")[-1]

