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


def _remap01(name, driver, in_min, in_max):
    """remapValue 0..1 (auto-clamp) desde driver en [in_min, in_max]."""
    rmv = cmds.createNode("remapValue", name=f"{name}_RMV", ss=True)
    cmds.connectAttr(driver, f"{rmv}.inputValue")
    cmds.setAttr(f"{rmv}.inputMin", in_min)
    cmds.setAttr(f"{rmv}.inputMax", in_max)
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
        cmds.connectAttr(amount_attr, f"{mul}.input[1]")  # distancia máx (vivo)
        cmds.setAttr(f"{mul}.input[2]", float(ax[i]))     # componente del eje
        if enable_attr:
            cmds.connectAttr(enable_attr, f"{mul}.input[3]")
        cmds.connectAttr(f"{mul}.output", f"{jnt}.translate{comp}")

    return jnt


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
            cmds.connectAttr(amount_attr, f"{mul}.input[1]")
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
