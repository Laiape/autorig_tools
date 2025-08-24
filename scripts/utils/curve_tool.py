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

    all_curves = cmds.ls("*_CTL")

    print(f"Found {all_curves} curves in the scene.")

    # Get the curves info: name, control points, degree, knots, overrideColor.

    curves_info = {}

    for curve in all_curves:
        
        side = curve.split("_")[0]
        names = curve.split("_")[1]
        name = f"{side}_{names}"

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
        if form == 2:
            radius = cmds.getAttr(f"{curve}.radius")
        draw_always_on_top = cmds.getAttr(f"{curve}.alwaysDrawOnTop")
        override_enabled = cmds.getAttr(f"{curve}.overrideEnabled")
        if override_enabled:
            override_color = cmds.getAttr(f"{curve}.overrideColor")
        else:
            override_color = None

        curves_info[curve] = {
            "name": name,
            "controlPoints": cvs,
            "degree": degree,
            "knots": list(knots),
            "overrideEnabled": override_enabled,
            "overrideColor": override_color if override_color is not None else None,
            "form": form,
            "radius": radius if form != 0 else None,
            "alwaysDrawOnTop": draw_always_on_top
    }

    final_path = os.path.join(TEMPLATE_PATH, "curves_info.json")

    with open(final_path, "w") as file:
        json.dump(curves_info, file, indent=4)

    om.MGlobal.displayInfo(f"Curves info saved to {final_path}")

def create_controller(name, offset=["GRP"]):

    """Creates the controller based on the curves information."""

    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split("\scripts")[0]
    guides_path = os.path.join(relative_path, "curves")
    final_path = os.path.join(guides_path, "curves_info.json") # Update this line

    name_temp = os.path.basename(final_path).split(".")[0]

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
        curves_data = json.load(file)

    # print(curves_info)

    shape = name + "_CTLShape"

    for path, data in curves_data.items():

        control_points = data["controlPoints"]
        degree = data["degree"]
        override_enabled = data["overrideEnabled"]
        form = data["form"]
        radius = data["radius"] 
        always_draw_on_top = data["alwaysDrawOnTop"]
        override_color = data["overrideColor"]

        # Create the NURBS curve.
        if form == 0:
            controller = cmds.curve(d=degree, p=control_points, name=f"{name}_CTL")
        else:
            controller = cmds.circle(name=f"{name}_CTL", ch=False, r=radius, nr=[0, 1, 0])[0]

        # Set the override color if it exists.
        cmds.setAttr(f"{controller}.overrideEnabled", override_enabled)
        if override_enabled != 0:
            cmds.setAttr(f"{controller}.overrideColor", override_color)

        cmds.setAttr(f"{controller}.form", form)
        cmds.setAttr(f"{controller}.alwaysDrawOnTop", always_draw_on_top)

    else:

        om.MGlobal.displayWarning(f"No curve info found for {shape}. Creating a default circle controller.")
        controller = cmds.circle(name=f"{name}_CTL", ch=False, r=3, nr=[0, 1, 0])[0]

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

def scale_selected_controller(value):

    """
    Scales the selected controller to a specific size.
    The user is prompted to enter the desired scale value.
    """

    selected = cmds.ls(selection=True, type="nurbsCurve")

    if not selected:
        om.MGlobal.displayError("Please select a controller to scale.")
        return
    
    if selected.endswith("_CTL"):

        ctl = selected[0]
        cvs = cmds.ls(f"{ctl}.cv[*]", flatten=True)
        if not cvs:
            om.MGlobal.displayError("No CVs found on the selected controller.")
            return
        
        for cv in cvs:
            cmds.scale(value, value, value, cv, relative=True, ocp=True)
    
    else:

        om.MGlobal.displayError("Please select a controller with the suffix '_CTL'.")
        return

def scale_all_controllers(value):

    """
    Scales all controllers in the scene to a specific size.
    The user is prompted to enter the desired scale value.
    """

    all_controllers = cmds.ls("*_CTL", type="nurbsCurve")

    if not all_controllers:
        om.MGlobal.displayError("No controllers found in the scene.")
        return
    
    for controller in all_controllers:
        cvs = cmds.ls(f"{controller}.cv[*]", flatten=True)
        if not cvs:
            om.MGlobal.displayError(f"No CVs found on the controller: {controller}.")
            continue
        
        for cv in cvs:
            cmds.scale(value, value, value, cv, relative=True, ocp=True)

   


