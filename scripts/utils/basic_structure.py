import maya.cmds as cmds
import maya.api.OpenMaya as om
from utils import data_export
from utils import curve_tool

from importlib import reload

reload(data_export)
reload(curve_tool)


def create_basic_structure():

    """ Create the basic structure for the rig, including character, rig, controls, meshes, and deformers groups."""

    if cmds.objExists("Character"):

        om.MGlobal.displayError("Basic structure already exists. Please delete it before creating a new one.")
        return
    

    nodes = ["Character", "rig_GRP", "controls_GRP", "meshes_GRP", "deformers_GRP"]

    for i, node in enumerate(nodes):

        cmds.createNode("transform", name=node, ss=True)

        if i != 0:
            cmds.parent(node, nodes[0])

    character_node, character_ctl = curve_tool.create_controller(name="C_character", offset=["GRP", "ANM"])
    masterwalk_node, masterwalk_ctl = curve_tool.create_controller(name="C_masterwalk", offset=["GRP", "ANM"])
    cmds.parent(character_node[0], nodes[2])
    cmds.parent(masterwalk_node[0], character_ctl)