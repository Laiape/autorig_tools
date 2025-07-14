import maya.cmds as cmds
import maya.api.OpenMaya as om
from scripts.utils import controller_creator
from scripts.utils import data_export


def create_basic_structure():

    """ Create the basic structure for the rig, including character, rig, controls, meshes, and deformers groups."""

    if cmds.objExists("Character"):

        om.MGlobal.displayError("Basic structure already exists. Please delete it before creating a new one.")
        return
    

    nodes = ["Character", "rig_GRP", "controls_GRP", "meshes_GRP", "deformers_GRP"]

    for i, node in enumerate(nodes):

        cmds.createNode("transform", name=node, ss=True)

        if i == 0:
            cmds.parent(node, nodes[0])

    masterwalk_node = cmds.createNode("transform", name="C_masterwalk_GRP", ss=True)
    cmds.parent(masterwalk_node, nodes[2])
    curve = cmds.circle(name="C_masterwalk_CTL", r=10)
    cmds.parent(curve, masterwalk_node)