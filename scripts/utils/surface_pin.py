import maya.cmds as cmds
from importlib import reload

from utils import matrix_manager

reload(matrix_manager)

# uvPin axis enum: 0=X 1=Y 2=Z 3=-X 4=-Y 5=-Z. Ambos lados llevan la normal de
# la surface al Y del joint; R invierte la tangente para espejar el frame.
PIN_AXES = {"L": (1, 2), "R": (1, 5), "C": (1, 2)}


def loft_from_chains(chains, name, degree=3):
    """
    Loft a NURBS surface through the world positions of several joint chains.
    Convención de parámetros del loft (verificado en Maya 2026): V corre a lo
    largo de cada cadena (root->tip) y U cruza de una cadena a la siguiente.

    Args:
        chains (list[list[str]]): transform chains ordered root->tip, listed in
            order across the surface (e.g. leading edge first, trailing last).
        name (str): prefix for the created nodes.
        degree (int): target degree in both directions, clamped to valid range.

    Returns:
        str: the lofted surface transform.
    """
    curves = []
    for i, chain in enumerate(chains):
        positions = [cmds.xform(node, q=True, ws=True, t=True) for node in chain]
        curves.append(cmds.curve(point=positions, degree=min(degree, len(positions) - 1), name=f"{name}Profile0{i}_CRV"))

    # loft solo acepta grado 1 o 3 en U. Con pocas cadenas cae a lineal (la
    # membrana pliega en los huesos, que es lo físico) y sectionSpans=2 mete
    # una fila de CVs a mitad de hueco para que un control pueda inflarla.
    u_degree = 3 if len(chains) > 3 else 1
    surface = cmds.loft(*curves, ch=False, uniform=True, autoReverse=False, degree=u_degree,
                        sectionSpans=2, range=False, polygon=0, name=f"{name}_NRB")[0]
    cmds.delete(curves)

    return surface


def _shape(surface):
    shapes = cmds.listRelatives(surface, shapes=True, noIntermediate=True)
    return shapes[0] if shapes else surface


def _param_ranges(shape):
    return (cmds.getAttr(f"{shape}.minValueU"), cmds.getAttr(f"{shape}.maxValueU"),
            cmds.getAttr(f"{shape}.minValueV"), cmds.getAttr(f"{shape}.maxValueV"))


def project_to_surface(surface, positions):
    """
    Closest normalized (u, v) on the surface for each world position, ready to
    feed to pin_to_surface. Se calcula una vez en build: la proyección es de
    colocación, no un nodo vivo.
    """
    shape = _shape(surface)
    u_min, u_max, v_min, v_max = _param_ranges(shape)

    uvs = []
    for position in positions:
        u, v = matrix_manager.getClosestParamsToPositionSurface(shape, position)
        uvs.append(((u - u_min) / (u_max - u_min), (v - v_min) / (v_max - v_min)))

    return uvs


def pin_to_surface(surface, name, uvs, parent=None, side="L"):
    """
    Pin one joint per (u, v) coordinate onto a NURBS surface with a single
    uvPin node, connected by offsetParentMatrix.

    Args:
        surface (str): NURBS surface (transform or shape).
        name (str): prefix for the created nodes.
        uvs (list[tuple]): normalized (u, v) coordinates, 0-1 in both directions.
        parent (str): parent for the created joints.
        side (str): 'L', 'R' or 'C'; R mirrors the tangent axis of the pin frame.

    Returns:
        tuple: (uvPin node, list of joints)
    """
    shape = _shape(surface)

    pin = cmds.createNode("uvPin", name=f"{name}_UVP", ss=True)
    cmds.connectAttr(f"{shape}.worldSpace[0]", f"{pin}.deformedGeometry")
    # con normalizedIsoParms el uvPin espera 0-1 sea cual sea el rango de
    # parámetros de la surface; fuera de rango devuelve identidad en silencio
    cmds.setAttr(f"{pin}.normalizedIsoParms", 1)
    normal_axis, tangent_axis = PIN_AXES[side]
    cmds.setAttr(f"{pin}.normalAxis", normal_axis)
    cmds.setAttr(f"{pin}.tangentAxis", tangent_axis)

    joints = []
    for i, (u, v) in enumerate(uvs):
        cmds.setAttr(f"{pin}.coordinate[{i}].coordinateU", u)
        cmds.setAttr(f"{pin}.coordinate[{i}].coordinateV", v)

        joint = cmds.createNode("joint", name=f"{name}0{i}_JNT", ss=True, parent=parent)
        cmds.setAttr(f"{joint}.inheritsTransform", 0)  # outputMatrix llega en espacio mundo
        cmds.connectAttr(f"{pin}.outputMatrix[{i}]", f"{joint}.offsetParentMatrix")
        joints.append(joint)

    return pin, joints
