import maya.cmds as cmds
import maya.api.OpenMaya as om
import json
import os
import glob

from utils import data_manager
from utils import rig_manager
from importlib import reload

CHARACTER_NAME = None
final_path = None
curves_name = None

complete_path = os.path.realpath(__file__)
relative_path = complete_path.split("\scripts")[0]
TEMPLATE_FILE = None


def get_all_ctl_curves_data(path=None):
    """
    Collects data from all controller curves in the scene and saves it to a JSON file.
    This function retrieves information about each controller's transform and its associated nurbsCurve shapes,
    including their CV positions, form, knots, degree, and override attributes.
    """

    ctl_data = {}

    transforms = cmds.ls("*_CTL*", type="transform", long=True)
    
    CHARACTER_NAME = rig_manager.get_character_name_from_scene()
    curves_name = f"{CHARACTER_NAME}_v001"

    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split("\scripts")[0]
    path = os.path.join(relative_path, "assets")
    character_path = os.path.join(path, CHARACTER_NAME)
    TEMPLATE_PATH = os.path.join(character_path, "curves")
    
    if path:
        TEMPLATE_FILE = os.path.normpath(path)
    else:
        TEMPLATE_FILE = os.path.join(TEMPLATE_PATH, f"{curves_name}.curves")

    if "_" in curves_name:
        curves_name = curves_name.split("_")[0]

    for transform_name in transforms:
        shapes = cmds.listRelatives(transform_name, shapes=True, fullPath=True) or []
        nurbs_shapes = []

        for shape in shapes:
            if cmds.nodeType(shape) == "nurbsCurve":
                nurbs_shapes.append(shape)

        if not nurbs_shapes:
            continue  

        sel_list = om.MSelectionList()
        sel_list.add(transform_name)
        transform_obj = sel_list.getDependNode(0)

        def get_override_info(node_obj):
            fn_dep = om.MFnDependencyNode(node_obj)
            try:
                override_enabled = fn_dep.findPlug('overrideEnabled', False).asBool()
                override_color = fn_dep.findPlug('overrideColor', False) if override_enabled else None
                override_color_value = override_color.asInt() if override_color else None
            except:
                override_enabled = False
                override_color_value = None
            return override_enabled, override_color_value

        transform_override_enabled, transform_override_color = get_override_info(transform_obj)

        shape_data_list = []

        for shape in nurbs_shapes:
            sel_list.clear()
            sel_list.add(shape)
            shape_obj = sel_list.getDependNode(0)

            shape_override_enabled, shape_override_color = get_override_info(shape_obj)

            fn_shape_dep = om.MFnDependencyNode(shape_obj)
            try:
                always_on_top = fn_shape_dep.findPlug('alwaysDrawOnTop', False).asBool()
            except:
                always_on_top = False

            curve_fn = om.MFnNurbsCurve(shape_obj)

            cvs = []
            for i in range(curve_fn.numCVs):
                pt = curve_fn.cvPosition(i)
                cvs.append((pt.x, pt.y, pt.z))

            form_types = {
                om.MFnNurbsCurve.kOpen: "open",
                om.MFnNurbsCurve.kClosed: "closed",
                om.MFnNurbsCurve.kPeriodic: "periodic"
            }

            line_width = None
            if cmds.attributeQuery("lineWidth", node=shape, exists=True):
                try:
                    line_width = cmds.getAttr(shape + ".lineWidth")
                except:
                    pass 

            form = form_types.get(curve_fn.form, "unknown")
            if form == "unknown":
                om.MGlobal.displayWarning(f"Curve form unknown for {shape}")

            knots = curve_fn.knots()
            degree = curve_fn.degree

            shape_data_list.append({
                "name": shape.split("|")[-1],
                "overrideEnabled": shape_override_enabled,
                "overrideColor": shape_override_color,
                "alwaysDrawOnTop": always_on_top,
                "lineWidth": line_width,
                "curve": {
                    "cvs": cvs,
                    "form": form,
                    "knots": list(knots),
                    "degree": degree
                }
            })

        ctl_data[transform_name] = {
            "transform": {
                "name": transform_name.split("|")[-1],
                "overrideEnabled": transform_override_enabled,
                "overrideColor": transform_override_color
            },
            "shapes": shape_data_list
        }

    with open(TEMPLATE_FILE, "w") as f:
        json.dump(ctl_data, f, indent=4)

    # if answer == "+1":
    #     om.MGlobal.displayInfo(f"Controllers template saved as new version: {TEMPLATE_FILE}")
    # else:
    #     om.MGlobal.displayInfo(f"Controllers template saved to: {TEMPLATE_FILE}")

def build_curves_from_template(target_transform_name=None):
    """
    Builds controller curves from a predefined template JSON file.
    If a specific target transform name is provided, it filters the curves to only create those associated with that transform.
    If no target transform name is provided, it creates all curves defined in the template.
    Args:
        target_transform_name (str, optional): The name of the target transform to filter curves by. Defaults to None.
    Returns:
        list: A list of created transform names.
    """
    CHARACTER_NAME = rig_manager.get_character_name_from_build()

    # Set up the template file path
    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split("\scripts")[0]
    path = os.path.join(relative_path, "assets")
    character_path = os.path.join(path, CHARACTER_NAME)
    TEMPLATE_PATH = os.path.join(character_path, "curves")
    last_version = rig_manager.get_latest_version(TEMPLATE_PATH)

    TEMPLATE_FILE = os.path.join(TEMPLATE_PATH, f"{CHARACTER_NAME}_v001.curves")


    if not os.path.exists(TEMPLATE_FILE):
        TEMPLATE_FILE = os.path.join(path, "-", "new", "curves", "new.curves")

    with open(TEMPLATE_FILE, "r") as f:
        ctl_data = json.load(f)

    if target_transform_name:
        ctl_data = {k: v for k, v in ctl_data.items() if v["transform"]["name"] == target_transform_name}
        if not ctl_data:
            return

    created_transforms = []

    for transform_path, data in ctl_data.items():
        transform_info = data["transform"]
        shape_data_list = data["shapes"]

        dag_modifier = om.MDagModifier()
        transform_obj = dag_modifier.createNode("transform")
        dag_modifier.doIt()

        transform_fn = om.MFnDagNode(transform_obj)
        final_name = transform_fn.setName(transform_info["name"])
        created_transforms.append(final_name)

        if transform_info["overrideEnabled"]:
            fn_dep = om.MFnDependencyNode(transform_obj)
            fn_dep.findPlug('overrideEnabled', False).setBool(True)
            fn_dep.findPlug('overrideColor', False).setInt(transform_info["overrideColor"])

        created_shapes = []

        for shape_data in shape_data_list:
            curve_info = shape_data["curve"]
            cvs = curve_info["cvs"]
            degree = curve_info["degree"]
            knots = curve_info["knots"]
            form = curve_info["form"]

            form_flags = {
                "open": om.MFnNurbsCurve.kOpen,
                "closed": om.MFnNurbsCurve.kClosed,
                "periodic": om.MFnNurbsCurve.kPeriodic
            }
            form_flag = form_flags.get(form, om.MFnNurbsCurve.kOpen)

            points = om.MPointArray()
            for pt in cvs:
                points.append(om.MPoint(pt[0], pt[1], pt[2]))

            curve_fn = om.MFnNurbsCurve()
            shape_obj = curve_fn.create(
                points,
                knots,
                degree,
                form_flag,
                False,    
                True,     
                transform_obj
            )

            shape_fn = om.MFnDagNode(shape_obj)
            shape_fn.setName(shape_data["name"])

            if shape_data["overrideEnabled"]:
                fn_dep = om.MFnDependencyNode(shape_obj)
                fn_dep.findPlug('overrideEnabled', False).setBool(True)
                fn_dep.findPlug('overrideColor', False).setInt(shape_data["overrideColor"])

            if shape_data.get("alwaysDrawOnTop", False):
                fn_dep = om.MFnDependencyNode(shape_obj)
                fn_dep.findPlug('alwaysDrawOnTop', False).setBool(True)

            line_width = shape_data.get("lineWidth", None)
            if line_width is not None:
                if cmds.attributeQuery("lineWidth", node=shape_fn.name(), exists=True):
                    try:
                        cmds.setAttr(shape_fn.name() + ".lineWidth", line_width)
                    except:
                        om.MGlobal.displayWarning(f"Could not set lineWidth for {shape_fn.name()}")

            created_shapes.append(shape_obj)


    return created_transforms


def create_controller(name, offset=["GRP"], parent=None, locked_attrs=[], match=None):
    """
    Creates a controller with a specific name and offset transforms and returns the controller and the groups.

    Args:
        name (str): Name of the controller.
        suffixes (list): List of suffixes for the groups to be created. Default is ["GRP"].
    """

    created_grps = []
    if offset:
        for suffix in offset:
            if cmds.ls(f"{name}_{suffix}"):
                om.MGlobal.displayWarning(f"{name}_{suffix} already exists.")
                if created_grps:
                    cmds.delete(created_grps[0])
                return
            tra = cmds.createNode("transform", name=f"{name}_{suffix}", ss=True)
            if created_grps:
                cmds.parent(tra, created_grps[-1])
            created_grps.append(tra)
    if parent and created_grps:
        cmds.parent(created_grps[0], parent)
    if match and created_grps:
        cmds.matchTransform(created_grps[0], match, pos=True, rot=True, scl=False)

    if cmds.ls(f"{name}_CTL"):
        om.MGlobal.displayWarning(f"{name}_CTL already exists.")
        if created_grps:
            cmds.delete(created_grps[0])
        return
    else:
        
        ctl = build_curves_from_template(f"{name}_CTL")

        if not ctl:
            ctl = cmds.circle(name=f"{name}_CTL", ch=False)
        else:
            ctl = [ctl[0]]  # make sure ctl is a list with one element for consistency
        
        if locked_attrs:
            for attr in locked_attrs:
                cmds.setAttr(f"{ctl[0]}.{attr}", lock=True, keyable=False)

        if created_grps:
            cmds.parent(ctl[0], created_grps[-1])
        
        return created_grps, ctl[0]
    

def text_curve(ctl_name):
    """
    Creates a text curve for a given controller name and letter.

    Args:
        ctl_name (str): The name of the controller.
        letter (str): The letter to use for the text curve.

    Returns:
        str: The name of the created text curve.
    """
    CHARACTER_NAME = rig_manager.get_character_name_from_build()
    letter = CHARACTER_NAME[0].upper()
    text_curve = cmds.textCurves(ch=False, t=letter)
    text_curve = cmds.rename(text_curve, ctl_name)
    relatives = cmds.listRelatives(text_curve, allDescendents=True, type="nurbsCurve")
  
    for i, relative in enumerate(relatives):
        cmds.parent(relative, text_curve, r=True, shape=True)
        cmds.rename(relative, f"{ctl_name}Shape{i+1:02d}")
    relatives_transforms = cmds.listRelatives(text_curve, allDescendents=True, type="transform")
    cmds.delete(relatives_transforms)

    pivot_world = cmds.xform(text_curve, q=True, ws=True, rp=True)
    
    cvs = cmds.ls(text_curve + ".cv[*]", fl=True)
    
    positions = [cmds.pointPosition(cv, w=True) for cv in cvs]
    
    avg_x = sum(p[0] for p in positions) / len(positions)
    avg_y = sum(p[1] for p in positions) / len(positions)
    avg_z = sum(p[2] for p in positions) / len(positions)
    center_cvs = (avg_x, avg_y, avg_z)
    
    offset = [pivot_world[0] - center_cvs[0],
            pivot_world[1] - center_cvs[1],
            pivot_world[2] - center_cvs[2]]
    
    cmds.move(offset[0], offset[1], offset[2], cvs, r=True, ws=True)
    return ctl_name

def mirror_curves():
    """
    Espeja controladores del lado L al R escalando a -1 en X y aplicando Freeze.
    Lógica de colores: L(18) -> R(4), L(6) -> R(13).
    """
    # Buscamos controladores del lado L
    left_controllers = cmds.ls("L_*_CTL", type="transform")

    if not left_controllers:
        om.MGlobal.displayWarning("No se encontraron controladores con prefijo 'L_'.")
        return

    for l_ctl in left_controllers:
        r_ctl = l_ctl.replace("L_", "R_", 1)

        if not cmds.objExists(r_ctl):
            continue

        # --- OPERACIÓN DE ESPEJADO (Escala -1 y Freeze) ---
        # Guardamos el padre actual para no perder la jerarquía
        parent = cmds.listRelatives(r_ctl, parent=True)
        
        # Desparentamos temporalmente para que el freeze no afecte a la jerarquía superior
        if parent:
            cmds.parent(r_ctl, world=True)

        # Aplicamos escala negativa en X
        cmds.setAttr(f"{r_ctl}.scaleX", -1)
        
        # Freeze Transformations (aplica escala, rotación y traslación)
        cmds.makeIdentity(r_ctl, apply=True, t=1, r=1, s=1, n=0, pn=1)

        # Re-parentamos a su sitio original
        if parent:
            cmds.parent(r_ctl, parent[0])

        # --- LÓGICA DE COLORES ---
        if cmds.getAttr(f"{l_ctl}.overrideEnabled"):
            l_color = cmds.getAttr(f"{l_ctl}.overrideColor")
            r_color = None

            # Mapeo de colores: 18 -> 4 | 6 -> 13
            if l_color == 18:
                r_color = 4
            elif l_color == 6:
                r_color = 13
            
            if r_color is not None:
                cmds.setAttr(f"{r_ctl}.overrideEnabled", True)
                cmds.setAttr(f"{r_ctl}.overrideColor", r_color)

    om.MGlobal.displayInfo("Mirror completado: Escala -1 aplicada y transformaciones freezadas.")

    
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


def replace_shapes():   
    
    """
    Replaces the shapes of selected controllers with those from the template file.
    """
    pass
    



