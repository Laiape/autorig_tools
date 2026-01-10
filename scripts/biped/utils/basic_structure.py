import maya.cmds as cmds
import maya.api.OpenMaya as om
from biped.utils import data_manager
from biped.utils import curve_tool

from importlib import reload

from biped.utils import rig_manager
from biped.utils import guides_manager

reload(data_manager)
reload(curve_tool)
reload(rig_manager)
reload(guides_manager)

def lock_attributes(ctl, attrs):

        """
        Lock and hide attributes on a controller.
        Args:
            ctl (str): The name of the controller.
            attrs (list): A list of attributes to lock and hide.
        """
        
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)


def create_basic_structure(character_name=None):

    """ Create the basic structure for the rig, including character, rig, controls, meshes, and deformers groups."""


    character_name, imported_files = rig_manager.prepare_rig_scene()
    print("Character Name from prepare_rig_scene:", character_name)

    data_manager.DataExportBiped().append_data("basic_structure",
                            {
                                "character_name": character_name
                            })

    nodes = [character_name, "rig_GRP", "controls_GRP", "geo_GRP", "deformers_GRP"]


    for i, node in enumerate(nodes):

        nod = cmds.createNode("transform", name=node, ss=True)

        if i != 0:
            cmds.parent(nod, nodes[0])

    # ---- CREATE SKELETON HIERARCHY ----
    skeleton_grp = cmds.createNode("transform", name="skeletonHierarchy_GRP", ss=True, p=nodes[1])

    # ---- CREATE TRANSFORMS FOR GEO_GRP ----
    proxy = cmds.createNode("transform", name="PROXY", ss=True, p=nodes[3])
    final_geo = cmds.createNode("transform", name="FINAL", ss=True, p=nodes[3])
    local = cmds.createNode("transform", name="LOCAL", ss=True, p=nodes[3])

    for imported_file in imported_files:
        cmds.parent(imported_file, final_geo)

    # Create skeleton and modules groups under rig_GRP
    skel_grp = cmds.createNode("transform", name="skel_GRP", ss=True, p=nodes[1])
    modules_grp = cmds.createNode("transform", name="modules_GRP", ss=True, p=nodes[1])
    character_node, character_ctl = curve_tool.create_controller(name="C_character", offset=["GRP", "ANM"])
    masterwalk_node, masterwalk_ctl = curve_tool.create_controller(name="C_masterwalk", offset=["GRP", "ANM"])
    preferences_node, preferences_ctl = curve_tool.create_controller(name="C_preferences", offset=["GRP"])


    lock_attributes(character_ctl, ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
    lock_attributes(preferences_ctl, ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
    lock_attributes(masterwalk_ctl, ["visibility"])


    cmds.addAttr(f"{preferences_ctl}", longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
    cmds.setAttr(f"{preferences_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True)

    for attr in ["Reference", "Show_Skeleton", "Show_Modules"]:

        if not cmds.attributeQuery(attr, node=preferences_ctl, exists=True):
            cmds.addAttr(f"{preferences_ctl}", longName=attr, attributeType="bool", keyable=True, defaultValue=1)
            cmds.setAttr(f"{preferences_ctl}.{attr}", keyable=False, channelBox=True)
            if attr == "Show_Modules" or attr == "Show_Skeleton":
                cmds.setAttr(f"{preferences_ctl}.{attr}", 0)

    
    cmds.connectAttr(f"{preferences_ctl}.Reference", f"{nodes[3]}.overrideEnabled")
    cmds.setAttr(f"{nodes[3]}.overrideDisplayType", 2)
    cmds.connectAttr(f"{preferences_ctl}.Show_Skeleton", f"{skel_grp}.visibility")
    cmds.connectAttr(f"{preferences_ctl}.Show_Modules", f"{modules_grp}.visibility")

    cmds.addAttr(masterwalk_ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
    cmds.setAttr(f"{masterwalk_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True)
    cmds.addAttr(masterwalk_ctl, longName="globalScale", attributeType="float", defaultValue=1, minValue=0.01, keyable=True)
    cmds.connectAttr(f"{masterwalk_ctl}.globalScale", f"{masterwalk_ctl}.scaleX")
    cmds.connectAttr(f"{masterwalk_ctl}.globalScale", f"{masterwalk_ctl}.scaleY")
    cmds.connectAttr(f"{masterwalk_ctl}.globalScale", f"{masterwalk_ctl}.scaleZ")

    for attr in ["scaleX", "scaleY", "scaleZ"]:

        cmds.setAttr(f"{masterwalk_ctl}.{attr}", lock=True, keyable=False, channelBox=False)

    # Freeze jnt
    cmds.createNode("joint", name="C_freeze_JNT", ss=True, p=skel_grp)

    cmds.parent(character_node[0], nodes[2])
    cmds.parent(preferences_node[0], masterwalk_ctl)
    cmds.parent(masterwalk_node[0], character_ctl)
    data_manager.DataExportBiped().append_data("basic_structure",
                            {
                                "skel_GRP" : skel_grp,
                                "modules_GRP" : modules_grp,
                                "masterwalk_ctl" : masterwalk_ctl,
                                "character_ctl" : character_ctl,
                                "preferences_ctl" : preferences_ctl
                            }
    )

    return character_name

