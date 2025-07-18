import maya.cmds as cmds
import maya.api.OpenMaya as om
import json
import os

TEMPLATE_PATH = "C:/GITHUB/curves"
final_path = None

def get_curves_info():

    """
    Get all curves in the scene and extract their information such as name, control points, degree, knots, and overrideColor.
    This information is stored in a dictionary with the curve name as the key.
    """

    all_curves = cmds.ls(type="nurbsCurve")

    print(f"Found {all_curves} curves in the scene.")

    # Get the curves info: name, control points, degree, knots, overrideColor.

    curves_info = {}

    for curve in all_curves:
        
        side = curve.split("_")[0]
        names = curve.split("_")[1]
        name = f"{side}_{names}"
        override_color = None

        sel = om.MSelectionList()
        sel.add(curve)
        dag = sel.getDagPath(0)
        curve_fn = om.MFnNurbsCurve(dag)

        cvs = []
        for i in range(curve_fn.numCVs):
            pt = curve_fn.cvPosition(i)
            cvs.append((pt.x, pt.y, pt.z))
        
        degree = curve_fn.degree
        knots = curve_fn.knots()
        form = cmds.getAttr(f"{curve}.form")
        draw_always_on_top = cmds.getAttr(f"{curve}.alwaysDrawOnTop")
        override_enabled = cmds.getAttr(f"{curve}.overrideEnabled")
        if override_enabled:
            override_color = cmds.getAttr(f"{curve}.overrideColor")

        curves_info[curve] = {
            "name": name,
            "controlPoints": cvs,
            "degree": degree,
            "knots": list(knots),
            "overrideEnabled": override_enabled,
            "overrideColor": override_color,
            "form": form,
            "alwaysDrawOnTop": draw_always_on_top
    }

    final_path = os.path.join(TEMPLATE_PATH, "curves_info.json")

    with open(final_path, "w") as file:
        json.dump(curves_info, file, indent=4)

    om.MGlobal.displayInfo(f"Curves info saved to {final_path}")

def create_controller(name, offset=["GRP"]):

    """Creates the controller based on the curves information."""

    final_path = os.path.join(TEMPLATE_PATH, "curves_info.json")

    # Build the controller offset groups.
    offset_grps = []

    if offset:
        for grp in offset:

            grp = cmds.createNode("transform", name=f"{name}_{grp}", ss=True)
            if offset_grps:
                cmds.parent(grp, offset_grps[-1])
            offset_grps.append(grp)
        
    else:
            grp = cmds.createNode("transform", name=f"{name}_GRP", ss=True)

    
    # Create the controller from the curve information.
    with open(final_path, 'r') as file:
        curves_info = json.load(file)

    shape = name + "_CTLShape"

    if shape in curves_info:

        control_points = curves_info[shape]["controlPoints"]
        degree = curves_info[shape]["degree"]
        override_enabled = curves_info[shape]["overrideEnabled"]
        override_color = curves_info[shape]["overrideColor"] if "overrideColor" in curves_info[shape] else None

        # Create the NURBS curve.
        controller = cmds.curve(d=degree, p=control_points, name=f"{name}_CTL")

        # Set the override color if it exists.
        cmds.setAttr(f"{controller}.overrideEnabled", override_enabled)
        if override_color != 0:
            cmds.setAttr(f"{controller}.overrideColor", override_color)
    
    else:

        controller = cmds.circle(name=f"{name}_CTL", ch=False)[0]

    cmds.parent(controller, offset_grps[-1])

    return offset_grps, controller

def mirror_controllers():

    one_side_cotrollers = cmds.ls("*_CTL", type="transform")

    for controller in one_side_cotrollers:

        if controller.startswith("L_") or controller.startswith("R_"):
            
            ctl_offset = cmds.ls(f"{controller.replace('CTL', 'GRP')}", type="transform")

            cmds.scale(-1, 1, 1, ctl_offset, relative=True)
            trans = cmds.xform(ctl_offset, translation=True)
            cmds.xform(ctl_offset, translation=(-trans[0], trans[1], trans[2]))
            cmds.makeIdentity(ctl_offset, apply=True, t=1, r=1, s=1, n=0, pn=1)


