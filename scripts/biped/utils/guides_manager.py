from importlib import reload
import maya.cmds as cmds
import maya.api.OpenMaya as om
import json
import os
import pathlib

from biped.utils import data_manager
from biped.utils import rig_manager

GUIDES_PATH = "C:\GITHUB\guides"
guides_node = "C_guides_GRP"
CHARACTER_NAME = None

reload(data_manager)
reload(rig_manager)
reload(pathlib)

def get_guides_info():

    """
    Get the guides transform and take the information from the joints and locators.

    """

    CHARACTER_NAME = data_manager.DataExportBiped().get_data("basic_structure", "character_name")

    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split("\scripts")[0]
    path = os.path.join(relative_path, "assets")
    character_path = os.path.join(path, CHARACTER_NAME)
    TEMPLATE_PATH = os.path.join(character_path, "guides")

    try:
        guides_transform = cmds.ls(guides_node, type="transform")[0]

    except IndexError:

        om.MGlobal.displayError("Not a guide transform.")
        return None

    answer = cmds.promptDialog(
                title="SAVE GUIDES AS",
                message="INSERT FILE NAME",
                button=["+1", "REPLACE", "CANCEL"],
                defaultButton="+1",
                cancelButton="Cancel",
                dismissString="Cancel",
                bgc=(0, 0.09, 0.388))
    if answer == "Cancel":
        om.MGlobal.displayInfo("Operation cancelled by user.")
        return
    if answer == "+1":
        file_name = rig_manager.get_next_version_name(last_version)
        print("New file name:", file_name)
    if answer == "REPLACE":
        last_version = rig_manager.get_latest_version(TEMPLATE_PATH)
        file_name = pathlib.Path(last_version).stem
        print("Replacing file name:", file_name)

    guides_name = cmds.promptDialog(query=True, text=False)
    guides_name = CHARACTER_NAME

    
    joint_guides = cmds.listRelatives(guides_transform, allDescendents=True, type="joint")
    locator_guides = cmds.listRelatives(guides_transform, allDescendents=True, type="locator")
    curves_in_scene = cmds.ls("*_CRV", type="transform", long=True)

    if curves_in_scene:
        shapes_data = []
        curve_guide = []

        for curve in curves_in_scene:

            curve_guide.append(curve.split("|")[-1])

        curve_shapes = cmds.listRelatives(curve_guide, allDescendents=True, type="nurbsCurve")
        
        for shape in curve_shapes:

            nurbs_shapes = []
            if cmds.nodeType(shape) == "nurbsCurve":
                nurbs_shapes.append(shape)

            if not nurbs_shapes:
                continue  

            sel_list = om.MSelectionList()
            shape_data_list = []
            sel_list.clear()
            sel_list.add(shape)
            shape_obj = sel_list.getDependNode(0)
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

            form = form_types.get(curve_fn.form, "unknown")
            if form == "unknown":
                om.MGlobal.displayWarning(f"Curve form unknown for {shape}")

            knots = curve_fn.knots()
            degree = curve_fn.degree

            shape_data_list.append({

                "name": shape.split("|")[-1],
                "curve": {
                    "cvs": cvs,
                    "form": form,
                    "knots": list(knots),
                    "degree": degree
                }
            })
            shapes_data.extend(shape_data_list)


    if joint_guides:

        joint_matrices = []
        joint_parents = []
        joint_prefered_angles = []
        joint_joint_orient = []

        left_guides = []
        right_guides = []

        for jnt in joint_guides:

            if jnt.startswith("L_"):
                left_guides.append(jnt)

            if jnt.startswith("R_"):
                right_guides.append(jnt)

            name = jnt.split("_")[1]
            joint_matrices.append(cmds.xform(jnt, q=True, ws=True, m=True))
            joint_parent = cmds.listRelatives(jnt, parent=True)[0]
            joint_parents.append(joint_parent)
            joint_children = cmds.listRelatives(jnt, children=True)
 

        if len(left_guides) != len(right_guides):
            om.MGlobal.displayInfo("The number of left and right guides are not the same.")


            for left_guide in left_guides:
                for right_guide in right_guides:
                    if name in left_guide and name in right_guide:
                        left_world_position = [round(coord, 3) for coord in cmds.xform(left_guide, q=True, ws=True, t=True)]
                        right_world_position = [round(coord, 3) for coord in cmds.xform(right_guide, q=True, ws=True, t=True)]

                        left_world_position[0] = right_world_position[0] * -1       
                                 
    else:
        om.MGlobal.displayError("No joint guides found.")

    if locator_guides:

        locator_positions = []

        for loc in locator_guides:
            side = loc.split("_")[0]

            parent_transform = cmds.listRelatives(loc, parent=True)[0]
            locator_positions.append(cmds.xform(parent_transform, q=True, ws=True, m=True))

    else:
        om.MGlobal.displayInfo("No locator guides found.")
     
    CHARACTER_NAME = data_manager.DataExportBiped().get_data("basic_structure", "character_name")
    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split("\scripts")[0]
    path = os.path.join(relative_path, "assets")
    character_path = os.path.join(path, CHARACTER_NAME)
    TEMPLATE_PATH = os.path.join(character_path, "guides")
    TEMPLATE_FILE = rig_manager.get_latest_version(TEMPLATE_PATH)
    guides_data = {guides_name: {}}
    

    for i, guide in enumerate(joint_guides):
        children = cmds.listRelatives(guide, allDescendents=True)
        key = guide[0] if isinstance(guide, list) else guide
        guides_data[guides_name][key] = {
            "joint_matrix": joint_matrices[i],
            "parent": joint_parents[i],
            "isLocator": False,
            "isJoint": True,
            "isCurve": False,
            "children": list(reversed(children if children else [])),
    }

        
    if locator_guides:
        for i, loc in enumerate(locator_guides):
            guides_data[guides_name][loc] = {
                "locator_position": locator_positions[i],
                "isLocator": True,
                "isJoint": False,
                "isCurve": False
            }
    
    if curves_in_scene:
        for shape_data in shapes_data:
            shape_name = shape_data["name"] 
            guides_data[guides_name][shape_name] = {
                "curve_data": shape_data["curve"],
                "isLocator": False,
                "isJoint": False,
                "isCurve": True
            }

    if not os.path.exists(TEMPLATE_FILE):
        os.makedirs(TEMPLATE_FILE)

    with open(TEMPLATE_FILE, "w") as output_file:
        json.dump(guides_data, output_file, indent=4)

    om.MGlobal.displayInfo(f"Guides data saved to {TEMPLATE_FILE}")

def load_guides_info(filePath=None):

    """ Load guides information from a JSON file and create the guides in the scene."""

    
    if not filePath:
        

        complete_path = os.path.realpath(__file__)
        relative_path = complete_path.split("\scripts")[0]
        TEMPLATE_PATH = os.path.join(relative_path, "assets")

        final_path = cmds.fileDialog2(fileMode=1, caption="Select a file", dir=TEMPLATE_PATH, fileFilter="*.guides")[0]
        print("Selected file path:", final_path)
       
        if not final_path:
            om.MGlobal.displayError("No file selected.")
            return None
        
    else:

        final_path = os.path.normpath(filePath)[0]

    if "v0" in final_path:
        name = os.path.basename(final_path).split(".")[0].split("_v0")[0]
    else:
        name = os.path.basename(final_path).split(".")[0]

    with open(final_path, "r") as input_file:
        guides_data = json.load(input_file)
    
    if not cmds.ls("C_guides_GRP"):

        guides_node = cmds.createNode("transform", name="C_guides_GRP", ss=True)

        for guide, data in reversed(list(guides_data[name].items())):
                
                if "isLocator" in data and data["isLocator"]:
                        locator = cmds.spaceLocator(name=guide.replace("LOCShape", "LOC"))[0]
                        cmds.xform(locator, ws=True, m=data["locator_position"])
                        cmds.parent(locator, guides_node)

                elif "isJoint" in data and data["isJoint"]:

                    cmds.select(clear=True)
                    imported_joint = cmds.joint(name=guide, r=5)
                    cmds.xform(imported_joint, ws=True, m=data["joint_matrix"])
                    cmds.makeIdentity(imported_joint, apply=True, r=True)
                    
                    # Make joint blue if L side, red if R side
                    if guide.startswith("L_"):
                        cmds.setAttr(f"{imported_joint}.overrideEnabled", 1)
                        cmds.setAttr(f"{imported_joint}.overrideColor", 6)  # Blue
                    elif guide.startswith("R_"):
                        cmds.setAttr(f"{imported_joint}.overrideEnabled", 1)
                        cmds.setAttr(f"{imported_joint}.overrideColor", 13)  # Red
                    elif guide.startswith("C_"):
                        cmds.setAttr(f"{imported_joint}.overrideEnabled", 1)
                        cmds.setAttr(f"{imported_joint}.overrideColor", 17)  # Yellow

                    if data["parent"] == "C_root_JNT":
                        cmds.parent(imported_joint, guides_node)
                    else:
                        cmds.parent(imported_joint, data["parent"])
                
                elif "isCurve" in data and data["isCurve"]:

                    curve_name = guide
                    dag_modifier = om.MDagModifier()
                    transform_obj = dag_modifier.createNode("transform")
                    dag_modifier.doIt()
                    transform_fn = om.MFnDagNode(transform_obj)
                    transform_fn.setName(curve_name.split("Shape")[0])
                    dag_modifier.doIt()
                    cmds.parent(transform_fn.name(), guides_node)

                    
                    curve_info = data["curve_data"]
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
                    shape_fn.setName(curve_name)

        rig_manager.import_meshes()

    else:

        om.MGlobal.displayError("Guides group 'C_guides_GRP' already exists. Please delete it before loading new guides.")

def delete_guides():

    """ Deletes the guides group and all its children."""

    guides_group = "C_guides_GRP"

    if cmds.objExists(guides_group):
        cmds.delete(guides_group)
        om.MGlobal.displayInfo(f"Deleted guides group: {guides_group}")
    else:
        om.MGlobal.displayError(f"Guides group '{guides_group}' does not exist.")

def get_guides(guide_export, parent=None):

    """
    Get the guides from the scene based on the provided guide export data.
    
    Args:
        guide_export (dict): The guide export data containing joint matrices and locator positions.
        allDescendants (bool): Whether to include all descendants in the search.

    Returns:
        list: A list of guides found in the scene.
    """

    CHARACTER_NAME = data_manager.DataExportBiped().get_data("basic_structure", "character_name")

    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split("\scripts")[0]
    path = os.path.join(relative_path, "assets")
    character_path = os.path.join(path, CHARACTER_NAME)
    TEMPLATE_PATH = os.path.join(character_path, "guides")
    TEMPLATE_FILE = rig_manager.get_latest_version(TEMPLATE_PATH)

    
    path = pathlib.Path(TEMPLATE_FILE)
    parts = path.parts # Get the parts of the path
    name = parts[parts.index('assets') + 1] # Get the character name after 'assets'

    if not os.path.exists(TEMPLATE_FILE):

        om.MGlobal.displayError("Guides path does not exist. Please create the guides first.")

        return 
    
    else:

        with open(TEMPLATE_FILE, "r") as input_file:
            guides_data = json.load(input_file)
              
        try:
            if guides_data[name][guide_export]["isJoint"] == True:
                chain = []

                joint_exported = cmds.joint(name=guide_export, r=5)
                cmds.xform(joint_exported, ws=True, m=guides_data[name][guide_export]["joint_matrix"])
                cmds.makeIdentity(joint_exported, apply=True, r=True)
                chain.append(joint_exported)

                if "children" in guides_data[name][guide_export]:
                    for child in guides_data[name][guide_export]["children"]:
                        child_joint = cmds.joint(name=child, r=5)
                        cmds.xform(child_joint, ws=True, m=guides_data[name][child]["joint_matrix"])
                        cmds.makeIdentity(child_joint, apply=True, r=True)
                        chain.append(child_joint)

                if parent:
                    if len(chain[0]) > 1:
                        cmds.parent(chain[0], parent)
                    else:
                        cmds.parent(chain, parent)

                return chain
            
            elif guides_data[name][guide_export]["isLocator"] == True:
                locator = cmds.spaceLocator(name=guide_export.replace("LOCShape", "LOC"))[0]
                cmds.xform(locator, ws=True, m=guides_data[name][guide_export]["locator_position"])
                if parent:
                    cmds.parent(locator.split("Shape")[0], parent)
                return locator
            
            elif guides_data[name][guide_export]["isCurve"] == True:

                curve_name = guide_export
                dag_modifier = om.MDagModifier()
                transform_obj = dag_modifier.createNode("transform")
                dag_modifier.doIt()
                transform_fn = om.MFnDagNode(transform_obj)
                transform_fn.setName(curve_name.split("Shape")[0])
                dag_modifier.doIt()

                # Retrieve curve data from the loaded guides_data
                curve_info = guides_data[name][curve_name]["curve_data"]
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
                shape_fn.setName(curve_name)

                if parent:
                    cmds.parent(transform_fn.name(), parent)
            
                return shape_fn.name()
        
        except KeyError:
            om.MGlobal.displayError(f"Guide '{guide_export}' not found in the guide export data.")
            return None