import maya.cmds as cmds
import maya.api.OpenMaya as om
import os

complete_path = os.path.realpath(__file__)
relative_path = complete_path.split("\scripts")[0]
TEMPLATE_FILE = os.path.join(relative_path, "curves", "template_curves.json")

def offset_groups(name, suffixes = ["GRP"]):

    """

    Create the offset groups for the given arguments.

    """
    created_groups = []

    for suffix in suffixes:

        if cmds.objExists(f"{name}_{suffix}"):
            om.MGlobal.displayError(f"Group {name}_{suffix} already exists.")
            return
        group = cmds.createNode("transform", name=f"{name}_{suffix}", ss=True)

        if created_groups:
            cmds.parent(group, created_groups[-1])
        created_groups.append(group)

        if cmds.ls(f"{name}_CTL"):
            om.MGlobal.displayError(f"Control {name}_CTL already exists.")
            return
        
        ctl = build_curve_from_template()

        if not ctl:

            ctl = cmds.circle(name=f"{name}_CTL", r=1, ch=False)
        else:
            ctl = ctl[0]
        
        cmds.parent(ctl, created_groups[-1])

        return ctl[0], created_groups

def get_curve_data():

    ctl_data = {}

    all_curves = cmds.ls("*_CTL*", type="transform")

    if cmds.listRelatives(all_curves, allDescendents=True) is None:
        om.MGlobal.displayError("No curves found.")
        return
    
    for curve in all_curves:
        shapes = cmds.listRelatives(curve, shapes=True, fullPath=True)

        sel_list = om.MSelectionList()
        sel_list.add(curve)
        trn_obj = sel_list.getDependNode(0)

    def get_overrides_info(trn_obj):
        try:
            fn_dep = om.MFnDependencyNode(trn_obj)
            override_attr = fn_dep.findPlug("overrideEnabled", False).asBool()
            override_color = fn_dep.findPlug("overrideColor", False) if override_attr else None

        except:
            override_attr = False
            override_color = None
        
        return override_attr, override_color
    
    shape_override_enabled, shape_override_color = get_overrides_info(trn_obj)


    
    

        



def export_curves_to_file():

    """
    Export the curves to a file.

    Args:
        curve_list (list): List of curves to export.
        file_path (str): Path to the file where the curves will be exported.

    Returns:
        None
    """

    

    all_curves = cmds.ls("*_CTL*", type="transform")

    if not all_curves:
        om.MGlobal.displayError("No curves found to export.")
        return
    
    if not TEMPLATE_FILE:
        om.MGlobal.displayError("No file path provided.")
        return

    with open(TEMPLATE_FILE, 'w') as f:
        for curve in all_curves:
            f.write(f"{curve}\n")


def build_curve_from_template():

    pass