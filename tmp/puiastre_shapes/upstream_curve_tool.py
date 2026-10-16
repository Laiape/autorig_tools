import maya.api.OpenMaya as om
import maya.cmds as cmds
import json
import os

from puiastreTools.utils import core
from importlib import reload
reload(core)

TEMPLATE_FILE = None

def lock_attr(ctl, attrs = ["scaleX", "scaleY", "scaleZ", "visibility"], ro=True):
    """
    Lock specified attributes of a controller, added rotate order attribute if ro is True.
    
    Args:
        ctl (str): The name of the controller to lock attributes on.
        attrs (list): List of attributes to lock. Default is ["scaleX", "scaleY", "scaleZ", "visibility"].
        ro (bool): If True, adds a rotate order attribute. Default is True.
    """

    for attr in attrs:
        cmds.setAttr(f"{ctl}.{attr}", keyable=False, channelBox=False, lock=True)
    
    if ro:
        cmds.addAttr(ctl, longName="rotate_order", nn="Rotate Order", attributeType="enum", enumName="xyz:yzx:zxy:xzy:yxz:zyx", keyable=False)
        cmds.setAttr(f"{ctl}.rotate_order", keyable=False, channelBox=True)

        cmds.connectAttr(f"{ctl}.rotate_order", f"{ctl}.rotateOrder")

def get_all_ctl_curves_data(path = "",prefix="CTL"):
    """
    Collects data from all controller curves in the scene and saves it to a JSON file.
    This function retrieves information about each controller's transform and its associated nurbsCurve shapes,
    including their CV positions, form, knots, degree, and override attributes.
    """

    TEMPLATE_FILE = core.DataManager.get_ctls_data()

    ctl_data = {}

    transforms = cmds.ls(f"*_{prefix}*", type="transform", long=True)

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

    print(f"Controller curves data saved to {TEMPLATE_FILE}")

def build_curves_from_template(target_transform_name=None, path=None):
    """
    Builds controller curves from a predefined template JSON file.
    If a specific target transform name is provided, it filters the curves to only create those associated with that transform.
    If no target transform name is provided, it creates all curves defined in the template.
    Args:
        target_transform_name (str, optional): The name of the target transform to filter curves by. Defaults to None.
    Returns:
        list: A list of created transform names.
    """

    if not os.path.exists(path):
        om.MGlobal.displayError("Template file does not exist.")
        return

    with open(path, "r") as f:
        ctl_data = json.load(f)

    if target_transform_name:
        ctl_data = {k: v for k, v in ctl_data.items() if "transform" in v and v["transform"].get("name") == target_transform_name}
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

def controller_creator(name, suffixes=["GRP", "ANM"], mirror=False, parent=None, match=None, lock=["scaleX", "scaleY", "scaleZ", "visibility"], ro=True, prefix="CTL"):
    """
    Creates a controller with a specific name and offset transforms and returns the controller and the groups.

    Args:
        name (str): Name of the controller.
        suffixes (list): List of suffixes for the groups to be created. Default is ["GRP"].
    """

    TEMPLATE_FILE = core.DataManager.get_ctls_data()

    created_grps = []
    if suffixes:
        for suffix in suffixes:
            if cmds.ls(f"{name}_{suffix}"):
                om.MGlobal.displayWarning(f"{name}_{suffix} already exists.")
                if created_grps:
                    cmds.delete(created_grps[0])
                return
            tra = cmds.createNode("transform", name=f"{name}_{suffix}", ss=True)
            if created_grps:
                cmds.parent(tra, created_grps[-1])
            created_grps.append(tra)

    if cmds.ls(f"{name}_{prefix}"):
        om.MGlobal.displayWarning(f"{name}_{prefix} already exists.")
        if created_grps:
            cmds.delete(created_grps[0])
        return
    else:
        ctl = build_curves_from_template(f"{name}_{prefix}", path = TEMPLATE_FILE)

        if not ctl:
            # if name == "C_preferences":
            #     ctl = text_curve(f"L_aaaa_CTL")
            #     print(ctl)
            #     cvs = cmds.ls(ctl + ".cv[*]", fl=True)
            #     cmds.move(0, 10, 0, cvs, r=True, ws=True)

            #     # cmds.setAttr(ctl + ".lineWidth", 1.5)
            #     cmds.setAttr(ctl + ".overrideEnabled", 1)
            #     cmds.setAttr(ctl + ".overrideColor", 14)
            #     ctl = [ctl]
            # else:
            ctl = cmds.circle(name=f"{name}_{prefix}", ch=False)
        else:
            ctl = [ctl[0]]

        if created_grps:
            cmds.parent(ctl[0], created_grps[-1])
    
        if match:
            if cmds.objExists(match):
                cmds.xform(ctl[0], ws=True, t=cmds.xform(match, q=True, ws=True, t=True))
                cmds.xform(ctl[0], ws=True, ro=cmds.xform(match, q=True, ws=True, ro=True))

        if parent:
            if cmds.objExists(parent):
                if created_grps:
                    cmds.parent(created_grps[0], parent)
                else:
                    cmds.parent(ctl[0], parent)


        if mirror:
            force_behavior_mirror(created_grps[0])

        lock_attr(ctl[0], lock, ro)

    if created_grps:
        return ctl[0], created_grps
    else:
        return ctl[0]

def force_behavior_mirror(node):

    """Mirrors the transform of a given node along the X-axis.
    It adjusts the translation and rotation values to achieve the mirroring effect.

    Args:
        node (str): The name of the node to mirror.
    """

    t = cmds.xform(node, q=True, ws=True, t=True)
    r = cmds.xform(node, q=True, ws=True, ro=True)

    mirrored_t = [-t[0], t[1], t[2]]
    mirrored_r = [(r[0] + 180) % 360, -r[1], -r[2]]

    for i in range(3):
        if mirrored_r[i] > 180:
            mirrored_r[i] -= 360

    cmds.xform(node, ws=True, t=mirrored_t, ro=mirrored_r)  

    name = node.replace("_GRP", "mirrored_GRP")
    mirror_transform = cmds.createNode("transform", name=name, ss=True)

    parent = cmds.listRelatives(node, parent=True, fullPath=True)
    if parent:
        cmds.parent(mirror_transform, parent[0])

    cmds.parent(node, mirror_transform)

def mirror_shapes():
    left_side = 'L_'
    right_side = 'R_'
    suffix = '_CTL'

    color_map = {
        6: 13,
        18: 4
    }

    all_ctls = cmds.ls(type='transform')
    source_ctls = []
    for tr in all_ctls:
        if suffix in tr:
            shapes = cmds.listRelatives(tr, shapes=True) or []
            if any(cmds.nodeType(s) == 'nurbsCurve' for s in shapes):
                source_ctls.append(tr)

    for src in source_ctls:
        if not src.startswith(left_side):
            continue

        tgt = src.replace(left_side, right_side, 1)
        src_shapes = cmds.listRelatives(src, shapes=True, fullPath=True) or []

        if not cmds.objExists(tgt):
            cmds.warning(f"No matching right-side transform for {src}, expected {tgt}")
            continue

        trans_override = cmds.getAttr(f'{src}.overrideEnabled')
        cmds.setAttr(f'{tgt}.overrideEnabled', trans_override)

        if trans_override:
            src_col = cmds.getAttr(f'{src}.overrideColor')
            tgt_col = color_map.get(src_col, src_col)
            cmds.setAttr(f'{tgt}.overrideColor', tgt_col)

        tgt_shapes = cmds.listRelatives(tgt, shapes=True, fullPath=True) or []
        for s in tgt_shapes:
            cmds.delete(s)

        for i, src_shape in enumerate(src_shapes):
            dup_tr = cmds.duplicate(src, name=src + '_dup')[0]
            dup_shapes = cmds.listRelatives(dup_tr, shapes=True, fullPath=True)
            dup_shape = dup_shapes[i] if i < len(dup_shapes) else dup_shapes[0]

            new_shape = cmds.parent(dup_shape, tgt, shape=True, relative=True)[0]
            shape_name = f'{tgt}Shape{i+1:02d}'
            new_shape = cmds.rename(new_shape, shape_name)

            cmds.delete(dup_tr)

            num_cvs = cmds.getAttr(f'{src_shape}.spans') + cmds.getAttr(f'{src_shape}.degree')
            for pt_idx in range(num_cvs + 1):
                pt = cmds.xform(f'{src_shape}.controlPoints[{pt_idx}]', q=True, t=True, ws=True)
                cmds.xform(f'{new_shape}.controlPoints[{pt_idx}]', t=(-pt[0], pt[1], pt[2]), ws=True)

            if cmds.attributeQuery('lineWidth', node=src_shape, exists=True):
                line_width = cmds.getAttr(f'{src_shape}.lineWidth')
                cmds.setAttr(f'{new_shape}.lineWidth', line_width)

            shape_override = cmds.getAttr(f'{src_shape}.overrideEnabled')
            cmds.setAttr(f'{new_shape}.overrideEnabled', shape_override)

            if shape_override:
                draw_type = cmds.getAttr(f'{src_shape}.overrideDisplayType')
                cmds.setAttr(f'{new_shape}.overrideDisplayType', draw_type)

                src_col = cmds.getAttr(f'{src_shape}.overrideColor')
                tgt_col = color_map.get(src_col, src_col)
                cmds.setAttr(f'{new_shape}.overrideColor', tgt_col)

        print(f"Mirrored {len(src_shapes)} shapes from {src} → {tgt}")

def text_curve(ctl_name):
    """
    Creates a text curve for a given controller name and letter.

    Args:
        ctl_name (str): The name of the controller.
        letter (str): The letter to use for the text curve.

    Returns:
        str: The name of the created text curve.
    """
    letter = ctl_name.split("_")[1][0].upper()
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

    return text_curve

def _get_override_info_from_mobj(node_obj):
    fn_dep = om.MFnDependencyNode(node_obj)
    try:
        override_enabled = fn_dep.findPlug('overrideEnabled', False).asBool()
        override_color = fn_dep.findPlug('overrideColor', False) if override_enabled else None
        override_color_value = override_color.asInt() if override_color else None
    except:
        override_enabled = False
        override_color_value = None
    return override_enabled, override_color_value

def get_all_nurbs_surfaces_data(transform_name=None):
    """
    Stores: transform name, shape name, override info, degreeInU/V, formInU/V,
    knots arrays, nested CVs (U-major: cvs[u][v] -> (x,y,z) or (x,y,z,w) if rational).
    """
    srf_data = {}

    shape = cmds.listRelatives(transform_name, shapes=True, type="nurbsSurface")[0]

    sel = om.MSelectionList()
    sel.add(shape)
    shape_obj = sel.getDependNode(0)

    fn_surf = om.MFnNurbsSurface(shape_obj)

    degree_u = int(fn_surf.degreeInU)
    degree_v = int(fn_surf.degreeInV)

    form_map = {
        om.MFnNurbsSurface.kOpen: "open",
        om.MFnNurbsSurface.kClosed: "closed",
        om.MFnNurbsSurface.kPeriodic: "periodic",
        om.MFnNurbsSurface.kInvalid: "invalid"
    }
    form_u = form_map.get(fn_surf.formInU, "unknown")
    form_v = form_map.get(fn_surf.formInV, "unknown")

    knots_u = list(fn_surf.knotsInU())
    knots_v = list(fn_surf.knotsInV())

    num_u = int(fn_surf.numCVsInU)
    num_v = int(fn_surf.numCVsInV)

    cvs = []
    is_rational = False
    for u in range(num_u):
        row = []
        for v in range(num_v):
            pt = fn_surf.cvPosition(u, v)
            if abs(pt.w - 1.0) > 1e-6:
                row.append((pt.x, pt.y, pt.z, pt.w))
                is_rational = True
            else:
                row.append((pt.x, pt.y, pt.z))
        cvs.append(row)
    srf_data= {
            "degreeInU": degree_u,
            "degreeInV": degree_v,
            "formInU": form_u,
            "formInV": form_v,
            "knotsInU": knots_u,
            "knotsInV": knots_v,
            "numCVsInU": num_u,
            "numCVsInV": num_v,
            "isRational": is_rational,
            "cvs": cvs
            }


    return srf_data


def build_surfaces_from_template(path=None, target_transform_name=None):
    """
    Read a surface template (as exported by get_all_nurbs_surfaces_data) and recreate transforms + nurbsSurface shapes.
    If target_transform_name is provided, only rebuild that surface.
    Returns list of created transform names.
    NOTE: trimmed surfaces (trims) are NOT handled here.
    """
    if not path or not os.path.exists(path):
        om.MGlobal.displayError("Template file does not exist.")
        return

    with open(path, "r") as f:
        srf_data = json.load(f)

    fallback_surface = {

            "degreeInU": 3,
            "degreeInV": 3,
            "formInU": "open",
            "formInV": "open",
            "knotsInU": [
                0.0,
                0.0,
                0.0,
                0.5,
                1.0,
                1.0,
                1.0
            ],
            "knotsInV": [
                0.0,
                0.0,
                0.0,
                1.0,
                1.0,
                1.0
            ],
            "numCVsInU": 5,
            "numCVsInV": 4,
            "isRational": False,
            "cvs": [
                [
                    [
                        -21.06217571392214,
                        325.087579121645,
                        629.8056276915859
                    ],
                    [
                        -21.06217571392214,
                        339.1290295975931,
                        629.8056276915859
                    ],
                    [
                        -21.06217571392214,
                        353.17048007354117,
                        629.8056276915859
                    ],
                    [
                        -21.06217571392214,
                        367.21193054948935,
                        629.8056276915859
                    ]
                ],
                [
                    [
                        -14.0414504759481,
                        325.087579121645,
                        645.106302542441
                    ],
                    [
                        -14.0414504759481,
                        339.1290295975931,
                        645.106302542441
                    ],
                    [
                        -14.0414504759481,
                        353.17048007354117,
                        645.106302542441
                    ],
                    [
                        -14.0414504759481,
                        367.21193054948935,
                        645.106302542441
                    ]
                ],
                [
                    [
                        -1.3954698182843127e-14,
                        325.087579121645,
                        659.3337980993169
                    ],
                    [
                        -1.3954698182843127e-14,
                        339.1290295975931,
                        659.3337980993169
                    ],
                    [
                        -1.3954698182843127e-14,
                        353.17048007354117,
                        659.3337980993169
                    ],
                    [
                        -1.3954698182843127e-14,
                        367.21193054948935,
                        659.3337980993169
                    ]
                ],
                [
                    [
                        14.041450475948102,
                        325.087579121645,
                        645.106302542441
                    ],
                    [
                        14.041450475948102,
                        339.1290295975931,
                        645.106302542441
                    ],
                    [
                        14.041450475948102,
                        353.17048007354117,
                        645.106302542441
                    ],
                    [
                        14.041450475948102,
                        367.21193054948935,
                        645.106302542441
                    ]
                ],
                [
                    [
                        21.062175713922137,
                        325.087579121645,
                        629.8056276915859
                    ],
                    [
                        21.062175713922137,
                        339.1290295975931,
                        629.8056276915859
                    ],
                    [
                        21.062175713922137,
                        353.17048007354117,
                        629.8056276915859
                    ],
                    [
                        21.062175713922137,
                        367.21193054948935,
                        629.8056276915859
                    ]
                ]
            ],
            "parent": "C_jaw_GUIDE",
            "jointTwist": "Child",
            "type": "Child",
            "moduleName": "Child",
            "prefix": "Child",
            "controllerNumber": "Child"

    }
    if target_transform_name:
        for key, index_data in srf_data[next(iter(srf_data))].items():
            if key == target_transform_name:
                data = index_data
    else:
        data = fallback_surface

    created_transforms = []

    form_flags = {
        "open": om.MFnNurbsSurface.kOpen,
        "closed": om.MFnNurbsSurface.kClosed,
        "periodic": om.MFnNurbsSurface.kPeriodic,
        "invalid": om.MFnNurbsSurface.kInvalid,
        "unknown": om.MFnNurbsSurface.kOpen
    }

    transform_name = target_transform_name

    # create transform
    dag_mod = om.MDagModifier()
    t_obj = dag_mod.createNode("transform")
    dag_mod.doIt()

    t_fn = om.MFnDagNode(t_obj)
    try:
        t_fn.setName(transform_name)
        created_transforms.append(transform_name)
    except:
        transform_name = t_fn.name()
        created_transforms.append(transform_name)
    degree_u = int(data["degreeInU"])
    degree_v = int(data["degreeInV"])
    form_u = form_flags.get(data.get("formInU", "open"), om.MFnNurbsSurface.kOpen)
    form_v = form_flags.get(data.get("formInV", "open"), om.MFnNurbsSurface.kOpen)
    knots_u = data.get("knotsInU", [])
    knots_v = data.get("knotsInV", [])
    cvs_nested = data["cvs"]
    num_u = int(data["numCVsInU"])
    num_v = int(data["numCVsInV"])
    is_rational = data.get("isRational", False)

    pts = om.MPointArray()
    for u in range(num_u):
        for v in range(num_v):
            cv = cvs_nested[u][v]
            if len(cv) == 4:
                pts.append(om.MPoint(cv[0], cv[1], cv[2], cv[3]))
            else:
                pts.append(om.MPoint(cv[0], cv[1], cv[2], 1.0))

    fn_surf = om.MFnNurbsSurface()
    try:
        shape_obj = fn_surf.create(
            pts,
            om.MDoubleArray(knots_u),
            om.MDoubleArray(knots_v),
            degree_u,
            degree_v,
            form_u,
            form_v,
            bool(is_rational),
            t_obj
        )
    except Exception as e:
        om.MGlobal.displayError(f"Failed to create surface {key}: {e}")
        return

    shape_fn = om.MFnDagNode(shape_obj)
    try:
        shape_fn.setName(transform_name + "Shape")
    except:
        pass

    try:
        # Assign a default shader to the created surface
        cmds.sets(shape_fn.name(), e=True, forceElement="initialShadingGroup")
    except:
        print("Could not assign initialShadingGroup to the created surface.")

    return created_transforms[0]

def replace_shape_colored():
    """
    1. Source = First Selection. Targets = All other selections.
    2. Replaces Target shapes with Source shape.
    3. Renames new shapes.
    4. Sets Color based on Naming Convention:
       - Starts with 'L' -> Color 6  (Blue)
       - Starts with 'R' -> Color 13 (Red)
       - Starts with 'C' -> Color 17 (Yellow)
    """
    
    # 1. Get current selection
    sel = cmds.ls(selection=True, long=True)
    
    if len(sel) < 2:
        cmds.warning("Please select at least two objects: [Source, Target1, Target2...]")
        return

    source_obj = sel[0]
    target_list = sel[1:]

    print(f"Source: {source_obj}")
    
    for target_obj in target_list:
        # --- SHAPE REPLACEMENT LOGIC ---
        
        # Duplicate source to create fresh shapes
        temp_obj = cmds.duplicate(source_obj, name="TEMP_REPLACE_SHAPE")[0]
        
        target_existing_shapes = cmds.listRelatives(target_obj, shapes=True, fullPath=True) or []
        temp_shapes = cmds.listRelatives(temp_obj, shapes=True, fullPath=True) or []

        if not temp_shapes:
            cmds.warning(f"Skipping '{target_obj}': Source has no shapes.")
            cmds.delete(temp_obj)
            continue

        # Parent new shapes to target
        try:
            cmds.parent(temp_shapes, target_obj, relative=True, shape=True)
        except Exception as e:
            print(f"Error on {target_obj}: {e}")
            cmds.delete(temp_obj)
            continue

        # Delete old shapes
        if target_existing_shapes:
            cmds.delete(target_existing_shapes)
            
        cmds.delete(temp_obj)
        
        # --- RENAMING & COLOR LOGIC ---
        
        # Get the new shapes that are now part of the target
        new_shapes = cmds.listRelatives(target_obj, shapes=True, fullPath=True)
        
        # Determine the "Short Name" (remove group path) for logic checks
        short_target_name = target_obj.split("|")[-1]
        
        # Determine Color based on prefix
        # 6 = Blue, 13 = Red, 17 = Yellow
        color_index = None
        
        if short_target_name.startswith("L"):
            color_index = 6
        elif short_target_name.startswith("R"):
            color_index = 13
        elif short_target_name.startswith("C"):
            color_index = 17
            
        if new_shapes:
            for i, shape in enumerate(new_shapes):
                # 1. Rename
                suffix = "Shape" if i == 0 else f"Shape{i}"
                new_name = f"{short_target_name}{suffix}"
                cmds.rename(shape, new_name)
                
                # We must update the shape variable with the new name for the setAttr command
                # (Since rename changes the name, the old 'shape' variable might be stale, 
                # though usually Maya handles this, it's safer to use the return of rename if needed.
                # In this simple case, we know the new name path.)
                
                # Note: cmds.rename returns the short name, we need the path for safety if objects have same names
                # Ideally, we query the renamed shape, but for setting attrs immediately, this works:
                current_shape_path = f"{target_obj}|{new_name}"

                # 2. Apply Color if a match was found
                if color_index is not None:
                    try:
                        # Turn on "Enable Overrides"
                        cmds.setAttr(f"{current_shape_path}.overrideEnabled", 1)
                        # Set the Color Index
                        cmds.setAttr(f"{current_shape_path}.overrideColor", color_index)
                    except:
                        pass # Fail silently if attributes are locked or unavailable


# core.DataManager.set_guide_data("P:/VFX_Project_20/PUIASTRE_PRODUCTIONS/00_Pipeline/puiastre_tools/guides/AYCHEDRAL_009.guides")

#core.DataManager.set_ctls_data(r"P:\VFX_Project_20\DCC_CUSTOM\MAYA\modules\puiastre_tools\assets\varyndor\curves\CHAR_varyndor_001.json")
# core.DataManager.set_ctls_data(r"P:\VFX_Project_20\DCC_CUSTOM\MAYA\modules\puiastre_tools\assets\aychedral\curves\CHAR_aychedral_002.json")

# core.DataManager.set_ctls_data(r"D:\git\maya\puiastre_tools\assets\moana\curves\CHAR_moana_001.json")
# core.DataManager.set_asset_name("varyndor")
# core.DataManager.set_mesh_data("C_body_MSH")
# # aa = get_all_nurbs_surfaces_data(transform_name="tt")
# # print(aa)
# # build_surfaces_from_template(core.DataManager.get_guide_data(), target_transform_name="tt")
# get_all_ctl_curves_data()
# mirror_shapes()